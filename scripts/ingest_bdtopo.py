"""ConX — ingestion BD TOPO IGN (couches TRONCON_DE_ROUTE + BATIMENT) par département HDF.

Pipeline :
1. Décompresse l'archive 7z BD TOPO du département dans data/raw/bdtopo/<dept>/extracted/
2. Localise le GeoPackage `BDT_*.gpkg` (un seul GPKG par dpt en "TOUSTHEMES")
3. Extrait UNIQUEMENT les couches `troncon_de_route` et `batiment` via ogr2ogr (container GDAL)
4. Mappe les colonnes vers public_data.topo_roads et public_data.topo_buildings

Migrations appliquées : 006 (topo_roads), 007 (topo_buildings).

Usage :
    python scripts/ingest_bdtopo.py 02
    python scripts/ingest_bdtopo.py --all

Prérequis :
- 7z disponible sur l'hôte OU py7zr (`pip install py7zr`). Fallback py7zr automatique.
- Variable d'env BDTOPO_MILLESIME (par défaut '3-5_2025-12-15').
- Container conx_postgres lancé, réseau conx_net.

Couches BD TOPO ingérées (D-008) :
- troncon_de_route → public_data.topo_roads (sous-indicateur S_faisa.acces_chantier)
- batiment        → public_data.topo_buildings (fallback 3D + cross-val hauteur BDNB)

Autres couches BD TOPO non utilisées au MVP (hydrographie, administratif, etc.).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_bdtopo")

ROOT = Path(__file__).resolve().parent.parent
BDTOPO_DIR = ROOT / "data" / "raw" / "bdtopo"
DEFAULT_DEPTS = ["02", "59", "60", "62", "80"]
DEFAULT_MILLESIME = "3-5_2025-12-15"

GDAL_IMAGE = "ghcr.io/osgeo/gdal:alpine-small-latest"
PG_NETWORK = "conx_net"
PG_INTERNAL_HOST = "conx_postgres"
PG_INTERNAL_PORT = "5432"


def find_archive(dept: str) -> Path | None:
    """Trouve l'archive 7z téléchargée pour un dpt."""
    dept_dir = BDTOPO_DIR / dept
    if not dept_dir.exists():
        return None
    candidates = list(dept_dir.glob("*.7z"))
    return candidates[0] if candidates else None


def extract_archive(archive: Path, dept: str) -> Path:
    """Décompresse l'archive 7z dans extracted/. Idempotent via .extracted.done.

    Essaie d'abord la commande `7z` système, sinon bascule sur py7zr.
    """
    target = archive.parent / "extracted"
    sentinel = target / ".extracted.done"
    if sentinel.exists():
        logger.info(f"Dpt {dept} : déjà décompressé ({target})")
        return target

    target.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Dpt {dept} : décompression de {archive.name} ({archive.stat().st_size / 1e9:.2f} GB) ..."
    )

    if shutil.which("7z"):
        result = subprocess.run(
            ["7z", "x", str(archive), f"-o{target}", "-y", "-bsp0", "-bso0"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"7z extraction failed: {result.stderr[-500:]}")
    else:
        try:
            import py7zr  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Ni `7z` ni `py7zr` disponibles. Installer p7zip-full (Linux) "
                "ou `pip install py7zr`."
            ) from e
        with py7zr.SevenZipFile(str(archive), mode="r") as z:
            z.extractall(path=str(target))

    sentinel.touch()
    logger.info(f"Dpt {dept} : décompression OK")
    return target


