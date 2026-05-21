"""ConX — ingestion des pgdumps BDNB par département dans postgres_local.

Pipeline :
1. Décompresse le ZIP de chaque département dans data/raw/bdnb/<dept>/extracted/
2. Identifie le fichier dump (format custom pg_restore ou SQL plain)
3. Restore dans un schéma dédié `bdnb_<dept>` du postgres_local
4. Inspecte le schéma réel et logue la liste des tables (pour adaptation)
5. (à compléter après inspection) Insère dans public_data.buildings la projection consolidée

Hypothèses (confirmées après restore du dpt 02) :
- Format : SQL plain (pas pg_restore custom). Le SQL contient ses CREATE SCHEMA.
- Schéma cible : bdnb_2025_07_a_open_data_dep<dept>.
- Tables clés : batiment_groupe, batiment_groupe_ffo_bat, batiment_groupe_bdtopo_bat,
  batiment_groupe_dpe_representatif_logement, batiment_groupe_urbanisme,
  batiment_groupe_proprietaire_simplifie (à confirmer).

Usage :
    python scripts/ingest_bdnb.py                 # tous les dpts téléchargés
    python scripts/ingest_bdnb.py 02              # un seul département
    python scripts/ingest_bdnb.py --inspect-only  # restore + inspect, pas de consolidation

Cf. BUILD_LOG.md J2 pour les adaptations effectives faites après inspection.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import zipfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_bdnb")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "bdnb"
SQL_MIGRATIONS_DIR = ROOT / "scripts" / "sql" / "migrations"

DEFAULT_DEPTS = ["02", "59", "60", "62", "80"]


def get_pg_env() -> dict[str, str]:
    """Construit l'environnement PG* pour psql/pg_restore.

    Pour accès depuis l'hôte : utilise POSTGRES_LOCAL_PORT_HOST (5433 par défaut)
    car le service Docker mappe 5433 hôte → 5432 container.
    Si le code tourne depuis l'intérieur du container backend, POSTGRES_LOCAL_HOST=postgres_local
    et POSTGRES_LOCAL_PORT=5432.
    """
    env = os.environ.copy()
    host = env.get("POSTGRES_LOCAL_HOST", "localhost")
    # Si on est sur l'hôte (host = postgres_local ou conx_postgres = noms internes Docker), bascule sur localhost:5433
    if host in ("postgres_local", "conx_postgres"):
        host = "localhost"
        port = env.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    else:
        port = env.get("POSTGRES_LOCAL_PORT", "5432")
    env["PGHOST"] = host
    env["PGPORT"] = port
    env["PGUSER"] = env.get("POSTGRES_LOCAL_USER", "conx")
    env["PGPASSWORD"] = env.get("POSTGRES_LOCAL_PASSWORD", "")
    env["PGDATABASE"] = env.get("POSTGRES_LOCAL_DB", "conx")
    return env


def using_docker_exec() -> bool:
    """Vrai si on doit invoquer psql via 'docker exec' (pas de client PG sur l'hôte Windows)."""
    return os.environ.get("CONX_USE_DOCKER_EXEC", "1") == "1"


def psql_command(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    """Exécute psql, soit sur l'hôte (si client installé), soit via docker exec sur conx_postgres."""
    if using_docker_exec():
        container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
        cmd = [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={env['PGPASSWORD']}",
            container,
            "psql",
            "-U",
            env["PGUSER"],
            "-d",
            env["PGDATABASE"],
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)
    cmd = ["psql", *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def find_zip(dept: str) -> Path | None:
    dept_dir = RAW_DIR / dept
    if not dept_dir.exists():
        return None
    zips = sorted(dept_dir.glob("*.zip"))
    dones = {z.with_suffix(".zip.done") for z in zips}
    ready = [z for z in zips if z.with_suffix(".zip.done").exists()]
    if not ready and zips and any(d.exists() for d in dones):
        # tolère le marker .done à côté
        ready = zips
    return ready[0] if ready else (zips[0] if zips else None)


def extract_zip(zip_path: Path) -> Path:
    """Décompresse le ZIP dans <parent>/extracted/. Renvoie le chemin du dossier extrait."""
    target = zip_path.parent / "extracted"
    target.mkdir(parents=True, exist_ok=True)
    sentinel = target / ".extracted.done"
    if sentinel.exists():
        logger.info(f"Zip déjà extrait : {target}")
        return target

    logger.info(f"Extraction {zip_path} → {target}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    sentinel.touch()
    return target


def find_dump_file(extracted_dir: Path) -> Path:
    """Identifie le fichier de dump principal (.sql, .dump, ou format custom)."""
    candidates: list[Path] = []
    for ext in ("*.dump", "*.sql", "*.backup"):
        candidates.extend(extracted_dir.rglob(ext))
    if not candidates:
        raise FileNotFoundError(f"Aucun dump trouvé dans {extracted_dir}")
    # Trie par taille décroissante (le plus gros est typiquement le dump principal)
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    logger.info(
        f"Dump file détecté : {candidates[0]} ({candidates[0].stat().st_size / 1e9:.2f} GB)"
    )
    return candidates[0]


def is_pg_custom_format(dump: Path) -> bool:
    """Détecte un dump pg_restore format custom (commence par 'PGDMP')."""
    with dump.open("rb") as f:
        magic = f.read(5)
    return magic.startswith(b"PGDMP")


def restore_dump(dump: Path, dept: str, env: dict[str, str]) -> None:
    """Restore le dump dans postgres_local. Le SQL plain crée son propre schéma (bdnb_2025_07_a_open_data_dep<dept>).

    Pour les SQL plain volumineux (1+ GB), on copie le fichier dans le container via docker cp,
    puis on lance psql -f /tmp/... dans le container. Plus rapide et stable que stdin sur Windows.
    """
    schema = f"bdnb_2025_07_a_open_data_dep{dept}"

    # Skip si schéma déjà peuplé (idempotence)
    check_sql = (
        "SELECT count(*) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        f"WHERE n.nspname='{schema}' AND c.relkind='r';"
    )
    check = psql_command(["-At", "-c", check_sql], env)
    if (
        check.returncode == 0
        and check.stdout.strip().isdigit()
        and int(check.stdout.strip()) > 0
    ):
        logger.info(
            f"Schéma {schema} déjà peuplé ({check.stdout.strip()} tables) — restore skip."
        )
        return

    container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
    container_path = f"/tmp/bdnb_{dept}.sql"

    if is_pg_custom_format(dump):
        raise NotImplementedError(
            "Format pgdump custom détecté. Le pipeline supporte uniquement le SQL plain "
            "tel que livré par bdnb.io (millésime 2025-07.a). À étendre si nécessaire."
        )

    logger.info(
        f"Copie du dump {dump} ({dump.stat().st_size / 1e9:.2f} GB) dans le container..."
    )
    subprocess.run(
        ["docker", "cp", str(dump), f"{container}:{container_path}"], check=True
    )

    logger.info(f"Restore SQL plain dans {schema} (peut prendre 5-15 min selon dpt)...")
    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={env['PGPASSWORD']}",
        container,
        "psql",
        "-U",
        env["PGUSER"],
        "-d",
        env["PGDATABASE"],
        "-v",
        "ON_ERROR_STOP=0",  # warnings non bloquants (COMMENTS peuvent en générer)
        "-q",  # quiet
        "-f",
        container_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(
            f"psql exit {result.returncode} (warnings non-bloquants attendus)"
        )
        if result.stderr:
            stderr_tail = result.stderr[-2000:]
            logger.warning(f"stderr (last 2000 chars):\n{stderr_tail}")

    # Cleanup du fichier dans le container
    subprocess.run(
        ["docker", "exec", container, "rm", "-f", container_path], check=False
    )

    logger.info(f"Restore terminé pour {schema}")


def inspect_schema(schema: str, env: dict[str, str]) -> list[tuple[str, str, int]]:
    """Liste les tables du schéma + nb de lignes approximatif. Retourne [(name, type, est_rows)]."""
    query = f"""
    SELECT
        c.relname AS name,
        c.relkind AS kind,
        c.reltuples::bigint AS est_rows
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = '{schema}'
      AND c.relkind IN ('r','v','m','p')
    ORDER BY c.relname;
    """
    result = psql_command(["-At", "-F", "|", "-c", query], env)
    if result.returncode != 0:
        logger.error(f"inspect_schema failed: {result.stderr[-500:]}")
        return []
    rows: list[tuple[str, str, int]] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], int(parts[2])))
    return rows


def apply_migrations(env: dict[str, str]) -> None:
    """Applique les fichiers SQL de scripts/sql/migrations/ dans l'ordre (.sql uniquement, pas .template)."""
    migrations = sorted(
        p for p in SQL_MIGRATIONS_DIR.glob("*.sql") if not p.name.endswith(".template")
    )
    container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
    for m in migrations:
        logger.info(f"Migration {m.name}")
        if using_docker_exec():
            # Copie + exec dans le container
            target = f"/tmp/{m.name}"
            subprocess.run(
                ["docker", "cp", str(m), f"{container}:{target}"], check=True
            )
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-e",
                    f"PGPASSWORD={env['PGPASSWORD']}",
                    container,
                    "psql",
                    "-U",
                    env["PGUSER"],
                    "-d",
                    env["PGDATABASE"],
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    target,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            subprocess.run(
                ["docker", "exec", container, "rm", "-f", target], check=False
            )
            if result.returncode != 0:
                logger.error(f"Migration {m.name} failed: {result.stderr[-1000:]}")
                raise RuntimeError(f"Migration {m.name} failed")
        else:
            subprocess.run(
                ["psql", "-v", "ON_ERROR_STOP=1", "-f", str(m)],
                env=env,
                check=True,
            )


def ingest_department(dept: str, inspect_only: bool = False) -> bool:
    """Pipeline complet pour un département. Renvoie True si succès."""
    zip_path = find_zip(dept)
    if not zip_path:
        logger.error(f"Aucun ZIP trouvé pour le département {dept}")
        return False

    extracted = extract_zip(zip_path)
    # Le SQL plain BDNB est dans extracted/pgdump/bdnb.sql
    pgdump_dir = extracted / "pgdump"
    if pgdump_dir.exists():
        dump = pgdump_dir / "bdnb.sql"
        if not dump.exists():
            dump = find_dump_file(pgdump_dir)
    else:
        dump = find_dump_file(extracted)

    schema = f"bdnb_2025_07_a_open_data_dep{dept}"
    env = get_pg_env()

    restore_dump(dump, dept, env)

    tables = inspect_schema(schema, env)
    logger.info(f"--- Schéma {schema} : {len(tables)} tables/vues ---")
    for name, kind, est_rows in tables[:30]:
        kind_label = {"r": "table", "v": "view", "m": "matview", "p": "partition"}.get(
            kind, kind
        )
        logger.info(f"  {kind_label:8s} {name:50s} ~{est_rows:>10,} rows")
    if len(tables) > 30:
        logger.info(f"  ... +{len(tables) - 30} autres")

    if inspect_only:
        logger.info("Mode --inspect-only : pas de consolidation.")
        return True

    # Application des migrations consolidées (création buildings + fonctions helpers)
    apply_migrations(env)

    # Consolidation : INSERT depuis bdnb_<dept>.* vers public_data.buildings
    consolidate_dept(dept, env)

    return True


def _apply_template(template_name: str, dept: str, env: dict[str, str]) -> None:
    """Instancie un template SQL par dépt (remplace {DEPT}) et l'exécute."""
    template_path = SQL_MIGRATIONS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(template_path)

    sql = template_path.read_text(encoding="utf-8").replace("{DEPT}", dept)
    stem = template_path.stem.replace(".sql", "")
    tmp_path = SQL_MIGRATIONS_DIR.parent / "tmp" / f"{stem}_dep{dept}.sql"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(sql, encoding="utf-8")

    if using_docker_exec():
        container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
        target = f"/tmp/{tmp_path.name}"
        subprocess.run(
            ["docker", "cp", str(tmp_path), f"{container}:{target}"], check=True
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                f"PGPASSWORD={env['PGPASSWORD']}",
                container,
                "psql",
                "-U",
                env["PGUSER"],
                "-d",
                env["PGDATABASE"],
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                target,
            ],
            capture_output=True,
            text=True,
        )
        subprocess.run(["docker", "exec", container, "rm", "-f", target], check=False)
    else:
        result = subprocess.run(
            ["psql", "-v", "ON_ERROR_STOP=1", "-f", str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        logger.error(f"Template {template_name} échec pour dpt {dept} :")
        logger.error(result.stderr[-2000:])
        raise RuntimeError(f"Template {template_name} failed for dept {dept}")


def consolidate_dept(dept: str, env: dict[str, str]) -> None:
    """Applique les templates SQL paramétrés pour consolider un dpt :
    - 003 : public_data.buildings
    - 005 : public_data.dpe (DPE détaillé pour ML J5 + Mode Projet)
    """
    logger.info(
        f"Consolidation public_data.buildings depuis bdnb_2025_07_a_open_data_dep{dept}"
    )
    _apply_template("003_consolidate_buildings_dept.sql.template", dept, env)
    cnt_b = psql_command(
        [
            "-At",
            "-c",
            f"SELECT count(*) FROM public_data.buildings WHERE dept = '{dept}';",
        ],
        env,
    )
    logger.info(
        f"✅ Dept {dept} buildings : {cnt_b.stdout.strip() if cnt_b.returncode == 0 else '?'} lignes"
    )

    logger.info(
        f"Consolidation public_data.dpe depuis bdnb_2025_07_a_open_data_dep{dept}"
    )
    _apply_template("005_consolidate_dpe_dept.sql.template", dept, env)
    cnt_d = psql_command(
        ["-At", "-c", f"SELECT count(*) FROM public_data.dpe WHERE dept = '{dept}';"],
        env,
    )
    logger.info(
        f"✅ Dept {dept} dpe      : {cnt_d.stdout.strip() if cnt_d.returncode == 0 else '?'} lignes"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestion BDNB par département")
    parser.add_argument(
        "dept",
        nargs="?",
        default=None,
        help="Code dpt (02/59/60/62/80) ou rien pour tous",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Restore + inspect, pas de consolidation",
    )
    args = parser.parse_args()

    depts = [args.dept] if args.dept else DEFAULT_DEPTS
    failed: list[str] = []

    for d in depts:
        logger.info(f"════════ Département {d} ════════")
        try:
            ok = ingest_department(d, inspect_only=args.inspect_only)
            if not ok:
                failed.append(d)
        except Exception as e:
            logger.exception(f"Échec ingestion {d} : {e}")
            failed.append(d)

    if failed:
        logger.error(f"Départements en échec : {failed}")
        return 1
    logger.info("Tous les départements ingérés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
