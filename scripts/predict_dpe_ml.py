"""ConX — prédiction massive ML DPE sur les bâtiments sans DPE réel HDF (J5 phase 2).

Pipeline :
1. Vérifie que `public_data.dpe` ne contient PAS encore de ligne `source='ml-predicted'` (idempotent).
2. Pré-calcule `public_data.building_neighborhood_predict` (k=20 KNN sur les bâtiments avec DPE réel),
   pour tous les bâtiments SANS DPE.
3. Charge le bundle v2 (`dpe_estimator_v2_balanced_de48d81c.pkl` par défaut).
4. Itère par chunks de 50 000 bâtiments : build features → encode_features (dummy_columns alignés)
   → predict_batch → 4 règles d'anomalie → écrêtage [0, 800] kWh → INSERT public_data.dpe
   (source='ml-predicted', identifiant_dpe='ml-pred-<building_id>') + UPDATE public_data.buildings
   (dpe_classe, dpe_kwh_ep_m2_an, dpe_source — uniquement WHERE dpe_classe IS NULL).
5. **Garde-fous critiques** :
   - Aucune ligne `source='ademe-real'` ne doit être touchée (test invariant pré/post).
   - UPDATE buildings filtre strictement `WHERE dpe_classe IS NULL`.
   - INSERT dpe utilise `ON CONFLICT (building_id, identifiant_dpe) DO NOTHING` → idempotent.

Usage :
    python scripts/predict_dpe_ml.py --all
    python scripts/predict_dpe_ml.py --dept 02      # limite à un dpt
    python scripts/predict_dpe_ml.py --all --dry-run   # ne touche pas la DB
    python scripts/predict_dpe_ml.py --all --model data/storage/ml/dpe_estimator_v3_manual_FG_35e2b41a.pkl

D-017, D-020, D-021 — modèle retenu : v2 (`class_weight='balanced'`).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.features import build_feature_row, load_feature_config  # noqa: E402
from app.ml.predict import detect_anomalies, load_bundle, predict_batch  # noqa: E402
from app.ml.train import encode_features  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("predict_dpe_ml")


DEFAULT_MODEL = (
    ROOT / "data" / "storage" / "ml" / "dpe_estimator_v2_balanced_de48d81c.pkl"
)
BATCH_SIZE = 50_000


def get_conn_str() -> str:
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


def compute_neighborhood_predict(conn: psycopg.Connection, k: int = 20) -> None:
    """Pré-calcule la classe DPE moyenne du voisinage k pour les bâtiments SANS DPE réel.

    Table dédiée `public_data.building_neighborhood_predict` (PERMANENT — idempotente via PK).
    Voisins candidats : bâtiments AVEC DPE réel (`dpe_classe IS NOT NULL`).
    """
    logger.info(f"Calcul neighborhood (predict) k={k} sur ~2.7 M bâtiments...")
    start = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public_data.building_neighborhood_predict (
                building_id text PRIMARY KEY REFERENCES public_data.buildings(building_id),
                mean_ordinal numeric,
                count int,
                computed_at timestamptz DEFAULT now()
            );
        """)
        conn.commit()

        cur.execute("SELECT count(*) FROM public_data.building_neighborhood_predict;")
        existing = cur.fetchone()[0]
        if existing > 0:
            logger.info(
                f"Table déjà peuplée ({existing} rows). Skip — DROP manuel pour re-compute."
            )
            return

        depts = ["02", "59", "60", "62", "80"]
        for d in depts:
            logger.info(f"Dpt {d} : calcul neighborhood predict ...")
            t0 = time.time()
            cur.execute(
                """
                INSERT INTO public_data.building_neighborhood_predict (building_id, mean_ordinal, count)
                SELECT
                    b.building_id,
                    (
                        SELECT AVG(CASE nb.dpe_classe
                                    WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4
                                    WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 END)::numeric
                        FROM (
                            SELECT nb2.dpe_classe
                            FROM public_data.buildings nb2
                            WHERE nb2.dpe_classe IS NOT NULL
                              AND nb2.building_id <> b.building_id
                            ORDER BY b.centroid <-> nb2.centroid
                            LIMIT %s
                        ) nb
                    ) AS mean_ordinal,
                    %s AS count
                FROM public_data.buildings b
                WHERE b.dept = %s
                  AND b.dpe_classe IS NULL
                  AND b.code_commune_insee IS NOT NULL
                ON CONFLICT (building_id) DO NOTHING;
                """,
                (k, k, d),
            )
            conn.commit()
            n = cur.rowcount
            elapsed = time.time() - t0
            logger.info(
                f"Dpt {d} : {n} rows insérées en {elapsed:.1f}s ({n / max(elapsed, 1):.0f}/s)"
            )
    elapsed_total = time.time() - start
    logger.info(f"Neighborhood predict pré-calculé en {elapsed_total / 60:.1f} min")


