"""ConX — wrapper Anthropic Managed Agents (J12+).

Référence : `agents/agents.yaml` + `agents/agents.lock.yaml` (généré par
`agents/sync.py` après création effective des agents par le partenaire).
Le wrapper lit le lock-file au démarrage pour résoudre les noms d'agent
('conx-selection', 'conx-plan', 'conx-conformite') en agent_id Anthropic.

⚠ Toutes les méthodes lèvent HTTPException 503 si :
- la lib `anthropic` n'est pas dispo ;
- la clé `ANTHROPIC_API_KEY` n'est pas définie ;
- `agents.lock.yaml` n'existe pas (sync.py pas encore lancé par le partenaire).

Ces erreurs sont des arrêts propres, pas des crashs — le backend démarre
même sans Anthropic configuré, seuls les endpoints `/api/agents/*` seront
indisponibles.

⚠ COÛT (règle §9.D CLAUDE.md) :
- Création de session : gratuit (config storage).
- Envoi d'un message + génération d'une réponse Claude Opus 4.7 : ~0.20-0.50 €
  selon longueur. Mode Projet typique : 3-5 tours = 1-3 € par utilisateur.
- Cf. budgétisation B-007 / R12.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from fastapi import HTTPException, status

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = logging.getLogger("conx.agents")

ROOT = Path(__file__).resolve().parent.parent.parent
LOCK_YAML = ROOT / "agents" / "agents.lock.yaml"
AGENTS_YAML = ROOT / "agents" / "agents.yaml"

# Beta headers (cf. agents/agents.yaml + docs/AGENTS.md)
BETA_HEADER = "managed-agents-2026-04-01,skills-2025-10-02,files-api-2025-04-14,code-execution-2025-08-25"

# Cache module-level (les agent_ids sont stables pour la durée du backend)
_AGENT_IDS_CACHE: dict[str, str] | None = None


def _load_agent_ids() -> dict[str, str]:
    """Lit agents.lock.yaml et retourne le mapping {agent_name: agent_id}.

    Lève 503 si le fichier n'existe pas (le partenaire n'a pas encore lancé
    `python agents/sync.py`).
    """
    global _AGENT_IDS_CACHE
    if _AGENT_IDS_CACHE is not None:
        return _AGENT_IDS_CACHE

    if not LOCK_YAML.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "agents.lock.yaml absent — le partenaire doit lancer "
                "`python agents/sync.py` après validation §9.D."
            ),
        )
    lock = yaml.safe_load(LOCK_YAML.read_text(encoding="utf-8")) or {}
    ids = lock.get("agents") or {}
    if not isinstance(ids, dict) or not ids:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"agents.lock.yaml mal formé ou vide : {LOCK_YAML}",
        )
    _AGENT_IDS_CACHE = dict(ids)
    return _AGENT_IDS_CACHE


def get_agent_id(agent_name: str) -> str:
    """Résout 'conx-plan' → 'agt_xxxxxxx' depuis agents.lock.yaml."""
    ids = _load_agent_ids()
    if agent_name not in ids:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent {agent_name!r} non trouvé dans agents.lock.yaml.",
        )
    return ids[agent_name]


def _get_anthropic_client() -> Anthropic:
    """Crée un client Anthropic avec les beta headers requis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-ant-..."):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANTHROPIC_API_KEY non défini ou placeholder.",
        )
    try:
        import anthropic
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Module anthropic non installé : {exc}",
        ) from exc

    return anthropic.Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": BETA_HEADER},
    )


# ---------------------------------------------------------------------------
# Opérations haut-niveau (utilisées par routers/agents.py)
# ---------------------------------------------------------------------------


def create_session(agent_name: str) -> dict[str, Any]:
    """Crée une session sur l'agent et retourne {session_id, status, agent_id}.

    Coût : 0 € (la session est facturée à l'envoi de messages, pas à sa création).
    """
    client = _get_anthropic_client()
    agent_id = get_agent_id(agent_name)
    logger.info("Création session sur agent %s (id=%s)...", agent_name, agent_id)
    session = client.beta.agents.sessions.create(agent_id=agent_id)
    return {
        "session_id": session.id,
        "status": getattr(session, "status", "unknown"),
        "agent_id": agent_id,
        "agent_name": agent_name,
    }


def send_user_message(session_id: str, content: str) -> dict[str, Any]:
    """Envoie un user_message sur la session. Retour : {event_id, type}.

    L'agent traite ensuite asynchroniquement — il faut écouter le stream
    `events.list/stream` (cf. stream_events()) pour récupérer la réponse.
    """
    client = _get_anthropic_client()
    logger.info("Send user message à session %s (%d chars)...", session_id, len(content))
    event = client.beta.agents.sessions.events.create(
        session_id=session_id,
        type="user_message",
        content=content,
    )
    return {
        "event_id": getattr(event, "id", None),
        "type": getattr(event, "type", "user_message"),
    }


def retrieve_session(session_id: str) -> dict[str, Any]:
    """Status d'une session (idle / working / terminated / error)."""
    client = _get_anthropic_client()
    session = client.beta.agents.sessions.retrieve(session_id=session_id)
    return {
        "session_id": session.id,
        "status": getattr(session, "status", "unknown"),
    }


def list_events(session_id: str, after: str | None = None) -> list[dict[str, Any]]:
    """Liste tous les events de la session (filtre après event_id si fourni)."""
    client = _get_anthropic_client()
    kwargs: dict[str, Any] = {"session_id": session_id}
    if after:
        kwargs["after"] = after
    events = client.beta.agents.sessions.events.list(**kwargs)
    out: list[dict[str, Any]] = []
    for e in events:
        out.append(_event_to_dict(e))
    return out


def _event_to_dict(e: Any) -> dict[str, Any]:
    """Convertit un event SDK en dict JSON-sérialisable pour le SSE."""
    return {
        "id": getattr(e, "id", None),
        "type": getattr(e, "type", None),
        "role": getattr(e, "role", None),
        "content": getattr(e, "content", None),
        "created_at": (
            e.created_at.isoformat() if hasattr(e, "created_at") and e.created_at else None
        ),
    }


# ---------------------------------------------------------------------------
# Helpers pour SSE (utilisé par routers/agents.py)
# ---------------------------------------------------------------------------


def serialize_event_for_sse(event: dict[str, Any]) -> bytes:
    """Format SSE : `data: {json}\\n\\n`."""
    payload = json.dumps(event, ensure_ascii=False, default=str)
    return f"data: {payload}\n\n".encode()


def keepalive_event() -> bytes:
    """Event SSE keepalive (commentaire). Garde la connexion vivante derrière
    les proxies (Nginx 60s, Cloudflare 100s) — envoyer toutes les 15-30s."""
    return b": keepalive\n\n"


def reset_cache() -> None:
    """Vide le cache `_AGENT_IDS_CACHE` (tests + re-sync runtime)."""
    global _AGENT_IDS_CACHE
    _AGENT_IDS_CACHE = None
