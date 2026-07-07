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
    tous les champs scoring sont garantis non-null (cf. SQL_LIST).

    PHASE 1 fix : ajout de hauteur_m, dpe_kwh_ep_m2_an, monument_historique
    qui étaient utilisés par BuildingDrawer côté frontend mais pas renvoyés
    par cet endpoint (affichage '—' en silence).
    """

    building_id: str
    rnb_id: str | None
    dept: str
    surface_m2: float | None
    hauteur_m: float | None  # PHASE 1.2
    nb_logements: int | None
    annee_constr: int | None
    type_principal: str | None
    type_proprietaire: str | None
    monument_historique: bool  # PHASE 1.2
    dpe_classe: str | None
    dpe_kwh_ep_m2_an: float | None  # PHASE 1.2
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
    b.building_id, b.rnb_id, b.dept, b.surface_m2, b.hauteur_m, b.nb_logements,
    b.annee_constr, b.type_principal, b.type_proprietaire,
    b.monument_historique,
    b.dpe_classe, b.dpe_kwh_ep_m2_an,
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
            raise HTTPException(status_code=400, detail=f"bbox invalide : {exc}") from exc

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
            f"AND b.centroid && ST_Transform(ST_MakeEnvelope(" f"${n}, ${n + 1}, ${n + 2}, ${n + 3}, 4326), 2154)"
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
        sql_filters["annee_filter"] = f"AND b.annee_constr BETWEEN ${n} AND ${n + 1}"
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
            f"AND ({score_expr} < ${n}" f" OR ({score_expr} = ${n} AND b.building_id > ${n + 1}))"
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
            hauteur_m=float(r["hauteur_m"]) if r["hauteur_m"] is not None else None,
            nb_logements=r["nb_logements"],
            annee_constr=r["annee_constr"],
            type_principal=r["type_principal"],
            type_proprietaire=r["type_proprietaire"],
            monument_historique=bool(r["monument_historique"]),
            dpe_classe=r["dpe_classe"],
            dpe_kwh_ep_m2_an=(float(r["dpe_kwh_ep_m2_an"]) if r["dpe_kwh_ep_m2_an"] is not None else None),
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
            w_co2=w_co2,
            w_faisa=w_faisa,
            w_cout=w_cout,
            w_social=w_social,
            w_passoire=w_passoire,
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
    """Fiche détaillée enrichie (J18 refonte dashboard).

    Architecture aplatie : les composantes de scoring sont AU TOP-LEVEL
    (fix PHASE 1.1) ET aussi nichées dans `score` pour rétrocompatibilité.
    Les données BDNB sont regroupées en sous-objets thématiques pour
    lisibilité côté frontend.
    """

    # --- Identité ----------------------------------------------------------
    building_id: str
    rnb_id: str | None
    dept: str
    code_commune_insee: str | None
    code_iris: str | None
    commune_nom: str | None  # BDNB libelle_commune_insee
    code_epci_insee: str | None
    bdnb_millesime: str = "2025-07.a"  # PHASE 1.3 constante

    # --- Adresse BAN -------------------------------------------------------
    adresse_postale: str | None  # PHASE 2.1 — ex "98 Rue des Sarrazins 59000 Lille"
    cle_interop_ban: str | None

    # --- Bâti --------------------------------------------------------------
    surface_m2: float | None  # emprise au sol
    hauteur_m: float | None
    nb_niveaux_ffo: int | None  # PHASE 2.8 — plus précis que hauteur/3
    nb_logements: int | None
    annee_constr: int | None
    periode_construction: str | None
    periode_thermique_reglementaire: str | None  # PHASE 2.14 dérivé
    type_principal: str | None
    materiau_mur: str | None
    materiau_toiture: str | None  # PHASE 2.8
    type_proprietaire: str | None
    monument_historique: bool
    spr: bool

    # --- DPE base ----------------------------------------------------------
    dpe_classe: str | None
    classe_emission_ges: str | None  # PHASE 2.5
    dpe_kwh_ep_m2_an: float | None
    dpe_kg_co2_m2_an: float | None
    dpe_coefficient_ep_electricite: float
    dpe_source: str | None
    identifiant_dpe_ademe: str | None  # PHASE 2.2 — lien observatoire-dpe
    date_etablissement_dpe: str | None
    date_reception_dpe: str | None
    dpe_expire_le: str | None  # PHASE 2.14 — date_etablissement + 10 ans
    shab_immeuble_m2: float | None  # PHASE 2.2 surface habitable cumulée

    # --- Géométrie ---------------------------------------------------------
    geom_geojson: dict[str, Any]
    centroid_lon: float
    centroid_lat: float

    # --- Score (à plat, PHASE 1.1) ----------------------------------------
    score_total: float | None
    s_co2: float | None
    s_faisa: float | None
    s_cout: float | None
    s_social: float | None
    s_passoire: float | None
    co2_evite_t: float | None
    cout_estime_eur: float | None
    cout_eur_par_t_co2: float | None
    confidence: float | None
    incomplete_data: bool | None
    s_faisa_partial: bool | None
    missing_fields: list[str] | None
    thresholds_version: str | None
    computed_at: str | None
    # Compat : objet score nesté (rétrocompatibilité scripts internes)
    score: dict[str, Any] | None

    # --- Voisinage ---------------------------------------------------------
    neighbors: list[dict[str, Any]]

    # --- QPV --------------------------------------------------------------
    dans_qpv: bool
    qpv_nom: str | None

    # --- Réseau de chaleur ------------------------------------------------
    reseau_chaleur_id: str | None
    reseau_chaleur_prioritaire: bool
    reseau_chaleur_distance: str | None

    # --- Diagnostic technique détaillé (BDNB DPE représentatif) ----------
    diagnostic_technique: dict[str, Any] | None

    # --- RPLS bailleurs sociaux -------------------------------------------
    rpls: dict[str, Any] | None

    # --- Conso réelle 7 ans (DLE) -----------------------------------------
    conso_reelle_annuelle: list[dict[str, Any]]

    # --- Risques naturels -------------------------------------------------
    risques: dict[str, str | None]

    # --- Urbanisme --------------------------------------------------------
    urbanisme: dict[str, Any]

    # --- Fiabilité données BDNB -------------------------------------------
    fiabilite: dict[str, Any]

    # --- Acces chantier ---------------------------------------------------
    acces_chantier: dict[str, Any] | None

    # --- Dérivés économiques (PHASE 2.14) ----------------------------------
    cout_energie_annuel_eur: float | None
    cout_energie_30_ans_eur: float | None
    emissions_totales_30_ans_t: float | None

    # --- Aides éligibles (PHASE 2.16) -------------------------------------
    aides_eligibles: list[dict[str, Any]]


# Tarif moyen pondéré (gaz 0.10 + élec 0.20 → ~0.15 €/kWh, à raffiner si
# besoin selon type_energie_chauffage). Documenté ici pour transparence.
TARIF_KWH_PONDERE = 0.15  # €/kWh EP

# Whitelist stricte des départements supportés (HDF), pour interpolation
# de schéma SQL safe (la BDNB est ingérée par schéma dpt).
_BDNB_DEPTS = {"02", "59", "60", "62", "80"}


def _bdnb_schema(dept: str | None) -> str | None:
    """Retourne le nom de schéma BDNB pour un dpt, ou None si invalide.

    La whitelist empêche l'injection SQL lors de l'interpolation directe
    du nom de schéma (pg ne supporte pas les params pour les identifiers).
    """
    if not dept:
        return None
    d = dept.zfill(2)
    if d not in _BDNB_DEPTS:
        return None
    return f"bdnb_2025_07_a_open_data_dep{d}"


SQL_DETAIL_PUBLIC = """
SELECT
  b.building_id, b.rnb_id, b.dept, b.code_commune_insee, b.code_iris,
  b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
  b.periode_construction, b.type_principal, b.materiau_mur,
  b.type_proprietaire, b.monument_historique, b.spr,
  b.dpe_classe, b.dpe_kwh_ep_m2_an, b.dpe_kg_co2_m2_an,
  b.dpe_coefficient_ep_electricite, b.dpe_source, b.bdnb_millesime,
  ST_AsGeoJSON(ST_Transform(b.geom, 4326))::jsonb AS geom_geojson,
  ST_X(ST_Transform(b.centroid, 4326)) AS centroid_lon,
  ST_Y(ST_Transform(b.centroid, 4326)) AS centroid_lat,
  bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
  bs.co2_evite_t, bs.cout_estime_eur, bs.cout_eur_par_t_co2,
  bs.confidence, bs.dpe_source AS score_dpe_source,
  bs.thresholds_version, bs.incomplete_data, bs.s_faisa_partial,
  bs.missing_fields, bs.computed_at,
  ac.acces_chantier, ac.nearest_largeur_m, ac.nearest_distance_m
