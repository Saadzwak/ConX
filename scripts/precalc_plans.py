"""ConX — pré-calcul des plans IA pour la démo (cache local + Supabase).

Génère 3 plans IA en utilisant l'agent `conx-plan` (Claude Opus 4.7) sur les
bâtiments vedettes (D-023) et persiste :
- en cache local JSON : `./docs/demo_assets/cached_plans/<building_id>_v<n>.json`
  (committé en repo pour qu'un checkout frais ait le cache prêt pour la démo)
- dans `app.renovation_plans` Supabase (via service_role).

Le backend frontend pourra alors consulter le cache local AVANT de faire un
appel API Anthropic, ce qui sécurise la démo contre toute hiccup réseau.

Usage :
    python scripts/precalc_plans.py
    python scripts/precalc_plans.py --only wazemmes-v1   # plus granulaire

⚠ COÛT : ~0.4-0.7 € par plan (3 plans = 1.2-2.1 €). Cap budget : 2 € (cf.
décision matinale 2026-05-22 PM).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Cache committé en repo (docs/demo_assets/) plutôt que data/storage/
# (gitignored) pour qu'un checkout frais ait les plans prêts pour la démo.
CACHE_DIR = ROOT / "docs" / "demo_assets" / "cached_plans"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("precalc_plans")

# Targets : (building_id, version, follow_up_message_si_v2)
TARGETS = {
    "wazemmes-v1": {
        "building_id": "bdnb-bg-81UB-UTZE-ZP7F",
        "label": "Wazemmes vedette (bailleur social R+3 1978 F)",
        "target_class": "C",
        "preferences": {"biosource": True},
        "version": 1,
        "follow_up": None,
    },
    "wazemmes-v2": {
        "building_id": "bdnb-bg-81UB-UTZE-ZP7F",
        "label": "Wazemmes — variation chanvre dominant",
        "target_class": "C",
        "preferences": {"biosource": True},
        "version": 2,
        "follow_up": "Et plutôt avec du chanvre comme matériau dominant ? Régénère le plan complet.",
    },
    "vieux-lille-v1": {
        "building_id": "bdnb-bg-JBP7-PFQL-4T69",
        "label": "Vieux-Lille candidat B (copro R+3 1930 G)",
        "target_class": "C",
        "preferences": {"biosource": True},
        "version": 1,
        "follow_up": None,
    },
}

DEV_USER_ID = "00000000-0000-0000-0000-0000000000de"
WAIT_TIMEOUT_S = 360  # 6 min max par plan


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.split("#", 1)[0].strip()


def _latest_event_id(client, sid):
    evs = list(client.beta.sessions.events.list(session_id=sid, limit=1, order="desc").data)
    return getattr(evs[0], "id", None) if evs else None


def _wait_for_idle(client, sid: str, pre_event_id: str | None) -> str:
    """Polling jusqu'à status=idle ET nouvel event après pre_event_id."""
    deadline = time.time() + WAIT_TIMEOUT_S
    last_status = "?"
    time.sleep(2)
    while time.time() < deadline:
        sess = client.beta.sessions.retrieve(session_id=sid)
        status = getattr(sess, "status", "?")
        if status != last_status:
            logger.info("  session.status = %s", status)
            last_status = status
        if status in ("terminated", "error"):
            return status
        if status in ("idle", "completed"):
            if pre_event_id is None:
                return status
            current = _latest_event_id(client, sid)
            if current and current != pre_event_id:
                return status
        time.sleep(3)
    return "timeout"


def _latest_agent_text(client, sid: str) -> str:
    events = list(client.beta.sessions.events.list(session_id=sid, limit=200).data)
    # On veut le DERNIER agent.message (pas les intermédiaires).
    for ev in reversed(events):
        t = getattr(ev, "type", "")
        if "agent.message" in t:
            content = getattr(ev, "content", None) or []
            chunks = []
            for block in content:
                text = getattr(block, "text", None)
                if text is None and isinstance(block, dict):
                    text = block.get("text")
                if text:
                    chunks.append(text)
            if chunks:
                return "\n".join(chunks)
    return ""


