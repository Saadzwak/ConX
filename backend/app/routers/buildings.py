"""ConX — endpoints `/api/buildings` Mode Stratégie (J11).

Lit `public_data.buildings` + `public_data.building_scores`. Le score total est
calculé à la VOLÉE en SQL pur (cf. SCORING.md §"Calcul à la volée") à partir
des 5 composantes pré-calculées et des poids passés par l'utilisateur.

Convention bbox : tableau [west, south, east, north] en degrés WGS84 (EPSG:4326).
Le backend transforme en EPSG:2154 (Lambert-93) pour le filtre PostGIS, car
`buildings.geom` est en 2154.

Limites de pagination :
- pas d'OFFSET sur 3 M lignes (lent + cursor-instable).
- on retourne max 5000 lignes par requête + curseur opaque pour la suite
  (`next_cursor`), basé sur ordre canonique (`-score_total, building_id`).
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import AuthUser, get_current_user
from ..db import get_db

logger = logging.getLogger("conx.routers.buildings")

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------


class ScoringWeights(BaseModel):
    """Poids des 5 composantes (somme contrainte ≈ 1 côté UI ; non strict côté API)."""

    w_co2: float = Field(0.35, ge=0.0, le=1.0)
    w_faisa: float = Field(0.25, ge=0.0, le=1.0)
    w_cout: float = Field(0.20, ge=0.0, le=1.0)
    w_social: float = Field(0.10, ge=0.0, le=1.0)
    w_passoire: float = Field(0.10, ge=0.0, le=1.0)


class BuildingListItem(BaseModel):
    """Item de la liste Mode Stratégie. INNER JOIN avec building_scores —
    tous les champs scoring sont garantis non-null (cf. SQL_LIST)."""

    building_id: str
    rnb_id: str | None
    dept: str
    surface_m2: float | None
    nb_logements: int | None
    annee_constr: int | None
    type_principal: str | None
    type_proprietaire: str | None
    dpe_classe: str | None
    dpe_source: str  # 'ademe-real' | 'ml-predicted'
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
    confidence: float


class BuildingsListResponse(BaseModel):
    items: list[BuildingListItem]
    count: int
    next_cursor: str | None
    weights_used: ScoringWeights
    bbox: tuple[float, float, float, float] | None  # (W,S,E,N) 4326


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------


SQL_LIST = """
-- Mode Stratégie : liste des bâtiments SCORED uniquement. Si un bâtiment n'a
-- pas de building_scores (cas attendu = 0 post-J5.15), il n'apparaît PAS dans
-- la liste. Voir docs/API.md §6 "score total à la volée" + contrat de pagination.
WITH base AS (
  SELECT
    b.building_id, b.rnb_id, b.dept, b.surface_m2, b.nb_logements,
    b.annee_constr, b.type_principal, b.type_proprietaire,
    b.dpe_classe,
    bs.dpe_source,
    ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
    ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
    bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
    bs.co2_evite_t, bs.cout_estime_eur, bs.confidence,
    /* Score total à la volée — formule SCORING.md §"Calcul à la volée" */
    (
      $1::float8 * bs.s_co2
      + $2::float8 * bs.s_faisa
      + $3::float8 * bs.s_cout
      + $4::float8 * bs.s_social
      + $5::float8 * bs.s_passoire
    ) AS score_total
  FROM public_data.buildings b
  JOIN public_data.building_scores bs USING (building_id)
  WHERE 1=1
    {bbox_filter}
    {dept_filter}
    {dpe_filter}
    {typo_filter}
    {annee_filter}
    {min_surface_filter}
    {cursor_filter}
)
SELECT * FROM base
ORDER BY score_total DESC, building_id ASC
LIMIT $6;
"""


@router.get("", response_model=BuildingsListResponse)
async def list_buildings(  # -- many query params, c'est l'endpoint principal
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    bbox: Annotated[
        str | None,
        Query(description="WGS84 'west,south,east,north' en degrés", examples=["3.0,50.5,3.2,50.7"]),
    ] = None,
    dept: Annotated[list[str] | None, Query(description="Codes département (59,62,80,60,02)")] = None,
    dpe_classes: Annotated[
        list[str] | None,
        Query(description="Classes DPE à inclure (A..G)"),
    ] = None,
    typo_proprietaire: Annotated[
        list[str] | None, Query(description="Types propriétaire (bailleur_social, ...)")
    ] = None,
    annee_max: Annotated[int | None, Query(description="Construits avant cette année")] = None,
    annee_min: Annotated[int | None, Query()] = None,
    surface_min_m2: Annotated[float | None, Query(ge=0.0)] = None,
    w_co2: Annotated[float, Query(ge=0.0, le=1.0)] = 0.35,
    w_faisa: Annotated[float, Query(ge=0.0, le=1.0)] = 0.25,
    w_cout: Annotated[float, Query(ge=0.0, le=1.0)] = 0.20,
    w_social: Annotated[float, Query(ge=0.0, le=1.0)] = 0.10,
    w_passoire: Annotated[float, Query(ge=0.0, le=1.0)] = 0.10,
    limit: Annotated[int, Query(ge=1, le=5000)] = 200,
    cursor: Annotated[
        str | None,
        Query(description="Curseur opaque pour pagination (issu d'une réponse précédente)"),
    ] = None,
) -> BuildingsListResponse:
    """Liste paginée de bâtiments avec filtres et scoring à la volée.

    **Auth requise** (tout rôle valide).
    """
    _ = user  # auth obligatoire — pas de logique par rôle ici (lecture publique)

    bbox_tuple: tuple[float, float, float, float] | None = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("attendu 4 valeurs")
            bbox_tuple = (parts[0], parts[1], parts[2], parts[3])
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=400, detail=f"bbox invalide : {exc}"
            ) from exc

    params: list[Any] = [w_co2, w_faisa, w_cout, w_social, w_passoire]
    sql_filters: dict[str, str] = {
        "bbox_filter": "",
        "dept_filter": "",
        "dpe_filter": "",
        "typo_filter": "",
        "annee_filter": "",
        "min_surface_filter": "",
        "cursor_filter": "",
    }
    n = 6  # prochain $n disponible

    if bbox_tuple is not None:
        w, s, e, n_ = bbox_tuple
        sql_filters["bbox_filter"] = (
            f"AND b.centroid && ST_Transform(ST_MakeEnvelope("
            f"${n}, ${n + 1}, ${n + 2}, ${n + 3}, 4326), 2154)"
        )
        params.extend([w, s, e, n_])
        n += 4

    if dept:
        sql_filters["dept_filter"] = f"AND b.dept = ANY(${n})"
        params.append(dept)
        n += 1

    if dpe_classes:
        sql_filters["dpe_filter"] = f"AND b.dpe_classe = ANY(${n})"
        params.append(dpe_classes)
        n += 1

    if typo_proprietaire:
        sql_filters["typo_filter"] = f"AND b.type_proprietaire = ANY(${n})"
        params.append(typo_proprietaire)
        n += 1

    if annee_max is not None and annee_min is not None:
        sql_filters["annee_filter"] = (
            f"AND b.annee_constr BETWEEN ${n} AND ${n + 1}"
        )
        params.extend([annee_min, annee_max])
        n += 2
    elif annee_max is not None:
        sql_filters["annee_filter"] = f"AND b.annee_constr <= ${n}"
        params.append(annee_max)
        n += 1
    elif annee_min is not None:
        sql_filters["annee_filter"] = f"AND b.annee_constr >= ${n}"
        params.append(annee_min)
        n += 1

    if surface_min_m2 is not None:
        sql_filters["min_surface_filter"] = f"AND b.surface_m2 >= ${n}"
        params.append(surface_min_m2)
        n += 1

    # Curseur opaque : on encode (score_total, building_id) du dernier item de la
    # page précédente en JSON base64 — pas de fuite d'info, robuste aux poids
    # qui changent (l'utilisateur doit re-paginer si il modifie ses poids).
    if cursor:
        try:
            cur = _decode_cursor(cursor)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"cursor invalide : {exc}") from exc
        # Condition lexicographique sur (score DESC, building_id ASC) :
        # (score < cur_score) OR (score = cur_score AND id > cur_id)
        # INNER JOIN garantit que bs.s_* ne sont jamais NULL — pas de CASE.
        score_expr = (
            "($1::float8 * bs.s_co2 + $2::float8 * bs.s_faisa + $3::float8 * bs.s_cout "
            "+ $4::float8 * bs.s_social + $5::float8 * bs.s_passoire)"
        )
        sql_filters["cursor_filter"] = (
            f"AND ({score_expr} < ${n}"
            f" OR ({score_expr} = ${n} AND b.building_id > ${n + 1}))"
        )
        params.extend([cur["score"], cur["id"]])
        n += 2

    params.append(limit)  # toujours $6 ? non, c'est le dernier paramètre — on règle ci-dessous.
    sql = SQL_LIST.format(**sql_filters)
    # Le placeholder $6 dans le SQL_LIST est réservé au LIMIT ; on doit le
    # renuméroter selon l'ordre réel des paramètres. Plus simple : on substitue
    # explicitement la position du LIMIT.
    limit_idx = len(params)  # le LIMIT vient d'être ajouté en dernier
    sql = sql.replace("LIMIT $6;", f"LIMIT ${limit_idx};")

    rows = await conn.fetch(sql, *params)

    items = [
        BuildingListItem(
            building_id=r["building_id"],
            rnb_id=r["rnb_id"],
            dept=r["dept"],
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
            confidence=float(r["confidence"]),
        )
        for r in rows
    ]

    next_cursor: str | None = None
    if len(items) == limit and items:
        last = items[-1]
        next_cursor = _encode_cursor({"score": last.score_total, "id": last.building_id})

    return BuildingsListResponse(
        items=items,
        count=len(items),
        next_cursor=next_cursor,
        weights_used=ScoringWeights(
            w_co2=w_co2, w_faisa=w_faisa, w_cout=w_cout,
            w_social=w_social, w_passoire=w_passoire,
        ),
        bbox=bbox_tuple,
    )


# ---------------------------------------------------------------------------
# Curseur opaque (base64 JSON)
# ---------------------------------------------------------------------------


def _encode_cursor(payload: dict[str, Any]) -> str:
    import base64

    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(s: str) -> dict[str, Any]:
    import base64

    pad = "=" * (-len(s) % 4)
    raw = base64.urlsafe_b64decode((s + pad).encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or "score" not in payload or "id" not in payload:
        raise ValueError("payload de curseur invalide")
    return payload


# ---------------------------------------------------------------------------
# Endpoint fiche bâtiment (/api/buildings/:id)
# ---------------------------------------------------------------------------


class BuildingDetail(BaseModel):
    building_id: str
    rnb_id: str | None
    dept: str
    code_commune_insee: str | None
    code_iris: str | None
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
    geom_geojson: dict[str, Any]  # MultiPolygon GeoJSON en EPSG:4326
    centroid_lon: float
    centroid_lat: float
    # Scoring (peut être null si incomplete_data)
    score: dict[str, Any] | None
    # Voisinage (k=5 plus proches) — utile pour le narratif IA
    neighbors: list[dict[str, Any]]


SQL_DETAIL = """
SELECT
  b.building_id, b.rnb_id, b.dept, b.code_commune_insee, b.code_iris,
  b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
  b.periode_construction, b.type_principal, b.materiau_mur,
  b.type_proprietaire, b.monument_historique, b.spr,
  b.dpe_classe, b.dpe_kwh_ep_m2_an, b.dpe_kg_co2_m2_an,
  b.dpe_coefficient_ep_electricite, b.dpe_source,
  ST_AsGeoJSON(ST_Transform(b.geom, 4326))::jsonb AS geom_geojson,
  ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
  ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
  bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
  bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
  bs.confidence, bs.dpe_source AS score_dpe_source,
  bs.thresholds_version, bs.incomplete_data, bs.s_faisa_partial,
  bs.missing_fields, bs.computed_at
