"""ConX — tests unitaires module carbon (J6).

Vérifie : (1) facteurs d'émission par énergie, (2) compute_exploitation 10 cas de référence,
(3) compute_incorpore avec FDES statique, (4) compute_evite_horssite,
(5) compute_total cohérent (net = signe attendu).
"""

from __future__ import annotations

import pytest

from app.carbon import (
    CLASS_MIDPOINTS_KWH_EP,
    MaterialQuantity,
    co2_factor_for_energy,
    compute_evite_horssite,
    compute_exploitation,
    compute_incorpore,
    compute_total,
    list_materials,
    normalize_energy,
    report_to_json,
)

# ---------------------------------------------------------------------------
# 1. Facteurs d'émission par énergie
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected_bucket",
    [
        ("Gaz naturel", "gaz"),
        ("électricité", "electricite"),
        ("Fioul domestique", "fioul"),
        ("Bois bûches", "bois"),
        ("Granulés de bois", "bois"),
        ("Réseau de chaleur urbain", "reseau_chaleur"),
        ("PAC air-eau", "pac"),
        ("Pompe à chaleur", "pac"),
        (None, "unknown"),
        ("xyz inconnu", "unknown"),
    ],
)
def test_normalize_energy(label, expected_bucket):
    assert normalize_energy(label) == expected_bucket


def test_factor_for_each_known_energy():
    """Chaque bucket renvoie un facteur > 0 et différent."""
    factors = {b: co2_factor_for_energy(b) for b in ["electricite", "gaz", "fioul", "bois", "pac"]}
    assert all(v > 0 for v in factors.values())
    assert factors["pac"] < factors["electricite"] < factors["gaz"] < factors["fioul"]


# ---------------------------------------------------------------------------
# 2. compute_exploitation — 10 cas de référence
# ---------------------------------------------------------------------------


def test_exploitation_passoire_g_to_b_gaz():
    """Cas type : passoire G (500 kWh/m²/an) rénovée en B (90), 100 m², gaz."""
    res = compute_exploitation(
        surface_m2=100,
        classe_avant="G",
        classe_apres="B",
        type_energie_chauffage="gaz naturel",
    )
    # Delta : (500 - 90) x 100 = 41 000 kWh/an
    # Émissions an : 41 000 x 0.227 = 9 307 kg/an
    # Sur 30 ans : 279 210 kg ≈ 279 t
    assert abs(res.delta_kwh_an_total - 41000) < 1
    assert abs(res.emissions_evitees_an_kg - 9307.0) < 50  # ±50 kg/an
    assert abs(res.emissions_evitees_horizon_kg - 279210.0) < 1500
    assert res.energy_bucket == "gaz"


def test_exploitation_e_to_c_electricite():
    """E (295) → C (145) sur 80 m² électricité (coef ep→ef divisé)."""
    res = compute_exploitation(surface_m2=80, classe_avant="E", classe_apres="C", type_energie_chauffage="électricité")
    # Delta : (295-145) x 80 = 12 000 kWh ep / an
    # Facteur électricité ep : 0.034 → 408 kg/an
    # Sur 30 ans : 12 240 kg ≈ 12.2 t
    assert abs(res.delta_kwh_an_total - 12000) < 1
    assert abs(res.emissions_evitees_horizon_kg - 12240.0) < 200


def test_exploitation_f_to_a_pac():
    """F (390) → A (55) sur 120 m² PAC."""
    res = compute_exploitation(surface_m2=120, classe_avant="F", classe_apres="A", type_energie_chauffage="PAC")
    # Delta : (390-55) x 120 = 40 200 kWh
    # Facteur PAC : 0.011 → 442 kg/an
    # Sur 30 ans : 13 266 kg
    assert abs(res.delta_kwh_an_total - 40200) < 1
    assert res.energy_bucket == "pac"
    assert abs(res.emissions_evitees_horizon_kg - 13266.0) < 200


def test_exploitation_d_to_c_minor_gain():
    """D (215) → C (145), un saut modeste."""
    res = compute_exploitation(surface_m2=100, classe_avant="D", classe_apres="C", type_energie_chauffage="gaz")
    assert abs(res.delta_kwh_an_total - 7000) < 1


