"""ConX — ingestion BD TOPO `TRONCON_DE_ROUTE` dans public_data.topo_roads.

Pipeline :
1. Décompresse l'archive BD TOPO du département (7z ou zip).
2. Localise le GeoPackage (.gpkg) — généralement dans `BDTOPO_*/TRANSPORT/...`.
3. Extrait la couche `troncon_de_route` via ogr2ogr (dans le container postgis si pas dispo localement)
   OU via psycopg + ogr (à raffiner selon environnement).
4. Insert dans public_data.topo_roads avec dept.

Usage :
    python scripts/ingest_bdtopo_roads.py 02
    python scripts/ingest_bdtopo_roads.py --all

PRÉREQUIS : avoir téléchargé les GPKG via `bash scripts/download_bdtopo.sh`.
URLs à compléter manuellement dans scripts/bdtopo_urls.txt (cf. BUILD_LOG.md J4).
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("ingest_bdtopo_roads")

ROOT = Path(__file__).resolve().parent.parent
BDTOPO_DIR = ROOT / "data" / "raw" / "bdtopo"
DEFAULT_DEPTS = ["02", "59", "60", "62", "80"]


def find_gpkg(dept: str) -> Path | None:
    """Cherche le fichier .gpkg pour un dpt après décompression."""
    dept_dir = BDTOPO_DIR / dept
    if not dept_dir.exists():
        return None
    candidates = list(dept_dir.rglob("*.gpkg"))
    # Préfère le GPKG le plus gros (souvent BDTOPO toute thème)
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0] if candidates else None


def ingest_dept(dept: str) -> bool:
    """Lance ogr2ogr pour copier la couche troncon_de_route en PostGIS."""
    gpkg = find_gpkg(dept)
    if not gpkg:
        logger.warning(
            f"Dpt {dept} : aucun .gpkg trouvé dans {BDTOPO_DIR / dept}. "
            "Compléter scripts/bdtopo_urls.txt puis lancer bash scripts/download_bdtopo.sh."
        )
        return False

    logger.info(f"Dpt {dept} : utilisation de {gpkg}")

    # ogr2ogr tourne depuis un container gdal léger avec accès au réseau Docker (conx_net).
    # Postgis/postgis:16-3.4 n'embarque pas ogr2ogr — d'où le container séparé.
    # Note : ogr2ogr utilise le hostname interne 'conx_postgres' (réseau Docker), port 5432.
    pg_user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pg_pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    pg_db = os.environ.get("POSTGRES_LOCAL_DB", "conx")

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "conx_net",
        "-v",
        f"{gpkg.parent}:/data:ro",
        "ghcr.io/osgeo/gdal:alpine-small-latest",
        "ogr2ogr",
        "-f",
        "PostgreSQL",
        f"PG:host=conx_postgres port=5432 dbname={pg_db} user={pg_user} password={pg_pw}",
        f"/data/{gpkg.name}",
        "troncon_de_route",
        "-nln",
        "public_data.topo_roads_staging",
        "-nlt",
        "LINESTRING",
        "-t_srs",
        "EPSG:2154",
        "-overwrite",
        "-progress",
    ]
    logger.info(f"ogr2ogr cmd : {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"ogr2ogr failed for dept {dept}:\n{result.stderr[-1000:]}")
        return False

    # Move staging → final table avec mapping de colonnes
    # (les noms exacts des colonnes dépendent de l'édition BD TOPO ; à valider post-ingestion réelle).
    map_sql = f"""
    INSERT INTO public_data.topo_roads (cleabs, dept, nature, importance, largeur_m, nombre_de_voies, sens, nom, geom)
    SELECT
        cleabs,
        '{dept}',
        nature,
        importance,
        largeur::numeric,
        nombre_de_voies::int,
        sens,
        nom_1_droite,
        ST_LineMerge(wkb_geometry)::geometry(LineString, 2154)
    FROM public_data.topo_roads_staging
    WHERE wkb_geometry IS NOT NULL;
    DROP TABLE IF EXISTS public_data.topo_roads_staging;
    """
    container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
    map_path = ROOT / "scripts" / "tmp" / f"006_map_dep{dept}.sql"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(map_sql, encoding="utf-8")
    subprocess.run(["docker", "cp", str(map_path), f"{container}:/tmp/006.sql"], check=True)
    r = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={pg_pw}",
            container,
            "psql",
            "-U",
            pg_user,
            "-d",
            pg_db,
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            "/tmp/006.sql",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        logger.error(f"Staging → final failed for dept {dept}:\n{r.stderr[-1000:]}")
        return False

    logger.info(f"✅ Dpt {dept} : routes ingérées dans public_data.topo_roads")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dept", nargs="?", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    depts = DEFAULT_DEPTS if args.all else [args.dept or "02"]
    failed: list[str] = []
    for d in depts:
        if not ingest_dept(d):
            failed.append(d)
    if failed:
        logger.error(f"Departements en echec : {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
