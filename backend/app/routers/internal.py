"""ConX — endpoints `/api/internal/*` appelés par les Managed Agents Anthropic.

Architecture D-009 + D-013 : le container Anthropic est isolé du réseau interne ;
pour accéder à PostGIS, il appelle un endpoint HTTP du backend via le tunnel
ngrok (`NGROK_PUBLIC_URL`). Auth : token partagé `INTERNAL_SHARED_TOKEN`
posé dans le header `X-Internal-Token` (cf. `auth.verify_internal_token`).

Endpoints exposés :
- `POST /api/internal/score-buildings` : agent Sélection — top N bâtiments
  filtrés selon le périmètre demandé par l'utilisateur, avec score calculé.
  L'agent appelle pour OBTENIR les données ; il ne calcule jamais (D-006).
- `GET /api/internal/building/{id}` : agent Plan — fiche bâtiment minimale
  pour générer un plan de rénovation (sans voisinage, plus rapide).

⚠ Ces endpoints sont publics via ngrok pendant la démo. Le seul rempart est
le token partagé. Rotation possible en .env sans redéploiement.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import verify_internal_token
from ..db import get_db

logger = logging.getLogger("conx.routers.internal")

router = APIRouter(
    prefix="/api/internal",
    tags=["internal-agents"],
    dependencies=[Depends(verify_internal_token)],
)


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------


class ScoreRequest(BaseModel):
    """Périmètre passé par l'agent Sélection. Tout est optionnel — au moins
    un filtre doit être fourni pour éviter de scanner 3 M lignes."""

    bbox: tuple[float, float, float, float] | None = Field(
        None, description="WGS84 [W,S,E,N]"
    )
    dept: list[str] | None = None
    code_commune_insee: list[str] | None = None
    dpe_classes: list[str] | None = None
    typo_proprietaire: list[str] | None = None
    annee_max: int | None = None
    annee_min: int | None = None
    surface_min_m2: float | None = None
    # Poids — défaut SCORING.md weights_default
    w_co2: float = 0.35
    w_faisa: float = 0.25
    w_cout: float = 0.20
    w_social: float = 0.10
    w_passoire: float = 0.10
    top_n: int = Field(50, ge=1, le=500)
    order: Literal["score_desc", "co2_evite_desc", "cout_eur_par_t_co2_asc"] = "score_desc"


class ScoredBuilding(BaseModel):
    building_id: str
    rnb_id: str | None
    dept: str
    code_commune_insee: str | None
    surface_m2: float | None
    nb_logements: int | None
    annee_constr: int | None
    type_principal: str | None
    type_proprietaire: str | None
    dpe_classe: str | None
    dpe_source: str | None
    centroid_lon: float
    centroid_lat: float
    score_total: float
    s_co2: float
    s_faisa: float
    s_cout: float
    s_social: float
    s_passoire: float
    co2_evite_t: float
    cout_estime_eur: float
    cout_eur_par_t_co2: float | None
    confidence: float


class ScoreResponse(BaseModel):
    items: list[ScoredBuilding]
    count: int
    thresholds_version: str | None  # même version pour tous les items (sinon None)
    perimeter_used: ScoreRequest


# ---------------------------------------------------------------------------
# Endpoint score-buildings
# ---------------------------------------------------------------------------


@router.post("/score-buildings", response_model=ScoreResponse)
async def score_buildings(
    req: ScoreRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> ScoreResponse:
    """Retourne les `top_n` bâtiments du périmètre, ordonnés par `order`.

    Agent Sélection appelle cet endpoint avec le périmètre extrait du prompt
    utilisateur, reçoit la liste, et la NARRE — il ne recalcule jamais (D-006).
    """
    # Garde-fou : refuser un appel sans aucun filtre (scan complet 3 M lignes)
    has_filter = any(
        [
            req.bbox,
            req.dept,
            req.code_commune_insee,
            req.dpe_classes,
            req.typo_proprietaire,
            req.annee_max is not None,
            req.annee_min is not None,
        ]
    )
    if not has_filter:
        raise HTTPException(
            status_code=400,
            detail=(
                "Au moins un filtre requis (bbox, dept, code_commune_insee, "
                "dpe_classes, typo_proprietaire, ou annee_min/max). "
                "Refuse de scanner les ~3 M bâtiments HDF sans périmètre."
            ),
        )

    params: list[Any] = [req.w_co2, req.w_faisa, req.w_cout, req.w_social, req.w_passoire]
    where: list[str] = []
    n = 6

    if req.bbox is not None:
        w, s, e, n_ = req.bbox
        where.append(
            f"b.centroid && ST_Transform(ST_MakeEnvelope(${n}, ${n + 1}, ${n + 2}, ${n + 3}, 4326), 2154)"
        )
        params.extend([w, s, e, n_])
        n += 4
    if req.dept:
        where.append(f"b.dept = ANY(${n})")
        params.append(req.dept)
        n += 1
    if req.code_commune_insee:
        where.append(f"b.code_commune_insee = ANY(${n})")
        params.append(req.code_commune_insee)
        n += 1
    if req.dpe_classes:
        where.append(f"b.dpe_classe = ANY(${n})")
        params.append(req.dpe_classes)
        n += 1
    if req.typo_proprietaire:
        where.append(f"b.type_proprietaire = ANY(${n})")
        params.append(req.typo_proprietaire)
        n += 1
    if req.annee_max is not None:
        where.append(f"b.annee_constr <= ${n}")
        params.append(req.annee_max)
        n += 1
    if req.annee_min is not None:
        where.append(f"b.annee_constr >= ${n}")
        params.append(req.annee_min)
        n += 1
    if req.surface_min_m2 is not None:
        where.append(f"b.surface_m2 >= ${n}")
        params.append(req.surface_min_m2)
        n += 1

    order_clause = {
        "score_desc": "score_total DESC NULLS LAST, b.building_id",
        "co2_evite_desc": "bs.co2_evite_t DESC NULLS LAST, b.building_id",
        "cout_eur_par_t_co2_asc": "bs.cout_eur_par_t_co2 ASC NULLS LAST, b.building_id",
    }[req.order]

    sql = f"""
    SELECT
      b.building_id, b.rnb_id, b.dept, b.code_commune_insee,
      b.surface_m2, b.nb_logements, b.annee_constr,
      b.type_principal, b.type_proprietaire,
      b.dpe_classe, bs.dpe_source,
      ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
      ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
      (
        $1::float8 * bs.s_co2 + $2::float8 * bs.s_faisa + $3::float8 * bs.s_cout
        + $4::float8 * bs.s_social + $5::float8 * bs.s_passoire
      ) AS score_total,
      bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
      bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
      bs.confidence, bs.thresholds_version
    FROM public_data.buildings b
    JOIN public_data.building_scores bs USING (building_id)
    WHERE {' AND '.join(where) if where else 'TRUE'}
    ORDER BY {order_clause}
    LIMIT ${n};
    """
    params.append(req.top_n)

    rows = await conn.fetch(sql, *params)

    items = [
        ScoredBuilding(
            building_id=r["building_id"],
            rnb_id=r["rnb_id"],
            dept=r["dept"],
            code_commune_insee=r["code_commune_insee"],
            surface_m2=float(r["surface_m2"]) if r["surface_m2"] is not None else None,
            nb_logements=r["nb_logements"],
            annee_constr=r["annee_constr"],
            type_principal=r["type_principal"],
            type_proprietaire=r["type_proprietaire"],
            dpe_classe=r["dpe_classe"],
            dpe_source=r["dpe_source"],
            centroid_lon=float(r["centroid_lon"]),
            centroid_lat=float(r["centroid_lat"]),
            score_total=float(r["score_total"]),
            s_co2=float(r["s_co2"]),
            s_faisa=float(r["s_faisa"]),
            s_cout=float(r["s_cout"]),
            s_social=float(r["s_social"]),
            s_passoire=float(r["s_passoire"]),
            co2_evite_t=float(r["co2_evite_t"]),
            cout_estime_eur=float(r["cout_estime_eur"]),
            cout_eur_par_t_co2=(
                float(r["cout_eur_par_t_co2"])
                if r["cout_eur_par_t_co2"] is not None
                else None
            ),
            confidence=float(r["confidence"]),
        )
        for r in rows
    ]
    versions = {r["thresholds_version"] for r in rows}
    thresholds_version = next(iter(versions)) if len(versions) == 1 else None

    return ScoreResponse(
        items=items,
        count=len(items),
        thresholds_version=thresholds_version,
        perimeter_used=req,
    )


# ---------------------------------------------------------------------------
# Endpoint building-light pour Agent Plan
# ---------------------------------------------------------------------------


class BuildingLight(BaseModel):
    """Fiche bâtiment minimale pour générer un plan — pas de geometry, pas
    de voisinage. Agent Plan reçoit ça en `user_message` initial."""

    building_id: str
    rnb_id: str | None
    dept: str
    code_commune_insee: str | None
    surface_m2: float | None
    hauteur_m: float | None
    nb_logements: int | None
    annee_constr: int | None
    periode_construction: str | None
    type_principal: str | None
    materiau_mur: str | None
    type_proprietaire: str | None
    monument_historique: bool
    spr: bool
    dpe_classe: str | None
    dpe_kwh_ep_m2_an: float | None
    dpe_kg_co2_m2_an: float | None
    dpe_coefficient_ep_electricite: float
    dpe_source: str | None
    score: dict[str, Any] | None
    centroid_lon: float
    centroid_lat: float


@router.get("/building/{building_id}", response_model=BuildingLight)
async def get_building_light(
    building_id: str,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> BuildingLight:
    """Fiche light pour Agent Plan : pas de geometry pour réduire la taille
    du contexte envoyé à Claude."""
    row = await conn.fetchrow(
        """
        SELECT
          b.building_id, b.rnb_id, b.dept, b.code_commune_insee,
          b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
          b.periode_construction, b.type_principal, b.materiau_mur,
          b.type_proprietaire, b.monument_historique, b.spr,
          b.dpe_classe, b.dpe_kwh_ep_m2_an, b.dpe_kg_co2_m2_an,
          b.dpe_coefficient_ep_electricite, b.dpe_source,
          ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
          ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
          bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
          bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
          bs.confidence, bs.thresholds_version
        FROM public_data.buildings b
        LEFT JOIN public_data.building_scores bs USING (building_id)
        WHERE b.building_id = $1;
        """,
        building_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Bâtiment introuvable.")

    score: dict[str, Any] | None = None
    if row["s_co2"] is not None:
        score = {
            "s_co2": float(row["s_co2"]),
            "s_faisa": float(row["s_faisa"]),
            "s_cout": float(row["s_cout"]),
            "s_social": float(row["s_social"]),
            "s_passoire": float(row["s_passoire"]),
            "co2_evite_t": float(row["co2_evite_t"]),
            "cout_estime_eur": float(row["cout_estime_eur"]),
            "cout_eur_par_t_co2": (
                float(row["cout_eur_par_t_co2"])
                if row["cout_eur_par_t_co2"] is not None
                else None
            ),
            "confidence": float(row["confidence"]),
            "thresholds_version": row["thresholds_version"],
        }

    return BuildingLight(
        building_id=row["building_id"],
        rnb_id=row["rnb_id"],
        dept=row["dept"],
        code_commune_insee=row["code_commune_insee"],
        surface_m2=float(row["surface_m2"]) if row["surface_m2"] is not None else None,
        hauteur_m=float(row["hauteur_m"]) if row["hauteur_m"] is not None else None,
        nb_logements=row["nb_logements"],
        annee_constr=row["annee_constr"],
        periode_construction=row["periode_construction"],
        type_principal=row["type_principal"],
        materiau_mur=row["materiau_mur"],
        type_proprietaire=row["type_proprietaire"],
        monument_historique=bool(row["monument_historique"]),
        spr=bool(row["spr"]),
        dpe_classe=row["dpe_classe"],
        dpe_kwh_ep_m2_an=(
            float(row["dpe_kwh_ep_m2_an"]) if row["dpe_kwh_ep_m2_an"] is not None else None
        ),
        dpe_kg_co2_m2_an=(
            float(row["dpe_kg_co2_m2_an"]) if row["dpe_kg_co2_m2_an"] is not None else None
        ),
        dpe_coefficient_ep_electricite=float(row["dpe_coefficient_ep_electricite"]),
        dpe_source=row["dpe_source"],
        score=score,
        centroid_lon=float(row["centroid_lon"]),
        centroid_lat=float(row["centroid_lat"]),
    )
