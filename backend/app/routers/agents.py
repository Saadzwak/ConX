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
    # Si la session Anthropic était `terminated` (TTL), on en a créé une
    # nouvelle et rejoué le dernier plan en contexte. `was_replayed=True`
    # signale au frontend qu'il doit basculer son state vers `session_id`
    # (le nouveau).
    was_replayed: bool = False
    previous_session_id: str | None = None


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
    # supabase-py = httpx sync → offload hors event loop (AUDIT C3).
    await asyncio.to_thread(
        lambda: sb.schema("app").table("agent_sessions").insert(
            {
                "session_id": session_info["session_id"],
                "agent_name": session_info["agent_name"],
                "user_id": user.user_id,
                "user_query": user_query[:500],
                "building_id": building_id,
            }
        ).execute()
    )


async def _next_version(user: AuthUser, session_id: str) -> int:
    """[Legacy, conservée pour `start_plan_session`] Retourne la prochaine
    version (1, 2, 3...) depuis `app.renovation_plans`. NB : actuellement
    cette table n'est pas peuplée (persistance frontend différée post-J12.5)
    donc renvoie toujours 1. Pour compter correctement les itérations de
    chat, utiliser `_count_user_messages` qui inspecte les events Anthropic.
    """
    if not is_supabase_configured():
        return 1
    sb = supabase_for_user(user)
    res = (
        sb.schema("app").table("renovation_plans")
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


async def _count_user_messages(session_id: str) -> int:
    """Compte les events `user.message` d'une session Anthropic.

    Source de vérité robuste pour la numérotation de version : chaque
    `user.message` correspond à une itération de plan (v1 = premier message
    auto-injecté avec la fiche bâtiment, v2 = premier follow-up, etc.).
    Plus fiable que `app.renovation_plans` qui n'est pas peuplée.
    """
    try:
        events = await asyncio.to_thread(list_events, session_id, None)
    except Exception as exc:
        logger.warning("count_user_messages %s a échoué (%s) — fallback 1", session_id, exc)
        return 1
    return sum(1 for e in events if e.get("type") == "user.message")


# ---------------------------------------------------------------------------
# Fallback "replay-previous-plan" (B-001 long-idle)
# ---------------------------------------------------------------------------


def _build_replay_prompt(previous_plan_json: dict[str, Any], new_user_message: str) -> str:
    """Construit le prompt de relance avec contexte du plan précédent.

    L'agent Plan a pour consigne (system prompt) de régénérer un plan COMPLET
    à chaque tour. Cette fonction injecte le dernier plan stocké en début de
    message pour que l'agent ait le contexte sans devoir réinterroger la BD.
    """
    plan_str = json.dumps(previous_plan_json, ensure_ascii=False, indent=2)
    return (
        "## Contexte — plan précédent (la session précédente a été terminée pour "
        "inactivité, on en démarre une nouvelle)\n\n"
        "Voici le dernier plan que nous avions construit ensemble :\n\n"
        f"```json\n{plan_str}\n```\n\n"
        "Conserve cette base et applique la nouvelle demande utilisateur ci-dessous. "
        "Régénère un plan COMPLET (jamais un diff). Garde les éléments du plan "
        "précédent qui ne sont pas explicitement contredits.\n\n"
        "## Nouvelle demande utilisateur\n\n"
        f"{new_user_message}\n"
    )


async def _fetch_last_plan_context(
    user: AuthUser, session_id: str
) -> tuple[str | None, dict[str, Any] | None]:
    """Lit le dernier plan persisté pour cette session (la plus haute version).

    Retourne (building_id, plan_json) ou (None, None) si Supabase non
    configuré ou aucun plan persisté.
    """
    if not is_supabase_configured():
        return None, None
    sb = supabase_for_user(user)
    res = await asyncio.to_thread(  # supabase-py sync → offload (C3)
        lambda: sb.schema("app").table("renovation_plans")
        .select("building_id, plan_json, version")
        .eq("session_id", session_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data if hasattr(res, "data") else res.get("data", [])
    if not rows:
        return None, None
    return rows[0].get("building_id"), rows[0].get("plan_json") or {}


async def _send_with_replay_fallback(
    user: AuthUser,
    session_id: str,
    content: str,
) -> tuple[str, bool, str | None]:
    """Envoie un user_message en gérant le cas session terminated.

    Retourne (session_id_effective, was_replayed, previous_session_id_si_replay).

    1. Vérifie le status de la session Anthropic.
    2. Si idle/working : envoie le message, renvoie le même session_id.
    3. Si terminated/error :
       a. Récupère le dernier plan (sb.app.renovation_plans).
       b. Crée une nouvelle session Anthropic sur 'conx-plan'.
       c. Envoie un user_message combinant le plan précédent + la nouvelle question.
       d. Persiste la nouvelle session en `app.agent_sessions` (lien soft avec
          l'ancienne via `previous_session_id`).
       e. Renvoie le NOUVEAU session_id + was_replayed=True.
    """
    try:
        sess = await asyncio.to_thread(retrieve_session, session_id)
        status_val = sess.get("status", "unknown")
    except Exception as exc:
        logger.warning("retrieve_session %s a échoué (%s) — assumed terminated.", session_id, exc)
        status_val = "terminated"

    if status_val not in ("terminated", "error", "expired"):
        # Cas nominal : on envoie directement.
        await asyncio.to_thread(send_user_message, session_id, content)
        return session_id, False, None

    # ----- Replay fallback path -----
    logger.warning(
        "Session %s status=%s → replay-previous-plan fallback engagé.",
        session_id, status_val,
    )
    building_id, plan_json = await _fetch_last_plan_context(user, session_id)
    if plan_json is None:
        # Pas de plan stocké à rejouer — on relance sans contexte.
        # L'utilisateur perdra le détail des tours précédents mais la nouvelle
        # session pourra repartir depuis zéro.
        plan_json = {"note": "Pas de plan v1 stocké. Démarrage from-scratch."}
    if building_id is None:
        building_id = "unknown"

    prompt = _build_replay_prompt(plan_json, content)
    new_session = await asyncio.to_thread(create_session, "conx-plan")
    new_sid = new_session["session_id"]
    await asyncio.to_thread(send_user_message, new_sid, prompt)

    # Persist new session row (RLS isole user_id)
    if is_supabase_configured():
        sb = supabase_for_user(user)
        base_row = {
            "session_id": new_sid,
            "agent_name": "conx-plan",
            "user_id": user.user_id,
            "user_query": content[:500],
            "building_id": building_id,
        }
        try:
            # supabase-py sync → offload (AUDIT C3).
            await asyncio.to_thread(
                lambda: sb.schema("app").table("agent_sessions")
                .insert({**base_row, "previous_session_id": session_id})
                .execute()
            )
        except Exception as exc:
            # `previous_session_id` peut ne pas exister dans le schema —
            # on retente sans la colonne pour rester compatible.
            logger.warning(
                "Persist agent_sessions avec previous_session_id échoué (%s) — fallback sans.",
                exc,
            )
            try:
                await asyncio.to_thread(
                    lambda: sb.schema("app").table("agent_sessions")
                    .insert(base_row)
                    .execute()
                )
            except Exception as exc2:
                logger.warning("Persist agent_sessions (fallback) échoué (%s).", exc2)

    return new_sid, True, session_id


async def _verify_session_owned(user: AuthUser, session_id: str) -> str | None:
    """Vérifie que la session appartient à l'utilisateur (protection IDOR, M1).

    - Supabase non configuré → retourne None (mode offline : l'auth JWT fait foi).
    - Supabase configuré mais INJOIGNABLE (réseau/projet en pause) → warning +
      retourne None (dégradation vers JWT-only, cohérent avec le mode offline ;
      on ne casse pas le stream quand l'infra d'autorisation est down).
    - Supabase répond, session absente/non possédée → lève 404 (fail-closed).
    - Session trouvée → retourne son `agent_name`.
    """
    if not is_supabase_configured():
        return None
    sb = supabase_for_user(user)
    try:
        res = await asyncio.to_thread(
            lambda: sb.schema("app").table("agent_sessions")
            .select("session_id, agent_name")
            .eq("session_id", session_id)
            .eq("user_id", user.user_id)  # défense en profondeur (AUDIT M1)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "Vérif ownership session %s indisponible (Supabase injoignable: %s) "
            "— dégradation JWT-only.",
            session_id, exc,
        )
        return None
    rows = res.data if hasattr(res, "data") else res.get("data", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    return rows[0].get("agent_name")


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

    # 1+2. Appels Anthropic (réseau, httpx sync) offloadés hors de l'event loop
    # pour ne pas geler le stream SSE / les requêtes concurrentes (AUDIT C3).
    session_info = await asyncio.to_thread(create_session, "conx-plan")
    await asyncio.to_thread(send_user_message, session_info["session_id"], prompt)

    # 3. Persister côté Supabase (best-effort : la session est déjà créée et le
    # message Opus payé — un échec de persistance ne doit pas perdre le
    # session_id côté client, cf. AUDIT M4).
    try:
        await _persist_session(user, session_info, req.building_id, prompt[:500])
    except Exception as exc:
        logger.warning(
            "Persistance session %s échouée (%s) — session renvoyée quand même.",
            session_info["session_id"], exc,
        )

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
    agent_name = await _verify_session_owned(user, session_id)
    if agent_name is not None and agent_name != "conx-plan":
        raise HTTPException(
            status_code=400, detail="Cette session n'est pas une session Plan."
        )

    # _send_with_replay_fallback peut décider de basculer sur une nouvelle
    # session Anthropic si l'ancienne est `terminated` (B-001 long-idle).
    effective_sid, was_replayed, prev_sid = await _send_with_replay_fallback(
        user, session_id, req.content
    )
    # Version : compter les user.message events de la session Anthropic.
    # `_next_version` interrogeait `app.renovation_plans` qui n'est jamais
    # peuplé (la persistance frontend a été différée post-J12.5) → renvoyait
    # systématiquement 1, ce qui causait un duplicate React key v1 côté
    # frontend dès le 2ᵉ message. Compter via Anthropic events est correct
    # par construction (1 user.message = 1 version logique).
    # Si on a replayé, on compte sur prev_sid (l'historique métier) en
    # plus du user.message qu'on vient d'envoyer sur la nouvelle session.
    if was_replayed and prev_sid is not None:
        next_v = await _count_user_messages(prev_sid) + 1
    else:
        next_v = await _count_user_messages(effective_sid)

    # Note : la persistance du plan_json final se fera côté frontend (quand
    # il aura reçu l'agent_message complet via SSE et appelé un endpoint
    # `/api/agents/plan/{session_id}/persist` — à coder en J12.5 si besoin).
    # Pour l'instant, le frontend assume cette responsabilité.

    return PlanMessageResponse(
        session_id=effective_sid,
        version=next_v,
        was_replayed=was_replayed,
        previous_session_id=prev_sid,
    )


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
    # Contrôle d'appartenance : sans ça, tout JWT valide peut streamer le plan
    # d'un autre utilisateur en devinant le session_id (IDOR — AUDIT M1).
    # Dégrade proprement si Supabase est injoignable (cf. _verify_session_owned).
    await _verify_session_owned(user, session_id)

    async def _gen() -> AsyncIterator[bytes]:
        last_id: str | None = after
        loop_start = asyncio.get_running_loop().time()
        last_keepalive = loop_start
        total_events = 0
        poll_iter = 0
        consecutive_errors = 0  # circuit-breaker

        # Envoyer un premier "ping" pour ouvrir le canal côté browser
        yield serialize_event_for_sse({"type": "stream.open", "session_id": session_id})
        logger.info(
            "[SSE %s] stream.open after=%s",
            session_id, last_id,
        )

        while True:
            now = asyncio.get_running_loop().time()
            elapsed = now - loop_start
            if elapsed > MAX_STREAM_DURATION_S:
                logger.info(
                    "[SSE %s] timeout after %.1fs (%d events streamed)",
                    session_id, elapsed, total_events,
                )
                yield serialize_event_for_sse(
                    {"type": "stream.timeout", "after_s": MAX_STREAM_DURATION_S}
                )
                return

            # Récupérer les events depuis `last_id` — on tolère des erreurs
            # transitoires (rate-limit, hoquet réseau) jusqu'à 3 fois de suite
            # avant d'abandonner. Le frontend a son propre retry via le param
            # ?after=<last_id>.
            try:
                events = await asyncio.to_thread(list_events, session_id, last_id)
                consecutive_errors = 0
            except HTTPException as exc:
                consecutive_errors += 1
                logger.warning(
                    "[SSE %s] list_events HTTPException #%d (%d): %s",
                    session_id, consecutive_errors, exc.status_code, exc.detail,
                )
                if consecutive_errors >= 3:
                    yield serialize_event_for_sse(
                        {
                            "type": "stream.error",
                            "detail": exc.detail,
                            "status": exc.status_code,
                            "last_event_id": last_id,
                        }
                    )
                    return
                # Heartbeat + back-off doux, on retente
                yield keepalive_event()
                last_keepalive = now
                await asyncio.sleep(POLL_INTERVAL_S * 2)
                continue
            except Exception as exc:  # -- on tolère 3 erreurs avant d'abandonner
                consecutive_errors += 1
                logger.exception(
                    "[SSE %s] list_events Exception #%d (will retry %d more times)",
                    session_id, consecutive_errors, max(0, 3 - consecutive_errors),
                )
                if consecutive_errors >= 3:
                    yield serialize_event_for_sse(
                        {"type": "stream.error", "detail": str(exc), "last_event_id": last_id}
                    )
                    return
                yield keepalive_event()
                last_keepalive = now
                await asyncio.sleep(POLL_INTERVAL_S * 2)
                continue

            # Relayer les events au browser. Try/except autour de chaque event
            # individuellement : un event au format inattendu ne casse pas la
            # boucle entière.
            for e in events:
                try:
                    yield serialize_event_for_sse(e)
                    if e.get("id"):
                        last_id = e["id"]
                    total_events += 1
                except Exception as exc:
                    logger.warning(
                        "[SSE %s] event serialize failed (skipped): %s — event_type=%s",
                        session_id, exc, e.get("type", "?"),
                    )
                    continue

            # Vérifier le status de la session (idle = on s'arrête)
            try:
                sess = await asyncio.to_thread(retrieve_session, session_id)
            except HTTPException as exc:
                # Si retrieve_session plante, on log et on continue (le polling
                # events.list pourra capturer la fin sans nous dire le status).
                logger.warning(
                    "[SSE %s] retrieve_session HTTPException: %s — continuing",
                    session_id, exc.detail,
                )
                sess = {"status": "unknown"}
            except Exception as exc:
                logger.warning(
                    "[SSE %s] retrieve_session Exception: %s — continuing",
                    session_id, exc,
                )
                sess = {"status": "unknown"}

            if sess["status"] in ("idle", "terminated", "error"):
                logger.info(
                    "[SSE %s] session.%s after %.1fs (%d events, %d polls)",
                    session_id, sess["status"], elapsed, total_events, poll_iter,
                )
                yield serialize_event_for_sse(
                    {"type": f"session.{sess['status']}", "session_id": session_id}
                )
                return

            # Keepalive (toujours envoyé toutes les 15s même si pas d'event,
            # garde la connexion vivante derrière proxies Nginx/CF et navigateurs).
            if now - last_keepalive > KEEPALIVE_INTERVAL_S:
                yield keepalive_event()
                last_keepalive = now

            # Log structuré toutes les ~15 s (1 ligne par batch de polls)
            poll_iter += 1
            if poll_iter % 10 == 0:
                logger.info(
                    "[SSE %s] poll #%d elapsed=%.1fs total_events=%d status=%s last_id=%s",
                    session_id, poll_iter, elapsed, total_events,
                    sess.get("status", "?"), last_id,
                )

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
        sb.schema("app").table("agent_sessions")
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
    ins_res = sb.schema("app").table("renovation_plans").insert(insert_payload).execute()
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
        sb.schema("app").table("renovation_plans")
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


# ---------------------------------------------------------------------------
# POST /api/agents/plan/{session_id}/export-pdf?version=N
# ---------------------------------------------------------------------------


class PlanExportRequest(BaseModel):
    """Si le frontend a déjà le texte du plan (cas SSE complet ou cache local),
    il peut l'envoyer directement → on n'a pas besoin de re-fetch Anthropic.
    Sinon, on essaie de récupérer le plan depuis la session Anthropic + le
    cache."""
    plan_text: str | None = Field(
        None,
        description="Texte markdown du plan. Si absent, le backend ira le chercher.",
    )
    building_id: str | None = Field(
        None,
        description=(
            "ID BDNB du bâtiment (pour enrichir la couverture avec l'adresse). "
            "Si absent et session connue côté Supabase, on l'y lit."
        ),
    )


@router.post("/plan/{session_id}/export-pdf")
async def export_plan_pdf(
    session_id: str,
    req: PlanExportRequest,
    version: int,
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Any:
    """Génère un PDF du plan v{version} et le retourne en application/pdf.

    Source du markdown (par ordre de préférence) :
      1. `req.plan_text` (frontend l'envoie ; cas nominal)
      2. Cache local pré-calculé (`docs/demo_assets/cached_plans/`)
      3. Persistance Supabase `app.renovation_plans` (legacy)

    Enrichit la couverture avec l'adresse BAN et l'identifiant DPE
    ADEME si on connaît le building_id (lookup `public_data.buildings` +
    BDNB).
    """
    import io
    from pathlib import Path

    from fastapi.responses import StreamingResponse

    from ..plan_export import render_plan_pdf

    _ = user  # auth requise

    # --- 1. Résoudre le markdown du plan
    plan_text = req.plan_text
    if not plan_text:
        # Tentative cache local
        try:
            cached = await get_cached_plan(
                req.building_id or "unknown", version
            )
            plan_text = cached.get("plan_text") if isinstance(cached, dict) else None
        except HTTPException:
            plan_text = None

    if not plan_text:
        # TODO : tentative Supabase renovation_plans (legacy, peu peuplé J18)
        raise HTTPException(
            status_code=422,
            detail=(
                "Plan introuvable côté serveur. Envoyez `plan_text` dans le "
                "body de la requête (le frontend l'a après le streaming)."
            ),
        )

    # --- 2. Enrichir la couverture (adresse, commune, DPE ADEME)
    building_id = req.building_id or "unknown"
    cover_meta: dict[str, str | None] = {
        "adresse_postale": None,
        "commune_nom": None,
        "dept": None,
        "rnb_id": None,
        "identifiant_dpe_ademe": None,
        "bdnb_millesime": "2025-07.a",
    }
    if building_id and building_id != "unknown":
        row = await conn.fetchrow(
            """
            SELECT b.rnb_id, b.dept, b.bdnb_millesime
            FROM public_data.buildings b
            WHERE b.building_id = $1
            """,
            building_id,
        )
        if row:
            cover_meta["rnb_id"] = row["rnb_id"]
            cover_meta["dept"] = row["dept"]
            if row["bdnb_millesime"]:
                cover_meta["bdnb_millesime"] = row["bdnb_millesime"]

            # Adresse BAN + commune via BDNB (dépt-specific schema)
            dept = row["dept"]
            if dept and dept in {"02", "59", "60", "62", "80"}:
                schema = f"bdnb_2025_07_a_open_data_dep{dept}"
                try:
                    enr = await conn.fetchrow(
                        f"""
                        SELECT
                          a.libelle_adr_complete_ban AS adresse_postale,
                          a.libelle_commune,
                          dpe.identifiant_dpe AS identifiant_dpe_ademe
                        FROM {schema}.rel_batiment_groupe_adresse rga
                        LEFT JOIN {schema}.adresse a
                          ON a.cle_interop_adr = rga.cle_interop_adr
                        LEFT JOIN {schema}.batiment_groupe_dpe_representatif_logement dpe
                          ON dpe.batiment_groupe_id = rga.batiment_groupe_id
                        WHERE rga.batiment_groupe_id = $1
                          AND rga.classe = 'Principale'
                        LIMIT 1;
                        """,
                        building_id,
                    )
                    if enr:
                        cover_meta["adresse_postale"] = enr.get("adresse_postale")
                        cover_meta["commune_nom"] = enr.get("libelle_commune")
                        cover_meta["identifiant_dpe_ademe"] = enr.get("identifiant_dpe_ademe")
                except Exception as exc:
                    # Si la BDNB n'a pas tout (ou schema unexpected), on continue
                    logger.warning(
                        "Enrichissement couverture échoué pour %s: %s",
                        building_id, exc,
                    )

    # --- 3. Rendre le PDF dans un fichier temporaire UNIQUE puis le nettoyer.
    # Nom aléatoire (pas prévisible/partagé) → pas de collision entre deux
    # exports concurrents du même bâtiment, et suppression après lecture pour
    # ne pas fuir sur le disque (AUDIT — export_plan_pdf temp file). WeasyPrint
    # est CPU-bound → offload hors event loop (AUDIT C3).
    import tempfile
    import uuid as _uuid

    safe_id = building_id.replace("/", "_").replace("..", "_")
    out_path = Path(tempfile.gettempdir()) / f"conx_plan_{_uuid.uuid4().hex}.pdf"
    try:
        await asyncio.to_thread(
            render_plan_pdf,
            plan_markdown=plan_text,
            building_id=building_id,
            version=version,
            output_path=out_path,
            adresse_postale=cover_meta["adresse_postale"],
            commune_nom=cover_meta["commune_nom"],
            dept=cover_meta["dept"],
            rnb_id=cover_meta["rnb_id"],
            identifiant_dpe_ademe=cover_meta["identifiant_dpe_ademe"],
            bdnb_millesime=cover_meta["bdnb_millesime"],
        )
        # --- 4. Stream le PDF au browser
        pdf_bytes = out_path.read_bytes()
    finally:
        out_path.unlink(missing_ok=True)
    filename = f"ConX_pre-cadrage_{safe_id}_v{version}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-ConX-Plan-Version": str(version),
        },
    )


# ---------------------------------------------------------------------------
# GET /api/agents/plan/cached/{building_id}/{version}  — fallback démo offline
# ---------------------------------------------------------------------------


@router.get("/plan/cached/{building_id}/{version}")
async def get_cached_plan(building_id: str, version: int) -> dict[str, Any]:
    """Sert un plan pré-calculé depuis le cache local.

    Cherche dans cet ordre :
      1. `/app/docs/demo_assets/cached_plans/` (committé en repo, dispo en démo)
      2. `/app/data/storage/cached_plans/` (volume Docker, généré par precalc_plans.py)
      3. `<repo>/docs/demo_assets/cached_plans/` (fallback dev sans Docker)
      4. `<repo>/data/storage/cached_plans/` (fallback dev sans Docker)

    Endpoint volontairement non-authentifié pour permettre la démo offline si
    l'API Anthropic est inaccessible — les caches contiennent uniquement des
    plans pour les bâtiments vedette publics (D-022/D-023), pas de données
    utilisateur sensibles.

    Retourne `{plan_text, generated_at, session_id, ...}` ou 404 si absent.
    """
    from pathlib import Path

    # Sanitization basique : pas de slash ni de ..
    if "/" in building_id or ".." in building_id or "/" in str(version):
        raise HTTPException(status_code=400, detail="ID ou version invalide.")

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [
        Path("/app/docs/demo_assets/cached_plans"),
        Path("/app/data/storage/cached_plans"),
        repo_root / "docs" / "demo_assets" / "cached_plans",
        repo_root / "data" / "storage" / "cached_plans",
    ]

    filename = f"{building_id}_v{version}.json"
    cache_file: Path | None = None
    for cand in candidates:
        candidate_file = cand / filename
        if candidate_file.exists():
            cache_file = candidate_file
            break

    if cache_file is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan en cache absent : {building_id} v{version}",
        )
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cache illisible : {exc}") from exc


