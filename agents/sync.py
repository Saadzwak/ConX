"""ConX — sync idempotent des 3 Managed Agents + des 2 environments.

Lit `agents/agents.yaml` + `agents/skills.yaml` (mapping nom → skill_id), crée
ou met à jour :
  - les Environments (cloud configs : packages pip, networking allowed_hosts)
  - les Agents (model, system, tools, skills)
Persiste les IDs dans `agents/agents.lock.yaml`.

Architecture (confirmée par introspection SDK anthropic==0.96.0) :
  - `agents.create()` : pas de paramètre environment — il est lié à la SESSION
    (cf. sessions.create(agent, environment_id, ...)).
  - On crée donc 2 environments :
      conx-env-default     : pour conx-selection + conx-plan (web_fetch ngrok)
      conx-env-conformite  : avec ifcopenshell pip installé + pas de network
  - `agents.create(skills=[...])` : list de `{type:'custom', skill_id, version}`.
  - `tools=[{type:'agent_toolset_20260401', ...}]` : prebuilt toolset
    (bash+file+web_fetch+web_search+computer_use).

Beta headers : `managed-agents-2026-04-01,skills-2025-10-02,files-api-2025-04-14,code-execution-2025-08-25`

Usage :
    python agents/sync.py --check     # connectivité
    python agents/sync.py --dry-run   # diff sans appel API
    python agents/sync.py             # apply
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS_YAML = ROOT / "agents" / "agents.yaml"
SKILLS_YAML = ROOT / "agents" / "skills.yaml"
LOCK_YAML = ROOT / "agents" / "agents.lock.yaml"

BETA_HEADER = (
    "managed-agents-2026-04-01,skills-2025-10-02,"
    "files-api-2025-04-14,code-execution-2025-08-25"
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("agents.sync")


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


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-..."):
        logger.error("ANTHROPIC_API_KEY non défini ou placeholder.")
        sys.exit(3)
    try:
        import anthropic
    except ImportError:
        logger.error("Module anthropic non installé.")
        sys.exit(4)
    return anthropic.Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": BETA_HEADER},
    )


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------


def _resolve_allowed_hosts(hosts: list[str]) -> list[str]:
    """Substitue ${VAR} et normalise les hostnames (sans https://).

    Si la valeur résolue contient encore un placeholder (YOUR_), on tombe sur
    une wildcard ngrok par défaut pour ne pas bloquer la création d'env.
    """
    out: list[str] = []
    for h in hosts:
        if h.startswith("${") and h.endswith("}"):
            v = os.environ.get(h[2:-1], "").strip()
            if not v or "YOUR_" in v:
                # Placeholder non résolu — fallback wildcard ngrok
                logger.warning("Placeholder %s non résolu — fallback *.ngrok-free.app + *.ngrok.app", h)
                out.extend(["*.ngrok-free.app", "*.ngrok.app", "*.ngrok.io"])
                continue
            h = v
        h = h.replace("https://", "").replace("http://", "").split("/")[0]
        if h:
            out.append(h)
    return out


def _build_env_config(env_def: dict) -> dict:
    """Construit BetaCloudConfigParams."""
    cfg: dict[str, Any] = {"type": "cloud"}
    pkg = env_def.get("packages")
    if pkg:
        pkg_p = {"type": "packages"}
        for k in ("pip", "apt", "npm", "go", "cargo", "gem"):
            if k in pkg:
                pkg_p[k] = list(pkg[k])
        cfg["packages"] = pkg_p
    net = env_def.get("networking")
    if net:
        allowed = _resolve_allowed_hosts(net.get("allowed_hosts", []))
        cfg["networking"] = {
            "type": "limited",
            "allowed_hosts": allowed,
            "allow_mcp_servers": False,
            "allow_package_managers": True,  # nécessaire pour pip install
        }
    return cfg


# Définition des 2 environments
ENVIRONMENTS = {
    "conx-env-default": {
        # Pour conx-selection + conx-plan : accès HTTP au backend via ngrok
        "description": "Env par défaut ConX : accès web limité au backend ngrok.",
        "networking": {
            "allowed_hosts": ["${NGROK_PUBLIC_URL}"],
        },
    },
    "conx-env-conformite": {
        # Pour conx-conformite : ifcopenshell pré-installé, pas de network
        "description": "Env Conformité ConX : ifcopenshell + pas de network.",
        "packages": {
            "pip": ["ifcopenshell"],
        },
        # Pas de networking → purement local au container
    },
}

# Mapping agent_name → env_name
AGENT_ENV = {
    "conx-selection":   "conx-env-default",
    "conx-plan":        "conx-env-default",
    "conx-conformite":  "conx-env-conformite",
}


def sync_environments(client, lock: dict, dry_run: bool = False) -> dict[str, str]:
    """Crée ou récupère les environments. Retourne {name: env_id}."""
    existing = {e.name: e for e in client.beta.environments.list().data}
    env_ids: dict[str, str] = lock.get("environments", {}) or {}
    for name, defn in ENVIRONMENTS.items():
        cfg = _build_env_config(defn)
        if name in existing:
            env_id = existing[name].id
            logger.info("Env existant : %s (id=%s)", name, env_id)
            env_ids[name] = env_id
            if not dry_run:
                # On peut UPDATE pour rafraîchir la config (allowed_hosts notamment)
                try:
                    client.beta.environments.update(
                        environment_id=env_id, config=cfg, description=defn["description"]
                    )
                    logger.info("  → config rafraîchie")
                except Exception as e:
                    logger.warning("  update non disponible : %r", e)
        else:
            logger.info("Création env : %s", name)
            if dry_run:
                logger.info("  [DRY-RUN] config=%s", cfg)
                env_ids[name] = "<dry-run>"
                continue
            resp = client.beta.environments.create(
                name=name, description=defn["description"], config=cfg
            )
            env_ids[name] = resp.id
            logger.info("  ✅ id=%s", resp.id)
    return env_ids


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def _resolve_skill_params(skills_in_agent: list[dict], skills_map: dict) -> list[dict]:
    """Convertit [{name: 'carbon-calc'}, ...] → [{type, skill_id, version}, ...]."""
    out: list[dict] = []
    for s in skills_in_agent:
        name = s["name"] if isinstance(s, dict) else s
        sm = skills_map.get(name)
        if sm is None:
            raise SystemExit(f"Skill {name!r} non trouvé dans skills.yaml — uploader d'abord.")
        out.append({"type": "custom", "skill_id": sm["skill_id"], "version": sm["version"]})
    return out


def _build_tools(agent_cfg: dict) -> list[dict]:
    """Pour MVP on utilise un agent_toolset_20260401 par défaut, pas de configs."""
    tools = []
    for t in agent_cfg.get("builtin_tools", []):
        if t == "agent_toolset_20260401":
            tools.append({"type": "agent_toolset_20260401"})
        else:
            logger.warning("Tool inconnu (ignoré) : %s", t)
    return tools


def build_agent_payload(agent_cfg: dict, skills_map: dict) -> dict:
    sp_path = ROOT / agent_cfg["system_prompt_file"]
    if not sp_path.exists():
        logger.error("System prompt introuvable : %s", sp_path)
        sys.exit(6)
    system = sp_path.read_text(encoding="utf-8")

    return {
        "name": agent_cfg["name"],
        "description": agent_cfg.get("description", "").strip()[:1024],
        "model": agent_cfg["model"],
        "system": system,
        "tools": _build_tools(agent_cfg),
        "skills": _resolve_skill_params(agent_cfg.get("skills", []), skills_map),
    }


def sync_agents(client, config: dict, skills_map: dict, lock: dict, dry_run: bool = False) -> dict[str, str]:
    """Crée ou met à jour les agents. Retourne {name: agent_id}."""
    existing = {a.name: a for a in client.beta.agents.list().data}
    agent_ids: dict[str, str] = lock.get("agents", {}) or {}

    for a in config["agents"]:
        name = a["name"]
        payload = build_agent_payload(a, skills_map)
        if name in existing:
            agent_id = existing[name].id
            logger.info("Agent existant : %s (id=%s) — update", name, agent_id)
            agent_ids[name] = agent_id
            if dry_run:
                continue
            client.beta.agents.update(agent_id=agent_id, **{k: v for k, v in payload.items() if k != "name"})
            logger.info("  → update OK")
        else:
            logger.info("Création agent : %s", name)
            if dry_run:
                logger.info("  [DRY-RUN] payload keys: %s", list(payload.keys()))
                agent_ids[name] = "<dry-run>"
                continue
            resp = client.beta.agents.create(**payload)
            agent_ids[name] = resp.id
            logger.info("  ✅ id=%s", resp.id)
    return agent_ids


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Connectivité uniquement")
    parser.add_argument("--dry-run", action="store_true", help="Diff sans appel API")
    args = parser.parse_args()

    config = load_yaml(AGENTS_YAML)
    skills_map = load_yaml(SKILLS_YAML)
    lock = load_yaml(LOCK_YAML) or {"environments": {}, "agents": {}, "agent_env": {}}

    if not skills_map:
        logger.error("agents/skills.yaml vide — lancer d'abord upload_skills.py")
        return 7

    client = get_client()
    if args.check:
        try:
            n_agents = len(client.beta.agents.list().data)
            n_envs = len(client.beta.environments.list().data)
            n_skills = len(client.beta.skills.list().data)
            logger.info("Connecté Anthropic : %d agents, %d envs, %d skills", n_agents, n_envs, n_skills)
            return 0
        except Exception as e:
            logger.error("Erreur : %r", e)
            return 8

    env_ids = sync_environments(client, lock, dry_run=args.dry_run)
    agent_ids = sync_agents(client, config, skills_map, lock, dry_run=args.dry_run)

    # Sauvegarde du lock
    out = {
        "environments": env_ids,
        "agents": agent_ids,
        "agent_env": AGENT_ENV,  # mapping agent_name → env_name (pour sessions.create)
    }
    if not args.dry_run:
        LOCK_YAML.write_text(yaml.dump(out, allow_unicode=True, sort_keys=True), encoding="utf-8")
        logger.info("Lock écrit : %s", LOCK_YAML.name)
    else:
        logger.info("[DRY-RUN] lock non écrit. Aperçu :")
        print(yaml.dump(out, allow_unicode=True, sort_keys=True))

    return 0


if __name__ == "__main__":
    sys.exit(main())
