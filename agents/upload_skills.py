"""ConX — Upload des 6 Skills bundles vers Anthropic (B-009).

⚠ COÛT : 0 € (l'upload de Skills est gratuit, seules les utilisations en
session Agent sont facturées).

⚠ DRY-RUN PAR DÉFAUT : passe --apply pour upload effectif.

Idempotent : si une skill `conx-<name>` existe déjà, ce script crée une
nouvelle **version** au lieu d'écraser. Le mapping `agents/skills.yaml`
(nom → skill_id + version) est mis à jour.

Skills uploadées :
- conx-carbon-calc       : calcul carbone déterministe
- conx-fdes-lookup       : FDES INIES (base statique 30 matériaux)
- conx-ifc-check         : validation IFC + règles RE2020/PMR
- conx-horssite-biosource: catalogue procédés HDF
- conx-re2020-target     : seuils RE2020 + DPE
- conx-pmr-checks        : règles PMR (10 contrôles MVP)

Usage :
    python agents/upload_skills.py --dry-run    # affiche sans uploader
    python agents/upload_skills.py --apply      # upload effectif
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
MAP_YAML = ROOT / "agents" / "skills.yaml"

# Mapping local_dir → display_title (Anthropic prefix `conx-` pour disambiguer)
SKILLS = [
    ("carbon-calc",         "conx-carbon-calc"),
    ("fdes-lookup",         "conx-fdes-lookup"),
    ("ifc-check",           "conx-ifc-check"),
    ("horssite-biosource",  "conx-horssite-biosource"),
    ("re2020-target",       "conx-re2020-target"),
    ("pmr-checks",          "conx-pmr-checks"),
]

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("upload_skills")


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        # Override systématique : la variable peut être à "" dans l'env hérité (Windows)
        os.environ[k.strip()] = v.split("#", 1)[0].strip()


def _bundle_size_mb(p: Path) -> float:
    total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Upload effectif (sinon dry-run)")
    parser.add_argument("--only", help="Limiter à un nom (ex: --only ifc-check)")
    args = parser.parse_args()

    if not args.apply:
        logger.warning("DRY-RUN — aucun upload. Utiliser --apply pour effectif.")

    try:
        import anthropic
        from anthropic.lib import files_from_dir
    except ImportError as e:
        logger.error("anthropic SDK manquant : %s", e)
        return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-..."):
        logger.error("ANTHROPIC_API_KEY manquant ou placeholder.")
        return 3

    client = anthropic.Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "skills-2025-10-02"},
    )

    # Charger l'état existant
    skills_map: dict = {}
    if MAP_YAML.exists():
        skills_map = yaml.safe_load(MAP_YAML.read_text(encoding="utf-8")) or {}

    # Liste des skills déjà présents côté Anthropic
    existing = {s.id: s for s in client.beta.skills.list().data}
    existing_titles = {getattr(s, "display_title", None): s for s in existing.values()}
    logger.info("Skills déjà présents : %d (%s)", len(existing), ", ".join(existing.keys()))

    for local_dir, title in SKILLS:
        if args.only and args.only != local_dir:
            continue
        path = SKILLS_DIR / local_dir
        if not path.is_dir():
            logger.error("Bundle introuvable : %s", path)
            continue
        size_mb = _bundle_size_mb(path)
        logger.info("→ %s (%s, %.2f Mo)", title, local_dir, size_mb)
        if size_mb > 30:
            logger.error("  BUNDLE TROP GROS (max 30 Mo). Skip.")
            continue

        # Vérifier si un skill de ce title existe déjà → versions.create
        already = existing_titles.get(title)
        if already:
            logger.info("  → skill existe (id=%s, latest=%s) : versions.create", already.id, getattr(already, "latest_version", "?"))
            action = ("update_version", already.id)
        else:
            logger.info("  → nouveau skill : skills.create")
            action = ("create", None)

        if not args.apply:
            logger.info("  [DRY-RUN] action=%s", action)
            continue

        try:
            files = files_from_dir(path)
            logger.info("  files_from_dir : %d entrées", len(files))
            if action[0] == "create":
                resp = client.beta.skills.create(
                    display_title=title,
                    files=files,
                    betas=["skills-2025-10-02"],
                )
                sid = resp.id
                ver = getattr(resp, "latest_version", None) or getattr(resp, "version", "1")
                logger.info("  ✅ CREATE → id=%s version=%s", sid, ver)
            else:
                sid = action[1]
                resp = client.beta.skills.versions.create(
                    skill_id=sid,
                    files=files,
                    betas=["skills-2025-10-02"],
                )
                ver = getattr(resp, "version", None) or getattr(resp, "latest_version", "?")
                logger.info("  ✅ VERSION → id=%s version=%s", sid, ver)
            skills_map[local_dir] = {"skill_id": sid, "version": str(ver), "display_title": title}
        except Exception as e:
            logger.error("  ❌ ERREUR : %r", e)
            continue

    if args.apply and skills_map:
        MAP_YAML.write_text(yaml.dump(skills_map, allow_unicode=True, sort_keys=True), encoding="utf-8")
        logger.info("Mapping sauvegardé dans %s", MAP_YAML.name)

    logger.info("Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