def test_exploitation_real_kwh_overrides_classe():
    """Si dpe_kwh_ep_m2_an réel fourni, prime sur midpoint."""
    res = compute_exploitation(
        surface_m2=100,
        classe_avant="F",
        classe_apres="C",
        kwh_avant_per_m2_an=420.0,  # plus que midpoint F (390)
        type_energie_chauffage="gaz",
    )
    assert res.kwh_avant_per_m2_an == 420.0
    assert res.delta_kwh_an_total == (420.0 - 145.0) * 100


def test_exploitation_unknown_classe_fallback_d():
    """classe_avant None ou inconnue → midpoint D = 215."""
    res = compute_exploitation(surface_m2=100, classe_avant=None, classe_apres="A", type_energie_chauffage="gaz")
    assert res.kwh_avant_per_m2_an == CLASS_MIDPOINTS_KWH_EP["D"]


def test_exploitation_invalid_classe_apres():
    with pytest.raises(ValueError, match="classe_apres invalide"):
        compute_exploitation(100, "F", "Z", type_energie_chauffage="gaz")


def test_exploitation_zero_surface():
    with pytest.raises(ValueError, match="surface_m2 doit être"):
        compute_exploitation(0, "F", "C", type_energie_chauffage="gaz")


def test_exploitation_horizon_50_ans():
    """Horizon 50 ans = 50/30 x résultat 30 ans."""
    r30 = compute_exploitation(100, "F", "B", type_energie_chauffage="gaz", horizon_years=30)
    r50 = compute_exploitation(100, "F", "B", type_energie_chauffage="gaz", horizon_years=50)
    assert abs(r50.emissions_evitees_horizon_kg / r30.emissions_evitees_horizon_kg - 50 / 30) < 1e-6


def test_exploitation_hypotheses_format():
    """Hypothèses contiennent les sources et clés requises pour l'UI."""
    res = compute_exploitation(100, "F", "B", type_energie_chauffage="gaz")
    h = res.hypotheses
    assert "ADEME Base Carbone" in h["source_facteurs"]
    assert "Arrêté DPE 2021" in h["source_classes"]
    assert h["horizon_years"] == "30"
    assert "classe_avant" in h and "classe_apres" in h


# ---------------------------------------------------------------------------
# 3. compute_incorpore — FDES statique
# ---------------------------------------------------------------------------


def test_list_materials_30():
    """30 matériaux dans la base statique (D-014)."""
    mats = list_materials()
    assert len(mats) == 30
    ids = {m["id"] for m in mats}
    assert "bois-clt" in ids
    assert "ouate-cellulose-insufflee" in ids


def test_incorpore_bois_clt_biosource_carbone_negatif():
    """100 m² de bois CLT → kgCO2eq négatif (biosourcé carbone négatif)."""
    res = compute_incorpore([MaterialQuantity("bois-clt", 100, "Plancher CLT")])
    assert res.total_kg_co2_eq < 0
    assert res.total_biogenic_co2_stored_kg > 0


def test_incorpore_unknown_material():
    with pytest.raises(KeyError, match="introuvable|inconnu"):
        compute_incorpore([MaterialQuantity("xyz-inconnu", 100)])


def test_incorpore_zero_quantity_zero_co2():
    res = compute_incorpore([MaterialQuantity("bois-clt", 0)])
    assert res.total_kg_co2_eq == 0.0


def test_incorpore_breakdown_per_material():
    res = compute_incorpore(
        [
            MaterialQuantity("bois-clt", 100, "Plancher"),
            MaterialQuantity("ouate-cellulose-insufflee", 200, "Combles"),
        ]
    )
    assert len(res.breakdown) == 2
    assert res.breakdown[0]["material_id"] == "bois-clt"
    assert res.breakdown[1]["material_id"] == "ouate-cellulose-insufflee"


# ---------------------------------------------------------------------------
# 4. compute_evite_horssite
# ---------------------------------------------------------------------------


def test_evite_horssite_25_pct_default():
    """Médiane 25 % appliquée par défaut sur les positifs."""
    breakdown = [
        {"kg_co2_eq_total": 1000},
        {"kg_co2_eq_total": -200},  # biosourcé : ignoré dans la base
        {"kg_co2_eq_total": 500},
    ]
    res = compute_evite_horssite(breakdown)
    # base = 1500 (les -200 ne comptent pas)
    assert res.emissions_construction_positives_kg == 1500.0
    assert abs(res.emissions_evitees_kg - 375.0) < 1
    assert abs(res.emissions_evitees_low_kg - 300.0) < 1
    assert abs(res.emissions_evitees_high_kg - 600.0) < 1


