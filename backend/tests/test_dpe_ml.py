"""ConX — tests unitaires ML estimation DPE (J5).

Vérifie : (1) features pures, (2) split spatial sans fuite, (3) encodage cohérent train/test.
Ne charge PAS la DB ni le modèle .pkl complet (trop lourd).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.features import (
    CLASSE_TO_ORDINAL,
    ORDINAL_TO_CLASSE,
    build_feature_row,
    classe_to_ordinal,
    detect_ecs_individuelle,
    load_feature_config,
    normalize_materiau_mur,
    normalize_type_principal,
    ordinal_to_classe,
    periode_reglementaire,
    zone_climatique,
)
from app.ml.train import (
    TrainingConfig,
    accuracy_within_n_classes,
    encode_features,
    spatial_split,
)

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = load_feature_config(ROOT / "config" / "zone_climatique_dpt.yaml")


# ---------------------------------------------------------------------------
# Tests fonctions pures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annee,expected",
    [
        (None, "unknown"),
        (1500, "avant_1948"),
        (1947, "avant_1948"),
        (1948, "1948_1974"),
        (1973, "1948_1974"),
        (1974, "1974_1982"),
        (1982, "1982_1989"),
        (2012, "2012_2020"),
        (2020, "post_2020"),
        (2024, "post_2020"),
    ],
)
def test_periode_reglementaire(annee, expected):
    assert periode_reglementaire(annee) == expected


@pytest.mark.parametrize(
    "dept,expected",
    [
        ("02", "H1b"),
        ("59", "H1a"),
        ("60", "H1a"),
        ("62", "H1a"),
        ("80", "H1a"),
        ("75", "H1a"),  # default
        (None, "H1a"),
    ],
)
def test_zone_climatique(dept, expected):
    assert zone_climatique(dept, CONFIG) == expected


@pytest.mark.parametrize(
    "t,expected",
    [
        ("Résidentiel collectif", "residentiel_collectif"),
        ("appartement", "residentiel_collectif"),
        ("Maison individuelle", "pavillon"),
        ("Pavillon", "pavillon"),
        ("Bureau", "tertiaire_bureaux"),
        ("Commerce", "tertiaire_commerce"),
        ("magasin", "tertiaire_commerce"),
        ("Industriel", "industriel"),
        ("Bâtiment agricole", "autre"),
        (None, "unknown"),
    ],
)
def test_normalize_type_principal(t, expected):
    assert normalize_type_principal(t) == expected


@pytest.mark.parametrize(
    "m,expected",
    [
        ("béton armé", "beton"),
        ("Beton", "beton"),
        ("Brique", "brique"),
        ("Pierre", "pierre"),
        ("moellons", "pierre"),
        ("bois", "bois"),
        ("Parpaing", "parpaing"),
        ("Acier", "metal"),
        ("Inconnu", "autre"),
        (None, "unknown"),
    ],
)
def test_normalize_materiau_mur(m, expected):
    assert normalize_materiau_mur(m) == expected


@pytest.mark.parametrize(
    "ecs,expected",
    [
        ("Chauffe-eau individuel", True),
        ("Ballon individuel", True),
        ("Chaudière collective", False),
        ("ECS collective", False),
        (None, None),
        ("Pompe à chaleur", None),
    ],
)
def test_detect_ecs_individuelle(ecs, expected):
    assert detect_ecs_individuelle(ecs) == expected


def test_classe_to_ordinal_and_back():
    for c in "ABCDEFG":
        o = classe_to_ordinal(c)
        assert o is not None
        assert ordinal_to_classe(o) == c


def test_classe_to_ordinal_invalid():
    assert classe_to_ordinal(None) is None
    assert classe_to_ordinal("X") is None


def test_ordinal_to_classe_clip():
    """ordinal_to_classe doit clipper hors-bornes (utile pour predict regression)."""
    assert ordinal_to_classe(0.5) == "A"
    assert ordinal_to_classe(-3) == "A"
    assert ordinal_to_classe(7.9) == "G"
    assert ordinal_to_classe(100) == "G"


def test_build_feature_row_minimal():
    """build_feature_row sur un bâtiment minimal (toutes les colonnes attendues présentes)."""
    building = {
        "annee_constr": 1970,
        "surface_m2": 100.0,
        "hauteur_m": 8.0,
        "nb_logements": 1,
        "type_principal": "Pavillon",
        "materiau_mur": "Brique",
        "type_proprietaire": "particulier",
        "monument_historique": False,
        "spr": False,
        "dept": "59",
    }
    row = build_feature_row(building, None, None, CONFIG)
    assert row["periode_reglementaire"] == "1948_1974"
    assert row["zone_climatique"] == "H1a"
    assert row["type_principal"] == "pavillon"
    assert row["materiau_mur"] == "brique"
    assert row["ecs_individuelle"] is None
    assert row["neighborhood_dpe_class_mean"] is None
    assert row["neighborhood_dpe_class_count"] == 0


# ---------------------------------------------------------------------------
# Tests split spatial (anti-fuite — exigence brief J5 §10)
# ---------------------------------------------------------------------------


def test_spatial_split_no_overlap():
    """test_invariant : aucune commune en commun entre train et test."""
    rng = np.random.default_rng(0)
    # Crée 100 communes, 10 lignes par commune
    df = pd.DataFrame(
        {
            "code_commune_insee": np.repeat([f"C{i:03d}" for i in range(100)], 10),
            "dpe_classe": rng.choice(list("ABCDEFG"), size=1000),
            "dpe_kwh_ep_m2_an": rng.uniform(50, 500, size=1000),
            "annee_constr": rng.integers(1900, 2024, size=1000),
            "surface_m2": rng.uniform(50, 500, size=1000),
            "hauteur_m": rng.uniform(3, 30, size=1000),
            "nb_logements": rng.integers(1, 10, size=1000),
            "type_principal": "pavillon",
            "materiau_mur": "brique",
            "type_proprietaire": "particulier",
            "monument_historique": False,
            "spr": False,
            "dept": "59",
            "zone_climatique": "H1a",
            "periode_reglementaire": "1948_1974",
            "ecs_individuelle": True,
            "neighborhood_dpe_class_mean": 4.0,
            "neighborhood_dpe_class_count": 20,
        }
    )
    train, test = spatial_split(df, test_communes_frac=0.30, random_state=42)
    train_comm = set(train["code_commune_insee"].unique())
    test_comm = set(test["code_commune_insee"].unique())
    assert not (train_comm & test_comm), "FUITE SPATIALE : communes en commun train/test"
    # ~70/30 split sur les communes
    assert 25 <= len(test_comm) <= 35
    assert 65 <= len(train_comm) <= 75


def test_spatial_split_requires_commune():
    """spatial_split sans la colonne code_commune_insee → ValueError."""
    df = pd.DataFrame({"x": [1, 2, 3]})
    with pytest.raises(ValueError, match="code_commune_insee"):
        spatial_split(df, 0.3, 42)


# ---------------------------------------------------------------------------
# Tests encodage features
# ---------------------------------------------------------------------------


def test_encode_features_train_test_alignment():
    """L'encodage de test doit utiliser les mêmes colonnes que train (clé du contrat d'inférence)."""
    df_train = pd.DataFrame(
        {
            "annee_constr": [1970, 1990],
            "surface_m2": [100.0, 80.0],
            "hauteur_m": [8.0, 5.0],
            "nb_logements": [1, 1],
            "neighborhood_dpe_class_mean": [4.0, 3.5],
            "neighborhood_dpe_class_count": [20, 20],
            "monument_historique": [False, False],
            "spr": [False, False],
            "ecs_individuelle": [True, False],
            "periode_reglementaire": ["1948_1974", "1989_2000"],
            "type_principal": ["pavillon", "residentiel_collectif"],
            "materiau_mur": ["brique", "beton"],
            "type_proprietaire": ["particulier", "bailleur_social"],
            "dept": ["59", "62"],
            "zone_climatique": ["H1a", "H1a"],
        }
    )
    df_test = pd.DataFrame(
        {
            "annee_constr": [2000],
            "surface_m2": [120.0],
            "hauteur_m": [10.0],
            "nb_logements": [1],
            "neighborhood_dpe_class_mean": [None],  # NaN dans test, présent dans train
            "neighborhood_dpe_class_count": [0],
            "monument_historique": [True],  # valeur jamais vue en train
            "spr": [False],
            "ecs_individuelle": [None],
            "periode_reglementaire": ["2000_2012"],  # jamais vue en train
            "type_principal": ["pavillon"],
            "materiau_mur": ["pierre"],  # jamais vue en train
            "type_proprietaire": ["particulier"],
            "dept": ["80"],  # jamais vue en train
            "zone_climatique": ["H1a"],
        }
    )
    X_train, dummy_cols = encode_features(df_train)
    X_test, _ = encode_features(df_test, dummy_columns=dummy_cols)
    assert list(X_test.columns) == dummy_cols, "Test doit avoir les mêmes colonnes que train"
    # Catégories test inconnues → colonnes train remplies à 0 (one-hot)
    assert "dept_80" not in X_train.columns
    assert "dept_59" in X_train.columns


# ---------------------------------------------------------------------------
# Tests métrique accuracy ±1
# ---------------------------------------------------------------------------


def test_accuracy_within_n_classes():
    y_true = pd.Series(list("ABCDEFG"))
    y_pred_perfect = pd.Series(list("ABCDEFG"))
    assert accuracy_within_n_classes(y_true, y_pred_perfect, n=1) == 1.0
    assert accuracy_within_n_classes(y_true, y_pred_perfect, n=0) == 1.0
    y_pred_off_by_1 = pd.Series(list("BCDEFGG"))  # 6 off by 1, 1 same
    # Ord: ABCDEFG=1234567, BCDEFGG=2345677 → diff=1111110 (last is 0)
    # All 7 within ±1 → 1.0
    assert accuracy_within_n_classes(y_true, y_pred_off_by_1, n=1) == 1.0
    assert accuracy_within_n_classes(y_true, y_pred_off_by_1, n=0) == pytest.approx(1 / 7)


def test_classe_to_ordinal_consistency():
    """ordinal_to_classe ∘ classe_to_ordinal == identity."""
    for c in "ABCDEFG":
        assert ORDINAL_TO_CLASSE[CLASSE_TO_ORDINAL[c]] == c


def test_training_config_defaults():
    """Hyperparamètres conformes au brief J5."""
    cfg = TrainingConfig()
    assert cfg.n_estimators == 200
    assert cfg.max_depth == 15
    assert cfg.random_state == 42
    assert cfg.test_communes_frac == 0.30
    assert cfg.neighborhood_k == 20
