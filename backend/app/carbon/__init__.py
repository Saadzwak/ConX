"""ConX carbon — calcul déterministe du bilan carbone (J6, D-006).

3 modules :
- exploitation.py : gain CO₂ sur 30 ans (DPE avant → après)
- incorpore.py     : carbone matériaux via FDES statique (D-014)
- evite_horssite.py : carbone évité par préfabrication (CSTB)
- total.py         : bilan agrégé pour l'API/agent

L'IA explique le bilan, ne le calcule jamais (D-006).
"""

from app.carbon.evite_horssite import EviteHorsSiteResult, compute_evite_horssite
from app.carbon.exploitation import ExploitationResult, compute_exploitation
from app.carbon.factors import (
    CLASS_MIDPOINTS_KWH_EP,
    KG_CO2_PER_KWH_EP_BY_ENERGY,
    co2_factor_for_energy,
    normalize_energy,
)
from app.carbon.incorpore import (
    IncorporeResult,
    MaterialQuantity,
    compute_incorpore,
    get_material,
    list_materials,
)
from app.carbon.total import CarbonReport, compute_total, report_to_json

__all__ = [
    # factors
    "CLASS_MIDPOINTS_KWH_EP",
    "KG_CO2_PER_KWH_EP_BY_ENERGY",
    "co2_factor_for_energy",
    "normalize_energy",
    # exploitation
    "ExploitationResult",
    "compute_exploitation",
    # incorpore
    "IncorporeResult",
    "MaterialQuantity",
    "compute_incorpore",
    "get_material",
    "list_materials",
    # evite_horssite
    "EviteHorsSiteResult",
    "compute_evite_horssite",
    # total
    "CarbonReport",
    "compute_total",
    "report_to_json",
]
