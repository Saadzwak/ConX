"""ConX — inspection détaillée du schéma BDNB restauré dans postgres_local.

Liste les tables, leur nombre de lignes estimé, et les colonnes clés pour adapter
la consolidation public_data.buildings au schéma réel observé.

Usage :
    python scripts/inspect_bdnb_schema.py 02
    python scripts/inspect_bdnb_schema.py --all
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def get_pg_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PGHOST", env.get("POSTGRES_LOCAL_HOST", "localhost"))
    env.setdefault("PGPORT", env.get("POSTGRES_LOCAL_PORT_HOST", "5433"))
    env.setdefault("PGUSER", env.get("POSTGRES_LOCAL_USER", "conx"))
    env.setdefault("PGPASSWORD", env.get("POSTGRES_LOCAL_PASSWORD", ""))
    env.setdefault("PGDATABASE", env.get("POSTGRES_LOCAL_DB", "conx"))
    # Bypass docker if hostname is docker service name and PG client local n'a pas accès :
    if env["PGHOST"] in ("postgres_local", "conx_postgres"):
        env["PGHOST"] = "localhost"
        env["PGPORT"] = "5433"
    return env


def run_psql(sql: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["psql", "-At", "-F", "|", "-c", sql],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def list_tables(schema: str, env: dict[str, str]) -> list[tuple[str, str, int]]:
    sql = f"""
    SELECT c.relname, c.relkind, c.reltuples::bigint
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = '{schema}'
      AND c.relkind IN ('r','v','m','p')
    ORDER BY c.reltuples DESC, c.relname;
    """
    rows: list[tuple[str, str, int]] = []
    for line in run_psql(sql, env).strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], int(parts[2])))
    return rows


def list_columns(schema: str, table: str, env: dict[str, str]) -> list[tuple[str, str]]:
    sql = f"""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = '{schema}' AND table_name = '{table}'
    ORDER BY ordinal_position;
    """
    rows: list[tuple[str, str]] = []
    for line in run_psql(sql, env).strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def inspect_dept(dept: str, env: dict[str, str]) -> None:
    schema = f"bdnb_2025_07_a_open_data_dep{dept}"
    print(f"\n{'═' * 80}")
    print(f"  Inspection schéma : {schema}")
    print(f"{'═' * 80}\n")

    tables = list_tables(schema, env)
    if not tables:
        print(f"⚠️  Aucun objet dans {schema} — le restore est-il fini ?")
        return

    # Affichage compact
    kind_label = {"r": "table", "v": "view", "m": "matview", "p": "partition"}
    print(f"{len(tables)} objets trouvés (tri par nb_rows desc) :\n")
    for name, kind, est_rows in tables:
        print(f"  {kind_label.get(kind, kind):8s} {name:60s} ~{est_rows:>12,} rows")

    # Détail des colonnes pour les tables stratégiques (consolidation buildings)
    strategic = [
        "batiment_groupe",
        "batiment_groupe_complet",
        "batiment_groupe_ffo_bat",
        "batiment_groupe_bdtopo_bat",
        "batiment_groupe_dpe_representatif_logement",
        "batiment_groupe_dpe_statistique_logement",
        "batiment_groupe_urbanisme",
        "batiment_groupe_proprietaire_simplifie",
        "batiment_groupe_rnc",
        "rel_batiment_groupe_proprietaire_siren",
    ]
    table_names = {t[0] for t in tables}
    for t in strategic:
        if t not in table_names:
            print(f"\n  -- Table {t} : ABSENTE du schéma --")
            continue
        cols = list_columns(schema, t, env)
        print(f"\n  Colonnes de {t} ({len(cols)} colonnes) :")
        for col_name, col_type in cols[:50]:
            print(f"    - {col_name:50s} {col_type}")
        if len(cols) > 50:
            print(f"    ... +{len(cols) - 50} autres")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dept", nargs="?", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    env = get_pg_env()
    depts = ["02", "59", "60", "62", "80"] if args.all else [args.dept or "02"]
    for d in depts:
        inspect_dept(d, env)
    return 0


if __name__ == "__main__":
    sys.exit(main())