def _build_initial_prompt(building: dict, target_class: str, preferences: dict) -> str:
    parts = [
        "Génère un plan de rénovation hors-site biosourcé pour ce bâtiment.\n",
        f"## Fiche bâtiment\n```json\n{json.dumps(building, ensure_ascii=False, indent=2)}\n```\n",
        f"## Cible\nClasse DPE visée : **{target_class}**\n",
    ]
    if preferences:
        parts.append(
            f"## Préférences utilisateur\n```json\n"
            f"{json.dumps(preferences, ensure_ascii=False, indent=2)}\n```\n"
        )
    parts.append(
        "## Attendu\nRetourne un plan COMPLET avec :\n"
        "- Stratégie hors-site biosourcée détaillée (procédés, matériaux)\n"
        "- Bilan carbone en 3 composantes (exploitation, incorporé, évité)\n"
        "- Sources FDES citées par numéro\n"
        "- Coût estimé et délai\n"
    )
    return "\n".join(parts)


def _fetch_building_via_backend(building_id: str) -> dict:
    """Récupère la fiche bâtiment via l'API backend (qui retourne le format
    attendu par l'agent — cohérent avec /api/agents/plan/start)."""
    import urllib.request
    url = f"http://localhost:8000/api/buildings/{building_id}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def _save_local(target_key: str, building_id: str, version: int, plan_text: str,
                session_id: str, raw_meta: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{building_id}_v{version}.json"
    payload = {
        "target_key": target_key,
        "building_id": building_id,
        "version": version,
        "session_id": session_id,
        "plan_text": plan_text,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **raw_meta,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _save_supabase(target_key: str, building_id: str, version: int,
                   plan_text: str, session_id: str, target_class: str) -> tuple[str | None, str | None]:
    """Insère dans app.renovation_plans (+ app.agent_sessions parent au besoin)
    via service_role. Retourne (session_row_id, plan_row_id) ou (None, None) si
    Supabase non configuré."""
    try:
        from supabase import create_client
    except ImportError:
        logger.warning("supabase non installé localement — skip persistance cloud.")
        return None, None
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None, None
    sb = create_client(url, key)
    # 1. Upsert session (idempotent par session_id)
    sb.schema("app").table("agent_sessions").upsert({
        "session_id": session_id,
        "agent_name": "conx-plan",
        "user_id": DEV_USER_ID,
        "user_query": f"[precalc {target_key}]",
        "building_id": building_id,
    }, on_conflict="session_id").execute()
    # 2. Insert plan
    plan_id = str(uuid.uuid4())
    sb.schema("app").table("renovation_plans").insert({
        "id": plan_id,
        "session_id": session_id,
        "building_id": building_id,
        "user_id": DEV_USER_ID,
        "version": version,
        "plan_json": {
            "text": plan_text,
            "target_class": target_class,
            "source": f"precalc:{target_key}",
        },
        "carbon_t_total": None,  # extrait potentiel ultérieur si parsing structuré
    }).execute()
    return session_id, plan_id


def generate_target(target_key: str, target: dict) -> dict:
    """Lance la génération d'un plan pour un target précis. Retourne le dict de
    métadonnées (paths + ids)."""
    import anthropic

    logger.info("=" * 72)
    logger.info("TARGET %s — %s", target_key, target["label"])
    logger.info("=" * 72)

    # 1. Charger la fiche bâtiment via backend (déjà-up)
    building = _fetch_building_via_backend(target["building_id"])
    logger.info("Bâtiment fetché : %s (%s)", building["building_id"], building.get("rnb_id"))

    # 2. Créer le client Anthropic + session
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        default_headers={
            "anthropic-beta": "managed-agents-2026-04-01,skills-2025-10-02,"
                              "files-api-2025-04-14,code-execution-2025-08-25"
        },
    )

    # Lecture lockfile pour récupérer agent + env IDs
    import yaml
    lock = yaml.safe_load((ROOT / "agents" / "agents.lock.yaml").read_text())
    agent_id = lock["agents"]["conx-plan"]
    env_id = lock["environments"][lock["agent_env"]["conx-plan"]]

    session = client.beta.sessions.create(
        agent=agent_id, environment_id=env_id, title=f"ConX precalc {target_key}",
    )
    sid = session.id
    logger.info("Session créée : %s", sid)

    # 3. Envoi du message initial (avec fiche bâtiment lite)
    light_fiche = {
        k: building.get(k)
        for k in [
            "building_id", "rnb_id", "dept", "code_commune_insee", "surface_m2",
            "hauteur_m", "nb_logements", "annee_constr", "periode_construction",
            "type_principal", "materiau_mur", "type_proprietaire",
            "monument_historique", "spr", "dpe_classe", "dpe_kwh_ep_m2_an",
            "dpe_kg_co2_m2_an", "dpe_coefficient_ep_electricite", "dpe_source",
            "centroid_lon", "centroid_lat",
        ]
    }
    prompt = _build_initial_prompt(light_fiche, target["target_class"], target["preferences"])
    pre1 = _latest_event_id(client, sid)
    client.beta.sessions.events.send(
        session_id=sid,
        events=[{"type": "user.message", "content": [{"type": "text", "text": prompt}]}],
    )
    logger.info("[msg1] envoyé (%d chars). Attente idle…", len(prompt))
    s1 = _wait_for_idle(client, sid, pre1)
    if s1 not in ("idle", "completed"):
        logger.error("Echec génération v1 (status=%s)", s1)
        return {"target_key": target_key, "status": s1}
    plan_v1 = _latest_agent_text(client, sid)
    logger.info("[msg1] plan v1 reçu (%d chars)", len(plan_v1))

    final_plan = plan_v1
    final_version = 1
    if target.get("follow_up"):
        # Tour 2 — variation
        pre2 = _latest_event_id(client, sid)
        client.beta.sessions.events.send(
            session_id=sid,
            events=[{"type": "user.message", "content": [{"type": "text", "text": target["follow_up"]}]}],
        )
        logger.info("[msg2] envoyé : %s", target["follow_up"][:80])
        s2 = _wait_for_idle(client, sid, pre2)
        if s2 not in ("idle", "completed"):
            logger.error("Echec génération v2 (status=%s)", s2)
            return {"target_key": target_key, "status": s2, "v1_only": True}
        final_plan = _latest_agent_text(client, sid)
        final_version = target["version"]
        logger.info("[msg2] plan v%d reçu (%d chars)", final_version, len(final_plan))

    # 4. Cache local
    local_path = _save_local(
        target_key, target["building_id"], final_version,
        final_plan, sid, raw_meta={"label": target["label"]},
    )
    logger.info("✓ Cache local : %s", local_path)

    # 5. Persistance Supabase
    session_row, plan_row = _save_supabase(
        target_key, target["building_id"], final_version,
        final_plan, sid, target["target_class"],
    )
    if plan_row:
        logger.info("✓ Supabase : session=%s plan=%s", session_row, plan_row)
    else:
        logger.warning("Supabase non écrit (cloud non configuré).")

    return {
        "target_key": target_key,
        "building_id": target["building_id"],
        "version": final_version,
        "session_id": sid,
        "local_path": str(local_path),
        "supabase_session_id": session_row,
        "supabase_plan_id": plan_row,
        "plan_chars": len(final_plan),
        "status": "ok",
    }


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        choices=list(TARGETS.keys()),
        help="Génère un seul target (sinon tous).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        for k, t in TARGETS.items():
            print(f"{k}: {t['label']} ({t['building_id']}, v{t['version']})")
        return 0

    todo = {args.only: TARGETS[args.only]} if args.only else TARGETS
    logger.warning("⚠ COÛT ATTENDU : ~%d × 0.5-0.7 € = %.1f-%.1f €",
                   len(todo), len(todo) * 0.5, len(todo) * 0.7)
    time.sleep(1)

    results = []
    for k, t in todo.items():
        try:
            r = generate_target(k, t)
            results.append(r)
        except Exception as exc:
            logger.exception("Echec %s", k)
            results.append({"target_key": k, "status": "exception", "error": str(exc)})

    print()
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    logger.info("Bilan : %d/%d OK", ok_count, len(results))
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
