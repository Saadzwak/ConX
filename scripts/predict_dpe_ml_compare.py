"""ConX — diagnostic comparatif multi-modèles : 10 bâtiments avec DPE réel,
applique v1, v2, v3 (et tout autre bundle passé en argument), affiche un tableau
avec colonnes REAL | v1 | v2 | v3 | ...

Usage :
    python scripts/predict_dpe_ml_compare.py \
        v1=data/storage/ml/dpe_estimator_v1_baseline_560402f6.pkl \
        v2=data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl \
        v3=data/storage/ml/dpe_estimator_v3_manual_FG_35e2b41a.pkl

Les mêmes building_id sont tirés (seed=42 deterministe dans fetch_sample).
Ne touche PAS la DB.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.features import CLASSE_TO_ORDINAL, build_feature_row  # noqa: E402
from app.ml.predict import load_bundle, predict_batch  # noqa: E402
from app.ml.train import encode_features  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("predict_compare")


def get_conn_str() -> str:
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


def fetch_sample(conn: psycopg.Connection, n: int, seed: int = 42) -> list[dict]:
    sql = """
    SELECT
        b.building_id, b.dept, b.code_commune_insee,
        b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
        b.type_principal, b.materiau_mur, b.type_proprietaire,
        b.monument_historique, b.spr,
        b.dpe_classe AS dpe_classe_real, b.dpe_kwh_ep_m2_an AS dpe_kwh_real,
        d.type_installation_ecs,
        bnt.mean_ordinal AS neighborhood_mean,
        bnt.count AS neighborhood_count
    FROM public_data.buildings b
    LEFT JOIN LATERAL (
        SELECT type_installation_ecs FROM public_data.dpe dpe
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
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (str(seed), n))
        return list(cur)


def features_from_row(row: dict, config) -> dict:
    building = {
        "building_id": row["building_id"],
        "dept": row["dept"],
        "code_commune_insee": row["code_commune_insee"],
        "surface_m2": float(row["surface_m2"])
        if row["surface_m2"] is not None
        else None,
        "hauteur_m": float(row["hauteur_m"]) if row["hauteur_m"] is not None else None,
        "nb_logements": row["nb_logements"],
        "annee_constr": row["annee_constr"],
        "type_principal": row["type_principal"],
        "materiau_mur": row["materiau_mur"],
        "type_proprietaire": row["type_proprietaire"],
        "monument_historique": bool(row["monument_historique"]),
        "spr": bool(row["spr"]) if row["spr"] is not None else False,
    }
    dpe = (
        {"type_installation_ecs": row["type_installation_ecs"]}
        if row["type_installation_ecs"]
        else None
    )
    neighborhood = {
        "mean_ordinal": float(row["neighborhood_mean"])
        if row["neighborhood_mean"] is not None
        else None,
        "count": int(row["neighborhood_count"])
        if row["neighborhood_count"] is not None
        else 0,
    }
    return build_feature_row(building, dpe, neighborhood, config)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    # Parse args : label=path
    bundles: dict[str, object] = {}
    for arg in sys.argv[1:]:
        if "=" not in arg:
            raise SystemExit(f"Argument invalide : {arg!r} — format attendu label=path")
        label, path = arg.split("=", 1)
        bundle = load_bundle(Path(path))
        bundles[label] = bundle
        logger.info(
            f"Bundle {label} chargé (version {bundle.version}, "
            f"acc ±1 = {bundle.metrics['accuracy_plus_minus_1'] * 100:.2f} %)"
        )

    if not bundles:
        raise SystemExit("Aucun bundle chargé.")

    # Tous les bundles partagent la même feature_config (dpts HDF) — on prend le 1er.
    first_bundle = next(iter(bundles.values()))
    feature_config = first_bundle.feature_config

    with psycopg.connect(get_conn_str()) as conn:
        rows = fetch_sample(conn, n=10, seed=42)

    if not rows:
        logger.error("Aucun bâtiment échantillonné.")
        return 1

    # Construit features pour ces 10 bâtiments (une seule fois)
    feature_rows = [features_from_row(r, feature_config) for r in rows]
    df_features = pd.DataFrame(feature_rows)

    # Prédiction par chaque modèle (encodage aligné sur ses dummy_columns à lui)
    predictions_per_label: dict[str, list] = {}
    for label, bundle in bundles.items():
        X, _ = encode_features(df_features, dummy_columns=bundle.dummy_columns)
        X = X.fillna(0.0)
        preds = predict_batch(X, bundle)
        predictions_per_label[label] = preds

    # Affichage
    labels = list(bundles.keys())
    print("\n" + "=" * 130)
    print(f"DIAGNOSTIC COMPARATIF — 10 bâtiments — modèles : {', '.join(labels)}")
    print("=" * 130)
    header = (
        f"{'bg_id (22 chars)':<24} {'dpt':<4} {'annee':<6} "
        f"{'TYPE':<22} {'REAL':<5} "
    )
    for label in labels:
        header += f"{label:<6} "
    header += "Notes"
    print(header)
    print("-" * 130)

    exact_counters: dict[str, int] = dict.fromkeys(labels, 0)
    pm1_counters: dict[str, int] = dict.fromkeys(labels, 0)
    passoire_caught: dict[str, int] = dict.fromkeys(labels, 0)
    passoire_total = 0

    for i, r in enumerate(rows):
        real = r["dpe_classe_real"]
        is_passoire = real in ("F", "G")
        if is_passoire:
            passoire_total += 1
        bg_short = r["building_id"][:22]
        type_short = (r["type_principal"] or "?")[:20]
        line = (
            f"{bg_short:<24} {r['dept']:<4} {r['annee_constr'] or '?':<6} "
            f"{type_short:<22} {real:<5} "
        )
        notes = []
        for label in labels:
            pred = predictions_per_label[label][i].classe_predicted
            line += f"{pred:<6} "
            if pred == real:
                exact_counters[label] += 1
                pm1_counters[label] += 1
                if is_passoire:
                    passoire_caught[label] += 1
            else:
                gap = abs(CLASSE_TO_ORDINAL[pred] - CLASSE_TO_ORDINAL[real])
                if gap <= 1:
                    pm1_counters[label] += 1
                    if is_passoire and pred in ("F", "G"):
                        passoire_caught[label] += 1
                if is_passoire and pred not in ("F", "G"):
                    notes.append(f"{label}: passoire->{pred}")
        line += "  " + " ".join(notes) if notes else ""
        print(line)

    print("-" * 130)
    n = len(rows)
    summary = "  Exact match : "
    summary += " | ".join(f"{label}={exact_counters[label]}/{n}" for label in labels)
    print(summary)
    summary = "  Within ±1   : "
    summary += " | ".join(f"{label}={pm1_counters[label]}/{n}" for label in labels)
    print(summary)
    if passoire_total > 0:
        summary = "  Passoires F/G capturées (exact ou +1 dans F/G) : "
        summary += " | ".join(
            f"{label}={passoire_caught[label]}/{passoire_total}" for label in labels
        )
        print(summary)
    print("=" * 130 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
