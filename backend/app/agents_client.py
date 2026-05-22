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

def _resolve_agents_dir() -> Path:
    """Trouve le répertoire `agents/` quel que soit le layout (dev local ou
    container Docker où `/app/agents` est monté en read-only)."""
    # 1. Container Docker : /app/agents (monté via docker-compose).
    candidate_docker = Path("/app/agents")
    if (candidate_docker / "agents.lock.yaml").exists() or candidate_docker.is_dir():
        return candidate_docker
    # 2. Dev local : remonter depuis __file__ (.../backend/app/agents_client.py
    #    → .../agents/agents.lock.yaml).
    here = Path(__file__).resolve()
    for parent in (here.parent.parent.parent, here.parent.parent, here.parent.parent.parent.parent):
        candidate = parent / "agents"
        if (candidate / "agents.lock.yaml").exists() or candidate.is_dir():
            return candidate
    # 3. Fallback : on retourne le chemin attendu en dev (qui peut ne pas exister)
    return here.parent.parent.parent / "agents"


_AGENTS_DIR = _resolve_agents_dir()
LOCK_YAML = _AGENTS_DIR / "agents.lock.yaml"
AGENTS_YAML = _AGENTS_DIR / "agents.yaml"

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


def _load_env_ids() -> dict[str, str]:
    """Lit agents.lock.yaml et retourne le mapping {agent_name → env_id}."""
    if not LOCK_YAML.exists():
        return {}
    lock = yaml.safe_load(LOCK_YAML.read_text(encoding="utf-8")) or {}
    agent_env = lock.get("agent_env") or {}
    envs = lock.get("environments") or {}
    out: dict[str, str] = {}
    if isinstance(agent_env, dict) and isinstance(envs, dict):
        for agent_name, env_name in agent_env.items():
            env_id = envs.get(env_name)
            if env_id:
                out[agent_name] = env_id
    return out


def get_environment_id(agent_name: str) -> str:
    """Résout l'env_id Anthropic à utiliser pour cet agent (lié à la session)."""
    env_ids = _load_env_ids()
    if agent_name in env_ids:
        return env_ids[agent_name]
    # Fallback : env_default_id depuis l'env (legacy ou récupération directe)
    fallback = os.environ.get("ENV_DEFAULT_ID", "").strip()
    if fallback:
        return fallback
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Env Anthropic introuvable pour {agent_name!r} dans agents.lock.yaml.",
    )


def create_session(agent_name: str, title: str | None = None) -> dict[str, Any]:
    """Crée une session sur l'agent et retourne {session_id, status, agent_id}.

    Coût : 0 € (la session est facturée à l'envoi de messages, pas à sa création).

    Note : l'API beta managed-agents-2026-04-01 bind l'env_id à la SESSION
    (pas à l'agent — découverte SDK J10).
    """
    client = _get_anthropic_client()
    agent_id = get_agent_id(agent_name)
    env_id = get_environment_id(agent_name)
    logger.info(
        "Création session sur agent %s (id=%s) + env %s...", agent_name, agent_id, env_id,
    )
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=env_id,
        title=title or f"ConX {agent_name} session",
    )
    return {
        "session_id": session.id,
        "status": getattr(session, "status", "unknown"),
        "agent_id": agent_id,
        "env_id": env_id,
        "agent_name": agent_name,
    }


def send_user_message(session_id: str, content: str) -> dict[str, Any]:
    """Envoie un user_message sur la session. Retour : {event_id, type}.

    Format event : `{"type":"user.message", "content":[{"type":"text","text":...}]}`
    (validé par test_ttl.py).
    """
    client = _get_anthropic_client()
    logger.info("Send user message à session %s (%d chars)...", session_id, len(content))
    resp = client.beta.sessions.events.send(
        session_id=session_id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": content}],
            }
        ],
    )
    # La réponse contient une liste d'events créés ; on renvoie le 1er.
    events = getattr(resp, "events", None) or getattr(resp, "data", None) or []
    if events:
        e = events[0]
        return {"event_id": getattr(e, "id", None), "type": getattr(e, "type", "user.message")}
    return {"event_id": None, "type": "user.message"}


def retrieve_session(session_id: str) -> dict[str, Any]:
    """Status d'une session (idle / running / terminated / error)."""
    client = _get_anthropic_client()
    session = client.beta.sessions.retrieve(session_id=session_id)
    return {
        "session_id": session.id,
        "status": getattr(session, "status", "unknown"),
    }


def list_events(session_id: str, after: str | None = None) -> list[dict[str, Any]]:
    """Liste les events de la session après un event_id donné.

    Le SDK Anthropic `beta.sessions.events.list` n'accepte PAS `after=<event_id>`
    (cf. signature : il propose `created_at_gt`, `page`, `order`). On fetch
    donc l'intégralité de la session (limit=200, order=asc) puis on filtre
    côté Python : tout ce qui suit chronologiquement l'event `after`. Coût
    acceptable pour la démo (sessions courtes, polling 1.5 s).
    """
    client = _get_anthropic_client()
    events_iter = client.beta.sessions.events.list(
        session_id=session_id,
        limit=200,
        order="asc",
    )
    seen_after = after is None
    out: list[dict[str, Any]] = []
    for e in getattr(events_iter, "data", events_iter):
        if not seen_after:
            if getattr(e, "id", None) == after:
                seen_after = True
            continue
        out.append(_event_to_dict(e))
    return out


def _event_to_dict(e: Any) -> dict[str, Any]:
    """Convertit un event SDK en dict JSON-sérialisable pour le SSE.

    L'API beta utilise `processed_at` (pas `created_at`). On expose les deux
    pour rester compatible côté frontend.
    """
    ts = (
        getattr(e, "processed_at", None)
        or getattr(e, "created_at", None)
    )
    return {
        "id": getattr(e, "id", None),
        "type": getattr(e, "type", None),
        "role": getattr(e, "role", None),
        "content": _serialize_content(getattr(e, "content", None)),
        "created_at": ts.isoformat() if ts and hasattr(ts, "isoformat") else (str(ts) if ts else None),
        "processed_at": ts.isoformat() if ts and hasattr(ts, "isoformat") else (str(ts) if ts else None),
    }


def _serialize_content(content: Any) -> Any:
    """Sérialise content (peut être list[ContentBlock] avec attrs ou dict)."""
    if content is None:
        return None
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict):
                out.append(block)
            else:
                # SDK Pydantic block → dict
                d = {"type": getattr(block, "type", None)}
                text = getattr(block, "text", None)
                if text is not None:
                    d["text"] = text
                out.append(d)
        return out
    return content


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
