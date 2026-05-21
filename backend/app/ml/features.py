"""ConX — feature engineering pour ML estimation DPE (J5).

Features dérivées de BDNB + BD TOPO + voisinage PostGIS :
1. annee_constr (int) + periode_reglementaire (categorical 8 niveaux)
2. surface_m2 (numeric)
3. hauteur_m (numeric, BDNB ou BD TOPO crossvalidée — niveau de cross-val à raffiner J5+)
4. nb_logements (int)
5. type_principal (categorical, normalisé)
6. materiau_mur (categorical)
7. type_proprietaire (categorical)
8. monument_historique (bool)
9. spr (bool)
10. dept (categorical)
11. zone_climatique (categorical H1a/H1b/H2a, dérivée de dept)
12. ecs_individuelle (bool — DPE.type_installation_ecs ou fallback)
13. neighborhood_dpe_class_mean (numeric : classe DPE moyenne du voisinage k=20 en PostGIS)
14. neighborhood_dpe_class_count (int : nb de voisins ayant un DPE réel)

D-006 : seuls ces features sont utilisés. Modifier la liste = décision structurante D-018+.

Fonctions :
- periode_reglementaire(annee) → 'avant_1948' | '1948_1974' | '1974_1982' | ... | 'post_2020'
- zone_climatique(dept, config) → 'H1a' | 'H1b' | ...
- normalize_type_principal(t) → réutilise depuis scoring.compute pour cohérence
- prepare_features(rows) → DataFrame numpy/pandas prêt à donner à RandomForest
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureConfig:
    """Configuration des features ML (chargée depuis config/zone_climatique_dpt.yaml)."""

    dept_to_zone: dict[str, str]
    neighborhood_k: int = 20  # cf. brief J5
    feature_names: tuple[str, ...] = (
        "annee_constr",
        "periode_reglementaire",
        "surface_m2",
        "hauteur_m",
        "nb_logements",
        "type_principal",
        "materiau_mur",
        "type_proprietaire",
        "monument_historique",
        "spr",
        "dept",
        "zone_climatique",
        "ecs_individuelle",
        "neighborhood_dpe_class_mean",
        "neighborhood_dpe_class_count",
    )


def load_feature_config(yaml_path: Path | str) -> FeatureConfig:
    """Charge zone_climatique_dpt.yaml."""
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    return FeatureConfig(dept_to_zone=data["dept_to_zone"])


# ---------------------------------------------------------------------------
# Helpers (fonctions pures)
# ---------------------------------------------------------------------------


def periode_reglementaire(annee: int | None) -> str:
    """Plages réglementaires françaises (RT1974, RT1982, RT1989, RT2000, RT2005, RT2012, RE2020).

    Renvoie 'unknown' si annee=None.
    """
    if annee is None:
        return "unknown"
    if annee < 1948:
        return "avant_1948"
    if annee < 1974:
        return "1948_1974"
    if annee < 1982:
        return "1974_1982"
    if annee < 1989:
        return "1982_1989"
    if annee < 2000:
        return "1989_2000"
    if annee < 2012:
        return "2000_2012"
    if annee < 2020:
        return "2012_2020"
    return "post_2020"


def zone_climatique(dept: str | None, config: FeatureConfig) -> str:
    """Retourne la zone climatique RT/RE pour un département. Défaut 'H1a' si inconnu."""
    if dept is None:
        return "H1a"
    return config.dept_to_zone.get(dept, "H1a")


def normalize_type_principal(t: str | None) -> str:
    """Normalisation alignée avec backend.app.scoring.compute (cohérence cross-modules)."""
    if t is None:
        return "unknown"
    t_low = t.lower()
    if "collectif" in t_low or "appartement" in t_low or "immeuble" in t_low:
        return "residentiel_collectif"
    if "individuel" in t_low or "pavillon" in t_low or "maison" in t_low:
        return "pavillon"
    if "bureau" in t_low:
        return "tertiaire_bureaux"
    if "commerce" in t_low or "magasin" in t_low:
        return "tertiaire_commerce"
    if "industri" in t_low:
        return "industriel"
    return "autre"


def normalize_materiau_mur(m: str | None) -> str:
    """Bucketise BDNB materiau_mur en catégories larges. Texte libre BDNB → ~6 groupes."""
    if m is None:
        return "unknown"
    m_low = m.lower()
    if "beton" in m_low or "béton" in m_low:
        return "beton"
    if "brique" in m_low:
        return "brique"
    if "pierre" in m_low or "moellon" in m_low:
        return "pierre"
    if "bois" in m_low or "ossature_bois" in m_low:
        return "bois"
    if "parpaing" in m_low or "agglo" in m_low:
        return "parpaing"
    if "metal" in m_low or "métal" in m_low or "acier" in m_low:
        return "metal"
    return "autre"


def detect_ecs_individuelle(type_installation_ecs: str | None) -> bool | None:
    """True si ECS individuelle, False si collective, None si inconnu."""
    if type_installation_ecs is None:
        return None
    t = type_installation_ecs.lower()
    if "individuel" in t:
        return True
    if "collectif" in t or "collective" in t:
        return False
    return None


# ---------------------------------------------------------------------------
# Encodage classe DPE → ordinale (pour neighborhood_mean et régression)
# ---------------------------------------------------------------------------


CLASSE_TO_ORDINAL = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
ORDINAL_TO_CLASSE = {v: k for k, v in CLASSE_TO_ORDINAL.items()}


def classe_to_ordinal(classe: str | None) -> int | None:
    if classe is None:
        return None
    return CLASSE_TO_ORDINAL.get(classe)


def ordinal_to_classe(ordinal: float | int) -> str:
    """Arrondit l'ordinal et retourne la classe. Borné [1, 7]."""
    o = int(round(float(ordinal)))
    o = max(1, min(7, o))
    return ORDINAL_TO_CLASSE[o]


