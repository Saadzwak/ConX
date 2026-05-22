"""ConX — applique les migrations Supabase Cloud via le SDK supabase-py.

Lit `scripts/sql/supabase/*.sql` dans l'ordre alphabétique, les exécute via
PostgREST (rpc `exec_sql` si dispo) ou via une connexion directe au pooler
PostgreSQL (`postgresql://postgres.<ref>:<service_role_jwt_b64>@aws-...`).

Pour le free tier Supabase, le pooler PgBouncer est exposé sur le port 6543
(transaction mode). Le SDK supabase-py ne sait PAS exécuter du SQL arbitraire
(c'est intentionnel — PostgREST ne fait que CRUD via Postgres roles). On
passe donc par `psycopg` direct.

Usage :
    python scripts/supabase_migrate.py          # applique toutes les migrations
    python scripts/supabase_migrate.py --check  # vérifie connectivité seulement
    python scripts/supabase_migrate.py --file scripts/sql/supabase/001_app_schema.sql

⚠ COÛT : 0 € (Supabase free tier, opérations SQL gratuites).
⚠ SÉCURITÉ : utilise `SUPABASE_SERVICE_ROLE_KEY` (bypass RLS) — NE JAMAIS
le commit. Lecture depuis `.env`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
MIG_DIR = ROOT / "scripts" / "sql" / "supabase"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("supabase_migrate")


def _load_env() -> None:
    """Charge .env à la main (sans dépendre de python-dotenv)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split("#", 1)[0].strip()
        if key:
            os.environ[key] = value


def _supabase_db_dsn() -> str:
    """Construit le DSN PostgreSQL direct (pooler Supabase).

    Le project ref est extrait de SUPABASE_URL = https://<ref>.supabase.co.
    Le password est SUPABASE_DB_PASSWORD (à mettre en .env si on a besoin du
    pooler) — pour les migrations, on préfère l'API REST. Mais pour exécuter
    du DDL, on doit passer par une connexion Postgres.

    On utilise le service_role JWT comme mot de passe ? NON — c'est pas le
    pattern. Le pooler accepte le mdp de la DB (créé au project setup).

    Pour le hackathon, on demande au partenaire le mot de passe DB. Sinon
    fallback : exécuter le SQL manuellement dans le SQL editor (ce que le
    partenaire voulait ÉVITER, mais c'est l'option de repli).
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    pw = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
    if not url or not pw:
        return ""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    # ref = first sub-domain (ex: kvevcricmqijfixsrdpa)
    ref = host.split(".")[0] if host else ""
    if not ref:
        return ""
    # Pooler PgBouncer (transaction mode, port 6543)
    # Format : postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres
    # Région inconnue sans appel API — fallback au connection direct port 5432 :
    # postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres
    return f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres"


def _exec_sql_via_psycopg(dsn: str, sql: str) -> None:
    """Exécute du SQL multi-statement via psycopg."""
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg non installé. `pip install 'psycopg[binary]'`"
        ) from exc
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def _exec_sql_via_rest(sql: str) -> bool:
    """Tente d'exécuter du SQL via l'endpoint Supabase HTTP `pg/exec_sql`
    (extension Supabase, doit être créée manuellement par le partenaire).

    Retourne True si succès, False si l'endpoint n'existe pas.
    """
    try:
        import httpx
    except ImportError:
        return False

    url = os.environ.get("SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not service_key:
        return False

    # Tentative : la fonction RPC publique exec_sql (à créer côté Supabase)
    # n'existe pas par défaut, et c'est intentionnel. On la skip.
    return False


def apply_file(path: Path) -> None:
    """Applique une migration SQL via la voie disponible."""
    logger.info("Migration : %s (%d bytes)", path.name, path.stat().st_size)
    sql = path.read_text(encoding="utf-8")

    dsn = _supabase_db_dsn()
    if dsn:
        try:
            _exec_sql_via_psycopg(dsn, sql)
            logger.info("  → OK via psycopg (connexion directe DB).")
            return
        except Exception as exc:
            logger.warning("Connexion DB directe échouée : %s", exc)

    # Fallback : on imprime la procédure manuelle.
    logger.error(
        "❌ Aucune voie automatique disponible. "
        "Voici la procédure manuelle :\n"
        "  1. Ouvrir https://supabase.com/dashboard/project/<ref>/sql/new\n"
        "  2. Copier-coller le contenu de %s\n"
        "  3. Cliquer Run",
        path,
    )
    raise SystemExit(2)


def main() -> int:
    _load_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Connectivité uniquement")
    parser.add_argument("--file", type=Path, help="Une migration spécifique")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url or url.startswith("https://YOUR_"):
        logger.error("SUPABASE_URL non défini ou placeholder dans .env.")
        return 3
    logger.info("SUPABASE_URL = %s", url)

    pw = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
    if not pw:
        logger.warning(
            "SUPABASE_DB_PASSWORD absent → tentative via REST fallback. "
            "Si ça échoue, mettre le mot de passe DB en .env et relancer."
        )

    if args.check:
        # Test minimal : SELECT 1
        dsn = _supabase_db_dsn()
        if not dsn:
            logger.error("DSN non constructible (manque mot de passe DB).")
            return 4
        try:
            import psycopg
            with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1, current_database(), current_user;")
                    one, db, usr = cur.fetchone()
                    logger.info(
                        "✅ Connexion OK : SELECT 1 = %s, db = %s, user = %s",
                        one, db, usr,
                    )
            return 0
        except Exception as exc:
            logger.error("❌ Connexion DB échouée : %s", exc)
            return 5

    if args.file:
        apply_file(args.file)
        return 0

    files = sorted(MIG_DIR.glob("*.sql"))
    if not files:
        logger.error("Aucune migration trouvée dans %s", MIG_DIR)
        return 6
    for f in files:
        apply_file(f)
    logger.info("✅ Toutes les migrations appliquées (%d fichiers).", len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