def fetch_batch(
    conn: psycopg.Connection,
    dept_filter: str | None,
    offset: int,
    limit: int,
) -> list[dict]:
    """Charge un batch de bâtiments SANS DPE, avec features + neighborhood predict."""
    sql = """
    SELECT
        b.building_id, b.dept, b.code_commune_insee,
        b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
        b.type_principal, b.materiau_mur, b.type_proprietaire,
        b.monument_historique, b.spr,
        bnp.mean_ordinal AS neighborhood_mean,
        bnp.count AS neighborhood_count
    FROM public_data.buildings b
    LEFT JOIN public_data.building_neighborhood_predict bnp
      ON bnp.building_id = b.building_id
    WHERE b.dpe_classe IS NULL
      AND b.code_commune_insee IS NOT NULL
    """
    params: list = []
    if dept_filter is not None:
        sql += " AND b.dept = %s"
        params.append(dept_filter)
    sql += " ORDER BY b.building_id OFFSET %s LIMIT %s;"
    params.extend([offset, limit])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return list(cur)


def build_features_df(rows: list[dict], feature_config) -> pd.DataFrame:
    """Convertit les rows DB en DataFrame de features prêt pour encode_features."""
    feature_rows = []
    for r in rows:
        building = {
            "building_id": r["building_id"],
            "dept": r["dept"],
            "code_commune_insee": r["code_commune_insee"],
            "surface_m2": float(r["surface_m2"])
            if r["surface_m2"] is not None
            else None,
            "hauteur_m": float(r["hauteur_m"]) if r["hauteur_m"] is not None else None,
            "nb_logements": r["nb_logements"],
            "annee_constr": r["annee_constr"],
            "type_principal": r["type_principal"],
            "materiau_mur": r["materiau_mur"],
            "type_proprietaire": r["type_proprietaire"],
            "monument_historique": bool(r["monument_historique"]),
            "spr": bool(r["spr"]) if r["spr"] is not None else False,
        }
        # ECS info non disponible côté predict (vient de la table dpe ademe-real qui n'existe pas pour
        # ces bâtiments). On passe None (sera encodé en 'unknown' dans le one-hot).
        neighborhood = {
            "mean_ordinal": float(r["neighborhood_mean"])
            if r["neighborhood_mean"] is not None
            else None,
            "count": int(r["neighborhood_count"])
            if r["neighborhood_count"] is not None
            else 0,
        }
        f = build_feature_row(building, None, neighborhood, feature_config)
        feature_rows.append(f)
    return pd.DataFrame(feature_rows)


