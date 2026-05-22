"""ConX — J8 : pipeline LAZ → mesh glTF via PDAL (Docker).

Convertit une dalle LiDAR HD .copc.laz (ou .laz classique) en mesh glTF utilisable
par Three.js côté Mode Projet.

Pipeline :
  1. PDAL filtre les points classés "bâti" (classification 6) dans le LAZ.
  2. (Optionnel) crop sur l'emprise d'un bâtiment depuis public_data.buildings.
  3. Triangulation via filters.poisson (ou greedy).
  4. Export en .ply ou .stl puis conversion glTF via meshlabxmlplus / py3dtiles.

Pour le MVP : on utilise une image Docker `pdal/pdal:latest` qui embarque PDAL +
ses dépendances. Si l'image n'est pas dispo (réseau corp restrictif) → bascule
sur stub avec mesh placeholder.

Usage :
    python scripts/lidar_to_gltf.py --dalle <dalle_name>
    python scripts/lidar_to_gltf.py --building <building_id>
    python scripts/lidar_to_gltf.py --building bdnb-bg-XYZ --crop-only

Pré-requis :
  - Dalle déjà téléchargée (cf. scripts/download_lidar.sh)
  - Docker disponible (`docker run pdal/pdal:latest` doit fonctionner)
  - Bâtiment géolocalisé dans public_data.buildings (pour --building)

NB : ce script est UN STUB STRUCTUREL pour J8. Le pipeline PDAL complet sera
finalisé soit par le partenaire (machine dédiée GPU) soit en J15+ avec pré-génération
hors-ligne des 5-10 bâtiments démo.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORAGE_LIDAR = ROOT / "data" / "storage" / "lidar"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lidar_to_gltf")


def check_pdal_docker() -> bool:
    """Vérifie que l'image pdal/pdal est disponible (sinon retourne False)."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "pdal/pdal:latest"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pull_pdal_docker() -> bool:
    """Pull l'image pdal/pdal:latest."""
    logger.info("Pull image Docker pdal/pdal:latest (peut prendre quelques min)...")
    try:
        subprocess.run(["docker", "pull", "pdal/pdal:latest"], check=True, timeout=600)
        return True
    except subprocess.CalledProcessError:
        logger.error(
            "Impossible de puller pdal/pdal — vérifier la connexion réseau et "
            "https://hub.docker.com/r/pdal/pdal"
        )
        return False


def run_pdal_pipeline(
    input_laz: Path, output_ply: Path, building_id: str | None = None
) -> bool:
    """Exécute le pipeline PDAL : filtre bâti + triangulation greedy.

    Si building_id fourni, crop sur l'emprise du bâtiment (à implémenter via
    PostGIS query → bbox → filters.crop).

    Returns True si OK, False sinon.
    """
    pipeline = {
        "pipeline": [
            str(input_laz),
            {
                "type": "filters.range",
                "limits": "Classification[6:6]",  # 6 = building
            },
            # crop bbox si building_id (TODO : query PostGIS)
            {
                "type": "filters.poisson",
                "depth": 8,
            },
            {
                "type": "writers.ply",
                "filename": str(output_ply),
            },
        ]
    }
    import json as _json

    pipeline_json = _json.dumps(pipeline)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{STORAGE_LIDAR.parent}:/data:rw",
        "pdal/pdal:latest",
        "pdal",
        "pipeline",
        "--stdin",
    ]
    logger.info(f"PDAL pipeline : {input_laz.name} → {output_ply.name}")
    try:
        result = subprocess.run(
            cmd,
            input=pipeline_json,
            text=True,
            capture_output=True,
            timeout=600,
        )
        if result.returncode != 0:
            logger.error(f"PDAL stderr : {result.stderr[:500]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("PDAL pipeline timeout (> 10 min).")
        return False


def ply_to_gltf(ply: Path, gltf: Path) -> bool:
    """Convertit PLY → glTF (texture aérienne optionnelle).

    Pour le MVP : utilisation de `trimesh` (pip install trimesh) qui supporte
    natif l'export glTF. Plus simple que py3dtiles.
    """
    try:
        import trimesh  # noqa: F401
    except ImportError:
        logger.error(
            "trimesh non installé. Installer : pip install trimesh\n"
            "Ce script est un stub J8 — la finalisation se fera en J15 avec "
            "pré-génération des 5-10 bâtiments démo."
        )
        return False

    try:
        import trimesh

        mesh = trimesh.load(ply)
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            logger.warning(f"Mesh vide ou multi-scene non géré pour {ply.name}.")
            return False
        mesh.export(gltf)
        return True
    except Exception as e:
        logger.error(f"Conversion PLY→glTF échouée : {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dalle", help="Nom de la dalle (ex: LHD_FXX_0700_7050_PTS_C_LAMB93_IGN69)"
    )
    parser.add_argument(
        "--building", help="building_id (BDNB) — détermine la dalle via PostGIS"
    )
    parser.add_argument(
        "--crop-only",
        action="store_true",
        help="Crop sur l'emprise bâtiment uniquement",
    )
    parser.add_argument(
        "--check-only", action="store_true", help="Vérifie deps sans exécuter"
    )
    args = parser.parse_args()

    # 1. Sanity checks
    if not check_pdal_docker():
        logger.warning("Image pdal/pdal:latest absente. Tentative de pull...")
        if not pull_pdal_docker():
            logger.error(
                "PDAL Docker indisponible. STUB J8 — finaliser en J15 avec une "
                "machine ayant PDAL natif OU pré-générer les 5-10 bâtiments démo "
                "hors-ligne et copier les .gltf dans data/storage/lidar/."
            )
            return 1

    if args.check_only:
        logger.info("Deps OK (pdal/pdal:latest dispo).")
        return 0

    # 2. Résoudre dalle / building
    if not args.dalle and not args.building:
        parser.print_help()
        return 1

    if args.building:
        # TODO : query PostGIS pour récupérer la dalle de ce bâtiment
        logger.error("Mode --building : implémentation à finaliser en J15.")
        return 2

    laz = STORAGE_LIDAR / f"{args.dalle}.copc.laz"
    if not laz.exists():
        laz = STORAGE_LIDAR / f"{args.dalle}.laz"
    if not laz.exists():
        logger.error(f"LAZ introuvable : {args.dalle}*.laz dans {STORAGE_LIDAR}")
        logger.error(
            "Télécharger d'abord : scripts/download_lidar.sh --dalle " + args.dalle
        )
        return 3

    ply = STORAGE_LIDAR / f"{args.dalle}.ply"
    gltf = STORAGE_LIDAR / f"{args.dalle}.gltf"

    if not run_pdal_pipeline(laz, ply, args.building):
        return 4

    if not ply_to_gltf(ply, gltf):
        return 5

    size_mb = gltf.stat().st_size / 1024 / 1024
    logger.info(f"OK : {gltf.name} généré ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