# ---------------------------------------------------------------------------
# Feature row builder (pure)
# ---------------------------------------------------------------------------


def build_feature_row(
    building: dict[str, Any],
    dpe: dict[str, Any] | None,
    neighborhood: dict[str, Any] | None,
    config: FeatureConfig,
) -> dict[str, Any]:
    """Assemble un dict de features prêt pour le DataFrame.

    Args:
        building : ligne de public_data.buildings (colonnes attendues : annee_constr, surface_m2,
                   hauteur_m, nb_logements, type_principal, materiau_mur, type_proprietaire,
                   monument_historique, spr, dept, code_commune_insee).
        dpe      : ligne DPE associée (peut être None — dans ce cas ECS = inconnue).
        neighborhood : dict {"mean_ordinal": float | None, "count": int} — pré-calculé via PostGIS.
        config   : FeatureConfig.

    Returns:
        dict {feature_name → value} prêt à être empilé dans un DataFrame pandas.
    """
    annee = building.get("annee_constr")
    type_ecs = (dpe or {}).get("type_installation_ecs")
    ecs_indiv = detect_ecs_individuelle(type_ecs)

    return {
        "annee_constr": annee,
        "periode_reglementaire": periode_reglementaire(annee),
        "surface_m2": building.get("surface_m2"),
        "hauteur_m": building.get("hauteur_m"),
        "nb_logements": building.get("nb_logements"),
        "type_principal": normalize_type_principal(building.get("type_principal")),
        "materiau_mur": normalize_materiau_mur(building.get("materiau_mur")),
        "type_proprietaire": building.get("type_proprietaire") or "unknown",
        "monument_historique": bool(building.get("monument_historique")),
        "spr": bool(building.get("spr")),
        "dept": building.get("dept") or "unknown",
        "zone_climatique": zone_climatique(building.get("dept"), config),
        "ecs_individuelle": ecs_indiv,  # bool | None
        "neighborhood_dpe_class_mean": (neighborhood or {}).get("mean_ordinal"),
        "neighborhood_dpe_class_count": (neighborhood or {}).get("count", 0),
    }


# ---------------------------------------------------------------------------
# Encodage pour scikit-learn (one-hot des catégorielles)
# ---------------------------------------------------------------------------


# Catégorielles à encoder (one-hot via pandas.get_dummies en train)
CATEGORICAL_FEATURES = (
    "periode_reglementaire",
    "type_principal",
    "materiau_mur",
    "type_proprietaire",
    "dept",
    "zone_climatique",
)
NUMERIC_FEATURES = (
    "annee_constr",
    "surface_m2",
    "hauteur_m",
    "nb_logements",
    "neighborhood_dpe_class_mean",
    "neighborhood_dpe_class_count",
)
BOOLEAN_FEATURES = (
    "monument_historique",
    "spr",
    "ecs_individuelle",  # peut être None → NaN
)
