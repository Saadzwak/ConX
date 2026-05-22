"""ConX — endpoints `/api/exports/*` (J11).

Export CSV ou GeoJSON de la liste filtrée Mode Stratégie. Réutilise les mêmes
filtres que `/api/buildings`. Streaming pour gros volumes (jusqu'à 100k lignes).

CSV : séparateur `;`, encodage UTF-8 BOM (Excel friendly).
GeoJSON : FeatureCollection EPSG:4326, properties = colonnes plates.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..auth import AuthUser, get_current_user
from ..db import get_pool

logger = logging.getLogger("conx.routers.exports")

router = APIRouter(prefix="/api/exports", tags=["exports"])

MAX_EXPORT_ROWS = 100_000

# Singletons pour les `Query(...)` partagés (évite B008 ruff sur defaults)
_QUERY_NONE: Any = Query(None)
_QUERY_LIMIT_CSV: Any = Query(50_000, ge=1, le=MAX_EXPORT_ROWS)
_QUERY_LIMIT_GEOJSON: Any = Query(10_000, ge=1, le=MAX_EXPORT_ROWS)


# ---------------------------------------------------------------------------
# SQL commun (sans LIMIT — on contrôle via fetchmany)
# ---------------------------------------------------------------------------


def _build_export_sql(
    bbox: tuple[float, float, float, float] | None,
    dept: list[str] | None,
    dpe_classes: list[str] | None,
    typo_proprietaire: list[str] | None,
    annee_max: int | None,
    annee_min: int | None,
    surface_min_m2: float | None,
    weights: tuple[float, float, float, float, float],
    with_geom: bool,
) -> tuple[str, list[Any]]:
    """Construit le SQL paramétré + la liste de params. Retourne (sql, params)."""
    params: list[Any] = list(weights)  # $1..$5
    where: list[str] = []
    n = 6

    if bbox is not None:
        w, s, e, n_ = bbox
        where.append(
            f"b.centroid && ST_Transform(ST_MakeEnvelope(${n}, ${n + 1}, ${n + 2}, ${n + 3}, 4326), 2154)"
        )
        params.extend([w, s, e, n_])
        n += 4
    if dept:
        where.append(f"b.dept = ANY(${n})")
        params.append(dept)
        n += 1
    if dpe_classes:
        where.append(f"b.dpe_classe = ANY(${n})")
        params.append(dpe_classes)
        n += 1
    if typo_proprietaire:
        where.append(f"b.type_proprietaire = ANY(${n})")
        params.append(typo_proprietaire)
        n += 1
    if annee_max is not None:
        where.append(f"b.annee_constr <= ${n}")
        params.append(annee_max)
        n += 1
    if annee_min is not None:
        where.append(f"b.annee_constr >= ${n}")
        params.append(annee_min)
        n += 1
    if surface_min_m2 is not None:
        where.append(f"b.surface_m2 >= ${n}")
        params.append(surface_min_m2)
        n += 1

    geom_select = (
        "ST_AsGeoJSON(ST_Transform(b.geom, 4326)) AS geom_geojson," if with_geom else ""
    )

    sql = f"""
    SELECT
      b.building_id, b.rnb_id, b.dept, b.code_commune_insee,
      b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
      b.periode_construction, b.type_principal, b.materiau_mur,
      b.type_proprietaire, b.monument_historique, b.spr,
      b.dpe_classe, b.dpe_kwh_ep_m2_an, b.dpe_kg_co2_m2_an,
      b.dpe_source,
      ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
      ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
      {geom_select}
      bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
      bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
      bs.confidence, bs.thresholds_version,
      (
        $1::float8 * bs.s_co2 + $2::float8 * bs.s_faisa + $3::float8 * bs.s_cout
        + $4::float8 * bs.s_social + $5::float8 * bs.s_passoire
      ) AS score_total
    FROM public_data.buildings b
    JOIN public_data.building_scores bs USING (building_id)
    WHERE {' AND '.join(where) if where else 'TRUE'}
    ORDER BY score_total DESC NULLS LAST, b.building_id;
    """
    return sql, params


CSV_COLUMNS = [
    "building_id", "rnb_id", "dept", "code_commune_insee",
    "surface_m2", "hauteur_m", "nb_logements", "annee_constr",
    "periode_construction", "type_principal", "materiau_mur",
    "type_proprietaire", "monument_historique", "spr",
    "dpe_classe", "dpe_kwh_ep_m2_an", "dpe_kg_co2_m2_an", "dpe_source",
    "centroid_lon", "centroid_lat",
    "s_co2", "s_faisa", "s_cout", "s_social", "s_passoire",
    "score_total", "co2_evite_t", "cout_estime_eur", "cout_eur_par_t_co2",
    "confidence", "thresholds_version",
]


# ---------------------------------------------------------------------------
# CSV endpoint
# ---------------------------------------------------------------------------


@router.get("/strategie.csv")
async def export_csv(
    user: Annotated[AuthUser, Depends(get_current_user)],
    bbox: str | None = None,
    dept: list[str] | None = _QUERY_NONE,
    dpe_classes: list[str] | None = _QUERY_NONE,
    typo_proprietaire: list[str] | None = _QUERY_NONE,
    annee_max: int | None = None,
    annee_min: int | None = None,
    surface_min_m2: float | None = None,
    w_co2: float = 0.35,
    w_faisa: float = 0.25,
    w_cout: float = 0.20,
    w_social: float = 0.10,
    w_passoire: float = 0.10,
    limit: int = _QUERY_LIMIT_CSV,
) -> StreamingResponse:
    """Export CSV de la liste filtrée. Stream pour rester ≤ RAM raisonnable."""
    _ = user
    bbox_tuple = _parse_bbox(bbox)
    sql, params = _build_export_sql(
        bbox_tuple, dept, dpe_classes, typo_proprietaire,
        annee_max, annee_min, surface_min_m2,
        (w_co2, w_faisa, w_cout, w_social, w_passoire),
        with_geom=False,
    )

    pool = await get_pool()

    async def _gen() -> AsyncIterator[bytes]:
        buf = io.StringIO()
        buf.write("﻿")  # BOM UTF-8 (Excel friendly)
        writer = csv.writer(buf, delimiter=";", lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        # Acquérir une connexion DEDIÉE pour la durée du stream — la dépendance
        # `get_db` libère la connexion à la fin du handler, donc on ne peut pas
        # l'utiliser après que le StreamingResponse a commencé à itérer.
        count = 0
        async with pool.acquire() as conn:
            async with conn.transaction():
                async for r in conn.cursor(sql, *params, prefetch=1000):
                    writer.writerow([_csv_cell(r.get(c)) for c in CSV_COLUMNS])
                    count += 1
                    if count >= limit:
                        break
                    if count % 1000 == 0:
                        yield buf.getvalue().encode("utf-8")
                        buf.seek(0)
                        buf.truncate(0)
                if buf.tell():
                    yield buf.getvalue().encode("utf-8")
        logger.info("Export CSV : %d lignes émises.", count)

    headers = {
        "Content-Disposition": "attachment; filename=conx_strategie.csv",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(_gen(), media_type="text/csv; charset=utf-8", headers=headers)


# ---------------------------------------------------------------------------
# GeoJSON endpoint
# ---------------------------------------------------------------------------


@router.get("/strategie.geojson")
async def export_geojson(
    user: Annotated[AuthUser, Depends(get_current_user)],
    bbox: str | None = None,
    dept: list[str] | None = _QUERY_NONE,
    dpe_classes: list[str] | None = _QUERY_NONE,
    typo_proprietaire: list[str] | None = _QUERY_NONE,
    annee_max: int | None = None,
    annee_min: int | None = None,
    surface_min_m2: float | None = None,
    w_co2: float = 0.35,
    w_faisa: float = 0.25,
    w_cout: float = 0.20,
    w_social: float = 0.10,
    w_passoire: float = 0.10,
    limit: int = _QUERY_LIMIT_GEOJSON,
) -> StreamingResponse:
    """Export GeoJSON (FeatureCollection EPSG:4326). Limite plus basse que CSV
    (la geometry MultiPolygon coûte cher en bande passante)."""
    _ = user
    bbox_tuple = _parse_bbox(bbox)
    sql, params = _build_export_sql(
        bbox_tuple, dept, dpe_classes, typo_proprietaire,
        annee_max, annee_min, surface_min_m2,
        (w_co2, w_faisa, w_cout, w_social, w_passoire),
        with_geom=True,
    )

    pool = await get_pool()

    async def _gen() -> AsyncIterator[bytes]:
        yield b'{"type":"FeatureCollection","crs":{"type":"name","properties":{"name":"EPSG:4326"}},"features":['
        first = True
        count = 0
        async with pool.acquire() as conn:
            async with conn.transaction():
                async for r in conn.cursor(sql, *params, prefetch=500):
                    props = {
                        c: _json_cell(r.get(c))
                        for c in CSV_COLUMNS
                        if c not in ("centroid_lon", "centroid_lat")
                    }
                    geom_str = r.get("geom_geojson")
                    feature = {
                        "type": "Feature",
                        "geometry": json.loads(geom_str) if geom_str else None,
                        "properties": props,
                    }
                    prefix = b"" if first else b","
                    yield prefix + json.dumps(feature, ensure_ascii=False).encode("utf-8")
                    first = False
                    count += 1
                    if count >= limit:
                        break
        yield b"]}"
        logger.info("Export GeoJSON : %d features émises.", count)

    headers = {
        "Content-Disposition": "attachment; filename=conx_strategie.geojson",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(_gen(), media_type="application/geo+json", headers=headers)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        parts = [float(x) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("attendu 4 valeurs")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"bbox invalide : {exc}") from exc
    return (parts[0], parts[1], parts[2], parts[3])


def _csv_cell(v: Any) -> str:
    """Sérialise une valeur DB pour CSV : booleens en 'oui'/'non', floats en
    notation point, None en string vide."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return str(v)


def _json_cell(v: Any) -> Any:
    """Sérialise pour propriétés GeoJSON : float-natifs, str, bool, None."""
    if v is None or isinstance(v, bool | int | str):
        return v
    if isinstance(v, float):
        return v
    # Decimal et autres → string
    return str(v)
