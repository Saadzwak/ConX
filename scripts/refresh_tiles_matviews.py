#!/usr/bin/env python3
"""ConX — rafraîchit les vues matérialisées du schéma `tiles` (martin MVT).

Référencé par migration 012 et docs/TILES_MVT.md mais **manquant** jusqu'ici
(cf. docs/AUDIT_2026-07-07.md C4). Sans lui, toute évolution des données
(ré-ingestion BDNB, recalcul des scores, prédiction ML) laisse les tuiles
périmées jusqu'à un REFRESH manuel.

À lancer **après** tout changement de données sous-jacentes :
    python scripts/refresh_tiles_matviews.py

REFRESH ... CONCURRENTLY (non bloquant : la carte reste servie pendant le
refresh) grâce aux index uniques créés en migration 012. Repli sur un REFRESH
simple si une matview n'est pas encore peuplée (1ᵉ population).

Usage psql via `docker exec` par défaut (pas de client PG requis sur l'hôte
Windows) — override par CONX_USE_DOCKER_EXEC=0. Cf. get_pg_env().
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("conx.refresh_tiles")

# Matviews à rafraîchir, dans l'ordre (chacune dépend de sa vue _v sous-jacente).
MATVIEWS = [
    "tiles_pub.buildings_mv",
    "tiles_pub.buildings_centroids_mv",
    "tiles_pub.commune_passoires_heatmap_mv",
]


def get_pg_env() -> dict[str, str]:
    """Env PG* — bascule sur localhost:5433 si on cible un nom de service Docker."""
    env = os.environ.copy()
    host = env.get("POSTGRES_LOCAL_HOST", "localhost")
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


def _using_docker_exec() -> bool:
    return os.environ.get("CONX_USE_DOCKER_EXEC", "1") == "1"


def _psql(sql: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Exécute une commande SQL via psql (docker exec par défaut)."""
    if _using_docker_exec():
        container = os.environ.get("CONX_POSTGRES_CONTAINER", "conx_postgres")
        cmd = [
            "docker", "exec", "-e", f"PGPASSWORD={env['PGPASSWORD']}", container,
            "psql", "-U", env["PGUSER"], "-d", env["PGDATABASE"],
            "-v", "ON_ERROR_STOP=1", "-c", sql,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "-c", sql]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def refresh_one(mv: str, env: dict[str, str]) -> bool:
    """Rafraîchit une matview. CONCURRENTLY d'abord, repli sur simple si besoin."""
    t0 = time.monotonic()
    res = _psql(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv};", env)
    if res.returncode != 0:
        # Cas typique : matview jamais peuplée → CONCURRENTLY interdit. On retombe
        # sur un REFRESH simple (bloquant mais correct pour la 1ᵉ population).
        logger.warning(
            "%s : CONCURRENTLY a échoué (%s) — repli sur REFRESH simple.",
            mv, (res.stderr or "").strip()[-200:],
        )
        res = _psql(f"REFRESH MATERIALIZED VIEW {mv};", env)
        if res.returncode != 0:
            logger.error("%s : REFRESH a échoué : %s", mv, (res.stderr or "").strip()[-400:])
            return False
    logger.info("%s rafraîchie en %.1fs", mv, time.monotonic() - t0)
    return True


def main() -> int:
    env = get_pg_env()
    logger.info("Refresh des %d matviews tiles...", len(MATVIEWS))
    ok = all(refresh_one(mv, env) for mv in MATVIEWS)
    if ok:
        logger.info("Toutes les matviews tiles sont à jour.")
        return 0
    logger.error("Au moins une matview n'a pas pu être rafraîchie.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