def find_gpkg(extracted_dir: Path) -> Path | None:
    """Localise le .gpkg principal après décompression (préfère le plus gros)."""
    candidates = list(extracted_dir.rglob("*.gpkg"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def ogr2ogr_layer(
    gpkg: Path,
    layer_name: str,
    staging_table: str,
    pg_user: str,
    pg_pw: str,
    pg_db: str,
    nlt: str | None = None,
) -> tuple[bool, str]:
    """Lance ogr2ogr pour extraire UNE couche dans une staging table."""
    pg_conn = (
        f"PG:host={PG_INTERNAL_HOST} port={PG_INTERNAL_PORT} "
        f"dbname={pg_db} user={pg_user} password={pg_pw}"
    )
    # Convertir le chemin Windows vers format Unix (avec / au lieu de \) pour le mount Docker
    # Le mount monte le DOSSIER parent du gpkg, on accède par /data/<filename>
    gpkg_parent = str(gpkg.parent).replace("\\", "/")
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        PG_NETWORK,
        "-v",
        f"{gpkg_parent}:/data:ro",
        GDAL_IMAGE,
        "ogr2ogr",
        "-f",
        "PostgreSQL",
        pg_conn,
        f"/data/{gpkg.name}",
        layer_name,
        "-nln",
        staging_table,
        "-t_srs",
        "EPSG:2154",
        "-overwrite",
        "-progress",
    ]
    if nlt:
        cmd.extend(["-nlt", nlt])
    logger.info(f"ogr2ogr layer={layer_name} → {staging_table}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr[-1500:]
    return True, ""


def psql_file(sql: str, env: dict[str, str], label: str) -> bool:
    """Exécute un fichier SQL via docker exec sur conx_postgres."""
    container = env.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
    pg_user = env.get("POSTGRES_LOCAL_USER", "conx")
    pg_pw = env.get("POSTGRES_LOCAL_PASSWORD", "")
    pg_db = env.get("POSTGRES_LOCAL_DB", "conx")

    map_path = ROOT / "scripts" / "tmp" / f"bdtopo_{label}.sql"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(sql, encoding="utf-8")
    subprocess.run(
        ["docker", "cp", str(map_path), f"{container}:/tmp/{label}.sql"], check=True
    )
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
            f"/tmp/{label}.sql",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        logger.error(f"psql {label} failed:\n{r.stderr[-1500:]}")
        return False
    return True


def consolidate_roads(dept: str, env: dict[str, str], millesime: str) -> bool:
    """Migre topo_roads_staging → public_data.topo_roads avec mapping de colonnes BD TOPO v3-5.

    Schéma source BD TOPO 3-5 (validé empiriquement sur dpt 60, 2026-05-21) :
    - largeur_de_chaussee (numeric, en mètres) ; PAS `largeur` ni `largeur_m`.
    - sens_de_circulation (text) ; PAS `sens`.
    - nom_collaboratif_droite / nom_voie_ban_droite (text) ; PAS `nom_1_droite`.
    - geometrie (geometry 2154) ; PAS `wkb_geometry`.
    """
    sql = f"""
    DELETE FROM public_data.topo_roads WHERE dept = '{dept}';
    INSERT INTO public_data.topo_roads
        (cleabs, dept, nature, importance, largeur_m, nombre_de_voies, sens, nom, geom, bdtopo_millesime)
    SELECT
        cleabs,
        '{dept}',
        nature,
        importance,
        largeur_de_chaussee::numeric,
        nombre_de_voies::int,
        sens_de_circulation,
        COALESCE(nom_voie_ban_droite, nom_collaboratif_droite),
        ST_LineMerge(geometrie)::geometry(LineString, 2154),
        '{millesime}'
    FROM public_data.topo_roads_staging
    WHERE geometrie IS NOT NULL;
    DROP TABLE IF EXISTS public_data.topo_roads_staging;
    """
    return psql_file(sql, env, f"006_map_roads_dep{dept}")


def consolidate_buildings(dept: str, env: dict[str, str], millesime: str) -> bool:
    """Migre topo_buildings_staging → public_data.topo_buildings (BD TOPO v3-5 columns)."""
    sql = f"""
    DELETE FROM public_data.topo_buildings WHERE dept = '{dept}';
    INSERT INTO public_data.topo_buildings
        (cleabs, dept, nature, usage_1, usage_2,
         nombre_de_logements, nombre_d_etages,
         materiaux_des_murs, materiaux_de_la_toiture,
         hauteur, altitude_minimale_sol, altitude_maximale_sol,
         altitude_minimale_toit, altitude_maximale_toit, geom, bdtopo_millesime)
    SELECT
        cleabs,
        '{dept}',
        nature,
        usage_1,
        usage_2,
        nombre_de_logements::int,
        nombre_d_etages::int,
        materiaux_des_murs,
        materiaux_de_la_toiture,
        hauteur::numeric,
        altitude_minimale_sol::numeric,
        altitude_maximale_sol::numeric,
        altitude_minimale_toit::numeric,
        altitude_maximale_toit::numeric,
        ST_Multi(geometrie)::geometry(MultiPolygon, 2154),
        '{millesime}'
    FROM public_data.topo_buildings_staging
    WHERE geometrie IS NOT NULL;
    DROP TABLE IF EXISTS public_data.topo_buildings_staging;
    """
    return psql_file(sql, env, f"007_map_buildings_dep{dept}")


def ingest_dept(dept: str, millesime: str) -> bool:
    """Pipeline complet pour un département : extract 7z → ogr2ogr 2 couches → consolidate."""
    archive = find_archive(dept)
    if not archive:
        logger.warning(
            f"Dpt {dept} : aucune archive .7z trouvée dans {BDTOPO_DIR / dept}. "
            "Compléter scripts/bdtopo_urls.txt + lancer scripts/download_bdtopo.sh."
        )
        return False

    extracted = extract_archive(archive, dept)
    gpkg = find_gpkg(extracted)
    if not gpkg:
        logger.error(f"Dpt {dept} : .gpkg introuvable après décompression de {archive}")
        return False
    logger.info(
        f"Dpt {dept} : GPKG localisé {gpkg.name} ({gpkg.stat().st_size / 1e9:.2f} GB)"
    )

    env = os.environ.copy()
    pg_user = env.get("POSTGRES_LOCAL_USER", "conx")
    pg_pw = env.get("POSTGRES_LOCAL_PASSWORD", "")
    pg_db = env.get("POSTGRES_LOCAL_DB", "conx")

    # 1) TRONCON_DE_ROUTE → staging → final
    ok, err = ogr2ogr_layer(
        gpkg,
        "troncon_de_route",
        "public_data.topo_roads_staging",
        pg_user,
        pg_pw,
        pg_db,
        nlt="LINESTRING",
    )
    if not ok:
        logger.error(f"Dpt {dept} : ogr2ogr troncon_de_route a échoué :\n{err}")
        return False
    if not consolidate_roads(dept, env, millesime):
        return False
    logger.info(f"✅ Dpt {dept} : topo_roads consolidées")

    # 2) BATIMENT → staging → final
    ok, err = ogr2ogr_layer(
        gpkg,
        "batiment",
        "public_data.topo_buildings_staging",
        pg_user,
        pg_pw,
        pg_db,
        nlt="MULTIPOLYGON",
    )
    if not ok:
        logger.error(f"Dpt {dept} : ogr2ogr batiment a échoué :\n{err}")
        return False
    if not consolidate_buildings(dept, env, millesime):
        return False
    logger.info(f"✅ Dpt {dept} : topo_buildings consolidées")

    return True


def apply_migrations(env: dict[str, str]) -> bool:
    """Applique les migrations BD TOPO si absentes (006 topo_roads, 007 topo_buildings)."""
    migrations = [
        ("topo_roads", "006_create_topo_roads.sql"),
        ("topo_buildings", "007_create_topo_buildings.sql"),
    ]
    for table_name, sql_file in migrations:
        container = env.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
        pg_user = env.get("POSTGRES_LOCAL_USER", "conx")
        pg_pw = env.get("POSTGRES_LOCAL_PASSWORD", "")
        pg_db = env.get("POSTGRES_LOCAL_DB", "conx")
        # Check if table exists
        check = subprocess.run(
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
                "-At",
                "-c",
                f"SELECT 1 FROM information_schema.tables "
                f"WHERE table_schema='public_data' AND table_name='{table_name}';",
            ],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0 and check.stdout.strip() == "1":
            continue
        sql_path = ROOT / "scripts" / "sql" / "migrations" / sql_file
        sql = sql_path.read_text(encoding="utf-8")
        tmp_path = ROOT / "scripts" / "tmp" / sql_file
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(sql, encoding="utf-8")
        subprocess.run(
            ["docker", "cp", str(tmp_path), f"{container}:/tmp/{sql_file}"], check=True
        )
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
                f"/tmp/{sql_file}",
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            logger.error(f"Migration {sql_file} failed:\n{r.stderr[-500:]}")
            return False
        logger.info(f"Migration {sql_file} appliquée.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dept", nargs="?", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    millesime = os.environ.get("BDTOPO_MILLESIME", DEFAULT_MILLESIME)
    logger.info(f"Millésime BD TOPO pinné : {millesime}")
    if not apply_migrations(os.environ.copy()):
        return 1
    depts = DEFAULT_DEPTS if args.all else [args.dept or "02"]
    failed: list[str] = []
    for d in depts:
        if not ingest_dept(d, millesime):
            failed.append(d)
    if failed:
        logger.error(f"Departements en echec : {failed}")
        return 1
    logger.info("Tous les départements BD TOPO ingérés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
