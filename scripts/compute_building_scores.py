"""ConX — pré-calcul batch des composantes scoring sur public_data.buildings.

Stratégie :
1. Charge config/scoring_thresholds.yaml → ScoringThresholds + hash.
2. Détecte les dpts qui ont public_data.topo_roads peuplé (S_faisa.acces_chantier dispo).
3. Pour chaque dpt, parcourt buildings + DPE par chunks (server-side cursor) et UPSERT building_scores.
4. Idempotent : `ON CONFLICT (building_id) DO UPDATE` met à jour si déjà calculé.

Usage :
    python scripts/compute_building_scores.py                    # tous les dpts
    python scripts/compute_building_scores.py 02                 # un dpt
    python scripts/compute_building_scores.py --chunk 5000       # taille de batch
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Permet l'import depuis backend/app/...
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from app.scoring.compute import (  # noqa: E402
    BuildingScoreComponents,
    ScoringThresholds,
    compute_components,
    load_thresholds,
    thresholds_version_hash,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compute_building_scores")

DEFAULT_DEPTS = ["02", "59", "60", "62", "80"]


def get_conn_str() -> str:
    """URL host-side (localhost:5433) pour le script lancé depuis l'hôte."""
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


def detect_has_topo_roads(conn: psycopg.Connection, dept: str) -> bool:
    """True si public_data.topo_roads a au moins une ligne pour ce dpt."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM public_data.topo_roads WHERE dept = %s LIMIT 1;", (dept,)
        )
        return cur.fetchone() is not None


def fetch_buildings_dpe(
    read_conn: psycopg.Connection,
    dept: str,
    chunk: int = 5000,
):
    """Server-side cursor : itère sur tous les bâtiments d'un dpt + DPE log/tert le plus récent.

    Utilise une connexion DÉDIÉE à la lecture (read_conn) pour ne pas perdre le cursor server-side
    quand la write_conn fait des commit() entre batches.

    Yields des dicts {building, dpe} prêts à passer à compute_components.
    """
    sql = """
    SELECT
        b.building_id, b.dept, b.surface_m2, b.hauteur_m, b.annee_constr,
        b.periode_construction, b.type_principal, b.type_proprietaire,
        b.monument_historique, b.spr, b.dpe_classe, b.dpe_kwh_ep_m2_an,
        d.type_dpe, d.type_energie_chauffage, d.type_energie_ecs,
        d.classe_bilan_dpe, d.conso_5_usages_ep_m2_an
    FROM public_data.buildings b
    LEFT JOIN LATERAL (
        SELECT * FROM public_data.dpe dpe
        WHERE dpe.building_id = b.building_id
        ORDER BY dpe.date_etablissement_dpe DESC NULLS LAST
        LIMIT 1
    ) d ON true
    WHERE b.dept = %s
    """
    with read_conn.cursor(name=f"cursor_dept_{dept}", row_factory=dict_row) as cur:
        cur.itersize = chunk
        cur.execute(sql, (dept,))
        for row in cur:
            building = {
                "building_id": row["building_id"],
                "dept": row["dept"],
                "surface_m2": float(row["surface_m2"])
                if row["surface_m2"] is not None
                else None,
                "hauteur_m": float(row["hauteur_m"])
                if row["hauteur_m"] is not None
                else None,
                "annee_constr": row["annee_constr"],
                "periode_construction": row["periode_construction"],
                "type_principal": row["type_principal"],
                "type_proprietaire": row["type_proprietaire"],
                "monument_historique": bool(row["monument_historique"]),
                "spr": bool(row["spr"]) if row["spr"] is not None else False,
                "dpe_classe": row["dpe_classe"],
                "dpe_kwh_ep_m2_an": float(row["dpe_kwh_ep_m2_an"])
                if row["dpe_kwh_ep_m2_an"] is not None
                else None,
            }
            dpe = None
            if row["type_dpe"] is not None:
                dpe = {
                    "type_dpe": row["type_dpe"],
                    "type_energie_chauffage": row["type_energie_chauffage"],
                    "type_energie_ecs": row["type_energie_ecs"],
                    "classe_bilan_dpe": row["classe_bilan_dpe"],
                    "conso_5_usages_ep_m2_an": float(row["conso_5_usages_ep_m2_an"])
                    if row["conso_5_usages_ep_m2_an"] is not None
                    else None,
                }
            yield building, dpe


UPSERT_SQL = """
INSERT INTO public_data.building_scores (
    building_id,
    s_co2, s_faisa, s_cout, s_social, s_passoire,
    co2_evite_t, cout_estime_eur, cout_eur_par_t_co2,
    confidence, dpe_source, thresholds_version,
    incomplete_data, s_faisa_partial, missing_fields,
    computed_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
)
ON CONFLICT (building_id) DO UPDATE SET
    s_co2 = EXCLUDED.s_co2,
    s_faisa = EXCLUDED.s_faisa,
    s_cout = EXCLUDED.s_cout,
    s_social = EXCLUDED.s_social,
    s_passoire = EXCLUDED.s_passoire,
    co2_evite_t = EXCLUDED.co2_evite_t,
    cout_estime_eur = EXCLUDED.cout_estime_eur,
    cout_eur_par_t_co2 = EXCLUDED.cout_eur_par_t_co2,
    confidence = EXCLUDED.confidence,
    dpe_source = EXCLUDED.dpe_source,
    thresholds_version = EXCLUDED.thresholds_version,
    incomplete_data = EXCLUDED.incomplete_data,
    s_faisa_partial = EXCLUDED.s_faisa_partial,
    missing_fields = EXCLUDED.missing_fields,
    computed_at = now();
