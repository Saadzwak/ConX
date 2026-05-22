"""ConX — endpoints méta (config publique scoring, version, etc.)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..scoring.compute import load_thresholds, thresholds_version_hash

logger = logging.getLogger("conx.routers.meta")

router = APIRouter(prefix="/api/meta", tags=["meta"])

# Lecture unique au démarrage (relire = relancer). Modification = redéploiement.
_THRESHOLDS_PATH = Path(
    os.environ.get("SCORING_THRESHOLDS_PATH", "/app/config/scoring_thresholds.yaml")
)
_THRESHOLDS_CACHE = None


def _get_thresholds():
    global _THRESHOLDS_CACHE
    if _THRESHOLDS_CACHE is None:
        if not _THRESHOLDS_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=f"Fichier seuils introuvable : {_THRESHOLDS_PATH}",
            )
        _THRESHOLDS_CACHE = load_thresholds(_THRESHOLDS_PATH)
    return _THRESHOLDS_CACHE


@router.get("/scoring-config")
async def scoring_config() -> dict:
    """Retourne la config scoring publique : poids par défaut, version, etc.

    Utile pour le frontend qui affiche les sliders avec leurs valeurs initiales
    et qui doit pouvoir comparer `thresholds_version` côté UI vs côté backend.

    Note D-006 : la formule est gravée. Cet endpoint ne permet PAS de modifier
    les seuils — il n'expose que les valeurs en lecture pour pré-remplir l'UI.
    """
    t = _get_thresholds()
    return {
        "version": t.version,
        "version_hash": thresholds_version_hash(t),
        "weights_default": t.weights_default,
        "target_class": {
            "kwh_ep_m2_an": t.target_kwh_ep_m2_an,
            "label": "B",  # cf. config/scoring_thresholds.yaml
        },
        "horizon_amortissement_ans": t.horizon_ans,
        "co2_max_tonnes_30ans": t.co2_max_tonnes_30ans,
        "cost_eur_per_tco2_range": [
            t.cost_min_eur_per_tco2,
            t.cost_max_eur_per_tco2,
        ],
    }