FROM public_data.buildings b
LEFT JOIN public_data.building_scores bs USING (building_id)
WHERE b.building_id = $1;
"""

# Voisins : k=5 plus proches dans un rayon de 200 m autour du centroid 2154
# du bâtiment de référence. Utilise l'index GIST + opérateur <-> pour KNN.
SQL_NEIGHBORS = """
WITH ref AS (
  SELECT centroid FROM public_data.buildings WHERE building_id = $1
)
SELECT
  b.building_id, b.dpe_classe,
  ST_Distance(b.centroid, ref.centroid) AS distance_m
FROM public_data.buildings b, ref
WHERE b.building_id <> $1
  AND b.centroid && ST_Expand(ref.centroid, 200)
ORDER BY b.centroid <-> ref.centroid
LIMIT 5;
"""


@router.get("/{building_id}", response_model=BuildingDetail)
async def get_building(
    building_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> BuildingDetail:
    """Fiche détaillée d'un bâtiment (geom + scoring + voisins)."""
    _ = user
    row = await conn.fetchrow(SQL_DETAIL, building_id)
    if not row:
        raise HTTPException(status_code=404, detail="Bâtiment introuvable.")

    neigh_rows = await conn.fetch(SQL_NEIGHBORS, building_id)
    neighbors = [
        {
            "building_id": n["building_id"],
            "dpe_classe": n["dpe_classe"],
            "distance_m": float(n["distance_m"]),
        }
        for n in neigh_rows
    ]

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
            "dpe_source": row["score_dpe_source"],
            "thresholds_version": row["thresholds_version"],
            "incomplete_data": bool(row["incomplete_data"]),
            "s_faisa_partial": bool(row["s_faisa_partial"]),
            "missing_fields": list(row["missing_fields"] or []),
            "computed_at": row["computed_at"].isoformat() if row["computed_at"] else None,
        }

    return BuildingDetail(
        building_id=row["building_id"],
        rnb_id=row["rnb_id"],
        dept=row["dept"],
        code_commune_insee=row["code_commune_insee"],
        code_iris=row["code_iris"],
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
        geom_geojson=row["geom_geojson"] if isinstance(row["geom_geojson"], dict) else json.loads(row["geom_geojson"]),
        centroid_lon=float(row["centroid_lon"]),
        centroid_lat=float(row["centroid_lat"]),
        score=score,
        neighbors=neighbors,
    )