FROM public_data.buildings b
LEFT JOIN public_data.building_scores bs USING (building_id)
LEFT JOIN public_data.building_acces_chantier ac USING (building_id)
WHERE b.building_id = $1;
"""

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


def _periode_thermique(annee: int | None) -> str | None:
    """Bucket réglementaire thermique (PHASE 2.14)."""
    if annee is None:
        return None
    if annee < 1948:
        return "Avant 1948 (sans réglementation thermique)"
    if annee < 1975:
        return "1948-1974 (avant 1ère réglementation)"
    if annee < 1982:
        return "RT 1974"
    if annee < 1989:
        return "RT 1982"
    if annee < 2001:
        return "RT 1988"
    if annee < 2006:
        return "RT 2000"
    if annee < 2013:
        return "RT 2005"
    if annee < 2022:
        return "RT 2012"
    return "RE 2020"


def _aides_eligibles(
    type_proprietaire: str | None,
    dans_qpv: bool,
    dpe_classe: str | None,
    nb_logements: int | None,
    reseau_chaleur_prioritaire: bool,
) -> list[dict[str, Any]]:
    """Matrice règles aides rénovation énergétique (PHASE 2.16).

    Simplifié pour MVP. Les montants sont indicatifs et reposent sur les
    barèmes publics 2024-2025 — à confirmer pour chaque projet.
    """
    aides: list[dict[str, Any]] = []
    is_passoire = dpe_classe in ("F", "G")
    is_bailleur = type_proprietaire == "bailleur_social"
    is_copro = type_proprietaire == "personne_morale_privee" and (nb_logements or 0) >= 2

    if is_bailleur:
        montant = (nb_logements or 0) * 16_000
        aides.append(
            {
                "code": "ECO_PLS",
                "nom": "Éco-PLS rénovation",
                "condition": "Bailleur social",
                "montant_estimatif_eur": montant,
                "source": "Caisse des Dépôts",
            }
        )
    if dans_qpv:
        aides.append(
            {
                "code": "ANRU",
                "nom": "Programme ANRU / Quartier Politique de la Ville",
                "condition": f"Bâtiment en QPV{' + bailleur social' if is_bailleur else ''}",
                "montant_estimatif_eur": None,
                "source": "ANRU",
            }
        )
    if is_passoire:
        aides.append(
            {
                "code": "CEE_BS_PASSOIRE" if is_bailleur else "CEE_PASSOIRE",
                "nom": "CEE majorés passoires énergétiques",
                "condition": f"DPE {dpe_classe} (passoire)",
                "montant_estimatif_eur": (nb_logements or 0) * 2_500 if is_bailleur else None,
                "source": "Coup de pouce CEE",
            }
        )
    if is_copro:
        aides.append(
            {
                "code": "MPR_COPRO",
                "nom": "MaPrimeRénov' Copropriété",
                "condition": f"Copropriété ≥ 2 logements ({nb_logements} logts)",
                "montant_estimatif_eur": None,
                "source": "Anah",
            }
        )
    if reseau_chaleur_prioritaire:
        aides.append(
            {
                "code": "RCU_RACCORD",
                "nom": "Coup de pouce raccordement au réseau de chaleur",
                "condition": "Bâtiment en périmètre de développement prioritaire",
                "montant_estimatif_eur": None,
                "source": "CEE coup de pouce RCU",
            }
        )
    if dans_qpv or is_bailleur:
        aides.append(
            {
                "code": "FONDS_VERT",
                "nom": "Fonds vert (rénovation HLM / public)",
                "condition": "Bâtiment social / patrimoine public",
                "montant_estimatif_eur": None,
                "source": "DDT département",
            }
        )
    return aides


# Constante pondération scoring (réplique SQL_LIST ; on garde la même)
_SCORING_WEIGHTS = {"co2": 0.35, "faisa": 0.25, "cout": 0.20, "social": 0.10, "passoire": 0.10}


def _compute_score_total(s_co2, s_faisa, s_cout, s_social, s_passoire) -> float | None:
    """Score pondéré à la volée — réplique formule SCORING.md."""
    if any(x is None for x in (s_co2, s_faisa, s_cout, s_social, s_passoire)):
        return None
    return (
        _SCORING_WEIGHTS["co2"] * float(s_co2)
        + _SCORING_WEIGHTS["faisa"] * float(s_faisa)
        + _SCORING_WEIGHTS["cout"] * float(s_cout)
        + _SCORING_WEIGHTS["social"] * float(s_social)
        + _SCORING_WEIGHTS["passoire"] * float(s_passoire)
    )


async def _fetch_bdnb_enrichment(conn: asyncpg.Connection, building_id: str, dept: str) -> dict[str, Any]:
    """Charge l'enrichissement BDNB depuis le schéma dpt (PHASE 2).

    Une seule requête multi-LEFT-JOIN pour les tables stable (1 ligne par
    bâtiment). Les conso DLE multi-millésime sont fetched séparément.
    Retourne un dict avec toutes les colonnes (toutes optionnelles).
    """
    schema = _bdnb_schema(dept)
    if not schema:
        return {}
    # NOTE : `schema` vient de la whitelist _BDNB_DEPTS, safe pour interpolation.
    sql = f"""
    SELECT
      -- adresse
      adr.libelle_adr_principale_ban       AS adresse_postale,
      adr.cle_interop_adr_principale_ban   AS cle_interop_ban,
      -- DPE détaillé
      dpe.identifiant_dpe                  AS identifiant_dpe_ademe,
      dpe.date_etablissement_dpe::text     AS date_etablissement_dpe,
      dpe.date_reception_dpe::text         AS date_reception_dpe,
      dpe.surface_habitable_immeuble       AS shab_immeuble_m2,
      dpe.classe_emission_ges,
      dpe.type_installation_chauffage,
      dpe.type_energie_chauffage,
      dpe.type_generateur_chauffage,
      dpe.type_generateur_chauffage_anciennete,
      dpe.type_installation_ecs,
      dpe.type_energie_ecs,
      dpe.type_generateur_ecs,
      dpe.type_generateur_ecs_anciennete,
      dpe.type_ventilation,
      dpe.type_vitrage,
      dpe.type_materiaux_menuiserie,
      dpe.vitrage_vir,
      dpe.uw,
      dpe.type_isolation_mur_exterieur,
      dpe.materiaux_structure_mur_exterieur,
      dpe.epaisseur_structure_mur_exterieur,
      dpe.u_mur_exterieur,
      dpe.type_isolation_plancher_bas,
      dpe.u_plancher_bas_final_deperditif,
      dpe.type_isolation_plancher_haut,
      dpe.u_plancher_haut_deperditif,
      dpe.type_adjacence_principal_plancher_haut,
      dpe.u_porte,
      dpe.surface_porte,
      dpe.deperdition_mur,
      dpe.deperdition_plancher_haut,
      dpe.deperdition_plancher_bas,
      dpe.deperdition_baie_vitree,
      dpe.deperdition_porte,
      -- QPV
      qpv.nom_quartier                     AS qpv_nom,
      -- Réseau de chaleur
      rcf.id_reseau                        AS reseau_chaleur_id,
      rcf.perimetre_developpement_prioritaire AS reseau_chaleur_prioritaire,
      rcf.indicateur_distance_au_reseau    AS reseau_chaleur_distance,
      -- RPLS
      rpls.rpls_open,
      rpls.classe_ener_principale          AS rpls_classe_ener,
      rpls.classe_ges_principale           AS rpls_classe_ges,
      rpls.accessible_pmr                  AS rpls_accessible_pmr,
      rpls.dans_qpv                        AS rpls_dans_qpv,
      rpls.s_log_hab                       AS rpls_shab_total,
      rpls.nb_classe_ener_a, rpls.nb_classe_ener_b, rpls.nb_classe_ener_c,
      rpls.nb_classe_ener_d, rpls.nb_classe_ener_e, rpls.nb_classe_ener_f,
      rpls.nb_classe_ener_g, rpls.nb_classe_ener_nc,
      -- FFO Bâtiment
      ffo.nb_niveau                        AS nb_niveaux_ffo,
      ffo.mat_toit_txt                     AS materiau_toiture,
      -- Risques
      risk.alea_radon, risk.alea_argile, risk.alea_sismique,
      -- Urbanisme
      urb.contrainte_urbanisme_ac1         AS zone_ac1,
      urb.zone_plu_bati_patrimonial,
      urb.distance_monument_historique,
      urb.denomination_monument_historique,
      -- Fiabilité
      geo.fiabilite_emprise_sol,
      geo.fiabilite_hauteur,
      geo.fiabilite_adresse,
      -- Commune
      bg.libelle_commune_insee             AS commune_nom,
      bg.code_epci_insee
    FROM (SELECT $1::text AS bid) ref
    LEFT JOIN {schema}.batiment_groupe_adresse adr ON adr.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_dpe_representatif_logement dpe ON dpe.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_qpv qpv ON qpv.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_indicateur_reseau_chaud_froid rcf ON rcf.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_rpls rpls ON rpls.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_ffo_bat ffo ON ffo.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_risques risk ON risk.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_urbanisme urb ON urb.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe_geospx geo ON geo.batiment_groupe_id = ref.bid
    LEFT JOIN {schema}.batiment_groupe bg ON bg.batiment_groupe_id = ref.bid
    LIMIT 1;
    """
    try:
        row = await conn.fetchrow(sql, building_id)
        return dict(row) if row else {}
    except Exception as exc:
        logger.warning("BDNB enrichment failed for %s (dept=%s): %s", building_id, dept, exc)
        return {}


async def _fetch_conso_dle(conn: asyncpg.Connection, building_id: str, dept: str) -> list[dict[str, Any]]:
    """Récupère la série temporelle conso réelle élec+gaz (PHASE 2.7).

    Joint les 2 tables multimillésime par année. Sortie : un item par
    année avec les 2 énergies.
    """
    schema = _bdnb_schema(dept)
    if not schema:
        return []
    sql = f"""
    SELECT
      COALESCE(e.millesime, g.millesime) AS annee,
      e.nb_pdl_res AS pdl_elec_residentiel,
      e.conso_res  AS kwh_elec_residentiel,
      g.nb_pdl_res AS pdl_gaz_residentiel,
      g.conso_res  AS kwh_gaz_residentiel
    FROM {schema}.batiment_groupe_dle_elec_multimillesime e
    FULL OUTER JOIN {schema}.batiment_groupe_dle_gaz_multimillesime g
      ON e.batiment_groupe_id = g.batiment_groupe_id AND e.millesime = g.millesime
    WHERE COALESCE(e.batiment_groupe_id, g.batiment_groupe_id) = $1
    ORDER BY annee;
    """
    try:
        rows = await conn.fetch(sql, building_id)
    except Exception as exc:
        logger.warning("DLE conso failed for %s: %s", building_id, exc)
        return []
    return [
        {
            "annee": r["annee"],
            "pdl_elec_residentiel": float(r["pdl_elec_residentiel"]) if r["pdl_elec_residentiel"] is not None else None,
            "kwh_elec_residentiel": float(r["kwh_elec_residentiel"]) if r["kwh_elec_residentiel"] is not None else None,
            "pdl_gaz_residentiel": float(r["pdl_gaz_residentiel"]) if r["pdl_gaz_residentiel"] is not None else None,
            "kwh_gaz_residentiel": float(r["kwh_gaz_residentiel"]) if r["kwh_gaz_residentiel"] is not None else None,
        }
        for r in rows
    ]


@router.get("/{building_id}", response_model=BuildingDetail)
async def get_building(
    building_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> BuildingDetail:
    """Fiche détaillée enrichie : public_data + jointure BDNB dpt + dérivés.

    Voir docs/BUILDING_DATA_INVENTORY.md pour le détail des sources.
    """
    _ = user
    row = await conn.fetchrow(SQL_DETAIL_PUBLIC, building_id)
    if not row:
        raise HTTPException(status_code=404, detail="Bâtiment introuvable.")

    dept = row["dept"]

    # Enrichissement BDNB : asyncpg ne supporte pas les opérations
    # concurrentes sur une même connection → on séquence (~150 ms cumulés,
    # acceptable). Pour paralléliser il faudrait acquérir 2 connections
    # du pool, surdimensionnement pour la démo.
    bdnb_raw = await _fetch_bdnb_enrichment(conn, building_id, dept)
    conso = await _fetch_conso_dle(conn, building_id, dept)
    neigh_rows = await conn.fetch(SQL_NEIGHBORS, building_id)
    neighbors = [
        {
            "building_id": n["building_id"],
            "dpe_classe": n["dpe_classe"],
            "distance_m": float(n["distance_m"]),
        }
        for n in neigh_rows
    ]

    # ---- Scoring (à plat + nesté) ----
    has_score = row["s_co2"] is not None
    if has_score:
        s_co2 = float(row["s_co2"])
        s_faisa = float(row["s_faisa"])
        s_cout = float(row["s_cout"])
        s_social = float(row["s_social"])
        s_passoire = float(row["s_passoire"])
        score_total = _compute_score_total(s_co2, s_faisa, s_cout, s_social, s_passoire)
        co2_evite_t = float(row["co2_evite_t"])
        cout_estime_eur = float(row["cout_estime_eur"])
        cout_eur_par_t_co2 = float(row["cout_eur_par_t_co2"]) if row["cout_eur_par_t_co2"] is not None else None
        confidence = float(row["confidence"])
        incomplete_data = bool(row["incomplete_data"])
        s_faisa_partial = bool(row["s_faisa_partial"])
        missing_fields = list(row["missing_fields"] or [])
        thresholds_version = row["thresholds_version"]
        computed_at = row["computed_at"].isoformat() if row["computed_at"] else None
        score_nested = {
            "s_co2": s_co2,
            "s_faisa": s_faisa,
            "s_cout": s_cout,
            "s_social": s_social,
            "s_passoire": s_passoire,
            "score_total": score_total,
            "co2_evite_t": co2_evite_t,
            "cout_estime_eur": cout_estime_eur,
            "cout_eur_par_t_co2": cout_eur_par_t_co2,
            "confidence": confidence,
            "dpe_source": row["score_dpe_source"],
            "thresholds_version": thresholds_version,
            "incomplete_data": incomplete_data,
            "s_faisa_partial": s_faisa_partial,
            "missing_fields": missing_fields,
            "computed_at": computed_at,
        }
    else:
        s_co2 = s_faisa = s_cout = s_social = s_passoire = None
        score_total = co2_evite_t = cout_estime_eur = cout_eur_par_t_co2 = None
        confidence = None
        incomplete_data = s_faisa_partial = None
        missing_fields = None
        thresholds_version = computed_at = None
        score_nested = None

    # ---- Dérivés économiques (PHASE 2.14) ----
    surface_m2 = float(row["surface_m2"]) if row["surface_m2"] is not None else None
    dpe_kwh = float(row["dpe_kwh_ep_m2_an"]) if row["dpe_kwh_ep_m2_an"] is not None else None
    dpe_co2 = float(row["dpe_kg_co2_m2_an"]) if row["dpe_kg_co2_m2_an"] is not None else None
    cout_energie_annuel = dpe_kwh * surface_m2 * TARIF_KWH_PONDERE if (dpe_kwh and surface_m2) else None
    cout_energie_30 = cout_energie_annuel * 30 if cout_energie_annuel else None
    emissions_30 = (dpe_co2 * surface_m2 * 30 / 1000) if (dpe_co2 and surface_m2) else None

    # DPE expire (arrêté 2021 : valide 10 ans)
    dpe_expire_le: str | None = None
    date_etabli = bdnb_raw.get("date_etablissement_dpe")
    if date_etabli:
        try:
            from datetime import datetime, timedelta

            d = datetime.fromisoformat(date_etabli.replace("Z", "+00:00"))
            dpe_expire_le = (d + timedelta(days=365 * 10)).date().isoformat()
        except Exception:
            dpe_expire_le = None

    # ---- Diagnostic technique (regroupé) ----
    # Cohérence : on remonte tous les champs DPE détaillés en un sous-objet.
    diag_keys = [
        "classe_emission_ges",
        "type_installation_chauffage",
        "type_energie_chauffage",
        "type_generateur_chauffage",
        "type_generateur_chauffage_anciennete",
        "type_installation_ecs",
        "type_energie_ecs",
        "type_generateur_ecs",
        "type_generateur_ecs_anciennete",
        "type_ventilation",
        "type_vitrage",
        "type_materiaux_menuiserie",
        "vitrage_vir",
        "uw",
        "type_isolation_mur_exterieur",
        "materiaux_structure_mur_exterieur",
        "epaisseur_structure_mur_exterieur",
        "u_mur_exterieur",
        "type_isolation_plancher_bas",
        "u_plancher_bas_final_deperditif",
        "type_isolation_plancher_haut",
        "u_plancher_haut_deperditif",
        "type_adjacence_principal_plancher_haut",
        "u_porte",
        "surface_porte",
        "deperdition_mur",
        "deperdition_plancher_haut",
        "deperdition_plancher_bas",
        "deperdition_baie_vitree",
        "deperdition_porte",
    ]
    diag = {k: bdnb_raw.get(k) for k in diag_keys}
    # Cast numerics
    for k in (
        "uw",
        "u_mur_exterieur",
        "u_plancher_bas_final_deperditif",
        "u_plancher_haut_deperditif",
        "u_porte",
        "surface_porte",
        "deperdition_mur",
        "deperdition_plancher_haut",
        "deperdition_plancher_bas",
        "deperdition_baie_vitree",
        "deperdition_porte",
    ):
        if diag.get(k) is not None:
            try:
                diag[k] = float(diag[k])
            except (TypeError, ValueError):
                pass
    diagnostic_technique = diag if any(v is not None for v in diag.values()) else None

    # ---- RPLS ----
    rpls_open = bdnb_raw.get("rpls_open")
    rpls_dict: dict[str, Any] | None = None
    if rpls_open:
        dist = {cls: bdnb_raw.get(f"nb_classe_ener_{cls.lower()}") for cls in ["A", "B", "C", "D", "E", "F", "G"]}
        # Cast int
        dist = {k: int(v) if v is not None else 0 for k, v in dist.items()}
        rpls_dict = {
            "rpls_open": True,
            "classe_ener_principale": bdnb_raw.get("rpls_classe_ener"),
            "classe_ges_principale": bdnb_raw.get("rpls_classe_ges"),
            "accessible_pmr": bdnb_raw.get("rpls_accessible_pmr"),
            "dans_qpv": bool(bdnb_raw.get("rpls_dans_qpv")),
            "shab_total_m2": float(bdnb_raw["rpls_shab_total"])
            if bdnb_raw.get("rpls_shab_total") is not None
            else None,
            "distribution_dpe": dist,
        }

    # ---- QPV (combine rpls.dans_qpv + table qpv.nom_quartier) ----
    dans_qpv = bool(bdnb_raw.get("qpv_nom")) or bool(bdnb_raw.get("rpls_dans_qpv"))
    qpv_nom = bdnb_raw.get("qpv_nom")

    # ---- Réseau chaleur ----
    rcf_id = bdnb_raw.get("reseau_chaleur_id")
    reseau_chaleur_prioritaire = bool(bdnb_raw.get("reseau_chaleur_prioritaire"))

    # ---- Aides éligibles ----
    aides = _aides_eligibles(
        type_proprietaire=row["type_proprietaire"],
        dans_qpv=dans_qpv,
        dpe_classe=row["dpe_classe"],
        nb_logements=row["nb_logements"],
        reseau_chaleur_prioritaire=reseau_chaleur_prioritaire,
    )

    # ---- Risques ----
    risques = {
        "radon": bdnb_raw.get("alea_radon"),
        "argile": bdnb_raw.get("alea_argile"),
        "sismique": bdnb_raw.get("alea_sismique"),
    }

    # ---- Urbanisme ----
    urbanisme = {
        "zone_ac1": bool(bdnb_raw.get("zone_ac1")),
        "zone_plu_bati_patrimonial": bool(bdnb_raw.get("zone_plu_bati_patrimonial")),
        "distance_monument_historique": (
            int(bdnb_raw["distance_monument_historique"])
            if bdnb_raw.get("distance_monument_historique") is not None
            else None
        ),
        "denomination_monument_historique": bdnb_raw.get("denomination_monument_historique"),
    }

    # ---- Fiabilité ----
    fiabilite = {
        "emprise_sol": bdnb_raw.get("fiabilite_emprise_sol"),
        "hauteur": bdnb_raw.get("fiabilite_hauteur"),
        "adresse": bool(bdnb_raw.get("fiabilite_adresse")) if bdnb_raw.get("fiabilite_adresse") is not None else None,
    }

    # ---- Accès chantier ----
    acces_chantier_dict: dict[str, Any] | None = None
    if row["acces_chantier"] is not None:
        acces_chantier_dict = {
            "score": float(row["acces_chantier"]),
            "nearest_largeur_m": (float(row["nearest_largeur_m"]) if row["nearest_largeur_m"] is not None else None),
            "nearest_distance_m": (float(row["nearest_distance_m"]) if row["nearest_distance_m"] is not None else None),
        }

    return BuildingDetail(
        building_id=row["building_id"],
        rnb_id=row["rnb_id"],
        dept=row["dept"],
        code_commune_insee=row["code_commune_insee"],
        code_iris=row["code_iris"],
        commune_nom=bdnb_raw.get("commune_nom"),
        code_epci_insee=bdnb_raw.get("code_epci_insee"),
        bdnb_millesime=row["bdnb_millesime"] or "2025-07.a",
        adresse_postale=bdnb_raw.get("adresse_postale"),
        cle_interop_ban=bdnb_raw.get("cle_interop_ban"),
        surface_m2=surface_m2,
        hauteur_m=float(row["hauteur_m"]) if row["hauteur_m"] is not None else None,
        nb_niveaux_ffo=(int(bdnb_raw["nb_niveaux_ffo"]) if bdnb_raw.get("nb_niveaux_ffo") is not None else None),
        nb_logements=row["nb_logements"],
        annee_constr=row["annee_constr"],
        periode_construction=row["periode_construction"],
        periode_thermique_reglementaire=_periode_thermique(row["annee_constr"]),
        type_principal=row["type_principal"],
        materiau_mur=row["materiau_mur"],
        materiau_toiture=bdnb_raw.get("materiau_toiture"),
        type_proprietaire=row["type_proprietaire"],
        monument_historique=bool(row["monument_historique"]),
        spr=bool(row["spr"]),
        dpe_classe=row["dpe_classe"],
        classe_emission_ges=bdnb_raw.get("classe_emission_ges"),
        dpe_kwh_ep_m2_an=dpe_kwh,
        dpe_kg_co2_m2_an=dpe_co2,
        dpe_coefficient_ep_electricite=float(row["dpe_coefficient_ep_electricite"]),
        dpe_source=row["dpe_source"],
        identifiant_dpe_ademe=bdnb_raw.get("identifiant_dpe_ademe"),
        date_etablissement_dpe=bdnb_raw.get("date_etablissement_dpe"),
        date_reception_dpe=bdnb_raw.get("date_reception_dpe"),
        dpe_expire_le=dpe_expire_le,
        shab_immeuble_m2=(
            float(bdnb_raw["shab_immeuble_m2"]) if bdnb_raw.get("shab_immeuble_m2") is not None else None
        ),
        geom_geojson=row["geom_geojson"] if isinstance(row["geom_geojson"], dict) else json.loads(row["geom_geojson"]),
        centroid_lon=float(row["centroid_lon"]),
        centroid_lat=float(row["centroid_lat"]),
        score_total=score_total,
        s_co2=s_co2,
        s_faisa=s_faisa,
        s_cout=s_cout,
        s_social=s_social,
        s_passoire=s_passoire,
        co2_evite_t=co2_evite_t,
        cout_estime_eur=cout_estime_eur,
        cout_eur_par_t_co2=cout_eur_par_t_co2,
        confidence=confidence,
        incomplete_data=incomplete_data,
        s_faisa_partial=s_faisa_partial,
        missing_fields=missing_fields,
        thresholds_version=thresholds_version,
        computed_at=computed_at,
        score=score_nested,
        neighbors=neighbors,
        dans_qpv=dans_qpv,
        qpv_nom=qpv_nom,
        reseau_chaleur_id=rcf_id,
        reseau_chaleur_prioritaire=reseau_chaleur_prioritaire,
        reseau_chaleur_distance=bdnb_raw.get("reseau_chaleur_distance"),
        diagnostic_technique=diagnostic_technique,
        rpls=rpls_dict,
        conso_reelle_annuelle=conso,
        risques=risques,
        urbanisme=urbanisme,
        fiabilite=fiabilite,
        acces_chantier=acces_chantier_dict,
        cout_energie_annuel_eur=cout_energie_annuel,
        cout_energie_30_ans_eur=cout_energie_30,
        emissions_totales_30_ans_t=emissions_30,
        aides_eligibles=aides,
    )


# ---------------------------------------------------------------------------
# Endpoint classement /api/buildings/:id/rank  (PHASE 2.15, lazy)
# ---------------------------------------------------------------------------


class BuildingRank(BaseModel):
    building_id: str
    score_total: float
    rank_iris: int | None
    total_iris: int | None
    percentile_iris: float | None  # 0.0 (top) → 1.0 (bottom)
    rank_commune: int | None
    total_commune: int | None
    rank_dept: int | None
    total_dept: int | None


# SQL_RANK : décision pragmatique pour la perf —
# - IRIS (~qq centaines de bât) : très rapide (~30 ms)
# - Commune (Lille ~80k bât) : on matérialise UNE FOIS le CTE puis on
#   recompte 2x dessus (rang + total). Évite 2 scans complets ~3 s.
# - Dept : abandonné côté API. Le scan dept 59 = 600k x formule = 5+s,
#   pas justifié pour la valeur UX d'un "rang département". Le frontend
#   affichera juste les rangs IRIS + commune.
#
# Les colonnes total_dept/rank_dept restent dans la réponse mais à null
# pour rétrocompat de la signature.
SQL_RANK = """
WITH ref AS (
  SELECT
    b.building_id, b.code_iris, b.code_commune_insee, b.dept,
    (0.35::float8 * bs.s_co2 + 0.25 * bs.s_faisa + 0.20 * bs.s_cout
     + 0.10 * bs.s_social + 0.10 * bs.s_passoire) AS score
  FROM public_data.buildings b
  JOIN public_data.building_scores bs USING (building_id)
  WHERE b.building_id = $1
),
iris_rows AS MATERIALIZED (
  SELECT (0.35::float8*bs2.s_co2 + 0.25*bs2.s_faisa + 0.20*bs2.s_cout
          + 0.10*bs2.s_social + 0.10*bs2.s_passoire) AS sc
  FROM public_data.buildings b2
  JOIN public_data.building_scores bs2 USING (building_id)
  WHERE b2.code_iris = (SELECT code_iris FROM ref)
),
commune_rows AS MATERIALIZED (
  SELECT (0.35::float8*bs2.s_co2 + 0.25*bs2.s_faisa + 0.20*bs2.s_cout
          + 0.10*bs2.s_social + 0.10*bs2.s_passoire) AS sc
  FROM public_data.buildings b2
  JOIN public_data.building_scores bs2 USING (building_id)
  WHERE b2.code_commune_insee = (SELECT code_commune_insee FROM ref)
)
SELECT
  ref.building_id,
  ref.score,
  (SELECT 1 + COUNT(*) FROM iris_rows i WHERE i.sc > ref.score) AS rk_iris,
  (SELECT COUNT(*) FROM iris_rows) AS n_iris,
  (SELECT 1 + COUNT(*) FROM commune_rows c WHERE c.sc > ref.score) AS rk_commune,
  (SELECT COUNT(*) FROM commune_rows) AS n_commune
