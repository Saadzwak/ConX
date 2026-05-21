# ConX — Module carbon (J6)

**Statut** : implémenté, 32/32 tests OK.
**Dernière mise à jour** : 2026-05-22.
**Décisions liées** : D-006 (déterminisme : l'IA explique, ne calcule jamais), D-014 (base FDES statique).

---

## 1. Objet

Calcul **100 % déterministe** du bilan carbone d'un projet de rénovation : pas d'appel IA, pas
d'aléatoire, traçabilité totale des hypothèses et des sources.

Trois sous-modules :
- **exploitation** : gain CO₂ sur l'horizon (DPE avant → après).
- **incorpore**     : carbone matériaux via la base statique FDES (30 matériaux clés, D-014).
- **evite_horssite** : carbone évité par la préfabrication hors-site (référentiel CSTB).

Un module agrégateur `total.py` produit un `CarbonReport` et un dict JSON sérialisable pour l'agent
Plan et l'UI.

---

## 2. Pipeline d'un calcul

```
INPUT
  surface_m2, classe_avant, classe_apres, materials[], type_energie_chauffage, horizon_years
       │
       ▼
exploitation.compute_exploitation
  ├─ kwh_avant     = dpe_kwh_ep_m2_an OR CLASS_MIDPOINTS_KWH_EP[classe_avant]
  ├─ kwh_apres     = CLASS_MIDPOINTS_KWH_EP[classe_apres]
  ├─ delta_kwh_an  = (kwh_avant - kwh_apres) × surface_m2
  ├─ co2_factor    = KG_CO2_PER_KWH_EP_BY_ENERGY[type_energie]
  └─ emissions_evitees_horizon_kg = delta_kwh_an × co2_factor × horizon_years
       │
       ▼
incorpore.compute_incorpore  (lit data/fdes_static.json — D-014)
  ├─ pour chaque MaterialQuantity : kgCO2eq_total = kgCO2eq_per_uf × quantity
  ├─ total = somme algébrique (positif = émissions ; négatif = stockage biogénique net)
  └─ breakdown[1 entrée / matériau] + total_biogenic_co2_stored_kg
       │
       ▼
evite_horssite.compute_evite_horssite
  ├─ base = somme des kgCO2eq_total POSITIFS du breakdown
  └─ emissions_evitees_kg = base × fraction (défaut 0.25 médiane CSTB, fourchette [20%, 40%])
       │
       ▼
total.compute_total + report_to_json
  net_kg_co2_eq_horizon =
      + incorpore.total_kg_co2_eq         (peut être négatif)
      - exploitation.emissions_evitees_horizon_kg
      - evite_horssite.emissions_evitees_kg

  verdict = "vertueux" si net < 0 sinon "emissif"
```

---

## 3. Facteurs d'émission (Base Carbone ADEME 2023)

Note méthodologique critique : le DPE est en **énergie primaire (kWh ep)**, les facteurs ADEME
sont en **énergie finale (kWh ef)**. Conversion via le coefficient EP (1.9 pour électricité,
1.0 pour les autres énergies — arrêté DPE 2021).

| Énergie | kgCO2/kWh ef (ADEME) | EP→EF | **kgCO2/kWh ep effectif** |
|---|---|---|---|
| Électricité | 0.064 | 1.9 | **0.034** |
| Gaz naturel | 0.227 | 1.0 | **0.227** |
| Fioul | 0.272 | 1.0 | **0.272** |
| Bois bûches/granulés | 0.024 | 1.0 | **0.024** |
| Réseau de chaleur (mix FR) | 0.116 | 1.0 | **0.116** |
| Pompe à chaleur (COP≈3) | — | 1.9 × 3 | **0.011** |
| Mix inconnu (médiane prudente) | — | — | **0.150** |

Source : `backend/app/carbon/factors.py` (dict `KG_CO2_PER_KWH_EP_BY_ENERGY`).

---

## 4. Midpoints kWh par classe DPE (arrêté 2021 / coef EP 1.9)

| Classe | kWh ep/m²/an (midpoint) |
|---|---|
| A | 55 |
| B | 90 |
| C | 145 |
| D | 215 |
| E | 295 |
| F | 390 |
| G | 500 |

Identiques à `scoring.compute.class_midpoints` (D-006 cohérence).

---

## 5. Hors-site — fraction évitée

Source : CSTB 2023 "Construction hors-site et bilan carbone" + retours d'expérience CD2E.
La part d'émissions évitées par préfabrication (logistique optimisée, dégâts chantier réduits,
moins de déchets) est dans la fourchette **20 % – 40 %** des émissions du procédé constructif.

| Fraction | Valeur |
|---|---|
| Basse | 20 % (HORS_SITE_AVOID_FRACTION_LOW) |
| **Médiane (défaut)** | **25 %** (HORS_SITE_AVOID_FRACTION_MEDIAN) |
| Haute | 40 % (HORS_SITE_AVOID_FRACTION_HIGH) |

**Convention de calcul** : appliquée **uniquement aux émissions positives** du breakdown FDES
(les matériaux biosourcés avec bilan négatif ont déjà leur bénéfice via le carbone biogénique
stocké — on ne double-compte pas). Le `EviteHorsSiteResult` expose `emissions_evitees_low_kg`
et `emissions_evitees_high_kg` pour afficher la fourchette dans l'UI.

---

## 6. Convention de signes

Pour éviter toute ambiguïté à la lecture :

- **`emissions_evitees_horizon_kg`** (exploitation) : POSITIF = CO₂ qui ne sera pas émis grâce à la
  rénovation. Plus c'est grand, mieux c'est.
