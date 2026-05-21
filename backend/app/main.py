"""ConX — point d'entrée FastAPI. J1 stub : health endpoint uniquement."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="ConX API",
    version="0.1.0-j1",
    description="Plateforme IA pour la rénovation énergétique hors-site (Hauts-de-France).",
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
