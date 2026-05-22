"""ConX — Pré-warmup des tuiles MVT Vieux-Lille pour la démo.

Pour J22 (polish démo) : on requête tous les tiles dans la bbox Vieux-Lille
zoom 14-18 sur les layers principaux, pour que martin charge ses caches et
serve les requêtes en < 50 ms pendant la démo live.

Usage :
    python scripts/prewarm_vl_tiles.py
    python scripts/prewarm_vl_tiles.py --zooms 14,15,16,17,18
    python scripts/prewarm_vl_tiles.py --layers buildings_mv,topo_buildings

Volume total : ~273 tiles par layer (env. 1 + 4 + 16 + 56 + 196). Sur 2 layers
= ~546 requêtes. Durée typique : 30-60 s.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

# Vieux-Lille bbox WGS84
VL_LON_MIN, VL_LAT_MIN = 3.057, 50.640
VL_LON_MAX, VL_LAT_MAX = 3.075, 50.652

MARTIN_BASE = "http://localhost:3000"
DEFAULT_LAYERS = ["buildings_mv", "topo_buildings", "commune_passoires_heatmap_mv"]
DEFAULT_ZOOMS = list(range(14, 19))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("prewarm_vl")


def deg2num(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to tile x/y at given zoom (XYZ/slippy scheme)."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_range(zoom: int) -> tuple[range, range]:
    x_min, y_min = deg2num(VL_LAT_MAX, VL_LON_MIN, zoom)
    x_max, y_max = deg2num(VL_LAT_MIN, VL_LON_MAX, zoom)
    return range(x_min, x_max + 1), range(y_min, y_max + 1)


def fetch_tile(layer: str, z: int, x: int, y: int) -> tuple[bool, int, int]:
    url = f"{MARTIN_BASE}/{layer}/{z}/{x}/{y}"
    try:
        with urlopen(url, timeout=10) as resp:
            data = resp.read()
            return True, resp.status, len(data)
    except HTTPError as e:
        return False, e.code, 0
    except URLError as e:
        return False, -1, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zooms", default=",".join(str(z) for z in DEFAULT_ZOOMS),
                        help="liste de zooms séparés par ',' (def 14,15,16,17,18)")
    parser.add_argument("--layers", default=",".join(DEFAULT_LAYERS),
                        help="liste de layers martin séparés par ',' (def buildings_mv,topo_buildings,commune_passoires_heatmap_mv)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true", help="liste les URLs sans requeter")
    args = parser.parse_args()

    zooms = [int(z) for z in args.zooms.split(",") if z.strip()]
    layers = [l.strip() for l in args.layers.split(",") if l.strip()]

    # 1. Plan des requêtes
    tasks = []
    for layer in layers:
        for z in zooms:
            xs, ys = tile_range(z)
            for x in xs:
                for y in ys:
                    tasks.append((layer, z, x, y))
    logger.info("Pré-warmup VL : %d tiles à requeter (layers=%s, zooms=%s)",
                len(tasks), layers, zooms)

    if args.dry_run:
        for t in tasks[:20]:
            print(f"  GET {MARTIN_BASE}/{t[0]}/{t[1]}/{t[2]}/{t[3]}")
        if len(tasks) > 20:
            print(f"  ... ({len(tasks) - 20} more)")
        return 0

    # 2. Exécution parallèle
    t0 = time.time()
    ok = 0
    ko = 0
    total_bytes = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_tile, l, z, x, y): (l, z, x, y) for (l, z, x, y) in tasks}
        for fut in as_completed(futs):
            l, z, x, y = futs[fut]
            success, status, size = fut.result()
            if success:
                ok += 1
                total_bytes += size
            else:
                ko += 1
                if ko <= 5:
                    logger.warning("KO %s/%d/%d/%d -> status=%s", l, z, x, y, status)
    dt = time.time() - t0

    logger.info("✅ Terminé : %d OK / %d KO en %.1f s (%.0f tiles/s, %.1f KB total)",
                ok, ko, dt, ok / max(dt, 0.001), total_bytes / 1024)
    return 0 if ko == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
