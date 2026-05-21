"""ConX — bilan carbone total agrégé pour API JSON (J6).

Combine les 3 modules en un payload structuré pour l'agent Plan et l'UI :
  net_30y_kg = - emissions_evitees_horizon_kg (exploitation, signe +)
               + total_kg_co2_eq (incorpore, signe variable)
               - emissions_evitees_kg (hors-site, signe +)
  → net négatif = projet net carbone vertueux sur l'horizon.

NB : par convention dans ConX :
  - "emissions évitées" (exploitation, hors-site) sont des valeurs positives représentant
    du CO₂ qui ne sera pas émis grâce à la rénovation/préfabrication.
  - "total_kg_co2_eq incorporé" est l'algébrique : positif = émissions du procédé,
    négatif = bilan biosourcé favorable.
  - Le **net** est l'émission nette du projet sur l'horizon. Plus c'est négatif, mieux c'est.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.carbon.evite_horssite import EviteHorsSiteResult, compute_evite_horssite
from app.carbon.exploitation import ExploitationResult, compute_exploitation
from app.carbon.factors import (
    DEFAULT_HORIZON_YEARS,
    HORS_SITE_AVOID_FRACTION_MEDIAN,
)
from app.carbon.incorpore import IncorporeResult, MaterialQuantity, compute_incorpore


@dataclass(frozen=True)
class CarbonReport:
    exploitation: ExploitationResult
    incorpore: IncorporeResult
    evite_horssite: EviteHorsSiteResult
    net_kg_co2_eq_horizon: float  # bilan net sur l'horizon (négatif = vertueux)
    horizon_years: int


def compute_total(
    surface_m2: float,
    classe_avant: str | None,
    classe_apres: str,
    materials: list[MaterialQuantity],
    kwh_avant_per_m2_an: float | None = None,
    type_energie_chauffage: str | None = None,
    horizon_years: int = DEFAULT_HORIZON_YEARS,
    horssite_fraction: float = HORS_SITE_AVOID_FRACTION_MEDIAN,
    fdes_path: str | None = None,
) -> CarbonReport:
    """Bilan carbone complet d'un projet de rénovation.

    Args:
        surface_m2 : surface utile du bâtiment.
        classe_avant : DPE avant rénovation (A-G ou None).
        classe_apres : classe cible (A-G).
        materials : liste de MaterialQuantity (FDES + quantités).
        kwh_avant_per_m2_an : DPE réel kWh ep/m²/an (prime sur midpoint si fourni).
        type_energie_chauffage : libellé énergie (pour facteur de conversion).
        horizon_years : horizon d'évaluation (défaut 30 ans).
        horssite_fraction : part hors-site évitée (défaut 0.25 médiane).

    Returns:
        CarbonReport agrégé avec les 3 sous-résultats et le net.
    """
    expl = compute_exploitation(
        surface_m2=surface_m2,
        classe_avant=classe_avant,
        classe_apres=classe_apres,
        kwh_avant_per_m2_an=kwh_avant_per_m2_an,
        type_energie_chauffage=type_energie_chauffage,
        horizon_years=horizon_years,
    )
    inc = compute_incorpore(materials, fdes_path=fdes_path)
    hs = compute_evite_horssite(inc.breakdown, fraction_used=horssite_fraction)

    # Net : convention émissions nettes du projet sur l'horizon (négatif = vertueux)
    # = + carbone incorporé (peut être négatif)
    # - emissions évitées exploitation (toujours positif)
    # - emissions évitées hors-site (toujours positif)
    net = inc.total_kg_co2_eq - expl.emissions_evitees_horizon_kg - hs.emissions_evitees_kg

    return CarbonReport(
        exploitation=expl,
        incorpore=inc,
        evite_horssite=hs,
        net_kg_co2_eq_horizon=round(net, 2),
        horizon_years=horizon_years,
    )


def report_to_json(report: CarbonReport) -> dict:
    """Sérialise un CarbonReport en dict JSON-able (pour l'API et l'agent IA)."""
    return {
        "exploitation": asdict(report.exploitation),
        "incorpore": asdict(report.incorpore),
        "evite_horssite": asdict(report.evite_horssite),
        "summary": {
            "net_kg_co2_eq_horizon": report.net_kg_co2_eq_horizon,
            "net_t_co2_eq_horizon": round(report.net_kg_co2_eq_horizon / 1000.0, 3),
            "horizon_years": report.horizon_years,
            "emissions_evitees_exploitation_t_horizon": round(
                report.exploitation.emissions_evitees_horizon_kg / 1000.0, 3
            ),
            "incorpore_t": round(report.incorpore.total_kg_co2_eq / 1000.0, 3),
            "evite_horssite_t": round(report.evite_horssite.emissions_evitees_kg / 1000.0, 3),
            "biogenic_stored_t": round(report.incorpore.total_biogenic_co2_stored_kg / 1000.0, 3),
            "verdict": "vertueux" if report.net_kg_co2_eq_horizon < 0 else "emissif",
        },
    }
