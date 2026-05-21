"""ConX — entraînement Random Forest pour estimation DPE (J5).

Pipeline :
1. Charge les bâtiments avec DPE réel (~417 k pour HDF).
2. Joint avec dpe table (energy_chauffage, ECS) et public_data.building_neighborhood pré-calculée
   (mean ordinal classe DPE des k=20 plus proches).
3. Split spatial : 70 % communes en train, 30 % en test (random sur communes uniques).
4. Train RF classifier (cible : classe A..G) + RF regressor (cible : kWh ep/m²/an).
5. Évalue : accuracy ±1, accuracy stricte, MAE, matrice de confusion 7 x 7.
6. Sauvegarde model_<sha8>.pkl + metrics.json.

D-006 + brief J5 :
- Split SPATIAL OBLIGATOIRE (par commune INSEE).
- Random Forest : 200 arbres, max_depth=15, n_jobs=-1, random_state=42.
- Métriques imprimées à la fin → STOP partner validation avant prédiction massive.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import confusion_matrix, mean_absolute_error

from app.ml.features import (
    BOOLEAN_FEATURES,
    CATEGORICAL_FEATURES,
    CLASSE_TO_ORDINAL,
    NUMERIC_FEATURES,
    ORDINAL_TO_CLASSE,
    FeatureConfig,
)

logger = logging.getLogger("ml.train")


# ---------------------------------------------------------------------------
# Hyperparamètres (gravés dans le brief J5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainingConfig:
    n_estimators: int = 200
    max_depth: int = 15
    n_jobs: int = -1
    random_state: int = 42
    test_communes_frac: float = 0.30  # 30 % des communes → test
    neighborhood_k: int = 20  # k=20 voisins (brief J5)


# ---------------------------------------------------------------------------
# Encodage features pour scikit-learn
# ---------------------------------------------------------------------------


def encode_features(df: pd.DataFrame, dummy_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """One-hot encode les categorical features, garde numeric + booleans tels quels.

    Retourne (X_encoded, all_dummy_columns) — all_dummy_columns sert à aligner train et test.

    Si `dummy_columns` est fourni : aligne X sur ces colonnes (ajoute zéros pour celles absentes,
    supprime celles inattendues). Utilisé pour test/inference.
    """
    parts: list[pd.DataFrame] = []
    # Numeric : tels quels (NaN OK)
    parts.append(df[list(NUMERIC_FEATURES)].astype(float))
    # Boolean : True/False/None → 1/0/NaN
    bool_df = df[list(BOOLEAN_FEATURES)].copy()
    for col in BOOLEAN_FEATURES:
        bool_df[col] = bool_df[col].map(lambda v: float(v) if v is not None else np.nan)
    parts.append(bool_df.astype(float))
    # Categorical : one-hot
    cat_df = df[list(CATEGORICAL_FEATURES)].astype(str).fillna("unknown")
    one_hot = pd.get_dummies(cat_df, prefix=list(CATEGORICAL_FEATURES), dummy_na=False)
    parts.append(one_hot)

    X = pd.concat(parts, axis=1)

    if dummy_columns is not None:
        # Aligne sur les colonnes données (utile pour inference)
        for col in dummy_columns:
            if col not in X.columns:
                X[col] = 0
        X = X[dummy_columns]

    return X, list(X.columns)


# ---------------------------------------------------------------------------
# Split spatial par commune INSEE
# ---------------------------------------------------------------------------


def spatial_split(df: pd.DataFrame, test_communes_frac: float, random_state: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sépare le DataFrame en train/test par commune INSEE.

    Garantit : aucune commune ne se retrouve à la fois en train ET en test.
    """
    if "code_commune_insee" not in df.columns:
        raise ValueError("La colonne 'code_commune_insee' est requise pour le split spatial.")
    communes = np.array(df["code_commune_insee"].dropna().unique(), dtype=object)
    rng = np.random.default_rng(random_state)
    rng.shuffle(communes)
    n_test = int(len(communes) * test_communes_frac)
    test_communes = set(communes[:n_test])
    train_mask = ~df["code_commune_insee"].isin(test_communes)
    return df[train_mask].copy(), df[~train_mask].copy()


