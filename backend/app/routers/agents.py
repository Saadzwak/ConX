"""ConX — endpoints `/api/agents/*` Mode Projet (J12).

Chat itératif Agent Plan (D-005) :
- POST /api/agents/plan/start : crée une session Anthropic, envoie un
  `user_message` initial avec la fiche bâtiment, persiste la session dans
  `app.agent_sessions` Supabase.
- POST /api/agents/plan/{session_id}/message : envoie un user_message
  supplémentaire (turn N), incrémente la version, persiste le plan résultant.
- GET /api/agents/plan/{session_id}/stream : SSE proxy des events Anthropic
  vers le navigateur. Keepalive 15s. Reconnexion via `Last-Event-ID`.
- GET /api/agents/plan/{session_id}/history : liste des versions persistées.

⚠ COÛT (règle §9.D) : chaque message Plan = ~0.20-0.50 € Claude Opus.
Le frontend doit afficher un compteur et limiter (max 10 tours, cf. R13).

⚠ Non testé contre l'API Anthropic — voir BUILD_LOG Session 9. Les
signatures du SDK seront validées par le partenaire avant la première
exécution. Tests offline avec mocks dans `tests/test_agents.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agents_client import (
    create_session,
    keepalive_event,
    list_events,
    retrieve_session,
    send_user_message,
    serialize_event_for_sse,
)
from ..auth import AuthUser, get_current_user
from ..db import get_db
from ..supabase_client import is_supabase_configured, supabase_for_user

logger = logging.getLogger("conx.routers.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])

KEEPALIVE_INTERVAL_S = 15
POLL_INTERVAL_S = 1.5
MAX_STREAM_DURATION_S = 300  # 5 min — au-delà on coupe (anti runaway)


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------


class PlanStartRequest(BaseModel):
    building_id: str = Field(..., description="ID BDNB (batiment_groupe_id)")
    target_class: str = Field("B", description="Classe DPE cible (A..C en pratique)")
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Préférences libres ('biosource': True, 'budget_max': 200000)",
    )
    initial_message: str | None = Field(
        None,
        description=(
            "Message utilisateur initial. Si null, le backend construit un "
            "prompt standard avec la fiche bâtiment."
        ),
    )


class PlanStartResponse(BaseModel):
    session_id: str
    agent_name: str
    building_id: str
    status: str
    cost_estimate_eur: tuple[float, float] = (0.2, 0.5)


class PlanMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class PlanMessageResponse(BaseModel):
    session_id: str
    version: int  # version du plan que ce message va produire
    cost_estimate_eur: tuple[float, float] = (0.2, 0.5)


class PlanVersion(BaseModel):
    id: str
    session_id: str
    version: int
    user_message: str | None
    plan_json: dict[str, Any]
    carbon_t_total: float | None
    carbon_breakdown: dict[str, Any] | None
    created_at: str


class PlanHistoryResponse(BaseModel):
    session_id: str
    versions: list[PlanVersion]


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


async def _fetch_building_light(
    conn: asyncpg.Connection, building_id: str
) -> dict[str, Any]:
    """Lit la fiche light du bâtiment dans `public_data` (équivalent
    /api/internal/building/:id côté backend interne)."""
    row = await conn.fetchrow(
        """
        SELECT
          b.building_id, b.rnb_id, b.dept, b.code_commune_insee,
          b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
          b.periode_construction, b.type_principal, b.materiau_mur,
          b.type_proprietaire, b.monument_historique, b.spr,
          b.dpe_classe, b.dpe_kwh_ep_m2_an, b.dpe_kg_co2_m2_an,
          b.dpe_coefficient_ep_electricite, b.dpe_source,
          ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
          ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
          bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
          bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
          bs.confidence, bs.thresholds_version
        FROM public_data.buildings b
        LEFT JOIN public_data.building_scores bs USING (building_id)
        WHERE b.building_id = $1;
        """,
        building_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Bâtiment introuvable.")

    return {
        "building_id": row["building_id"],
        "rnb_id": row["rnb_id"],
        "dept": row["dept"],
        "code_commune_insee": row["code_commune_insee"],
        "surface_m2": float(row["surface_m2"]) if row["surface_m2"] is not None else None,
        "hauteur_m": float(row["hauteur_m"]) if row["hauteur_m"] is not None else None,
        "nb_logements": row["nb_logements"],
        "annee_constr": row["annee_constr"],
        "periode_construction": row["periode_construction"],
        "type_principal": row["type_principal"],
        "materiau_mur": row["materiau_mur"],
        "type_proprietaire": row["type_proprietaire"],
        "monument_historique": bool(row["monument_historique"]),
        "spr": bool(row["spr"]),
        "dpe_classe": row["dpe_classe"],
        "dpe_kwh_ep_m2_an": (
            float(row["dpe_kwh_ep_m2_an"]) if row["dpe_kwh_ep_m2_an"] is not None else None
        ),
        "dpe_kg_co2_m2_an": (
            float(row["dpe_kg_co2_m2_an"]) if row["dpe_kg_co2_m2_an"] is not None else None
        ),
        "dpe_coefficient_ep_electricite": float(row["dpe_coefficient_ep_electricite"]),
        "dpe_source": row["dpe_source"],
        "centroid_lon": float(row["centroid_lon"]),
        "centroid_lat": float(row["centroid_lat"]),
        "score": {
            "s_co2": float(row["s_co2"]) if row["s_co2"] is not None else None,
            "s_faisa": float(row["s_faisa"]) if row["s_faisa"] is not None else None,
            "s_cout": float(row["s_cout"]) if row["s_cout"] is not None else None,
            "s_social": float(row["s_social"]) if row["s_social"] is not None else None,
            "s_passoire": float(row["s_passoire"]) if row["s_passoire"] is not None else None,
            "co2_evite_t": (
                float(row["co2_evite_t"]) if row["co2_evite_t"] is not None else None
            ),
            "cout_estime_eur": (
                float(row["cout_estime_eur"])
                if row["cout_estime_eur"] is not None
                else None
            ),
        }
        if row["s_co2"] is not None
        else None,
    }


def _build_initial_prompt(building: dict[str, Any], req: PlanStartRequest) -> str:
    """Construit le user_message initial à partir de la fiche bâtiment.

    Le system prompt de l'agent (agents/system_prompts/plan.md) explique
    déjà la mission et la convention "REGÉNÈRE le plan COMPLET à chaque
    tour". Ici on injecte le contexte data + la demande utilisateur.
    """
    fiche_json = json.dumps(building, ensure_ascii=False, indent=2)
    parts = [
        f"Génère un plan de rénovation hors-site biosourcé pour ce bâtiment.\n\n"
        f"## Fiche bâtiment\n```json\n{fiche_json}\n```\n",
        f"## Cible\nClasse DPE visée : **{req.target_class}**\n",
    ]
    if req.preferences:
        parts.append(
            f"## Préférences utilisateur\n```json\n"
            f"{json.dumps(req.preferences, ensure_ascii=False, indent=2)}\n```\n"
        )
    if req.initial_message:
        parts.append(f"## Note utilisateur libre\n{req.initial_message}\n")
    parts.append(
        "## Attendu\nRetourne un plan COMPLET avec :\n"
        "- Stratégie hors-site biosourcée détaillée (procédés, matériaux)\n"
        "- Bilan carbone en 3 composantes (exploitation, incorporé, évité)\n"
        "- Sources FDES citées par numéro\n"
        "- Coût estimé et délai\n"
    )
    return "\n".join(parts)


async def _persist_session(
    user: AuthUser, session_info: dict[str, Any], building_id: str, user_query: str
) -> None:
    """Insert dans app.agent_sessions Supabase. No-op si Supabase non configuré
    (mode dev/test sans cloud)."""
    if not is_supabase_configured():
        logger.warning(
            "Supabase non configuré — session %s pas persistée côté cloud.",
            session_info["session_id"],
        )
        return
    sb = supabase_for_user(user)
    sb.table("agent_sessions").insert(
        {
            "session_id": session_info["session_id"],
            "agent_name": session_info["agent_name"],
            "user_id": user.user_id,
            "user_query": user_query[:500],
            "building_id": building_id,
        }
    ).execute()


async def _next_version(user: AuthUser, session_id: str) -> int:
    """Retourne la prochaine version (1, 2, 3...) pour cette session."""
    if not is_supabase_configured():
        return 1
    sb = supabase_for_user(user)
    res = (
        sb.table("renovation_plans")
        .select("version")
        .eq("session_id", session_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data if hasattr(res, "data") else res.get("data", [])
    if not rows:
        return 1
    return int(rows[0]["version"]) + 1


# ---------------------------------------------------------------------------
# POST /api/agents/plan/start
# ---------------------------------------------------------------------------


@router.post("/plan/start", response_model=PlanStartResponse)
async def start_plan(
    req: PlanStartRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> PlanStartResponse:
    """Démarre une nouvelle session Mode Projet sur l'Agent Plan.

    ⚠ COÛT : ~0.20-0.50 € (1 message Claude Opus 4.7 sur fiche bâtiment).
    """
    building = await _fetch_building_light(conn, req.building_id)
    prompt = _build_initial_prompt(building, req)

    # 1. Créer la session Anthropic
    session_info = create_session("conx-plan")

    # 2. Envoyer le user_message initial (en arrière-plan côté Anthropic)
    send_user_message(session_info["session_id"], prompt)

    # 3. Persister côté Supabase (RLS isole l'utilisateur)
    await _persist_session(user, session_info, req.building_id, prompt[:500])

    return PlanStartResponse(
        session_id=session_info["session_id"],
        agent_name="conx-plan",
        building_id=req.building_id,
        status=session_info["status"],
    )


# ---------------------------------------------------------------------------
# POST /api/agents/plan/{session_id}/message
# ---------------------------------------------------------------------------


@router.post("/plan/{session_id}/message", response_model=PlanMessageResponse)
async def send_plan_message(
    session_id: str,
    req: PlanMessageRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> PlanMessageResponse:
    """Envoie un message utilisateur supplémentaire (turn N) sur la session.

    L'agent Plan, par son system prompt, REGÉNÈRE le plan COMPLET à chaque
    tour (jamais un diff — anti-dérive D-005 + R13).

    ⚠ COÛT : ~0.20-0.50 € par appel.
    """
    # Vérifier que la session appartient bien à l'utilisateur (Supabase RLS).
    # En mode offline (pas Supabase) on saute le check et on assume l'auth JWT
    # suffit.
    if is_supabase_configured():
        sb = supabase_for_user(user)
        res = (
            sb.table("agent_sessions")
            .select("session_id, agent_name")
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        rows = res.data if hasattr(res, "data") else res.get("data", [])
        if not rows:
            raise HTTPException(status_code=404, detail="Session introuvable.")
        if rows[0]["agent_name"] != "conx-plan":
            raise HTTPException(
                status_code=400, detail="Cette session n'est pas une session Plan."
            )

    next_v = await _next_version(user, session_id)
    send_user_message(session_id, req.content)

    # Note : la persistance du plan_json final se fera côté frontend (quand
    # il aura reçu l'agent_message complet via SSE et appelé un endpoint
    # `/api/agents/plan/{session_id}/persist` — à coder en J12.5 si besoin).
    # Pour l'instant, le frontend assume cette responsabilité.

    return PlanMessageResponse(session_id=session_id, version=next_v)


# ---------------------------------------------------------------------------
# GET /api/agents/plan/{session_id}/stream  (SSE)
# ---------------------------------------------------------------------------


@router.get("/plan/{session_id}/stream")
async def stream_plan(
    session_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
    after: str | None = None,
) -> StreamingResponse:
    """SSE proxy des events Anthropic vers le navigateur.

    Tant que la session est `working`, on poll `events.list(after=last_id)`
    toutes les ~1.5s et on streame les nouveaux events. Keepalive `: keepalive`
    toutes les 15s pour traverser les proxies (Nginx, Cloudflare).

    Le frontend ouvre un `EventSource('/api/agents/plan/{sid}/stream')` et
    s'arrête quand un event de type `session.idle` arrive (ou après
    `MAX_STREAM_DURATION_S`).

    ⚠ Reconnexion : le browser peut se reconnecter avec `?after=<last_id>`.
    L'API Anthropic supporte le paramètre `after` sur events.list — on le
    propage tel quel.
    """
    _ = user  # auth requise — pas de logique par rôle ici

    async def _gen() -> AsyncIterator[bytes]:
        last_id: str | None = after
        loop_start = asyncio.get_running_loop().time()
        last_keepalive = loop_start

        # Envoyer un premier "ping" pour ouvrir le canal côté browser
        yield serialize_event_for_sse({"type": "stream.open", "session_id": session_id})

        while True:
            now = asyncio.get_running_loop().time()
            if now - loop_start > MAX_STREAM_DURATION_S:
                yield serialize_event_for_sse(
                    {"type": "stream.timeout", "after_s": MAX_STREAM_DURATION_S}
                )
                return

            # Récupérer les events depuis `last_id`
            try:
                events = await asyncio.to_thread(list_events, session_id, last_id)
            except HTTPException as exc:
                yield serialize_event_for_sse(
                    {"type": "stream.error", "detail": exc.detail, "status": exc.status_code}
                )
                return
            except Exception as exc:  # -- on relaie l'erreur au browser
                logger.exception("Erreur stream events session %s", session_id)
                yield serialize_event_for_sse(
                    {"type": "stream.error", "detail": str(exc)}
                )
                return

            for e in events:
                yield serialize_event_for_sse(e)
                if e.get("id"):
                    last_id = e["id"]

            # Vérifier le status de la session (idle = on s'arrête)
            try:
                sess = await asyncio.to_thread(retrieve_session, session_id)
            except HTTPException as exc:
                yield serialize_event_for_sse(
                    {"type": "stream.error", "detail": exc.detail}
                )
                return

            if sess["status"] in ("idle", "terminated", "error"):
                yield serialize_event_for_sse(
                    {"type": f"session.{sess['status']}", "session_id": session_id}
                )
                return

            # Keepalive
            if now - last_keepalive > KEEPALIVE_INTERVAL_S:
                yield keepalive_event()
                last_keepalive = now

            await asyncio.sleep(POLL_INTERVAL_S)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # disable Nginx buffering
        "Connection": "keep-alive",
    }
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)


# ---------------------------------------------------------------------------
# POST /api/agents/plan/{session_id}/persist  (persiste un plan finalisé)
# ---------------------------------------------------------------------------


class PlanPersistRequest(BaseModel):
    user_message: str | None = None  # le prompt qui a généré ce plan (turn N)
    plan_json: dict[str, Any]
    carbon_t_total: float | None = None
    carbon_breakdown: dict[str, Any] | None = None


@router.post("/plan/{session_id}/persist", response_model=PlanVersion)
async def persist_plan(
    session_id: str,
    req: PlanPersistRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> PlanVersion:
    """Persiste la version courante du plan (v_n) dans app.renovation_plans.

    Appelé par le frontend une fois la génération SSE terminée et le
    `plan_json` parsé. Le backend calcule le numéro de version et insère.
    """
    if not is_supabase_configured():
        raise HTTPException(
            status_code=503, detail="Supabase non configuré — persistance indisponible."
        )

    sb = supabase_for_user(user)
    # Lire le building_id depuis la session
    sess_res = (
        sb.table("agent_sessions")
        .select("building_id")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    sess_rows = sess_res.data if hasattr(sess_res, "data") else sess_res.get("data", [])
    if not sess_rows:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    building_id = sess_rows[0]["building_id"]

    version = await _next_version(user, session_id)
    insert_payload = {
        "building_id": building_id,
        "session_id": session_id,
        "user_id": user.user_id,
        "version": version,
        "plan_json": req.plan_json,
        "carbon_t_total": req.carbon_t_total,
        "carbon_breakdown": req.carbon_breakdown,
        "user_message": req.user_message,
    }
    ins_res = sb.table("renovation_plans").insert(insert_payload).execute()
    ins_rows = ins_res.data if hasattr(ins_res, "data") else ins_res.get("data", [])
    if not ins_rows:
        raise HTTPException(status_code=500, detail="Insertion plan échouée.")
    row = ins_rows[0]
    return PlanVersion(
        id=row["id"],
        session_id=row["session_id"],
        version=row["version"],
        user_message=row.get("user_message"),
        plan_json=row["plan_json"],
        carbon_t_total=row.get("carbon_t_total"),
        carbon_breakdown=row.get("carbon_breakdown"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /api/agents/plan/{session_id}/history
# ---------------------------------------------------------------------------


@router.get("/plan/{session_id}/history", response_model=PlanHistoryResponse)
async def plan_history(
    session_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> PlanHistoryResponse:
    """Liste toutes les versions persistées de la session (v1, v2, ...)."""
    if not is_supabase_configured():
        return PlanHistoryResponse(session_id=session_id, versions=[])

    sb = supabase_for_user(user)
    res = (
        sb.table("renovation_plans")
        .select("id,session_id,version,user_message,plan_json,carbon_t_total,carbon_breakdown,created_at")
        .eq("session_id", session_id)
        .order("version", desc=False)
        .execute()
    )
    rows = res.data if hasattr(res, "data") else res.get("data", [])
    versions = [
        PlanVersion(
            id=r["id"],
            session_id=r["session_id"],
            version=r["version"],
            user_message=r.get("user_message"),
            plan_json=r["plan_json"],
            carbon_t_total=r.get("carbon_t_total"),
            carbon_breakdown=r.get("carbon_breakdown"),
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return PlanHistoryResponse(session_id=session_id, versions=versions)