"""


def upsert_batch(
    conn: psycopg.Connection,
    rows: list[tuple[Any, ...]],
) -> None:
    """Bulk UPSERT d'un batch de tuples building_scores."""
    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, rows)
    conn.commit()


def to_row(
    building_id: str,
    comp: BuildingScoreComponents,
    thresholds_hash: str,
) -> tuple[Any, ...]:
    return (
        building_id,
        comp.s_co2,
        comp.s_faisa,
        comp.s_cout,
        comp.s_social,
        comp.s_passoire,
        comp.co2_evite_t,
        comp.cout_estime_eur,
        comp.cout_eur_par_t_co2,
        comp.confidence,
        comp.dpe_source,
        thresholds_hash,
        comp.incomplete_data,
        comp.s_faisa_partial,
        comp.missing_fields,
    )


def compute_dept(
    read_conn: psycopg.Connection,
    write_conn: psycopg.Connection,
    dept: str,
    thresholds: ScoringThresholds,
    thresholds_hash: str,
    chunk: int,
) -> dict[str, int]:
    """Calcule + UPSERT pour un département entier. Retourne stats."""
    has_topo = detect_has_topo_roads(write_conn, dept)
    logger.info(
        f"Dpt {dept} : démarrage pré-calcul (has_topo_roads={has_topo}, chunk={chunk})"
    )
    start = time.time()

    n_total = 0
    n_incomplete = 0
    n_faisa_partial = 0
    n_real_dpe = 0
    batch: list[tuple[Any, ...]] = []

    for building, dpe in fetch_buildings_dpe(read_conn, dept, chunk=chunk):
        comp = compute_components(building, dpe, thresholds, has_topo_roads=has_topo)
        if comp.incomplete_data:
            n_incomplete += 1
        if comp.s_faisa_partial:
            n_faisa_partial += 1
        if comp.dpe_source == "ademe-real":
            n_real_dpe += 1
        batch.append(to_row(building["building_id"], comp, thresholds_hash))
        n_total += 1
        if len(batch) >= chunk:
            upsert_batch(write_conn, batch)
            batch.clear()
            if n_total % (chunk * 4) == 0:
                logger.info(
                    f"Dpt {dept} : {n_total} traités "
                    f"({n_total / (time.time() - start):.0f}/s)"
                )

    if batch:
        upsert_batch(write_conn, batch)

    elapsed = time.time() - start
    logger.info(
        f"✅ Dpt {dept} : {n_total} bâtiments scorés en {elapsed:.1f}s "
        f"({n_total / elapsed:.0f}/s) — "
        f"incomplete={n_incomplete}, faisa_partial={n_faisa_partial}, real_dpe={n_real_dpe}"
    )
    return {
        "total": n_total,
        "incomplete": n_incomplete,
        "faisa_partial": n_faisa_partial,
        "real_dpe": n_real_dpe,
    }


def apply_migration_008(conn: psycopg.Connection) -> None:
    """Applique 008_create_building_scores.sql si table absente."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public_data' AND table_name='building_scores';
        """)
        if cur.fetchone():
            return
    sql_path = (
        ROOT / "scripts" / "sql" / "migrations" / "008_create_building_scores.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Migration 008_create_building_scores.sql appliquée.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dept", nargs="?", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--chunk", type=int, default=5000)
    args = parser.parse_args()

    thresholds_path = ROOT / "config" / "scoring_thresholds.yaml"
    thresholds = load_thresholds(thresholds_path)
    th_hash = thresholds_version_hash(thresholds)
    logger.info(f"Seuils chargés depuis {thresholds_path.name} (hash {th_hash})")

    conn_str = get_conn_str()
    # 2 connexions : une dédiée à la lecture (server-side cursor durable),
    # l'autre aux UPSERT (commit toutes les `chunk` lignes).
    with psycopg.connect(conn_str, autocommit=False) as read_conn, psycopg.connect(
        conn_str, autocommit=False
    ) as write_conn:
        apply_migration_008(write_conn)
        depts = DEFAULT_DEPTS if (args.all or args.dept is None) else [args.dept]
        agg = {"total": 0, "incomplete": 0, "faisa_partial": 0, "real_dpe": 0}
        for d in depts:
            stats = compute_dept(
                read_conn, write_conn, d, thresholds, th_hash, args.chunk
            )
            for k, v in stats.items():
                agg[k] += v

        logger.info("=" * 60)
        logger.info("Pré-calcul terminé sur tous les dpts demandés.")
        logger.info(f"  Total          : {agg['total']:>10}")
        logger.info(
            f"  Incomplete data: {agg['incomplete']:>10} ({agg['incomplete'] * 100 / max(agg['total'], 1):.1f} %)"
        )
        logger.info(
            f"  Faisa partial  : {agg['faisa_partial']:>10} ({agg['faisa_partial'] * 100 / max(agg['total'], 1):.1f} %)"
        )
        logger.info(
            f"  Avec DPE réel  : {agg['real_dpe']:>10} ({agg['real_dpe'] * 100 / max(agg['total'], 1):.1f} %)"
        )
        logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