# ---------------------------------------------------------------------------
# Métriques (brief J5 §4)
# ---------------------------------------------------------------------------


def accuracy_within_n_classes(y_true: pd.Series, y_pred: pd.Series, n: int = 1) -> float:
    """Accuracy ±n classes (par défaut ±1 classe d'écart). Sur ordinal A=1..G=7."""
    y_true_ord = y_true.map(CLASSE_TO_ORDINAL)
    y_pred_ord = y_pred.map(CLASSE_TO_ORDINAL)
    return float(((y_true_ord - y_pred_ord).abs() <= n).mean())


@dataclass
class ModelMetrics:
    accuracy_strict: float  # bonne classe exacte
    accuracy_plus_minus_1: float  # ±1 classe (cible brief J5)
    mae_kwh: float  # MAE régression conso
    confusion_matrix: list[list[int]]  # matrice 7 x 7 (A..G train | A..G pred)
    n_train: int
    n_test: int
    n_train_communes: int
    n_test_communes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy_strict": round(self.accuracy_strict, 4),
            "accuracy_plus_minus_1": round(self.accuracy_plus_minus_1, 4),
            "mae_kwh": round(self.mae_kwh, 2),
            "confusion_matrix": self.confusion_matrix,
            "confusion_matrix_labels": list("ABCDEFG"),
            "n_train": self.n_train,
            "n_test": self.n_test,
            "n_train_communes": self.n_train_communes,
            "n_test_communes": self.n_test_communes,
        }


def evaluate(
    clf: RandomForestClassifier,
    reg: RandomForestRegressor,
    X_test: pd.DataFrame,
    y_test_class: pd.Series,
    y_test_kwh: pd.Series,
    n_train: int,
    n_train_communes: int,
    n_test_communes: int,
) -> ModelMetrics:
    """Calcule les 4 métriques du brief J5 sur le hold-out."""
    y_pred_class = pd.Series(clf.predict(X_test), index=X_test.index)
    y_pred_kwh = reg.predict(X_test)

    acc_strict = float((y_pred_class == y_test_class).mean())
    acc_pm1 = accuracy_within_n_classes(y_test_class, y_pred_class, n=1)
    mae = float(mean_absolute_error(y_test_kwh, y_pred_kwh))
    cm = confusion_matrix(y_test_class, y_pred_class, labels=list("ABCDEFG")).tolist()

    return ModelMetrics(
        accuracy_strict=acc_strict,
        accuracy_plus_minus_1=acc_pm1,
        mae_kwh=mae,
        confusion_matrix=cm,
        n_train=n_train,
        n_test=len(X_test),
        n_train_communes=n_train_communes,
        n_test_communes=n_test_communes,
    )


# ---------------------------------------------------------------------------
# Pipeline d'entraînement complet
# ---------------------------------------------------------------------------