- **`emissions_evitees_kg`** (hors-site) : POSITIF, même logique.
- **`total_kg_co2_eq`** (incorpore) : ALGÉBRIQUE. Positif = émissions du procédé constructif.
  Négatif = bilan favorable (le carbone biogénique stocké dépasse les émissions du procédé).
- **`net_kg_co2_eq_horizon`** : ÉMISSIONS NETTES du projet sur l'horizon.
  Plus c'est négatif, plus le projet est vertueux carbone.
  Si `net < 0` : `verdict = "vertueux"`. Sinon : `"emissif"`.

---

## 7. Carbone biogénique stocké

Les matériaux biosourcés (bois, chanvre, paille, ouate, fibre de bois, etc.) **stockent du CO₂
atmosphérique** dans leur biomasse. Cette valeur est remontée séparément dans
`total_biogenic_co2_stored_kg` (différente du `total_kg_co2_eq` qui est le bilan procédé seul).

L'UI affiche les deux :
- "Émissions nettes du projet (procédé + exploitation - hors-site) sur 30 ans : **-280 t CO₂eq**"
- "Dont **carbone biogénique stocké** dans les biosourcés : **+12 t CO₂eq** piégés"

Cette séparation est importante méthodologiquement : le RE2020 distingue **stockage temporaire**
(biomasse, comptabilité contestée) et **émissions évitées** (chiffrage robuste). ConX reste prudent
en présentant les deux côte à côte sans les sommer.

---

## 8. Exemple : passoire G → B 100 m², gaz, plan biosourcé

```python
from app.carbon import compute_total, MaterialQuantity, report_to_json

res = compute_total(
    surface_m2=100,
    classe_avant="G",
    classe_apres="B",
    type_energie_chauffage="gaz naturel",
    materials=[
        MaterialQuantity("bois-clt", 80, "Murs CLT"),
        MaterialQuantity("ouate-cellulose-insufflee", 200, "Combles+murs"),
        MaterialQuantity("triple-vitrage-4-12-4-12-4-argon", 25, "Fenêtres"),
    ],
)
print(report_to_json(res)["summary"])
```

Sortie typique (ordres de grandeur) :
```
{
  "net_kg_co2_eq_horizon": -290000,
  "net_t_co2_eq_horizon": -290.0,
  "horizon_years": 30,
  "emissions_evitees_exploitation_t_horizon": 279.2,   # passoire G→B gaz
  "incorpore_t": -1.5,                                   # bois domine
  "evite_horssite_t": 1.4,                               # 25% de la part positive
  "biogenic_stored_t": 18.3,
  "verdict": "vertueux"
}
```

---

## 9. Sources affichables (UI obligatoire)

Chaque chiffre dans l'UI vient avec sa source citable. Le dict `SOURCE_REFERENCES`
(`backend/app/carbon/factors.py`) contient les 4 sources canoniques :

```python
SOURCE_REFERENCES = {
    "ademe_base_carbone": "ADEME Base Carbone 2023 — https://base-carbone.ademe.fr/",
    "dpe_arrete_2021":    "Arrêté DPE 2021 (coef EP 1.9 anticipé 2026)",
    "cstb_horssite":      "CSTB 2023 — Construction hors-site et bilan carbone",
    "inies_fdes":         "INIES — base statique D-014",
}
```

Le module remonte les hypothèses sous forme de dict `hypotheses` pour chaque sous-résultat.
L'UI doit afficher ces hypothèses dans un tooltip ou une section "Détail de calcul" cliquable.

---

## 10. Limites connues

- **Pas de prise en compte de la durée de vie** (`duration_years` dans la FDES) : les calculs
  supposent que les matériaux durent au moins l'horizon de l'analyse (30 ans). À enrichir si le
  client demande une amortissement matériel.
- **Pas de calcul de la **part PAC** vs résistance simple** : on bucket "PAC" si le terme apparaît
  dans `type_energie_chauffage`. Pas de prise en compte fine du COP réel.
- **Hors-site fraction médiane** appliquée mais non personnalisable selon le procédé. Une étude
  CSTB 2024 pourra affiner par typologie (CLT vs MOB vs paille).
- **Pas de comptabilité ACV cradle-to-grave complète** : on suit l'approche "incorporé module A1-A3"
  (production) + "exploitation B6" (énergie), pas la fin de vie C. Suffit pour le MVP.
- **Pas de gestion devises** (€) — voir SCORING.md pour le coût €/tCO₂eq évité.

---

## 11. Tests d'invariants

`backend/tests/test_carbon.py` — 32 tests :

| Bloc | Tests |
|---|---|
| Facteurs énergie | `test_normalize_energy` (10 cas), `test_factor_for_each_known_energy` |
| Exploitation 10 cas | passoire G→B gaz, E→C élec, F→A PAC, D→C minor, real_kwh override, unknown→D fallback, invalid classe, zero surface, horizon 50 ans, hypothèses format |
| Incorpore | 30 matériaux, bois CLT carbone négatif, unknown raises, zero quantity, breakdown |
| Évite hors-site | 25 % défaut, all biosource→0, invalid fraction |
| Total | passoire G→B+bois vertueux, D→C+béton, JSON structure |

Lancement :
```bash
cd backend && python -m pytest tests/test_carbon.py -q
```

---

## 12. Fichiers et chemins

```
backend/app/carbon/
  __init__.py           — exports publics
  factors.py            — coefs ADEME + midpoints DPE + fractions hors-site
  exploitation.py       — compute_exploitation (gain CO2 sur horizon)
  incorpore.py          — compute_incorpore (lit fdes_static.json)
  evite_horssite.py     — compute_evite_horssite
  total.py              — compute_total + report_to_json

backend/tests/test_carbon.py  — 32 tests

data/fdes_static.json   — 30 matériaux clés (D-014)
```
