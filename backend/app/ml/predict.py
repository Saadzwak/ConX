"""ConX — prédiction massive + détection d'anomalies (J5).

Logique séparée du training (train.py) :
- load_bundle()      : charge le .pkl du modèle entraîné.
- predict_batch()    : applique classifier + regressor sur un DataFrame de features.
- detect_anomalies() : applique les 4 règles déterministes (brief J5 §5).
- clip_kwh()         : écrêtage à [0, 800] avec flag (brief J5 §8).

PAS de logique DB ici — c'est dans scripts/predict_dpe_ml.py.

Garde-fous (brief J5 §8) :
- Écrêtage kWh à [0, 800] + flag clipped.
- PAS de clamp dur sur la classe (un G post-2020 peut exister, la règle d'anomalie signale).

Brief J5 §7 — intervalle de confiance :
- classe prédite : argmax predict_proba.
- confidence : probabilité de cette classe.
- predicted_classes_top3 : 3 classes les plus probables (fourchette pour UI).
- kwh : moyenne des prédictions des arbres + quantile 10/90 pour intervalle bootstrap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.ml.features import (
    CLASSE_TO_ORDINAL,
    FeatureConfig,
)

logger = logging.getLogger("ml.predict")


KWH_MIN = 0.0
KWH_MAX = 800.0
NEIGHBORHOOD_OUTLIER_THRESHOLD = 3  # classes d'écart


@dataclass
class Prediction:
    building_id: str
    classe_predicted: str
    confidence: float
    predicted_classes_top3: list[str]  # ordre décroissant par proba
    kwh_predicted: float
    kwh_low_10: float  # quantile 10 % (intervalle bootstrap)
    kwh_high_90: float  # quantile 90 %
    clipped: bool
    anomaly_rt2012_unexpected: bool
    anomaly_re2020_unexpected: bool
    anomaly_pac_low_class: bool
    anomaly_neighborhood_outlier: bool


@dataclass
class ModelBundle:
    classifier: RandomForestClassifier
    regressor: RandomForestRegressor
    dummy_columns: list[str]
    feature_config: FeatureConfig
    metrics: dict[str, Any]
    version: str  # sha256-8 du .pkl


def load_bundle(pkl_path: Path) -> ModelBundle:
    """Charge un .pkl produit par train.save_models."""
    raw = joblib.load(pkl_path)
    # Le hash est dérivé du nom de fichier (`dpe_estimator_<hash>.pkl`).
    name = pkl_path.stem
    version = name.split("_")[-1] if "_" in name else "unknown"
    return ModelBundle(
        classifier=raw["classifier"],
        regressor=raw["regressor"],
        dummy_columns=raw["dummy_columns"],
        feature_config=raw["feature_config"],
        metrics=raw["metrics"],
        version=version,
    )


def predict_batch(
    X: pd.DataFrame,
    bundle: ModelBundle,
) -> list[Prediction]:
    """Prédiction batch : classifier + regressor + top-3 + quantiles.

    Args:
        X : DataFrame déjà encodé via train.encode_features (mêmes dummy_columns).
        bundle : modèle chargé.

    Returns:
        Liste de Prediction (sans building_id ni anomalies — à compléter par le caller).
    """
    clf = bundle.classifier
    reg = bundle.regressor

    # Classification : proba complète + argmax + top-3
    proba = clf.predict_proba(X)  # shape (n, 7)
    classes_order = list(clf.classes_)  # ex: ['A', 'B', ..., 'G']
    argmax_idx = np.argmax(proba, axis=1)
    predicted_classes = [classes_order[i] for i in argmax_idx]
    confidences = proba[np.arange(len(X)), argmax_idx]
    top3_idx = np.argsort(-proba, axis=1)[:, :3]  # 3 plus probables descendant
    top3_classes = [[classes_order[i] for i in row] for row in top3_idx]

    # Régression : moyenne des arbres + quantiles bootstrap
    # Chaque arbre du RF donne une prédiction → on prend mean + percentile.
    n_estimators = len(reg.estimators_)
    tree_preds = np.array([est.predict(X) for est in reg.estimators_])  # (n_trees, n_samples)
    kwh_mean = tree_preds.mean(axis=0)
    kwh_q10 = np.percentile(tree_preds, 10, axis=0)
    kwh_q90 = np.percentile(tree_preds, 90, axis=0)
    logger.debug(f"Régresseur : {n_estimators} arbres, kwh mean range {kwh_mean.min():.0f}-{kwh_mean.max():.0f}")

    results: list[Prediction] = []
    for i in range(len(X)):
        kwh_raw = float(kwh_mean[i])
        kwh_clipped, was_clipped = clip_kwh(kwh_raw)
        results.append(
            Prediction(
                building_id="",  # rempli par le caller
                classe_predicted=predicted_classes[i],
                confidence=float(confidences[i]),
                predicted_classes_top3=top3_classes[i],
                kwh_predicted=kwh_clipped,
                kwh_low_10=float(kwh_q10[i]),
                kwh_high_90=float(kwh_q90[i]),
                clipped=was_clipped,
                anomaly_rt2012_unexpected=False,
                anomaly_re2020_unexpected=False,
                anomaly_pac_low_class=False,
                anomaly_neighborhood_outlier=False,
            )
        )
    return results


def clip_kwh(kwh: float) -> tuple[float, bool]:
    """Écrête à [0, 800] (brief J5 §8). Retourne (valeur_clippee, flag_clipped)."""
    if kwh < KWH_MIN:
        return KWH_MIN, True
    if kwh > KWH_MAX:
        return KWH_MAX, True
    return kwh, False


def detect_anomalies(
    pred: Prediction,
    annee_constr: int | None,
    type_energie_chauffage: str | None,
    neighborhood_ordinal_mean: float | None,
) -> Prediction:
    """Applique les 4 règles d'anomalie (brief J5 §5).

    Mutate la prédiction in place (les flags d'anomalie sont posés).
    Retourne la prédiction modifiée pour chaînage.
    """
    classe = pred.classe_predicted

    # Règle 1 : RT2012 — post-2012 prédit en F ou G
    if annee_constr is not None and annee_constr >= 2012 and classe in ("F", "G"):
        pred.anomaly_rt2012_unexpected = True

    # Règle 2 : RE2020 — post-2020 prédit en E, F, ou G
    if annee_constr is not None and annee_constr >= 2020 and classe in ("E", "F", "G"):
        pred.anomaly_re2020_unexpected = True

    # Règle 3 : PAC + classe F ou G — incohérence chauffage
    if type_energie_chauffage:
        e = type_energie_chauffage.lower()
        if ("pompe" in e or "pac" in e) and classe in ("F", "G"):
            pred.anomaly_pac_low_class = True

    # Règle 4 : écart > 3 classes vs moyenne voisinage
    if neighborhood_ordinal_mean is not None:
        predicted_ordinal = CLASSE_TO_ORDINAL.get(classe)
        if predicted_ordinal is not None:
            diff = abs(predicted_ordinal - neighborhood_ordinal_mean)
            if diff > NEIGHBORHOOD_OUTLIER_THRESHOLD:
                pred.anomaly_neighborhood_outlier = True

    return pred