def upsert_predictions(
    conn: psycopg.Connection,
    rows: list[dict],
    predictions,
    model_version: str,
) -> tuple[int, int]:
    """INSERT public_data.dpe + UPDATE public_data.buildings.

    Returns (n_inserted_dpe, n_updated_buildings).
    """
    insert_rows = []
    update_rows = []
    for r, pred in zip(rows, predictions, strict=True):
        bid = r["building_id"]
        insert_rows.append(
            (
                bid,
                f"ml-pred-{bid}",  # identifiant_dpe synthétique
                r["dept"],
                pred.classe_predicted,
                pred.kwh_predicted,
                "ml-predicted",
                model_version,
                pred.confidence,
                pred.predicted_classes_top3,
                pred.clipped,
                pred.anomaly_rt2012_unexpected,
                pred.anomaly_re2020_unexpected,
                pred.anomaly_pac_low_class,
                pred.anomaly_neighborhood_outlier,
            )
        )
        update_rows.append((pred.classe_predicted, pred.kwh_predicted, bid))

    n_inserted = 0
    n_updated = 0
    with conn.cursor() as cur:
        # INSERT
        cur.executemany(
            """
            INSERT INTO public_data.dpe (
                building_id, identifiant_dpe, dept,
                classe_bilan_dpe, conso_5_usages_ep_m2_an,
                source, model_version, confidence, prediction_date,
                predicted_classes_top3, clipped,
                anomaly_rt2012_unexpected, anomaly_re2020_unexpected,
                anomaly_pac_low_class, anomaly_neighborhood_outlier
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s)
            ON CONFLICT (building_id, identifiant_dpe) DO NOTHING;
            """,
            insert_rows,
        )
        n_inserted = cur.rowcount

        # UPDATE buildings — STRICT garde-fou : uniquement WHERE dpe_classe IS NULL
        cur.executemany(
            """
            UPDATE public_data.buildings
            SET dpe_classe = %s,
                dpe_kwh_ep_m2_an = %s,
                dpe_source = 'ml-predicted'
            WHERE building_id = %s
              AND dpe_classe IS NULL;
            """,
            update_rows,
        )
        n_updated = cur.rowcount
    return n_inserted, n_updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all", action="store_true", help="Prédit tous les bâtiments SANS DPE (2.7 M)."
    )
    parser.add_argument(
        "--dept",
        default=None,
        help="Limite à un dpt (02/59/60/62/80). Par défaut : tous.",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help=f"Chemin du modèle .pkl (défaut : {DEFAULT_MODEL.name}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Aucun INSERT/UPDATE DB. Affiche les stats prédictives.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Taille des chunks (défaut {BATCH_SIZE}).",
    )
    parser.add_argument(
        "--skip-neighborhood",
        action="store_true",
        help="Skip le pré-calcul neighborhood predict (suppose déjà fait).",
    )
    args = parser.parse_args()

    if not args.all and not args.dept:
        raise SystemExit("Précise --all ou --dept <code>.")

    model_path = Path(args.model)
    if not model_path.exists():
        raise SystemExit(f"Modèle introuvable : {model_path}")

    feature_config = load_feature_config(ROOT / "config" / "zone_climatique_dpt.yaml")
    bundle = load_bundle(model_path)
    logger.info(
        f"Bundle chargé : {model_path.name} (version {bundle.version}, "
        f"acc ±1 = {bundle.metrics['accuracy_plus_minus_1'] * 100:.2f} %)"
    )

    conn_str = get_conn_str()
    with psycopg.connect(conn_str) as conn:
        # 1. Vérif état initial
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public_data.dpe WHERE source='ademe-real';"
            )
            ademe_count_before = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM public_data.dpe WHERE source='ml-predicted';"
            )
            ml_count_before = cur.fetchone()[0]
        logger.info(
            f"État initial : {ademe_count_before:,} lignes ademe-real, "
            f"{ml_count_before:,} lignes ml-predicted."
        )
        if ml_count_before > 0 and not args.dry_run:
            logger.warning(
                f"⚠ {ml_count_before:,} lignes ml-predicted DÉJÀ présentes — "
                "ON CONFLICT skippera les doublons."
            )

        # 2. Neighborhood predict
        if not args.skip_neighborhood:
            compute_neighborhood_predict(conn, k=20)

        # 3. Total à prédire
        with conn.cursor() as cur:
            sql_count = (
                "SELECT count(*) FROM public_data.buildings "
                "WHERE dpe_classe IS NULL AND code_commune_insee IS NOT NULL"
            )
            params: list = []
            if args.dept is not None:
                sql_count += " AND dept = %s"
                params.append(args.dept)
            cur.execute(sql_count, params)
            total_to_predict = cur.fetchone()[0]
        logger.info(f"À prédire : {total_to_predict:,} bâtiments.")

        # 4. Boucle batches
        offset = 0
        global_inserted = 0
        global_updated = 0
        anomaly_counts = {
            "rt2012": 0,
            "re2020": 0,
            "pac": 0,
            "neighborhood": 0,
            "clipped": 0,
        }
        class_counts: dict[str, int] = {}
        start = time.time()

        while offset < total_to_predict:
            t0 = time.time()
            rows = fetch_batch(conn, args.dept, offset, args.batch_size)
            if not rows:
                break

            df_features = build_features_df(rows, feature_config)
            X, _ = encode_features(df_features, dummy_columns=bundle.dummy_columns)
            X = X.fillna(0.0)
            predictions = predict_batch(X, bundle)

            # Anomalies — on a besoin de type_energie_chauffage (non-disponible côté predict, NULL).
            for i, pred in enumerate(predictions):
                pred.building_id = rows[i]["building_id"]
                neighborhood_mean = (
                    float(rows[i]["neighborhood_mean"])
                    if rows[i]["neighborhood_mean"] is not None
                    else None
                )
                detect_anomalies(
                    pred,
                    annee_constr=rows[i]["annee_constr"],
                    type_energie_chauffage=None,  # pas dispo côté predict
                    neighborhood_ordinal_mean=neighborhood_mean,
                )
                # Stats
                class_counts[pred.classe_predicted] = (
                    class_counts.get(pred.classe_predicted, 0) + 1
                )
                if pred.anomaly_rt2012_unexpected:
                    anomaly_counts["rt2012"] += 1
                if pred.anomaly_re2020_unexpected:
                    anomaly_counts["re2020"] += 1
                if pred.anomaly_pac_low_class:
                    anomaly_counts["pac"] += 1
                if pred.anomaly_neighborhood_outlier:
                    anomaly_counts["neighborhood"] += 1
                if pred.clipped:
                    anomaly_counts["clipped"] += 1

            if not args.dry_run:
                inserted, updated = upsert_predictions(
                    conn, rows, predictions, bundle.version
                )
                conn.commit()
                global_inserted += inserted
                global_updated += updated
            else:
                global_inserted += len(rows)
                global_updated += len(rows)

            elapsed = time.time() - t0
            offset += len(rows)
            pct = 100 * offset / total_to_predict
            logger.info(
                f"  [{pct:5.1f}%] offset={offset:>8,} : "
                f"{len(rows):>5} bât. en {elapsed:.1f}s "
                f"({len(rows) / max(elapsed, 0.01):.0f}/s)"
            )

        elapsed_total = time.time() - start
        logger.info(
            f"Boucle terminée en {elapsed_total / 60:.1f} min "
            f"(global_inserted={global_inserted:,} dpe rows, "
            f"global_updated={global_updated:,} buildings rows)"
        )

        # 5. Garde-fou critique : aucun ademe-real touché
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public_data.dpe WHERE source='ademe-real';"
            )
            ademe_count_after = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM public_data.dpe WHERE source='ml-predicted';"
            )
            ml_count_after = cur.fetchone()[0]
        if ademe_count_after != ademe_count_before:
            logger.error(
                f"⚠⚠⚠ INVARIANT BRISÉ : ademe-real count changé "
                f"({ademe_count_before} → {ademe_count_after}). "
                "ROLLBACK manuel requis."
            )
            return 2
        logger.info(
            f"✓ Garde-fou OK : ademe-real intouché ({ademe_count_after:,}). "
            f"ml-predicted : {ml_count_before:,} → {ml_count_after:,} "
            f"(+{ml_count_after - ml_count_before:,})."
        )

        # 6. Stats finales
        print("\n" + "=" * 70)
        print(" STATS PREDICTION MASSIVE — model version " + bundle.version)
        print("=" * 70)
        print(f"  Total prédits         : {sum(class_counts.values()):,}")
        print(f"  Dpe rows insérés      : {global_inserted:,}")
        print(f"  Buildings mis à jour  : {global_updated:,}")
        print("\n  Distribution classes prédites :")
        for c in "ABCDEFG":
            n = class_counts.get(c, 0)
            pct = 100 * n / max(sum(class_counts.values()), 1)
            print(f"    {c} : {n:>9,}  ({pct:5.2f} %)")
        print("\n  Anomalies déclenchées :")
        for name, count in anomaly_counts.items():
            pct = 100 * count / max(sum(class_counts.values()), 1)
            print(f"    {name:<14} : {count:>9,}  ({pct:5.2f} %)")
        if args.dry_run:
            print("\n  [DRY-RUN] Aucun changement persisté en DB.")
        print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
