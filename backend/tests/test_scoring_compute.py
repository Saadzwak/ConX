"""ConX — tests unitaires du scoring déterministe (cf. docs/SCORING.md).

Vérifie : (1) formule SCORING.md respectée, (2) bornes [0,1], (3) flags qualité.
**Ces tests N'EXÉCUTENT PAS de DB** — pure logique Python.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.scoring.compute import (
    compute_components,
    load_thresholds,
    thresholds_version_hash,
)

ROOT = Path(__file__).resolve().parent.parent.parent
THRESHOLDS = load_thresholds(ROOT / "config" / "scoring_thresholds.yaml")


def test_thresholds_loaded():
    """Seuils SCORING.md chargés correctement."""
    assert THRESHOLDS.co2_max_tonnes_30ans == 500
    assert THRESHOLDS.cost_min_eur_per_tco2 == 500
    assert THRESHOLDS.cost_max_eur_per_tco2 == 5000
    assert THRESHOLDS.weights_default["w_co2"] == 0.35
    assert THRESHOLDS.weights_default["w_faisa"] == 0.25
    assert THRESHOLDS.weights_default["w_cout"] == 0.20
    assert THRESHOLDS.weights_default["w_social"] == 0.10
    assert THRESHOLDS.weights_default["w_passoire"] == 0.10
    # Somme des poids = 1
    s = sum(THRESHOLDS.weights_default.values())
    assert abs(s - 1.0) < 1e-9, f"Somme poids = {s}"


def test_thresholds_hash_stable():
    """Le hash du YAML est stable et de longueur 12."""
    h = thresholds_version_hash(THRESHOLDS)
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_passoire_F_logement_collectif():
    """Bâtiment passoire F → s_passoire = 1.0 et S_co2 > 0."""
    building = {
        "building_id": "bg-F-test",
        "dept": "59",
        "surface_m2": 1000.0,
        "hauteur_m": 18.0,
        "annee_constr": 1965,
        "type_principal": "résidentiel collectif",
        "type_proprietaire": "bailleur_social",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "F",
        "dpe_kwh_ep_m2_an": 390.0,
    }
    dpe = {"type_energie_chauffage": "gaz"}
    comp = compute_components(building, dpe, THRESHOLDS, acces_chantier_value=1.0)

    assert comp.s_passoire == 1.0
    assert comp.s_social == 1.0  # bailleur_social
    assert 0.0 <= comp.s_co2 <= 1.0
    assert comp.s_co2 > 0.0
    assert 0.0 <= comp.s_faisa <= 1.0
    assert 0.0 <= comp.s_cout <= 1.0
    assert comp.co2_evite_t > 0
    assert comp.dpe_source == "ademe-real"
    assert not comp.s_faisa_partial


def test_classe_A_no_passoire():
    """Bâtiment classe A → s_passoire = 0, S_co2 modéré (peu de gain)."""
    building = {
        "building_id": "bg-A-test",
        "dept": "59",
        "surface_m2": 100.0,
        "hauteur_m": 6.0,
        "annee_constr": 2018,
        "type_principal": "pavillon",
        "type_proprietaire": "particulier",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "A",
        "dpe_kwh_ep_m2_an": 55.0,
    }
    comp = compute_components(building, None, THRESHOLDS, acces_chantier_value=1.0)

    assert comp.s_passoire == 0.0
    assert comp.s_social == 0.30  # particulier
    # 55 < 90 (cible classe B) → co2_evite_t = 0 → s_co2 = 0
    assert comp.co2_evite_t == 0.0
    assert comp.s_co2 == 0.0
    assert comp.s_cout == 0.0  # pas de gain → efficience nulle
    assert comp.cout_eur_par_t_co2 is None


def test_co2_saturation_at_500_tonnes():
    """Au-delà de 500 tCO₂/30ans, s_co2 = 1.0 (clip)."""
    # Énorme bâtiment passoire G avec gaz → beaucoup de CO₂ évitable
    building = {
        "building_id": "bg-huge",
        "dept": "59",
        "surface_m2": 10000.0,  # 10 000 m²
        "hauteur_m": 24.0,
        "annee_constr": 1960,
        "type_principal": "résidentiel collectif",
        "type_proprietaire": "bailleur_social",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "G",
        "dpe_kwh_ep_m2_an": 500.0,
    }
    dpe = {"type_energie_chauffage": "gaz"}
    comp = compute_components(building, dpe, THRESHOLDS, acces_chantier_value=1.0)
    assert comp.s_co2 == 1.0
    assert comp.co2_evite_t > 500


def test_monument_historique_zeros_faisa_patrimoine():
    """MH → absence_patrimoine = 0 → S_faisa réduit."""
    base = {
        "building_id": "bg-mh",
        "dept": "59",
        "surface_m2": 500.0,
        "hauteur_m": 10.0,
        "annee_constr": 1850,
        "type_principal": "résidentiel collectif",
        "type_proprietaire": "particulier",
        "spr": False,
        "dpe_classe": "F",
        "dpe_kwh_ep_m2_an": 390.0,
    }
    with_mh = compute_components({**base, "monument_historique": True}, None, THRESHOLDS, acces_chantier_value=1.0)
    without_mh = compute_components({**base, "monument_historique": False}, None, THRESHOLDS, acces_chantier_value=1.0)
    assert with_mh.s_faisa < without_mh.s_faisa
    # MH coût modulator x 1.30
    assert with_mh.cout_estime_eur > without_mh.cout_estime_eur


def test_s_faisa_partial_flag_when_no_topo():
    """Sans BD TOPO ingéré → s_faisa_partial = True, S_faisa quand même calculé en redistribuant."""
    building = {
        "building_id": "bg-no-topo",
        "dept": "59",
        "surface_m2": 100.0,
        "hauteur_m": 10.0,
        "annee_constr": 1970,
        "type_principal": "pavillon",
        "type_proprietaire": "particulier",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "E",
        "dpe_kwh_ep_m2_an": 295.0,
    }
    comp_partial = compute_components(building, None, THRESHOLDS, acces_chantier_value=None)
    comp_full = compute_components(building, None, THRESHOLDS, acces_chantier_value=1.0)
    assert comp_partial.s_faisa_partial is True
    assert comp_full.s_faisa_partial is False
    assert 0.0 <= comp_partial.s_faisa <= 1.0
    # Confiance plus faible quand partial
    assert comp_partial.confidence < comp_full.confidence


def test_incomplete_data_flag_when_no_surface():
    """Bâtiment sans surface_m2 → flag + confiance réduite."""
    building = {
        "building_id": "bg-no-surface",
        "dept": "59",
        "surface_m2": None,
        "hauteur_m": 8.0,
        "annee_constr": 1970,
        "type_principal": "pavillon",
        "type_proprietaire": "particulier",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "E",
        "dpe_kwh_ep_m2_an": 295.0,
    }
    comp = compute_components(building, None, THRESHOLDS, acces_chantier_value=1.0)
    assert comp.incomplete_data is True
    assert "surface_m2" in comp.missing_fields
    assert comp.confidence < 1.0


def test_bornes_components_strict():
    """Quelques bâtiments aléatoires → toutes les composantes restent dans [0,1]."""
    rng_cases = [
        {"dpe_classe": "G", "dpe_kwh_ep_m2_an": 1000.0, "surface_m2": 50000.0},
        {"dpe_classe": "A", "dpe_kwh_ep_m2_an": 30.0, "surface_m2": 50.0},
        {"dpe_classe": None, "dpe_kwh_ep_m2_an": None, "surface_m2": 200.0},
    ]
    base = {
        "building_id": "bg",
        "dept": "59",
        "hauteur_m": 10.0,
        "annee_constr": 1975,
        "type_principal": "résidentiel collectif",
        "type_proprietaire": "particulier",
        "monument_historique": False,
        "spr": False,
    }
    for case in rng_cases:
        b = {**base, **case}
        comp = compute_components(b, None, THRESHOLDS, acces_chantier_value=1.0)
        for k, v in [
            ("s_co2", comp.s_co2),
            ("s_faisa", comp.s_faisa),
            ("s_cout", comp.s_cout),
            ("s_social", comp.s_social),
            ("s_passoire", comp.s_passoire),
            ("confidence", comp.confidence),
        ]:
            assert 0.0 <= v <= 1.0, f"{k}={v} hors [0,1] sur {case}"


def test_social_table_complete():
    """Toutes les valeurs canoniques type_proprietaire ont un score."""
    for t in ("bailleur_social", "personne_morale_privee", "particulier"):
        assert t in THRESHOLDS.social_table


@pytest.mark.parametrize(
    "classe,expected",
    [
        ("A", 0.0),
        ("B", 0.0),
        ("C", 0.0),
        ("D", 0.0),
        ("E", 0.5),
        ("F", 1.0),
        ("G", 1.0),
    ],
)
def test_passoire_table_values(classe, expected):
    """Mapping classe DPE → S_passoire conforme SCORING.md."""
    assert THRESHOLDS.passoire_table[classe] == expected


@pytest.mark.parametrize("type_principal", ["bureau", "tertiaire bureaux", "commerce", "magasin"])
def test_tertiaire_type_compatible_uniform(type_principal):
    """SCORING.md §Composante 2 : 'tertiaire ≤ R+4 = 0.9' — UNE seule valeur, peu importe bureaux/commerce.

    Garde-fou : interdit le drift (par ex. splitter bureaux=0.9 / commerce=0.6 sans validation).
    D-006 : la formule est gravée — la 5e catégorie tertiaire est SINGULIÈRE."""
    building = {
        "building_id": "bg-tert",
        "dept": "59",
        "surface_m2": 1000.0,
        "hauteur_m": 10.0,
        "annee_constr": 1980,
        "type_principal": type_principal,
        "type_proprietaire": "personne_morale_privee",
        "monument_historique": False,
        "spr": False,
        "dpe_classe": "D",
        "dpe_kwh_ep_m2_an": 215.0,
    }
    other = "bureau" if "commer" in type_principal or "magas" in type_principal else "commerce"
    other_building = {**building, "type_principal": other}
    comp1 = compute_components(building, None, THRESHOLDS, acces_chantier_value=1.0)
    comp2 = compute_components(other_building, None, THRESHOLDS, acces_chantier_value=1.0)
    assert comp1.s_faisa == comp2.s_faisa, (
        f"Drift SCORING.md : '{type_principal}' et '{other}' produisent S_faisa différents "
        f"({comp1.s_faisa} vs {comp2.s_faisa}). SCORING.md liste UNE seule valeur tertiaire = 0.9."
    )
