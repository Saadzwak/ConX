"""ConX — diagnostic ML : applique le modèle entraîné à N bâtiments aléatoires AVEC DPE réel,
imprime la prédiction vs la réalité + flags d'anomalie. Ne touche PAS la DB.

Sert à la validation partenaire post-training (brief J5 §11 — STOP avant prédiction massive).

Usage :
    python scripts/predict_dpe_ml_sample.py <model.pkl>
    python scripts/predict_dpe_ml_sample.py data/storage/ml/dpe_estimator_560402f6.pkl --n 10

Pour la prédiction massive (POST validation partenaire) :
    voir scripts/predict_dpe_ml.py (sera créé après le GO).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.features import build_feature_row  # noqa: E402
from app.ml.predict import (  # noqa: E402
    detect_anomalies,
    load_bundle,
    predict_batch,
)
from app.ml.train import encode_features  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("predict_dpe_ml_sample")


def get_conn_str() -> str:
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


def fetch_sample(conn: psycopg.Connection, n: int, seed: int = 42) -> list[dict]:
    """N bâtiments tirés au hasard avec real DPE + neighborhood + features."""
    sql = """
    SELECT
        b.building_id, b.dept, b.code_commune_insee,
        b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
        b.type_principal, b.materiau_mur, b.type_proprietaire,
        b.monument_historique, b.spr,
        b.dpe_classe AS dpe_classe_real, b.dpe_kwh_ep_m2_an AS dpe_kwh_real,
        d.type_installation_ecs, d.type_energie_chauffage,
        bnt.mean_ordinal AS neighborhood_mean,
        bnt.count AS neighborhood_count
    FROM public_data.buildings b
    LEFT JOIN LATERAL (
        SELECT type_installation_ecs, type_energie_chauffage
        FROM public_data.dpe dpe
        WHERE dpe.building_id = b.building_id AND dpe.source = 'ademe-real'
        LIMIT 1
    ) d ON true
    LEFT JOIN public_data.building_neighborhood_train bnt ON bnt.building_id = b.building_id
    WHERE b.dpe_classe IS NOT NULL
      AND b.dpe_kwh_ep_m2_an IS NOT NULL
      AND b.code_commune_insee IS NOT NULL
    ORDER BY md5(b.building_id || %s::text)
    LIMIT %s;
    """
    rows: list[dict] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (str(seed), n))
        rows = list(cur)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to .pkl model bundle")
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    bundle = load_bundle(Path(args.model))
    logger.info(
        f"Modèle {bundle.version} chargé "
        f"(accuracy +-1: {bundle.metrics['accuracy_plus_minus_1'] * 100:.2f} %)"
    )

    with psycopg.connect(get_conn_str()) as conn:
        rows = fetch_sample(conn, args.n)

    if not rows:
        logger.error("Aucun bâtiment échantillonné — DB vide ?")
        return 1

    # Construit features
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
        dpe = (
            {"type_installation_ecs": r["type_installation_ecs"]}
            if r["type_installation_ecs"]
            else None
        )
        neighborhood = {
            "mean_ordinal": float(r["neighborhood_mean"])
            if r["neighborhood_mean"] is not None
            else None,
            "count": int(r["neighborhood_count"])
            if r["neighborhood_count"] is not None
            else 0,
        }
        f = build_feature_row(building, dpe, neighborhood, bundle.feature_config)
        feature_rows.append(f)

    df = pd.DataFrame(feature_rows)
    X, _ = encode_features(df, dummy_columns=bundle.dummy_columns)
    X = X.fillna(0.0)

    predictions = predict_batch(X, bundle)

    # Anomalies + assoc
    for i, pred in enumerate(predictions):
        pred.building_id = rows[i]["building_id"]
        detect_anomalies(
            pred,
            annee_constr=rows[i]["annee_constr"],
            type_energie_chauffage=rows[i]["type_energie_chauffage"],
            neighborhood_ordinal_mean=float(rows[i]["neighborhood_mean"])
            if rows[i]["neighborhood_mean"] is not None
            else None,
        )

    # Affichage
    print("\n" + "=" * 100)
    print(
        f"DIAGNOSTIC ML — {args.n} bâtiments échantillonnés (model version {bundle.version})"
    )
    print("=" * 100)
    print(
        f"{'bg_id (12 first chars)':<24} {'dept':<5} {'annee':<6} "
        f"{'TYPE':<22} {'REAL':<6} {'PRED':<6} {'CONF':<6} {'kWh-r':<7} {'kWh-p':<7} {'IC10-90':<14} ANOMALIES"
    )
    print("-" * 100)
    correct = 0
    pm1 = 0
    for r, pred in zip(rows, predictions, strict=True):
        bg_short = r["building_id"][:22]
        real = r["dpe_classe_real"]
        pred_c = pred.classe_predicted
        if real == pred_c:
            correct += 1
        from app.ml.features import CLASSE_TO_ORDINAL as C

        if abs(C[real] - C[pred_c]) <= 1:
            pm1 += 1
        anomalies = []
        if pred.anomaly_rt2012_unexpected:
            anomalies.append("RT2012")
        if pred.anomaly_re2020_unexpected:
            anomalies.append("RE2020")
        if pred.anomaly_pac_low_class:
            anomalies.append("PAC")
        if pred.anomaly_neighborhood_outlier:
            anomalies.append("NEIGH")
        if pred.clipped:
            anomalies.append("CLIPPED")
        anomalies_str = ",".join(anomalies) if anomalies else "-"
        type_short = (r["type_principal"] or "?")[:20]
        print(
            f"{bg_short:<24} {r['dept']:<5} {r['annee_constr'] or '?':<6} "
            f"{type_short:<22} {real:<6} {pred_c:<6} {pred.confidence:<6.2f} "
            f"{int(r['dpe_kwh_real']):<7} {int(pred.kwh_predicted):<7} "
            f"[{int(pred.kwh_low_10):>3},{int(pred.kwh_high_90):>3}]   {anomalies_str}"
        )
    print("-" * 100)
    print(f"  Exact match : {correct}/{args.n}   |   Within +-1 : {pm1}/{args.n}")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
