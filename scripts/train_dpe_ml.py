"""ConX — script d'entraînement ML estimation DPE (J5).

1. Pre-computes neighborhood_dpe_class_mean (k=20) pour les bâtiments avec DPE réel.
   Stockage temporaire dans public_data.dpe_neighborhood_training (TEMP, droppée à la fin).
2. Charge le training set : tous les buildings.dpe_classe IS NOT NULL + features.
3. Split spatial 70/30 par commune INSEE + Train RF classification + régression.
4. Imprime les 4 métriques (accuracy ±1, strict, MAE, confusion 7×7).
5. Sauvegarde data/storage/ml/dpe_estimator_<version>.pkl + metrics.json.

**STOP partner validation requis avant de lancer la prédiction massive sur les 2.7M bâtiments
sans DPE** (cf. brief J5 §11).

Usage :
    python scripts/train_dpe_ml.py
    python scripts/train_dpe_ml.py --quick   # subsample 50k pour test rapide

D-006 + brief J5 : hyperparamètres gravés (200 arbres, max_depth=15, random_state=42).
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

from app.ml.features import (  # noqa: E402
    build_feature_row,
    load_feature_config,
)
from app.ml.train import (  # noqa: E402
    TrainingConfig,
    fit_models,
    save_models,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("train_dpe_ml")


def get_conn_str() -> str:
    user = os.environ.get("POSTGRES_LOCAL_USER", "conx")
    pw = os.environ.get("POSTGRES_LOCAL_PASSWORD", "")
    db = os.environ.get("POSTGRES_LOCAL_DB", "conx")
    port = os.environ.get("POSTGRES_LOCAL_PORT_HOST", "5433")
    return f"postgresql://{user}:{pw}@localhost:{port}/{db}"


def compute_neighborhood_table(conn: psycopg.Connection, k: int = 20) -> None:
    """Pré-calcule la classe DPE moyenne du voisinage k pour les bâtiments avec DPE réel.

    Crée public_data.building_neighborhood_train (PERMANENT — réutilisable pour prédiction).
    Pour chaque bâtiment, KNN PostGIS sur centroid avec k voisins (DPE réel uniquement, excluding self).

    Optimisation : on découpe par dpt pour bénéficier de cache spatial localisé.
    """
    logger.info(
        f"Calcul neighborhood k={k} (peut prendre 15-30 min sur 417k bâtiments) ..."
    )
    start = time.time()

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public_data.building_neighborhood_train (
                building_id text PRIMARY KEY REFERENCES public_data.buildings(building_id),
                mean_ordinal numeric,
                count int,
                computed_at timestamptz DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_bnt_count ON public_data.building_neighborhood_train (count);
        """)
        conn.commit()

        # Check existing count
        cur.execute("SELECT count(*) FROM public_data.building_neighborhood_train;")
        existing = cur.fetchone()[0]
        if existing > 0:
            logger.info(
                f"Table déjà peuplée ({existing} rows). Skip — DROP manuel pour re-compute."
            )
            return

        # Per-dept neighborhood computation
        depts = ["02", "59", "60", "62", "80"]
        for d in depts:
            logger.info(f"Dpt {d} : calcul neighborhood ...")
            t0 = time.time()
            cur.execute(
                """
                INSERT INTO public_data.building_neighborhood_train (building_id, mean_ordinal, count)
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
                  AND b.dpe_classe IS NOT NULL
                  AND b.dpe_kwh_ep_m2_an IS NOT NULL
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
    logger.info(f"Neighborhood pré-calculé en {elapsed_total:.1f}s")


def load_training_dataframe(conn: psycopg.Connection, config) -> pd.DataFrame:
    """Charge tous les bâtiments avec DPE réel + features + neighborhood pré-calculé.

    Retourne un DataFrame pandas prêt à passer à fit_models.
    """
    logger.info("Chargement training data ...")
    sql = """
    SELECT
        b.building_id, b.dept, b.code_commune_insee,
        b.surface_m2, b.hauteur_m, b.nb_logements, b.annee_constr,
        b.type_principal, b.materiau_mur, b.type_proprietaire,
        b.monument_historique, b.spr,
        b.dpe_classe, b.dpe_kwh_ep_m2_an,
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
    """
    rows: list[dict] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        for row in cur:
            building = {
                "building_id": row["building_id"],
                "dept": row["dept"],
                "code_commune_insee": row["code_commune_insee"],
                "surface_m2": float(row["surface_m2"])
                if row["surface_m2"] is not None
                else None,
                "hauteur_m": float(row["hauteur_m"])
                if row["hauteur_m"] is not None
                else None,
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
            features = build_feature_row(building, dpe, neighborhood, config)
            features["dpe_classe"] = row["dpe_classe"]
            features["dpe_kwh_ep_m2_an"] = float(row["dpe_kwh_ep_m2_an"])
            features["code_commune_insee"] = row["code_commune_insee"]
            features["building_id"] = row["building_id"]
            rows.append(features)

    df = pd.DataFrame(rows)
    logger.info(
        f"Training data : {len(df)} rows, {df['code_commune_insee'].nunique()} communes."
    )
    return df


def print_metrics(metrics_dict: dict) -> None:
    """Affichage ASCII des 4 métriques pour le STOP partner.

    ASCII-only (compat Windows cp1252).
    """
    print("\n" + "=" * 60)
    print("METRIQUES HOLD-OUT SPATIAL (cible brief J5 sec 4)")
    print("=" * 60)
    if metrics_dict.get("class_weight") is not None:
        print(f"  class_weight : {metrics_dict['class_weight']}")
    acc_pm1 = metrics_dict["accuracy_plus_minus_1"]
    print(f"  Accuracy +-1 classe         : {acc_pm1 * 100:.2f} %")
    if acc_pm1 >= 0.75:
        print("    -> Statut : OBJECTIF VISE [OK] (deploiement normal, >= 75 %)")
    elif acc_pm1 >= 0.60:
        print("    -> Statut : ACCEPTABLE AVEC AVERTISSEMENT (60-75 %)")
    else:
        print("    -> Statut : EN DESSOUS DU SEUIL (< 60 %, ne pas deployer)")
    print(
        f"  Accuracy stricte            : {metrics_dict['accuracy_strict'] * 100:.2f} %"
    )
    print(f"  MAE consommation kWh ep/m2  : {metrics_dict['mae_kwh']:.1f}")
    print(
        f"  Train rows                  : {metrics_dict['n_train']:,} "
        f"({metrics_dict['n_train_communes']} communes)"
    )
    print(
        f"  Test rows                   : {metrics_dict['n_test']:,} "
        f"({metrics_dict['n_test_communes']} communes)"
    )
    # Per-class accuracy ±1 (critique B-006/D-020)
    if "accuracy_pm1_per_class" in metrics_dict:
        print("\n  Accuracy +-1 PAR CLASSE (D-020 v2 — critere F/G):")
        print(f"      {'Classe':<6} {'n_test':>8} {'±1 %':>8}  Verdict")
        for classe in "ABCDEFG":
            n = metrics_dict["n_per_class"].get(classe, 0)
            acc = metrics_dict["accuracy_pm1_per_class"].get(classe, 0.0)
            verdict = ""
            if classe == "F":
                verdict = "[OK]" if acc >= 0.60 else "[FAIL >=60%]"
            elif classe == "G":
                verdict = "[OK]" if acc >= 0.50 else "[FAIL >=50%]"
            print(f"      {classe:<6} {n:>8,} {acc * 100:>7.2f}%  {verdict}")
    print("\n  Matrice de confusion (lignes = reel A-G | colonnes = predit A-G) :")
    cm = metrics_dict["confusion_matrix"]
    print(f"      {' '.join(f'{c:>6}' for c in 'ABCDEFG')}")
    for i, row in enumerate(cm):
        print(f"   {'ABCDEFG'[i]}  {' '.join(f'{v:>6}' for v in row)}")
    print("=" * 60 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Subsample 50k rows pour test rapide (debug). NE PAS UTILISER en prod.",
    )
    parser.add_argument(
        "--skip-neighborhood",
        action="store_true",
        help="Skip le pré-calcul neighborhood (suppose déjà fait).",
    )
    parser.add_argument(
        "--class-weight",
        default=None,
        help=(
            "Class weight pour le classifier RF. "
            "Valeurs : 'balanced' (sklearn auto, D-020 v2), 'none', "
            'ou JSON dict (ex: \'{"F":3,"G":5}\'). Défaut : None (v1 baseline).'
        ),
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Tag ajouté au nom du pkl (ex: 'v2_balanced'). Sinon, hash seul.",
    )
    args = parser.parse_args()

    # Parse --class-weight
    cw_arg: str | dict | None = None
    if args.class_weight is not None:
        s = args.class_weight.strip()
        if s.lower() in ("none", "null", ""):
            cw_arg = None
        elif s == "balanced":
            cw_arg = "balanced"
        elif s.startswith("{"):
            import json as _json

            cw_arg = _json.loads(s)
        else:
            raise SystemExit(f"--class-weight invalide : {args.class_weight!r}")

    feature_config_path = ROOT / "config" / "zone_climatique_dpt.yaml"
    feature_config = load_feature_config(feature_config_path)
    training_config = TrainingConfig(class_weight=cw_arg)
    logger.info(f"TrainingConfig.class_weight = {training_config.class_weight}")

    out_dir = ROOT / "data" / "storage" / "ml"
    conn_str = get_conn_str()
    with psycopg.connect(conn_str) as conn:
        if not args.skip_neighborhood:
            compute_neighborhood_table(conn, k=training_config.neighborhood_k)
        df = load_training_dataframe(conn, feature_config)

    if args.quick:
        logger.warning(f"MODE QUICK : subsample 50k (was {len(df)}) — debug only.")
        df = df.sample(n=min(50_000, len(df)), random_state=42)

    clf, reg, metrics, dummy_cols = fit_models(df, training_config)
    model_path, version = save_models(
        clf, reg, dummy_cols, feature_config, metrics, out_dir
    )

    # Tag optionnel : rename dpe_estimator_<hash>.pkl en dpe_estimator_<tag>_<hash>.pkl
    if args.tag:
        new_pkl = out_dir / f"dpe_estimator_{args.tag}_{version}.pkl"
        new_json = out_dir / f"dpe_estimator_{args.tag}_{version}_metrics.json"
        model_path.rename(new_pkl)
        (out_dir / f"dpe_estimator_{version}_metrics.json").rename(new_json)
        model_path = new_pkl

    logger.info(f"Modèle sauvegardé : {model_path.name} (version {version})")
    print_metrics(metrics.to_dict())
    print(f"[modele]  {model_path}")
    print(f"[metrics] {model_path.with_suffix('').as_posix()}_metrics.json")
    print("\n[STOP] Validation partenaire requise avant prediction massive.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
