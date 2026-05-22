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
from .routers import agents, buildings, exports, internal, meta

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="ConX API",
    version="0.12.0-j12",
    description=(
        "Plateforme IA pour la rénovation énergétique hors-site (Hauts-de-France). "
        "J12 : Mode Stratégie + Mode Projet (chat itératif Agent Plan via SSE)."
    ),
    lifespan=lifespan,
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