def test_evite_horssite_all_biosource_no_avoid():
    """100 % biosourcé (tous bilans négatifs) → rien à éviter."""
    breakdown = [{"kg_co2_eq_total": -500}, {"kg_co2_eq_total": -300}]
    res = compute_evite_horssite(breakdown)
    assert res.emissions_construction_positives_kg == 0.0
    assert res.emissions_evitees_kg == 0.0


def test_evite_horssite_invalid_fraction():
    with pytest.raises(ValueError, match="hors"):
        compute_evite_horssite([{"kg_co2_eq_total": 100}], fraction_used=1.5)


# ---------------------------------------------------------------------------
# 5. compute_total — bilan agrégé cohérent
# ---------------------------------------------------------------------------


def test_total_passoire_g_vers_b_avec_bois_donne_net_vertueux():
    """Rénovation passoire G → B avec isolation bois → net 30y négatif."""
    res = compute_total(
        surface_m2=100,
        classe_avant="G",
        classe_apres="B",
        type_energie_chauffage="gaz",
        materials=[
            MaterialQuantity("bois-clt", 50, "Murs"),
            MaterialQuantity("ouate-cellulose-insufflee", 200, "Isolation"),
        ],
    )
    # Exploitation : ~279 t évitées sur 30 ans → grand poste négatif
    # Incorpore : 50x-28.5 + 200x1.8 = -1425 + 360 = -1065 kg
    # Hors-site : sur la part positive (360 kg ouate) x 0.25 = 90 kg
    # Net = -1065 - 279 210 - 90 ≈ -280 365 kg
    assert res.net_kg_co2_eq_horizon < 0
    assert res.net_kg_co2_eq_horizon < -200_000  # net franchement vertueux


def test_total_renovation_minor_net_positif_possible():
    """Petite rénovation D → C, 80 m², électricité, avec béton C25/30 lourd.

    Vérifie la cohérence algébrique de compute_total : net = incorpore - exploitation - horssite.
    """
    res = compute_total(
        surface_m2=80,
        classe_avant="D",
        classe_apres="C",
        type_energie_chauffage="électricité",
        materials=[
            MaterialQuantity("beton-c25-30", 50, "Murs porteurs"),
        ],
    )
    # Exploitation : delta = (215-145) x 80 = 5600 kWh/an, facteur 0.034 EP, 30 ans
    # → 5600 x 0.034 x 30 = 5 712 kg évités
    assert abs(res.exploitation.emissions_evitees_horizon_kg - 5712.0) < 50
    # Incorpore : béton émet, donc positif
    assert res.incorpore.total_kg_co2_eq > 0
    # Hors-site : 25% par défaut, base = positifs incorpore
    assert res.evite_horssite.fraction_evitee_used == 0.25
    expected_evite_hs = res.incorpore.total_kg_co2_eq * 0.25
    assert abs(res.evite_horssite.emissions_evitees_kg - expected_evite_hs) < 1.0
    # Net = incorpore - exploitation - hors-site
    expected_net = (
        res.incorpore.total_kg_co2_eq
        - res.exploitation.emissions_evitees_horizon_kg
        - res.evite_horssite.emissions_evitees_kg
    )
    assert abs(res.net_kg_co2_eq_horizon - round(expected_net, 2)) < 1.0


def test_total_report_to_json_structure():
    """Le JSON de sortie a la structure attendue (clés requises pour l'API/agent)."""
    res = compute_total(
        surface_m2=100,
        classe_avant="F",
        classe_apres="B",
        type_energie_chauffage="gaz",
        materials=[MaterialQuantity("bois-clt", 50)],
    )
    j = report_to_json(res)
    assert "exploitation" in j and "incorpore" in j and "evite_horssite" in j
    assert "summary" in j
    s = j["summary"]
    assert "net_kg_co2_eq_horizon" in s
    assert "net_t_co2_eq_horizon" in s
    assert "horizon_years" in s
    assert "verdict" in s
    assert s["verdict"] in ("vertueux", "emissif")
