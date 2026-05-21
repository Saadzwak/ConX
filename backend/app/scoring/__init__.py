"""ConX scoring — calcul déterministe des 5 composantes (cf. docs/SCORING.md).

D-006 : la formule, les poids défaut et les seuils absolus sont gravés.
        L'IA explique le score, ne le calcule jamais.
"""

from app.scoring.compute import (
    BuildingScoreComponents,
    ScoringThresholds,
    compute_components,
    load_thresholds,
    thresholds_version_hash,
)

__all__ = [
    "BuildingScoreComponents",
    "ScoringThresholds",
    "compute_components",
    "load_thresholds",
    "thresholds_version_hash",
]
