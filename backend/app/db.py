"""ConX — pool asyncpg vers postgres_local.

Cf. CLAUDE.md §6.A : `postgres_local` (Docker) contient les données publiques
massives (`public_data.buildings`, `public_data.dpe`, `public_data.building_scores`,
`public_data.lidar_tiles`). Pas de RLS côté `public_data` — le backend met sa
propre couche d'autorisation devant (cf. `app/auth.py`).

Convention : on parse `DATABASE_URL_LOCAL` qui peut contenir le prefix
`+asyncpg` (utilisé par SQLAlchemy) ; asyncpg attend l'URL nue
`postgresql://...`. Le `init` d'asyncpg.create_pool retire le prefix.

Le pool est créé au startup FastAPI (lifespan) et fermé au shutdown. Routes
asynchrones obtiennent une connexion via la dépendance `Depends(get_db)`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

logger = logging.getLogger("conx.db")

# Module-level pool. Initialisé par `lifespan` au démarrage FastAPI.
_pool: asyncpg.Pool | None = None


def _normalize_url(url: str) -> str:
    """SQLAlchemy `postgresql+asyncpg://...` → asyncpg `postgresql://...`."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _build_dsn_from_env() -> str | None:
    """Construit le DSN depuis les variables POSTGRES_LOCAL_* (le pattern utilisé
    par tous les scripts). Retourne None si une variable critique manque.

    Fallback : si DATABASE_URL_LOCAL contient un placeholder (`changeme_*`) le
    DSN reconstruit est préféré. Évite de devoir maintenir 2 sources de vérité
    pour le mot de passe (cf. scripts/*.py qui font tous le même pattern).
    """
    host = os.environ.get("POSTGRES_LOCAL_HOST", "postgres_local")
    port = os.environ.get("POSTGRES_LOCAL_PORT", "5432")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    if not pw:
        return None
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Hook d'initialisation par connexion : règle le search_path + timezone."""
    await conn.execute("SET search_path TO public_data, tiles, public;")
    await conn.execute("SET timezone TO 'UTC';")
    # PostGIS retourne du WKT/WKB ; on garde le format natif et on convertit
    # en JSON via ST_AsGeoJSON côté SQL pour éviter les conversions custom.


async def get_pool() -> asyncpg.Pool:
    """Retourne le pool global. Lève si non initialisé (lifespan absent)."""
    if _pool is None:
        raise RuntimeError("Pool asyncpg non initialisé — vérifier que le lifespan FastAPI tourne.")
    return _pool


async def get_db() -> AsyncIterator[asyncpg.Connection]:
    """Dépendance FastAPI : yield une connexion empruntée au pool.

    Usage::

        @router.get("/buildings")
        async def list_buildings(conn: asyncpg.Connection = Depends(get_db)):
            rows = await conn.fetch("SELECT 1")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie FastAPI : crée le pool au startup, le ferme au shutdown."""
    global _pool

    url = os.environ.get("DATABASE_URL_LOCAL", "")
    dsn_from_url = _normalize_url(url) if url else None
    dsn_from_env = _build_dsn_from_env()

    # Préférer dsn_from_env si l'URL contient un placeholder évident.
    if dsn_from_url and "changeme" in dsn_from_url and dsn_from_env:
        logger.warning(
            "DATABASE_URL_LOCAL contient 'changeme' — utilisation des " "variables POSTGRES_LOCAL_* à la place."
        )
        dsn = dsn_from_env
    else:
        dsn = dsn_from_url or dsn_from_env

    if not dsn:
        logger.warning(
            "Aucun DSN PostgreSQL utilisable (DATABASE_URL_LOCAL et "
            "POSTGRES_LOCAL_PASSWORD vides) — pool DB non créé."
        )
        _pool = None
        yield
        return
    logger.info("Création du pool asyncpg (min=2, max=10)...")
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30.0,
        init=_init_connection,
    )
    logger.info("Pool asyncpg prêt.")

    try:
        yield
    finally:
        if _pool is not None:
            logger.info("Fermeture du pool asyncpg...")
            await _pool.close()
            _pool = None
            logger.info("Pool asyncpg fermé.")
