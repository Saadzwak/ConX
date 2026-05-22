"""ConX — B-001 : test du TTL d'une session Managed Agents Anthropic.

Procédure :
  1. Crée une session sur l'agent conx-plan (+ env conx-env-default).
  2. Envoie msg1 (plan rénovation chanvre pavillon 1965 DPE F).
  3. wait_for(idle) — poll status.
  4. sleep(N min) — défaut 10.
  5. Vérifie que la session est encore vivante (status != terminated).
  6. Envoie msg2 ("Et plutôt en bois CLT ?").
  7. wait_for(idle).
  8. Vérifie que la réponse mentionne des keywords du msg1 (pavillon, 1965, brique…)
     → preuve que le contexte du msg1 est rappelé.

Verdict :
- PASS : session vivante après N min ET contexte rappelé.
- FAIL session terminated → fallback "replay-previous-plan" obligatoire.
- FAIL contexte non rappelé → fallback aussi.

⚠ COÛT : ~0.5-1 € (2 messages Opus 4.7). Confirmation §9.D.

Usage :
    python agents/test_ttl.py --wait-min 10
    python agents/test_ttl.py --wait-min 0      # smoke test sans sleep
    python agents/test_ttl.py --dry-run         # n'envoie aucun message
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOCK_YAML = ROOT / "agents" / "agents.lock.yaml"
RESULTS_PATH = ROOT / "data" / "storage" / "ttl_test_results.jsonl"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("test_ttl")


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


def get_client():
    import anthropic
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        default_headers={
            "anthropic-beta": "managed-agents-2026-04-01,skills-2025-10-02,files-api-2025-04-14,code-execution-2025-08-25"
        },
    )


def _latest_event_id(client, session_id: str) -> str | None:
    """Renvoie l'id du dernier event existant (avant un nouveau send)."""
    evs = list(client.beta.sessions.events.list(session_id=session_id, limit=1, order="desc").data)
    if not evs:
        return None
    return getattr(evs[0], "id", None)


def send_user_text(client, session_id: str, text: str) -> str | None:
    """Envoie un user.message et retourne l'id du DERNIER event juste AVANT le send,
    pour permettre wait_for_idle de détecter qu'un nouveau event est arrivé."""
    pre_id = _latest_event_id(client, session_id)
    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": text}],
        }],
    )
    return pre_id


def wait_for_idle(client, session_id: str, pre_event_id: str | None = None, timeout_s: int = 300) -> str:
    """Poll jusqu'à ce que (a) la session soit idle ET (b) un nouvel event soit
    apparu APRÈS `pre_event_id`. Si `pre_event_id` est None, on attend juste idle.

    Fix race condition : sans (b), wait_for_idle pourrait retourner immédiatement
    sur l'état idle initial AVANT que l'agent ait traité le message envoyé.
    """
    deadline = time.time() + timeout_s
    last_status = "?"
    # Mini-délai initial pour laisser à Anthropic le temps de transitionner
    # vers `running` (typiquement < 1 s).
    time.sleep(2)
    while time.time() < deadline:
        sess = client.beta.sessions.retrieve(session_id=session_id)
        status = getattr(sess, "status", "?")
        if status != last_status:
            logger.info("  session.status = %s", status)
            last_status = status
        if status in ("terminated", "error"):
            return status
        if status in ("idle", "completed"):
            # Confirmer qu'un nouvel event est arrivé après pre_event_id
            if pre_event_id is None:
                return status
            current_last = _latest_event_id(client, session_id)
            if current_last and current_last != pre_event_id:
                return status
            # Sinon : status idle mais on n'a pas vu de nouvel event — l'agent
            # n'a pas encore commencé à traiter. Continuer à poll.
        time.sleep(3)
    return f"timeout_after_{timeout_s}s"


def latest_agent_text(client, session_id: str) -> str:
    """Récupère le texte du dernier event de type agent.message dans la session."""
    events = list(client.beta.sessions.events.list(session_id=session_id, limit=200).data)
    for ev in reversed(events):
        et = getattr(ev, "type", "")
        if "agent.message" in et or "agent_message" in et:
            content = getattr(ev, "content", None)
            if content is None:
                continue
            texts = []
            for block in content:
                t = getattr(block, "text", None)
                if t is None and isinstance(block, dict):
                    t = block.get("text")
                if t:
                    texts.append(t)
            if texts:
                return "\n".join(texts)
    return ""


