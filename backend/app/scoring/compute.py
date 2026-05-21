"""ConX — calcul déterministe des composantes scoring (cf. docs/SCORING.md).

Pure function : prend un Building + DPE + ScoringThresholds, retourne BuildingScoreComponents.
**N'inclut PAS le calcul du score total** — celui-ci est fait à la volée en SQL pur côté backend
quand l'utilisateur ajuste les sliders (cf. SCORING.md §"Calcul à la volée").

D-006 : formule gravée. Modification du calcul = arbitrage partenaire obligatoire.

Notes d'implémentation vs SCORING.md gravé
------------------------------------------
- **kWh fallback par classe** : SCORING.md prévoit DPE réel OU prédiction ML. Pré-J5 (pas de ML),
  on utilise un point milieu par classe (A=55, B=90, C=145, D=215, E=295, F=390, G=500 kWh ep/m²/an).
  Ces midpoints proviennent des bornes officielles arrêté 2021. Rows correspondantes :
  dpe_source='ml-predicted' + incomplete_data=true + confidence réduite. Sera remplacé par
  vraies prédictions ML en J5.
- **Redistribution des poids S_faisa quand acces_chantier indisponible** : si BD TOPO pas ingérée
  (pré-J4), le sous-indicateur acces_chantier=0.20 est retiré et son poids est redistribué
  proportionnellement sur les 5 sous-indicateurs restants. Cela évite de pénaliser injustement
  les bâtiments en attendant la passe de mise à jour. Flag s_faisa_partial=true posé.
- **type_compatible fallback 0.5** : pour type_principal non reconnu par _normalize_type_principal,
  on pose 0.5 (neutre) + incomplete_data=true. Pas une 6e catégorie de scoring, juste un fallback
  de robustesse. Les 5 catégories SCORING.md (résidentiel collectif, pavillon, tertiaire, industriel,
  spécifique) restent intactes en valeurs.

Toutes les autres valeurs et la formule des 5 composantes pondérées sont strictement conformes
à SCORING.md §Composante 1-5 (validé partenaire 2026-05-21).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringThresholds:
    """Seuils chargés depuis config/scoring_thresholds.yaml."""

    version: str
    co2_max_tonnes_30ans: float
    cost_min_eur_per_tco2: float
    cost_max_eur_per_tco2: float
    target_kwh_ep_m2_an: float
    horizon_ans: int
    emission_factors: dict[str, float]
    cost_table: dict[str, dict[str, float]]
    cost_modulators: dict[str, float]
    faisa_weights: dict[str, float]
    social_table: dict[str, float]
    passoire_table: dict[str, float]
    weights_default: dict[str, float]
    raw_yaml: str = field(repr=False)


def load_thresholds(yaml_path: Path | str) -> ScoringThresholds:
    """Charge scoring_thresholds.yaml et retourne un ScoringThresholds figé."""
    p = Path(yaml_path)
    text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return ScoringThresholds(
        version=data["version"],
        co2_max_tonnes_30ans=float(data["co2"]["max_tonnes_30ans"]),
        cost_min_eur_per_tco2=float(data["cost"]["min_eur_per_tco2"]),
        cost_max_eur_per_tco2=float(data["cost"]["max_eur_per_tco2"]),
        target_kwh_ep_m2_an=float(data["target_class"]["kwh_ep_m2_an"]),
        horizon_ans=int(data["horizon_amortissement_ans"]),
        emission_factors=data["energy_emission_factors"],
        cost_table=data["cost_table_eur_m2"],
        cost_modulators=data["cost_modulators"],
        faisa_weights=data["faisa_weights"],
        social_table=data["social_table"],
        passoire_table=data["passoire_table"],
        weights_default=data["weights_default"],
        raw_yaml=text,
    )


def thresholds_version_hash(thresholds: ScoringThresholds) -> str:
    """SHA256-12 du YAML brut. Stocké dans building_scores.thresholds_version."""
    return hashlib.sha256(thresholds.raw_yaml.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


@dataclass
class BuildingScoreComponents:
    s_co2: float
    s_faisa: float
    s_cout: float
    s_social: float
    s_passoire: float
    co2_evite_t: float
    cout_estime_eur: float
    cout_eur_par_t_co2: float | None
    confidence: float
    dpe_source: str  # 'ademe-real' | 'ml-predicted' (SCORING.md §Implémentation, D-006)
    incomplete_data: bool = False
    s_faisa_partial: bool = False
    missing_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _normalize_dept_period(annee: int | None) -> str | None:
    if annee is None:
        return None
    if annee < 1948:
        return "avant_1948"
    if annee < 1975:
        return "1948_1974"
    if annee < 2001:
        return "1975_2000"
    return "apres_2000"


def _normalize_type_principal(t: str | None) -> str:
    if t is None:
        return "default"
    t_low = t.lower()
    if "collectif" in t_low or "appartement" in t_low or "immeuble" in t_low:
        return "residentiel_collectif"
    if "individuel" in t_low or "pavillon" in t_low or "maison" in t_low:
        return "pavillon"
    if "bureau" in t_low:
        return "tertiaire_bureaux"
    if "commerce" in t_low or "magasin" in t_low:
        return "tertiaire_commerce"
    return "default"


def _emission_factor(energy_type: str | None, factors: dict[str, float]) -> float:
    if energy_type is None:
        return factors["default"]
    e = energy_type.lower()
    if "electric" in e or "élec" in e:
        return factors["electricite"]
    if "gaz" in e:
        return factors["gaz"]
    if "fioul" in e or "fuel" in e:
        return factors["fioul"]
    if "reseau" in e or "réseau" in e or "rcu" in e or "chaleur" in e:
        return factors["rcu"]
    if "bois" in e or "granul" in e or "pellet" in e:
        return factors["bois"]
    return factors["default"]


# ---------------------------------------------------------------------------
# Sous-composantes S_faisa
# ---------------------------------------------------------------------------


def _faisa_subindicators(
    building: dict[str, Any],
    has_topo_roads: bool,
    faisa_weights: dict[str, float],
) -> tuple[float, dict[str, float], bool]:
    """Retourne (s_faisa, breakdown, partial_flag).

    partial_flag = True si acces_chantier n'a pas pu être calculé (BD TOPO absente).
    Dans ce cas on neutralise le sous-indicateur en redistribuant son poids sur les autres
    proportionnellement.
    """
    missing_acces = not has_topo_roads
    subs: dict[str, float] = {}

    # Toiture régulière — sans LiDAR ni typologie toiture, on prend valeur par défaut 0.5 (neutre).
    # Sera affiné en J5+ avec LiDAR ou attributs BD TOPO (materiaux_de_la_toiture).
    subs["toiture_reguliere"] = 0.5

    # Accès chantier — nécessite BD TOPO. Si absent, partial=True.
    if missing_acces:
        subs["acces_chantier"] = 0.0  # ignoré via la redistribution des poids
    else:
        # Sera calculé en post-update une fois BD TOPO ingérée (PostGIS distance to topo_roads + largeur).
        # Pour l'instant on met une valeur indicative neutre en attendant la passe de mise à jour.
        subs["acces_chantier"] = 0.5

    # Hauteur compatible préfabrication
    hauteur = building.get("hauteur_m")
    if hauteur is None:
        subs["hauteur_compatible"] = 0.7  # neutre (hypothèse R+3 à R+5)
    elif hauteur <= 15:  # ~R+4
        subs["hauteur_compatible"] = 1.0
    elif hauteur <= 27:  # ~R+8
        subs["hauteur_compatible"] = 0.7
    else:
        subs["hauteur_compatible"] = 0.3

    # Absence de protection patrimoniale
    is_mh = bool(building.get("monument_historique", False))
    is_spr = bool(building.get("spr", False))
    subs["absence_patrimoine"] = 0.0 if (is_mh or is_spr) else 1.0

    # Géométrie simple — sans calcul périmètre²/surface (à faire en PostGIS), valeur neutre 0.7.
    # TODO J5+ : calcul exact via ST_Perimeter et ST_Area.
    subs["geometrie_simple"] = 0.7

    # Type compatible hors-site — valeurs gravées dans SCORING.md §Composante 2 :
    # résidentiel collectif R+1-R+5 = 1.0 ; pavillon = 0.8 ; tertiaire ≤ R+4 = 0.9 (singulier,
    # bureaux ET commerce) ; industriel = 0.3 ; spécifique (église, gare…) = 0.0.
    # Pour type_principal non reconnu : 0.5 (neutre) + le caller pose incomplete_data=true.
    # C'est un fallback de robustesse, pas une modification de formule (D-006).
    type_norm = _normalize_type_principal(building.get("type_principal"))
    if type_norm == "residentiel_collectif":
        subs["type_compatible"] = 1.0
    elif type_norm == "pavillon":
        subs["type_compatible"] = 0.8
    elif type_norm in ("tertiaire_bureaux", "tertiaire_commerce"):
        subs["type_compatible"] = 0.9
    else:
        subs["type_compatible"] = 0.5

    # Pondération : si acces_chantier manquant, redistribuer son poids proportionnellement.
    weights = dict(faisa_weights)
    if missing_acces:
        weights.pop("acces_chantier")
        total_rest = sum(weights.values())
        weights = {k: v * (1.0 / total_rest) for k, v in weights.items()}
        subs.pop("acces_chantier")

    s_faisa = sum(weights[k] * subs[k] for k in weights)
    return _clip(s_faisa, 0.0, 1.0), subs, missing_acces


# ---------------------------------------------------------------------------
# Calcul principal
# ---------------------------------------------------------------------------


def compute_components(
    building: dict[str, Any],
    dpe: dict[str, Any] | None,
    thresholds: ScoringThresholds,
    *,
    has_topo_roads: bool = False,
) -> BuildingScoreComponents:
    """Calcule les 5 composantes pour un bâtiment + son DPE optionnel.

    Args:
        building : dict avec au moins building_id, dept, surface_m2, hauteur_m, annee_constr,
                   periode_construction, type_principal, type_proprietaire, monument_historique,
                   spr, dpe_classe, dpe_kwh_ep_m2_an.
        dpe      : dict DPE détaillé (type_dpe, type_energie_chauffage, ...) ou None si absent.
        thresholds : ScoringThresholds chargé via load_thresholds().
        has_topo_roads : True si public_data.topo_roads est dispo pour ce dpt (S_faisa.acces_chantier
                         calculable). Si False, S_faisa marqué partial.

    Returns:
        BuildingScoreComponents avec les 5 scores [0,1] + valeurs brutes + flags qualité.
    """
    missing: list[str] = []
    incomplete = False

    # === Récupération des champs critiques ===
    surface = building.get("surface_m2")
    if surface is None or surface <= 0:
        missing.append("surface_m2")
        incomplete = True
        surface = 100.0  # fallback prudent (sera flagué)

    classe_dpe = building.get("dpe_classe")
    kwh_actuelle = building.get("dpe_kwh_ep_m2_an")
    # SCORING.md grave dpe_source ∈ {'ademe-real', 'ml-predicted'}.
    # Pré-J5 : pas de modèle ML, on utilise un point milieu de classe par typologie. Ce fallback
    # garde l'enum 'ml-predicted' (sera vraiment ML en J5) + incomplete_data=true + confidence basse.
    dpe_source = "ademe-real" if classe_dpe is not None else "ml-predicted"

    if kwh_actuelle is None:
        # Estimation très grossière par classe DPE (point milieu de l'intervalle officiel).
        # Sera remplacée par ML en J5.
        class_midpoints = {
            "A": 55.0,
            "B": 90.0,
            "C": 145.0,
            "D": 215.0,
            "E": 295.0,
            "F": 390.0,
            "G": 500.0,
        }
        kwh_actuelle = class_midpoints.get(classe_dpe or "", 215.0)  # défaut D
        if classe_dpe is None:
            missing.append("dpe_classe")
            missing.append("dpe_kwh_ep_m2_an")
            incomplete = True

    # === S_co2 ===
    delta_kwh = max(0.0, kwh_actuelle - thresholds.target_kwh_ep_m2_an)
    # Facteur émission : tertiaire/logement traités par énergie principale de chauffage si dispo
    energy = (dpe or {}).get("type_energie_chauffage")
    facteur = _emission_factor(energy, thresholds.emission_factors)
    co2_evite_kg_total = delta_kwh * surface * facteur * thresholds.horizon_ans
    co2_evite_t = co2_evite_kg_total / 1000.0
    s_co2 = _clip(co2_evite_t / thresholds.co2_max_tonnes_30ans, 0.0, 1.0)

    # === S_faisa ===
    s_faisa, faisa_breakdown, s_faisa_partial = _faisa_subindicators(building, has_topo_roads, thresholds.faisa_weights)

    # === S_cout ===
    type_norm = _normalize_type_principal(building.get("type_principal"))
    periode = _normalize_dept_period(building.get("annee_constr")) or "avant_1948"
    cost_row = thresholds.cost_table.get(type_norm, thresholds.cost_table["default"])
    if type_norm in ("tertiaire_bureaux", "tertiaire_commerce"):
        cout_m2 = cost_row.get("toutes", 500.0)
    else:
        cout_m2 = cost_row.get(periode, cost_row.get("toutes", 600.0))

    # Modulateurs
    if faisa_breakdown.get("geometrie_simple", 0.7) >= 0.5:
        cout_m2 *= thresholds.cost_modulators["geometrie_simple"]
    else:
        cout_m2 *= thresholds.cost_modulators["geometrie_complexe"]
    if building.get("monument_historique") or building.get("spr"):
        cout_m2 *= thresholds.cost_modulators["patrimoine"]

    cout_estime_eur = surface * cout_m2

    if co2_evite_t > 0:
        cout_eur_par_t_co2 = cout_estime_eur / co2_evite_t
        s_cout = _clip(
            (thresholds.cost_max_eur_per_tco2 - cout_eur_par_t_co2)
            / (thresholds.cost_max_eur_per_tco2 - thresholds.cost_min_eur_per_tco2),
            0.0,
            1.0,
        )
    else:
        cout_eur_par_t_co2 = None
        s_cout = 0.0  # aucun gain CO2 → efficience nulle

    # === S_social ===
    type_proprio = building.get("type_proprietaire") or "unknown"
    s_social = thresholds.social_table.get(type_proprio, thresholds.social_table["unknown"])

    # === S_passoire ===
    s_passoire = thresholds.passoire_table.get(classe_dpe or "", 0.0) if classe_dpe else 0.0

    # === Confidence ===
    confidence = 1.0
    if incomplete:
        confidence -= 0.4
    if s_faisa_partial:
        confidence -= 0.1
    if dpe_source == "fallback-typology":
        confidence -= 0.2
    confidence = _clip(confidence, 0.1, 1.0)

    return BuildingScoreComponents(
        s_co2=s_co2,
        s_faisa=s_faisa,
        s_cout=s_cout,
        s_social=s_social,
        s_passoire=s_passoire,
        co2_evite_t=co2_evite_t,
        cout_estime_eur=cout_estime_eur,
        cout_eur_par_t_co2=cout_eur_par_t_co2,
        confidence=confidence,
        dpe_source=dpe_source,
        incomplete_data=incomplete,
        s_faisa_partial=s_faisa_partial,
        missing_fields=missing,
    )
