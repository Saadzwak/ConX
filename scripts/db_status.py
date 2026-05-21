"""ConX — rapport de statut sur public_data : counts par dpt, par classe DPE, sanity.

Usage :
    python scripts/db_status.py

Pas de modifications, lecture seule. Utile pour vérifier où en est l'ingestion.
"""

from __future__ import annotations

import os
import subprocess
import sys


def psql(sql: str, env: dict[str, str]) -> str:
    container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
    user = env.get("POSTGRES_LOCAL_USER", "conx")
    db = env.get("POSTGRES_LOCAL_DB", "conx")
    pw = env.get("POSTGRES_LOCAL_PASSWORD", "")
    result = subprocess.run(
        ["docker", "exec", "-e", f"PGPASSWORD={pw}", container, "psql", "-U", user, "-d", db, "-At", "-c", sql],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr[-200:]}"
    return result.stdout.strip()


def main() -> int:
    env = os.environ.copy()
    print("=" * 70)
    print("  ConX — État de public_data")
    print("=" * 70)

    # buildings par dpt
    print("\n📊 public_data.buildings — count par département :")
    rows = psql("SELECT dept, count(*) FROM public_data.buildings GROUP BY dept ORDER BY dept;", env)
    print(rows or "  (vide)")
    total = psql("SELECT count(*) FROM public_data.buildings;", env)
    print(f"  TOTAL : {total}")

    # DPE classes
    print("\n📊 public_data.buildings — distribution classes DPE :")
    rows = psql(
        "SELECT dpe_classe, count(*) FROM public_data.buildings "
        "WHERE dpe_classe IS NOT NULL GROUP BY dpe_classe ORDER BY dpe_classe;",
        env,
    )
    print(rows or "  (aucun DPE)")

    # Type proprio
    print("\n📊 public_data.buildings — distribution type_proprietaire :")
    rows = psql(
        "SELECT type_proprietaire, count(*) FROM public_data.buildings "
        "GROUP BY type_proprietaire ORDER BY count(*) DESC;",
        env,
    )
    print(rows or "  (vide)")

    # Monuments Historiques
    print("\n📊 public_data.buildings — Monuments Historiques :")
    rows = psql(
        "SELECT monument_historique, count(*) FROM public_data.buildings GROUP BY monument_historique;",
        env,
    )
    print(rows or "  (vide)")

    # Sanity
    print("\n🔍 Sanity checks :")
    invalid = psql(
        "SELECT count(*) FROM public_data.buildings WHERE NOT ST_IsValid(geom);", env
    )
    print(f"  géométries invalides : {invalid}")

    srid = psql(
        "SELECT DISTINCT ST_SRID(geom) FROM public_data.buildings LIMIT 1;", env
    )
    print(f"  SRID                  : {srid}")

    bad_years = psql(
        "SELECT count(*) FROM public_data.buildings "
        "WHERE annee_constr IS NOT NULL AND (annee_constr<1800 OR annee_constr>2030);",
        env,
    )
    print(f"  années hors borne     : {bad_years}")

    # DPE détaillé
    print("\n📊 public_data.dpe — count par type :")
    rows = psql(
        "SELECT type_dpe, count(*) FROM public_data.dpe GROUP BY type_dpe ORDER BY type_dpe;",
        env,
    )
    print(rows or "  (aucun DPE)")
    dpe_total = psql("SELECT count(*) FROM public_data.dpe;", env)
    print(f"  TOTAL DPE détaillés   : {dpe_total}")

    # Topo roads (J4)
    print("\n📊 public_data.topo_roads — count par dpt :")
    rows = psql(
        "SELECT dept, count(*) FROM public_data.topo_roads GROUP BY dept ORDER BY dept;",
        env,
    )
    print(rows or "  (vide — J4 non lancé ou bdtopo_urls.txt à compléter)")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
