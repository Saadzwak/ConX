"""ConX — calcul carbone évité par la préfabrication hors-site (J6).

Logique :
  Référentiel CSTB/ADEME 2023 : la préfabrication hors-site évite **20-40 % des émissions
  du procédé constructif** (par rapport à un chantier traditionnel équivalent).
  Source : étude CSTB "Construction hors-site et bilan carbone".

  fraction_evitee = 0.25 (médiane) par défaut, peut être surchargée selon retours d'expérience CD2E.
  emissions_evitees_kg = fraction x carbone_incorpore_kg (signé : positif = vraiment évité)

Note méthodologique : on calcule l'évité **sur les émissions positives uniquement** (les matériaux
biosourcés avec bilan négatif n'ont pas d'émissions à éviter — le bénéfice carbone vient déjà
du carbone biogénique stocké). On somme donc kgCO2eq positifs du breakdown FDES.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.carbon.factors import (
    HORS_SITE_AVOID_FRACTION_HIGH,
    HORS_SITE_AVOID_FRACTION_LOW,
    HORS_SITE_AVOID_FRACTION_MEDIAN,
    SOURCE_REFERENCES,
)


@dataclass(frozen=True)
class EviteHorsSiteResult:
    """Résultat carbone évité par la préfabrication."""

    emissions_construction_positives_kg: float  # base de calcul (somme kgCO2eq positifs)
    fraction_evitee_used: float
    emissions_evitees_kg: float
    emissions_evitees_low_kg: float  # fourchette basse (20 %)
    emissions_evitees_high_kg: float  # fourchette haute (40 %)
    hypotheses: dict[str, str]


def compute_evite_horssite(
    incorpore_breakdown: list[dict],
    fraction_used: float = HORS_SITE_AVOID_FRACTION_MEDIAN,
) -> EviteHorsSiteResult:
    """Carbone évité par préfabrication, calculé sur le breakdown carbone incorporé.

    Args:
        incorpore_breakdown : sortie du `compute_incorpore.breakdown` (1 dict par matériau).
        fraction_used : fraction évitée appliquée (défaut 0.25 = médiane CSTB).

    Returns:
        EviteHorsSiteResult avec valeur centrale + fourchette low/high.
    """
    if not 0.0 <= fraction_used <= 1.0:
        raise ValueError(f"fraction_used hors [0,1] : {fraction_used}")

    # Base de calcul : somme des émissions positives du breakdown.
    # Les matériaux biosourcés avec bilan négatif ne sont pas comptés (déjà bénéficiaires).
    base = 0.0
    for entry in incorpore_breakdown:
        co2_total = float(entry.get("kg_co2_eq_total", 0.0))
        if co2_total > 0:
            base += co2_total

    emissions_evitees = base * fraction_used
    emissions_low = base * HORS_SITE_AVOID_FRACTION_LOW
    emissions_high = base * HORS_SITE_AVOID_FRACTION_HIGH

    hypotheses = {
        "fraction_used_pct": f"{fraction_used * 100:.0f}",
        "fraction_low_pct": f"{HORS_SITE_AVOID_FRACTION_LOW * 100:.0f}",
        "fraction_high_pct": f"{HORS_SITE_AVOID_FRACTION_HIGH * 100:.0f}",
        "base_emissions_positives_kg": f"{base:.0f}",
        "source": SOURCE_REFERENCES["cstb_horssite"],
        "convention": (
            "Calculé sur les émissions positives du procédé constructif uniquement. "
            "Les matériaux biosourcés (bilan négatif) ne sont pas comptés dans la base."
        ),
    }

    return EviteHorsSiteResult(
        emissions_construction_positives_kg=round(base, 2),
        fraction_evitee_used=fraction_used,
        emissions_evitees_kg=round(emissions_evitees, 2),
        emissions_evitees_low_kg=round(emissions_low, 2),
        emissions_evitees_high_kg=round(emissions_high, 2),
        hypotheses=hypotheses,
    )
