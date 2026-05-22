"""ConX — J10 : test TTL session Managed Agents (B-001).

Procédure (brief CLAUDE.md §7 + plan §2.5) :
  1. Créer une session sur l'agent Plan.
  2. Envoyer message 1 ("Génère un plan pour le bâtiment X en chanvre").
  3. wait_for(idle).
  4. sleep(10 minutes).
  5. Envoyer message 2 ("Et en bois CLT à la place ?").
  6. Vérifier que l'agent rappelle CTX message 1 sans qu'on le ré-injecte.

⚠ COÛT : ~ 0.5-1 € par exécution (2 messages Claude Opus 4.7). Validation
partenaire requise (règle §9.D).

Usage :
    python agents/test_ttl.py --agent conx-plan --wait-min 10

Si test PASSE → B-001 résolu, on continue J11+.
Si test ÉCHOUE (la session est terminated ou ne se souvient pas) → activer fallback
"replay-previous-plan" (cf. B-001 mitigation, à coder en J12 backend Mode Projet).
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

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s"
)
logger = logging.getLogger("test_ttl")


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY non défini.")
        sys.exit(2)
    import anthropic

    config_path = ROOT / "agents" / "agents.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return anthropic.Anthropic(
        api_key=api_key,
        default_headers={
            "anthropic-beta": f"{cfg['beta_header']},skills-2025-10-02,files-api-2025-04-14",
        },
    )


def wait_for_idle(client, session_id: str, timeout_s: int = 300) -> bool:
    """Poll session.status jusqu'à idle (ou timeout)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        session = client.beta.agents.sessions.retrieve(session_id=session_id)
        if session.status == "idle":
            return True
        if session.status in ("error", "terminated"):
            logger.error(f"Session {session_id} en statut {session.status}.")
            return False
        time.sleep(3)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent", default="conx-plan", help="Nom de l'agent (cf. agents.yaml)"
    )
    parser.add_argument(
        "--wait-min",
        type=int,
        default=10,
        help="Minutes à attendre entre msg1 et msg2 (défaut 10)",
    )
    args = parser.parse_args()

    if not LOCK_YAML.exists():
        logger.error(f"{LOCK_YAML} absent — lancer d'abord `python agents/sync.py`")
        return 3
    lock = yaml.safe_load(LOCK_YAML.read_text(encoding="utf-8"))
    agent_id = lock.get("agents", {}).get(args.agent)
    if not agent_id:
        logger.error(
            f"Agent {args.agent} non trouvé dans agents.lock.yaml — sync d'abord"
        )
        return 4

    logger.warning(
        "⚠ COÛT ATTENDU : ~ 0.5-1 € (2 messages Claude Opus). "
        "Confirmer avant d'exécuter. (Ctrl-C pour annuler)"
    )
    time.sleep(5)

    client = get_client()

    # Étape 1 : créer session + msg1
    logger.info(f"Création session sur agent {args.agent} (id={agent_id})...")
    session = client.beta.agents.sessions.create(agent_id=agent_id)
    logger.info(f"  → session_id={session.id}")

    msg1 = (
        "Génère un plan de rénovation pour ce bâtiment : pavillon brique 124 m² "
        "construit 1965, DPE F (412 kWh ep/m²/an), gaz, classe cible C. Privilégie "
        "le chanvre comme matériau dominant. Cite les sources FDES."
    )
    logger.info(f"[msg1] envoi : {msg1[:100]}...")
    client.beta.agents.sessions.events.create(
        session_id=session.id,
        type="user_message",
        content=msg1,
    )

    if not wait_for_idle(client, session.id, timeout_s=300):
        logger.error("[msg1] session pas idle après 5 min — abandon.")
        return 5
    logger.info("[msg1] session idle.")

    # Étape 2 : attendre N minutes
    wait_s = args.wait_min * 60
    logger.info(f"Sleep {args.wait_min} min ({wait_s} s)...")
    time.sleep(wait_s)

    # Étape 3 : vérifier que session est encore vivante
    session_check = client.beta.agents.sessions.retrieve(session_id=session.id)
    logger.info(f"Session status après sleep : {session_check.status}")
    if session_check.status == "terminated":
        logger.warning(
            "⚠ B-001 CONFIRMÉ : session terminated après "
            f"{args.wait_min} min idle. Implémenter fallback replay-previous-plan."
        )
        return 6

    # Étape 4 : msg2 sur la même session
    msg2 = "Et plutôt en bois CLT à la place du chanvre ?"
    logger.info(f"[msg2] envoi : {msg2}")
    client.beta.agents.sessions.events.create(
        session_id=session.id,
        type="user_message",
        content=msg2,
    )

    if not wait_for_idle(client, session.id, timeout_s=300):
        logger.error("[msg2] session pas idle après 5 min — abandon.")
        return 7

    # Récupérer la réponse de l'agent
    events = client.beta.agents.sessions.events.list(session_id=session.id)
    last_agent_event = None
    for e in events:
        if e.role == "agent" or e.type == "agent_message":
            last_agent_event = e
    if last_agent_event is None:
        logger.error("Pas de réponse agent au msg2.")
        return 8

    reply_text = (
        last_agent_event.content
        if hasattr(last_agent_event, "content")
        else str(last_agent_event)
    )
    logger.info(f"[msg2] réponse agent (premiers 500 chars) :\n{reply_text[:500]}\n...")

    # Test : la réponse mentionne-t-elle "bâtiment", "pavillon", "1965", ou "412 kWh" ?
    # → preuve que le contexte du msg1 est rappelé.
    keywords = ["pavillon", "1965", "412", "brique", "F", "gaz"]
    found = [k for k in keywords if k.lower() in reply_text.lower()]
    if len(found) >= 2:
        logger.info(f"✅ TTL test PASS — contexte msg1 rappelé (keywords : {found})")
        result = {
            "ttl_test": "pass",
            "wait_min": args.wait_min,
            "keywords_found": found,
        }
    else:
        logger.warning(f"❌ TTL test FAIL — contexte msg1 non détecté ({found})")
        result = {
            "ttl_test": "fail",
            "wait_min": args.wait_min,
            "keywords_found": found,
        }

    print(json.dumps(result, indent=2))
    return 0 if result["ttl_test"] == "pass" else 9


if __name__ == "__main__":
    sys.exit(main())