def _persist(result: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = {**result, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with RESULTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    logger.info("Résultat persisté : %s", RESULTS_PATH)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-min", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not LOCK_YAML.exists():
        logger.error("agents.lock.yaml absent — lancer d'abord agents/sync.py")
        return 3
    lock = yaml.safe_load(LOCK_YAML.read_text(encoding="utf-8")) or {}
    agent_id = lock.get("agents", {}).get("conx-plan")
    env_id = lock.get("environments", {}).get("conx-env-default")
    if not agent_id or not env_id:
        logger.error("agent_id ou env_id manquant dans le lock")
        return 4
    logger.info("Agent conx-plan : %s", agent_id)
    logger.info("Env default    : %s", env_id)

    if args.dry_run:
        logger.warning("DRY-RUN — aucun message envoyé.")
        return 0

    logger.warning("⚠ COÛT ATTENDU : ~0.5-1 € (2 messages Opus 4.7).")
    time.sleep(2)

    client = get_client()

    logger.info("Création session sur conx-plan + env default...")
    session = client.beta.sessions.create(agent=agent_id, environment_id=env_id, title="ConX TTL test")
    sid = session.id
    logger.info("  ✅ session_id = %s, status = %s", sid, getattr(session, "status", "?"))

    msg1 = (
        "Génère un plan de rénovation pour ce bâtiment : pavillon brique 124 m² "
        "construit en 1965, DPE F (412 kWh ep/m²/an), chauffage gaz, classe cible C. "
        "Privilégie le chanvre comme matériau dominant. Cite les sources FDES."
    )
    logger.info("[msg1] envoi : %s...", msg1[:80])
    pre1 = send_user_text(client, sid, msg1)

    s1 = wait_for_idle(client, sid, pre_event_id=pre1, timeout_s=300)
    if s1 != "idle":
        logger.error("[msg1] session pas idle (status=%s) — abandon.", s1)
        _persist({"ttl_test": "msg1_not_idle", "status": s1, "session_id": sid})
        return 5
    reply1 = latest_agent_text(client, sid)
    logger.info("[msg1] réponse agent (%d chars) :\n%s\n…", len(reply1), reply1[:400])

    wait_s = args.wait_min * 60
    if wait_s > 0:
        logger.info("Sleep %d min (%d s)…", args.wait_min, wait_s)
        t0 = time.time()
        while time.time() < t0 + wait_s:
            time.sleep(min(60, max(1, wait_s - (time.time() - t0))))
        logger.info("Sleep terminé.")

    sess_check = client.beta.sessions.retrieve(session_id=sid)
    status_after_sleep = getattr(sess_check, "status", "?")
    logger.info("Session status après sleep : %s", status_after_sleep)
    if status_after_sleep == "terminated":
        logger.warning("⚠ B-001 CONFIRMÉ : session terminated après %d min idle.", args.wait_min)
        _persist({"ttl_test": "session_terminated", "wait_min": args.wait_min, "session_id": sid})
        return 6

    msg2 = "Et plutôt en bois CLT à la place du chanvre ? Régénère le plan complet."
    logger.info("[msg2] envoi : %s", msg2)
    pre2 = send_user_text(client, sid, msg2)

    s2 = wait_for_idle(client, sid, pre_event_id=pre2, timeout_s=300)
    if s2 != "idle":
        logger.error("[msg2] session pas idle (status=%s) — abandon.", s2)
        _persist({"ttl_test": "msg2_not_idle", "status": s2, "session_id": sid})
        return 7
    reply2 = latest_agent_text(client, sid)
    logger.info("[msg2] réponse agent (%d chars) :\n%s\n…", len(reply2), reply2[:400])

    keywords = ["pavillon", "1965", "412", "brique", "124", "gaz", "chanvre"]
    found = [k for k in keywords if k.lower() in reply2.lower()]
    if len(found) >= 2:
        verdict = "pass"
        logger.info("✅ TTL test PASS — contexte msg1 rappelé (keywords : %s)", found)
    else:
        verdict = "fail_context_lost"
        logger.warning("❌ TTL test FAIL — contexte msg1 non détecté (keywords : %s)", found)

    result = {
        "ttl_test": verdict,
        "wait_min": args.wait_min,
        "keywords_found": found,
        "status_after_sleep": status_after_sleep,
        "session_id": sid,
        "reply1_excerpt": reply1[:500],
        "reply2_excerpt": reply2[:500],
    }
    _persist(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if verdict == "pass" else 9


if __name__ == "__main__":
    sys.exit(main())
