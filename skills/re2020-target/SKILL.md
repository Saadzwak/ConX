---
name: re2020-target
description: Indicateurs principaux RE2020 (Bbio, Cep_nr, Ic_construction, Ic_energie, DH) avec seuils et logiques de cible pour rénovation. À utiliser quand l'agent Plan définit une cible classe DPE après rénovation, ou quand l'agent Conformité vérifie qu'un projet IFC répond à RE2020.
---

# re2020-target — Indicateurs RE2020 et seuils

## Quand utiliser cette skill

- Définir une **classe DPE cible** réaliste après rénovation (lien avec `S_co2` du scoring).
- Vérifier que les choix matériaux et énergétiques sont compatibles RE2020.
- Expliquer à l'utilisateur les contraintes réglementaires (Bbio, Cep_nr, Ic_construction).
- Pour la rénovation : MaPrimeRénov, certif BBC-rénovation, DPE 2026 (coef EP 1.9).

## Cadre réglementaire (résumé)

### Constructions neuves — RE2020 (depuis 2022)

| Indicateur | Définition | Seuil neuf logement collectif |
|---|---|---|
| Bbio | Besoin bioclimatique (chauffage, refroidissement, éclairage) | ≤ Bbio_max (selon climat, surface) |
| Cep_nr | Consommation énergie primaire non renouvelable | ≤ 70-110 kWh ep/m²/an |
| Ic_construction | Carbone procédé constructif (incorporé A1-A5) | ≤ 740 puis 700 puis 600 kgCO2eq/m² (2025/2028/2031) |
| Ic_energie | Carbone exploitation énergétique (B6) sur 50 ans | ≤ 560 → 320 kgCO2eq/m² (2025 → 2031) |
| DH | Durée d'inconfort été | ≤ 1250 °C.h |

### Rénovation lourde (déclaration MaPrimeRénov / BBC-rénov)

Pas de RE2020 strict mais des cibles de gain énergétique :
- **DPE post-travaux ≤ E** pour MaPrimeRénov "Sérénité".
- **Gain ≥ 35 % kWh ep/m²/an** pour MaPrimeRénov.
- **DPE post-travaux ≤ B** pour BBC-rénovation 2024.

### DPE 2026 — réforme coefficient EP électricité

À partir du 2026-01-01 : coef EP électricité = **1.9** (au lieu de 2.3).
La BDNB 2025-07.a embarque déjà cette anticipation (cf. CLAUDE.md).
ConX aligne tous ses calculs (scoring, carbon, classes) sur ce coef.

## Règles de prescription

### Cible classe DPE après rénovation

```
Si classe_avant ∈ {F, G} (passoire) :
  - Cible standard : C (gain 2-3 classes, MaPrimeRénov éligible)
  - Cible ambitieuse : B (BBC-rénovation, financement aidé majoré)
  - Cible avant-gardiste : A (rare, bâtiment compatible avec ITE+menuiseries+VMC)

Si classe_avant ∈ {D, E} :
  - Cible : C ou B
  - Si bâtiment <1948 ou monument historique : C suffit, ne pas dégrader le bâti.

Si classe_avant ∈ {A, B, C} :
  - Rénovation légère, cible A ou B, focus sur ECS et étanchéité.
```

### Logique Ic_construction (rénovation hors-site)

Le poste **construction (A1-A5)** d'une rénovation hors-site biosourcée est typiquement
**négatif ou très faible** (stockage biogénique > émissions procédé), ce qui rend la
rénovation hors-site biosourcée **MIEUX que neuf** sur ce critère.

À justifier dans le pitch jury : "Notre plan de rénovation biosourcée a un
Ic_construction négatif de -150 kgCO2eq/m² grâce au stockage CO2 dans le chanvre +
bois CLT, contre 600 kgCO2eq/m² pour une construction neuve béton standard."

## Indicateurs à calculer (skill carbon-calc)

L'agent Plan utilise `carbon-calc` pour produire :
- `exploitation.emissions_evitees_horizon_kg` → équivalent Ic_energie économisé.
- `incorpore.total_kg_co2_eq + biogenic_stored_kg` → Ic_construction effective.
- `summary.net_t_co2_eq_horizon` → bilan total 30 ans.

Citer dans le rapport :
> "Ce plan respecte RE2020 (Ic_construction = -120 kgCO2eq/m² avec le carbone
> biogénique, bien sous le seuil 700 kgCO2eq/m² applicable au neuf 2028)."

## Limites

- ConX ne fait pas une étude RE2020 complète (StD, Bbio, RT_existant). Il pré-calcule
  les indicateurs carbone et énergie sur la base des plans matériaux/énergie.
- L'étude RE2020 officielle (par un BET) reste nécessaire pour les bâtiments neufs.
- Pour rénovation : MaPrimeRénov et BBC-rénov ont des modèles déclaratifs propres.

## Références

- Décret n°2021-1004 du 29/07/2021 (RE2020).
- Arrêté du 31/03/2021 modifié 2025 (DPE coef EP).
- Guide ADEME "RE2020 — Les essentiels" 2023.
