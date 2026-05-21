"""ConX — calcul PostGIS du sous-indicateur S_faisa.acces_chantier post-ingestion BD TOPO.

Formule SCORING.md §Composante 2 acces_chantier :
- 1.0 si rue ≥ 4 m de large à moins de 10 m du bâtiment
- 0.5 si rue 2-4 m
- 0.0 si aucune voie carrossable à < 10 m

Stratégie :
1. Pour chaque bâtiment d'un dpt, on cherche dans public_data.topo_roads la voie la plus large
   à moins de 10 m du centroïde (PostGIS ST_DWithin + ORDER BY largeur_m DESC LIMIT 1).
2. On UPSERT dans public_data.building_acces_chantier.
3. Une fois cette table peuplée, on RE-LANCE `compute_building_scores.py --all` qui pourra
   lire cette table et utiliser la vraie valeur acces_chantier (cf. compute.py TODO).

Usage :
    python scripts/compute_acces_chantier.py 02
    python scripts/compute_acces_chantier.py --all
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

import psycopg

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compute_acces_chantier")

DEFAULT_DEPTS = ["02", "59", "60", "62", "80"]


def get_conn_str() -> str:
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


# SQL : pour chaque bâtiment du dpt, trouve la voie la plus large à <=10 m. Si rien à 10m → 0.
# Buffer search optimisé avec index GIST + LIMIT 1.
COMPUTE_DEPT_SQL = """
INSERT INTO public_data.building_acces_chantier
    (building_id, acces_chantier, nearest_largeur_m, nearest_distance_m, computed_at)
SELECT
    b.building_id,
    CASE
        WHEN nearest.largeur_m IS NULL THEN 0.0      -- aucune voie à <10 m
        WHEN nearest.largeur_m >= 4 THEN 1.0
        WHEN nearest.largeur_m >= 2 THEN 0.5
        ELSE 0.0                                      -- voie < 2 m (impasse étroite)
    END AS acces_chantier,
    nearest.largeur_m,
    nearest.distance_m,
    now()
FROM public_data.buildings b
LEFT JOIN LATERAL (
    SELECT r.largeur_m, ST_Distance(b.geom, r.geom) AS distance_m
    FROM public_data.topo_roads r
    WHERE r.dept = %s
      AND ST_DWithin(b.geom, r.geom, 10)
    ORDER BY r.largeur_m DESC NULLS LAST
    LIMIT 1
) nearest ON true
WHERE b.dept = %s
ON CONFLICT (building_id) DO UPDATE SET
    acces_chantier = EXCLUDED.acces_chantier,
    nearest_largeur_m = EXCLUDED.nearest_largeur_m,
    nearest_distance_m = EXCLUDED.nearest_distance_m,
    computed_at = now();
"""


def apply_migration_009(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public_data' AND table_name='building_acces_chantier';
        """)
        if cur.fetchone():
            return
    from pathlib import Path

    sql_path = (
        Path(__file__).parent
        / "sql"
        / "migrations"
        / "009_update_s_faisa_acces_chantier.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Migration 009 appliquée.")


def compute_dept(conn: psycopg.Connection, dept: str) -> int:
    # Vérifie qu'il y a des routes pour ce dpt
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM public_data.topo_roads WHERE dept = %s;", (dept,)
        )
        n_roads = cur.fetchone()[0]
    if n_roads == 0:
        logger.warning(f"Dpt {dept} : 0 routes dans topo_roads — skip.")
        return 0

    logger.info(f"Dpt {dept} : {n_roads} routes BD TOPO → calcul acces_chantier ...")
    start = time.time()
    with conn.cursor() as cur:
        cur.execute(COMPUTE_DEPT_SQL, (dept, dept))
        n_buildings = cur.rowcount
    conn.commit()
    elapsed = time.time() - start
    logger.info(
        f"✅ Dpt {dept} : {n_buildings} bâtiments couverts en {elapsed:.1f}s "
        f"({n_buildings / elapsed:.0f}/s)"
    )
    return n_buildings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dept", nargs="?", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    conn_str = get_conn_str()
    with psycopg.connect(conn_str) as conn:
        apply_migration_009(conn)
        depts = DEFAULT_DEPTS if (args.all or args.dept is None) else [args.dept]
        total = 0
        for d in depts:
            total += compute_dept(conn, d)
        logger.info(f"Total bâtiments avec acces_chantier calculé : {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
