"""ConX — applique les migrations Supabase Cloud via la Management API.

Utilise un Personal Access Token (PAT) côté `SUPABASE_ACCESS_TOKEN` et le
project ref côté `SUPABASE_PROJECT_REF`. Appelle l'endpoint :

    POST https://api.supabase.com/v1/projects/<ref>/database/query
    Authorization: Bearer <PAT>
    {"query": "...SQL..."}

Le DDL n'est PAS exposé via PostgREST (anon/service_role) — c'est la voie
officielle pour appliquer des migrations sans avoir le mot de passe DB.

Fallback : si `SUPABASE_ACCESS_TOKEN` absent, tente une connexion psycopg
directe via `SUPABASE_DB_PASSWORD`.

Usage :
    python scripts/supabase_migrate.py                          # applique tout
    python scripts/supabase_migrate.py --check                  # SELECT 1
    python scripts/supabase_migrate.py --file scripts/sql/supabase/001_app_schema.sql

⚠ COÛT : 0 € (Supabase free tier).
⚠ SÉCURITÉ : le PAT est l'équivalent d'un mot de passe admin Supabase —
JAMAIS commit. Lecture depuis `.env`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MIG_DIR = ROOT / "scripts" / "sql" / "supabase"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("supabase_migrate")

MGMT_API_BASE = "https://api.supabase.com"


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


def _project_ref() -> str:
    """Récupère le project ref depuis env ou URL Supabase."""
    ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
    if ref:
        return ref
    url = os.environ.get("SUPABASE_URL", "").strip()
    if url:
        # https://<ref>.supabase.co
        host = url.replace("https://", "").replace("http://", "").rstrip("/")
        return host.split(".")[0]
    return ""


def _exec_sql_via_pat(sql: str) -> tuple[bool, Any]:
    """Exécute du SQL via Supabase Management API.

    Retourne (success, payload). Le payload est soit la liste de rows
    (`[{...}, ...]`), soit le message d'erreur.
    """
    import urllib.error
    import urllib.request

    pat = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    ref = _project_ref()
    if not pat or not ref:
        return False, "SUPABASE_ACCESS_TOKEN ou SUPABASE_PROJECT_REF absent"
    url = f"{MGMT_API_BASE}/v1/projects/{ref}/database/query"
    req = urllib.request.Request(
        url,
        data=json.dumps({"query": sql}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Supabase Management API derrière Cloudflare bloque les UA Python
            # par défaut (erreur 1010). On déguise en client moderne.
            "User-Agent": "conx-migrate/0.1 (+https://github.com/anthropics/conx)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(body)
            except json.JSONDecodeError:
                return True, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {body[:1000]}"
    except urllib.error.URLError as exc:
        return False, f"URLError: {exc}"


def _exec_sql_via_psycopg(sql: str) -> tuple[bool, Any]:
    """Fallback : connexion psycopg directe via SUPABASE_DB_PASSWORD."""
    pw = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
    ref = _project_ref()
    if not pw or not ref:
        return False, "SUPABASE_DB_PASSWORD ou ref absent"
    try:
        import psycopg
    except ImportError:
        return False, "psycopg non installé (pip install 'psycopg[binary]')"
    dsn = f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres"
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        return True, "OK (psycopg)"
    except Exception as exc:  # pragma: no cover
        return False, f"psycopg error: {exc}"


def apply_sql(sql: str, label: str) -> None:
    """Applique du SQL via PAT API, fallback psycopg si PAT absent."""
    logger.info("Apply : %s (%d chars)", label, len(sql))
    ok, payload = _exec_sql_via_pat(sql)
    voie = "Management API (PAT)"
    if not ok and "absent" in str(payload):
        logger.warning("PAT absent → fallback psycopg.")
        ok, payload = _exec_sql_via_psycopg(sql)
        voie = "psycopg (DB password)"

    if not ok:
        logger.error("❌ Echec via %s : %s", voie, str(payload)[:500])
        raise SystemExit(2)

    # Affiche un résumé du payload (success cases)
    if isinstance(payload, list):
        logger.info("  ✅ %s : %d rows retournées.", voie, len(payload))
        if payload:
            logger.info("    sample : %s", str(payload[0])[:200])
    else:
        logger.info("  ✅ %s : %s", voie, str(payload)[:200])


def apply_file(path: Path) -> None:
    logger.info("Migration : %s (%d bytes)", path.name, path.stat().st_size)
    apply_sql(path.read_text(encoding="utf-8"), path.name)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="SELECT 1 connectivity check")
    parser.add_argument("--file", type=Path, help="Apply a specific migration file")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liste les schemas/tables actuellement présents",
    )
    args = parser.parse_args()

    ref = _project_ref()
    if not ref or ref.startswith("YOUR_"):
        logger.error("SUPABASE_PROJECT_REF ou SUPABASE_URL invalide dans .env.")
        return 3
    logger.info("Project ref : %s", ref)

    pat = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if pat:
        logger.info("Auth : Management API PAT (commence par %s…)", pat[:8])
    else:
        logger.warning("SUPABASE_ACCESS_TOKEN absent — fallback psycopg uniquement.")

    if args.check:
        apply_sql("SELECT 1 AS one, current_database() AS db, current_user AS usr;", "check")
        return 0

    if args.list:
        apply_sql(
            "SELECT schemaname, tablename FROM pg_tables "
            "WHERE schemaname IN ('app','public') ORDER BY 1,2;",
            "list",
        )
        return 0

    if args.file:
        apply_file(args.file)
        return 0

    files = sorted(MIG_DIR.glob("*.sql"))
    if not files:
        logger.error("Aucune migration dans %s", MIG_DIR)
        return 6
    for f in files:
        apply_file(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
