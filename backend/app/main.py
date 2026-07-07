"""ConX — point d'entrée FastAPI.

J11 : Mode Stratégie en ligne. Endpoints `/api/buildings`, `/api/internal/*`,
`/api/exports/*`, `/api/meta/*`. Auth Supabase JWT (D-012) côté `/api/buildings`
et `/api/exports`. Bypass `X-Internal-Token` pour les Managed Agents (D-013).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import lifespan
from .routers import agents, buildings, exports, ifc, internal, meta

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
)

# Exposition de la doc interactive : désactivée en prod ou via CONX_DISABLE_DOCS.
# Évite d'exposer le schéma complet + Swagger « Try it out » quand le backend
# passe par un tunnel public (ngrok). Cf. docs/AUDIT_2026-07-07.md.
_env = (os.environ.get("CONX_ENV") or os.environ.get("ENV") or "").strip().lower()
_disable_docs = _env in {"prod", "production"} or os.environ.get("CONX_DISABLE_DOCS", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

app = FastAPI(
    title="ConX API",
    version="0.13.0-j13",
    description=(
        "Plateforme IA pour la rénovation énergétique hors-site (Hauts-de-France). "
        "J13 : Mode Stratégie + Mode Projet (SSE) + Mode Conformité (IFC + PDF)."
    ),
    lifespan=lifespan,
    docs_url=None if _disable_docs else "/docs",
    redoc_url=None if _disable_docs else "/redoc",
    openapi_url=None if _disable_docs else "/openapi.json",
)

if os.environ.get("CONX_DEV_BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes"}:
    logging.getLogger("conx").warning(
        "⚠ CONX_DEV_BYPASS_AUTH est activé au démarrage — auth contournée. "
        "Ne pas exposer publiquement dans cet état (cf. docs/AUDIT_2026-07-07.md C2)."
    )

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="conx-backend",
        version=app.version,
        timestamp=datetime.now(UTC).isoformat(),
    )


# Routers
app.include_router(buildings.router)
app.include_router(exports.router)
app.include_router(internal.router)
app.include_router(meta.router)
app.include_router(agents.router)
app.include_router(ifc.router)