FROM ref;
"""


@router.get("/{building_id}/rank", response_model=BuildingRank)
async def get_building_rank(
    building_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> BuildingRank:
    """Classement du bâtiment dans son IRIS, sa commune, son dpt.

    Endpoint séparé pour permettre un appel lazy depuis le frontend (la
    fenêtre du PARTITION peut être lourde sur les grosses communes).
    """
    _ = user
    # `scope` peut être lourd sur Lille (~80k bâtiments scoring) — c'est
    # acceptable car requête à la demande, pas en première page.
    row = await conn.fetchrow(SQL_RANK, building_id)
    if not row:
        raise HTTPException(status_code=404, detail="Bâtiment ou scoring introuvable.")
    rk_iris = int(row["rk_iris"]) if row["rk_iris"] is not None else None
    n_iris = int(row["n_iris"]) if row["n_iris"] is not None else None
    pct_iris = (rk_iris / n_iris) if (rk_iris and n_iris) else None
    return BuildingRank(
        building_id=row["building_id"],
        score_total=float(row["score"]),
        rank_iris=rk_iris,
        total_iris=n_iris,
        percentile_iris=pct_iris,
        rank_commune=int(row["rk_commune"]) if row["rk_commune"] is not None else None,
        total_commune=int(row["n_commune"]) if row["n_commune"] is not None else None,
        # Dept ranking abandonné (cf. commentaire SQL_RANK) — null par convention.
        rank_dept=None,
        total_dept=None,
    )
