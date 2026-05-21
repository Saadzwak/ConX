"""ConX — facteurs d'émission ADEME Base Carbone + midpoints DPE (J6).

Sources :
- ADEME Base Carbone 2023 (https://base-carbone.ademe.fr/), facteurs PCI moyens France.
- Bornes DPE arrêté 2021 (avec coefficient EP électricité 1.9 anticipé 2026, cf. CLAUDE.md).
- Référentiels CSTB/ADEME pour la part "hors-site évité" (fourchette 20-40 %, médiane 25 %).

Toutes les valeurs sont **gravées et citées** dans l'UI quand un chiffre apparaît (D-006).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Midpoints kWh ep/m²/an par classe DPE (bornes officielles arrêté 2021 / 1.9)
# ---------------------------------------------------------------------------
# Identiques à `backend/app/scoring/compute.py` class_midpoints (D-006).
# ⚠ SYNC MANUEL : si tu modifies ce dict, modifie aussi celui de scoring.compute.
# À refactorer en un seul module partagé en J11+.

CLASS_MIDPOINTS_KWH_EP: dict[str, float] = {
    "A": 55.0,
    "B": 90.0,
    "C": 145.0,
    "D": 215.0,
    "E": 295.0,
    "F": 390.0,
    "G": 500.0,
}


# ---------------------------------------------------------------------------
# Facteurs d'émission par énergie de chauffage (kgCO2eq / kWh PCI)
# ---------------------------------------------------------------------------
# Source : ADEME Base Carbone 2023 (valeurs France métropolitaine moyennes).
# Note méthodologique : ces facteurs sont en énergie finale (kWh ef). Le DPE est en énergie
# primaire (kWh ep). On convertit `ep → ef` via le coefficient EP (1.9 pour électricité,
# 1.0 pour les autres énergies — cf. arrêté 2021).
#
# kgCO2/kWh_ef     EP_to_EF coef  → kgCO2/kWh_ep effectif
# électricité  0.064  / 1.9        → 0.034
# gaz naturel  0.227  / 1.0        → 0.227
# fioul        0.272  / 1.0        → 0.272
# bois         0.024  / 1.0        → 0.024
# reseau       0.116  / 1.0        → 0.116 (mix moyen RCU France)
# pac          0.064  / (1.9 x COP3) → ≈ 0.011 (équiv. 1 kWh ep PAC = 1/COP kWh elec ef)

KG_CO2_PER_KWH_EP_BY_ENERGY: dict[str, float] = {
    "electricite": 0.034,  # 0.064 kgCO2/kWh ef / 1.9 EP→EF
    "gaz": 0.227,
    "fioul": 0.272,
    "bois": 0.024,
    "reseau_chaleur": 0.116,
    "pac": 0.011,  # PAC électricité COP≈3 ⇒ très bas
    "unknown": 0.150,  # mix moyen FR (valeur médiane prudente)
}

# Mapping libellés BDNB/DPE vers nos buckets normalisés
ENERGY_NORMALIZE: dict[str, str] = {
    "electricite": "electricite",
    "électricité": "electricite",
    "gaz": "gaz",
    "gaz naturel": "gaz",
    "fioul": "fioul",
    "fuel": "fioul",
    "bois": "bois",
    "biomasse": "bois",
    "granules": "bois",
    "réseau de chaleur": "reseau_chaleur",
    "reseau de chaleur": "reseau_chaleur",
    "rcu": "reseau_chaleur",
    "pompe à chaleur": "pac",
    "pompe a chaleur": "pac",
    "pac": "pac",
}


def normalize_energy(label: str | None) -> str:
    """Convertit un libellé énergie (BDNB ou input utilisateur) vers un bucket normalisé."""
    if not label:
        return "unknown"
    low = label.strip().lower()
    for key, bucket in ENERGY_NORMALIZE.items():
        if key in low:
            return bucket
    return "unknown"


def co2_factor_for_energy(energy_label: str | None) -> float:
    """Facteur kgCO2eq / kWh_ep pour une énergie donnée (label libre normalisé)."""
    bucket = normalize_energy(energy_label)
    return KG_CO2_PER_KWH_EP_BY_ENERGY[bucket]


# ---------------------------------------------------------------------------
# Préfabrication hors-site (carbone évité chantier — référentiel CSTB/ADEME)
# ---------------------------------------------------------------------------
# Source : étude CSTB 2023 "Construction hors-site et bilan carbone" + retours d'expérience
# CD2E. La part d'émissions évitées par la préfabrication (logistique + dégâts chantier +
# déchets) est dans la fourchette **20-40 %** des émissions du procédé constructif.
# Médiane retenue : **25 %**.

HORS_SITE_AVOID_FRACTION_LOW: float = 0.20
HORS_SITE_AVOID_FRACTION_MEDIAN: float = 0.25
HORS_SITE_AVOID_FRACTION_HIGH: float = 0.40


# ---------------------------------------------------------------------------
# Horizon temporel par défaut
# ---------------------------------------------------------------------------
# Convention RE2020 : 50 ans pour les bâtiments neufs, 30 ans en rénovation thermique.

DEFAULT_HORIZON_YEARS: int = 30


# ---------------------------------------------------------------------------
# Sources affichables (UI)
# ---------------------------------------------------------------------------

SOURCE_REFERENCES: dict[str, str] = {
    "ademe_base_carbone": "ADEME Base Carbone 2023 — https://base-carbone.ademe.fr/",
    "dpe_arrete_2021": "Arrêté DPE 2021 (coef EP 1.9 anticipé 2026)",
    "cstb_horssite": "CSTB 2023 — Construction hors-site et bilan carbone",
    "inies_fdes": "INIES — base statique D-014",
}