def fit_models(
    df_features: pd.DataFrame,
    config: TrainingConfig,
) -> tuple[RandomForestClassifier, RandomForestRegressor, ModelMetrics, list[str]]:
    """Pipeline complet : split spatial + encode + train + evaluate.

    Args:
        df_features : DataFrame avec features + colonnes 'dpe_classe', 'dpe_kwh_ep_m2_an',
                      'code_commune_insee', 'building_id'.
        config : hyperparamètres.

    Returns:
        (classifier, regressor, metrics, dummy_columns).
        dummy_columns sert à aligner les features lors de l'inférence ultérieure.
    """
    logger.info(f"Pipeline ML : {len(df_features)} rows en entrée.")

    df_train, df_test = spatial_split(df_features, config.test_communes_frac, config.random_state)
    n_train_communes = df_train["code_commune_insee"].nunique()
    n_test_communes = df_test["code_commune_insee"].nunique()
    logger.info(
        f"Split spatial : train={len(df_train)} ({n_train_communes} communes), "
        f"test={len(df_test)} ({n_test_communes} communes)."
    )

    # Vérif anti-fuite spatiale
    train_communes = set(df_train["code_commune_insee"].dropna())
    test_communes = set(df_test["code_commune_insee"].dropna())
    overlap = train_communes & test_communes
    if overlap:
        raise RuntimeError(f"Fuite spatiale détectée : {len(overlap)} communes en commun.")

    # Encode features
    X_train, dummy_columns = encode_features(df_train)
    X_test, _ = encode_features(df_test, dummy_columns=dummy_columns)
    y_train_class = df_train["dpe_classe"]
    y_train_kwh = df_train["dpe_kwh_ep_m2_an"].astype(float)
    y_test_class = df_test["dpe_classe"]
    y_test_kwh = df_test["dpe_kwh_ep_m2_an"].astype(float)

    # Imputation simple des NaN dans les numeric (Random Forest natif n'accepte pas NaN)
    X_train = X_train.fillna(X_train.median(numeric_only=True))
    X_test = X_test.fillna(X_train.median(numeric_only=True))  # même mediane que train

    logger.info(f"X_train shape={X_train.shape}, X_test shape={X_test.shape}")

    # Train classifier
    logger.info(f"Train classifier RF (n_estimators={config.n_estimators}, max_depth={config.max_depth}) ...")
    clf = RandomForestClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        n_jobs=config.n_jobs,
        random_state=config.random_state,
    )
    clf.fit(X_train, y_train_class)
    logger.info("Classifier OK.")

    # Train regressor
    logger.info("Train regressor RF ...")
    reg = RandomForestRegressor(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        n_jobs=config.n_jobs,
        random_state=config.random_state,
    )
    reg.fit(X_train, y_train_kwh)
    logger.info("Regressor OK.")

    # Évaluation
    metrics = evaluate(
        clf,
        reg,
        X_test,
        y_test_class,
        y_test_kwh,
        n_train=len(df_train),
        n_train_communes=n_train_communes,
        n_test_communes=n_test_communes,
    )

    return clf, reg, metrics, dummy_columns


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def model_version_hash(model_bytes: bytes) -> str:
    """SHA256-8 du modèle sérialisé. Stocké dans dpe.model_version."""
    return hashlib.sha256(model_bytes).hexdigest()[:8]


def save_models(
    clf: RandomForestClassifier,
    reg: RandomForestRegressor,
    dummy_columns: list[str],
    feature_config: FeatureConfig,
    metrics: ModelMetrics,
    out_dir: Path,
) -> tuple[Path, str]:
    """Sauvegarde le bundle classifier+regressor+columns+config dans out_dir.

    Returns (path_to_pkl, model_version_short_hash).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "classifier": clf,
        "regressor": reg,
        "dummy_columns": dummy_columns,
        "feature_config": feature_config,
        "metrics": metrics.to_dict(),
        "classe_to_ordinal": CLASSE_TO_ORDINAL,
        "ordinal_to_classe": ORDINAL_TO_CLASSE,
    }
    # Sérialiser une 1ère fois pour calculer le hash, puis renommer
    temp_path = out_dir / "tmp_bundle.pkl"
    joblib.dump(bundle, temp_path, compress=3)
    raw = temp_path.read_bytes()
    version = model_version_hash(raw)
    final_path = out_dir / f"dpe_estimator_{version}.pkl"
    temp_path.rename(final_path)

    metrics_path = out_dir / f"dpe_estimator_{version}_metrics.json"
    metrics_path.write_text(json.dumps(metrics.to_dict(), indent=2), encoding="utf-8")
    return final_path, version
