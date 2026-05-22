"""ConX — J10 : synchronisation idempotente des 3 Managed Agents Anthropic.

Lit `agents/agents.yaml`, crée ou met à jour les 3 agents (Sélection, Plan, Conformité)
via `client.beta.agents.create/update`. Persiste les IDs dans `agents/agents.lock.yaml`.

⚠ Requiert :
  - ANTHROPIC_API_KEY en .env
  - Skills déjà uploadées (cf. docs/SKILLS.md §5 + B-009 + B-010)
  - agents/skills.yaml (mapping nom skill → skill_id Anthropic) — à créer après upload

Usage :
    python agents/sync.py             # crée/update les 3 agents
    python agents/sync.py --dry-run   # affiche le diff sans toucher Anthropic
    python agents/sync.py --check     # vérifie connectivité + skills présents

⚠ COÛT : la création + l'update sont gratuites, mais les Tests sessions facturés
à l'utilisation. Pas de session lancée par ce script (sauf test-ttl).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS_YAML = ROOT / "agents" / "agents.yaml"
SKILLS_YAML = ROOT / "agents" / "skills.yaml"
LOCK_YAML = ROOT / "agents" / "agents.lock.yaml"

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s"
)
logger = logging.getLogger("agents.sync")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        logger.error(f"Fichier introuvable : {path}")
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_client():
    """Retourne un client Anthropic configuré avec les beta headers requis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY non défini dans l'environnement.")
        sys.exit(3)
    try:
        import anthropic
    except ImportError:
        logger.error("Module `anthropic` non installé. `pip install anthropic`.")
        sys.exit(4)

    config = load_yaml(AGENTS_YAML)
    return anthropic.Anthropic(
        api_key=api_key,
        default_headers={
            "anthropic-beta": (
                f"{config['beta_header']},skills-2025-10-02,"
                "code-execution-2025-08-25,files-api-2025-04-14"
            ),
        },
    )


def resolve_skill_ids(skills_config: list[dict], skills_map: dict) -> list[str]:
    """Convertit les noms de skills en IDs Anthropic via agents/skills.yaml."""
    ids = []
    for s in skills_config:
        name = s["name"]
        sid = skills_map.get(name)
        if sid is None:
            logger.error(
                f"Skill {name!r} non trouvé dans agents/skills.yaml — l'uploader d'abord."
            )
            sys.exit(5)
        ids.append(sid)
    return ids


def build_agent_payload(agent_config: dict, skills_map: dict) -> dict:
    """Convertit la config YAML en payload prêt pour client.beta.agents.create."""
    sp_path = ROOT / agent_config["system_prompt_file"]
    if not sp_path.exists():
        logger.error(f"System prompt introuvable : {sp_path}")
        sys.exit(6)
    system_prompt = sp_path.read_text(encoding="utf-8")

    payload = {
        "name": agent_config["name"],
        "description": agent_config.get("description", "").strip(),
        "model": agent_config["model"],
        "system_prompt": system_prompt,
        "tools": [{"type": t} for t in agent_config.get("builtin_tools", [])],
        "skills": resolve_skill_ids(agent_config.get("skills", []), skills_map),
    }

    if "environment" in agent_config:
        payload["environment"] = agent_config["environment"]
    if "networking" in agent_config:
        # Résoudre les variables d'env dans allowed_hosts
        hosts = []
        for h in agent_config["networking"].get("allowed_hosts", []):
            if h.startswith("${") and h.endswith("}"):
                env_var = h[2:-1]
                resolved = os.environ.get(env_var)
                if resolved:
                    hosts.append(
                        resolved.replace("https://", "")
                        .replace("http://", "")
                        .split("/")[0]
                    )
            else:
                hosts.append(h)
        payload["networking"] = {"allowed_hosts": hosts}

    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Affiche le diff sans appeler Anthropic"
    )
    parser.add_argument(
        "--check", action="store_true", help="Vérifie connectivité + skills présents"
    )
    args = parser.parse_args()

    config = load_yaml(AGENTS_YAML)
    skills_map = load_yaml(SKILLS_YAML) if SKILLS_YAML.exists() else {}
    lock = load_yaml(LOCK_YAML) if LOCK_YAML.exists() else {"agents": {}}

    if not skills_map:
        logger.error(
            "agents/skills.yaml absent ou vide. "
            "Upload les skills d'abord (docs/SKILLS.md §5), puis renseigne le mapping name→id."
        )
        return 7

    payloads = [build_agent_payload(a, skills_map) for a in config["agents"]]

    if args.dry_run or args.check:
        for p in payloads:
            logger.info(
                f"- {p['name']} : model={p['model']}, skills={len(p['skills'])}"
            )
            if args.dry_run:
                print(yaml.dump(p, allow_unicode=True))
        if args.check:
            try:
                client = get_client()
                logger.info("Client Anthropic OK.")
            except SystemExit:
                logger.error("Client Anthropic non disponible.")
                return 8
        return 0

    client = get_client()
    for payload in payloads:
        name = payload["name"]
        existing_id = lock.get("agents", {}).get(name)
        if existing_id:
            logger.info(f"Update agent {name} (id={existing_id})...")
            agent = client.beta.agents.update(agent_id=existing_id, **payload)
        else:
            logger.info(f"Create agent {name}...")
            agent = client.beta.agents.create(**payload)
        lock.setdefault("agents", {})[name] = agent.id
        logger.info(f"  → id={agent.id}")

    LOCK_YAML.write_text(yaml.dump(lock, allow_unicode=True), encoding="utf-8")
    logger.info(f"Lock écrit dans {LOCK_YAML.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
