---
name: carbon-calc
description: Calcul déterministe du bilan carbone d'un projet de rénovation (exploitation 30 ans + matériaux FDES + préfabrication évitée). À utiliser quand l'utilisateur demande un bilan carbone, des t CO2 évitées, un comparatif de matériaux, ou une justification chiffrée des choix de plan.
---

# carbon-calc — Bilan carbone déterministe ConX

## Quand utiliser cette skill

Utilise cette skill **chaque fois** que tu dois produire un chiffre carbone dans un
plan de rénovation : t CO₂ évitées, émissions incorporées, gain hors-site, comparatif
matériaux. **Ne JAMAIS estimer ces chiffres mentalement** — D-006 de ConX impose
que les valeurs viennent d'un calcul déterministe traçable.

## Outils fournis

⚠ **Connu — B-010** : ce skill bundle dépend de `backend/app/carbon/*` qui n'est PAS
inclus dans le zip uploadé sur Anthropic. **Avant l'upload, il faudra "aplatir"** :
copier les modules `backend/app/carbon/` dans `skills/carbon-calc/_lib/` et adapter
les imports. Alternativement : exposer le calcul via un endpoint HTTP backend que
la skill appelle. À traiter en J10 (cf. docs/SKILLS.md §10).

En attendant (dev local) :
```bash
PYTHONPATH=backend python skills/carbon-calc/carbon_calc.py --surface 100 ...
```

- `carbon_calc.py` : fonction `calculate_carbon_report(surface_m2, classe_avant,
  classe_apres, materials, type_energie_chauffage, horizon_years)` retourne un dict
  JSON structuré (exploitation, incorpore, evite_horssite, summary).
- `references/fdes_static.json` : base de 30 matériaux clés avec leur empreinte FDES
  (cf. skill `fdes-lookup` pour les lookups détaillés).
- `references/ademe_factors.md` : facteurs d'émission par énergie (Base Carbone ADEME 2023).

## Utilisation pas-à-pas

1. Identifie les paramètres : surface_m2, classe DPE actuelle, classe DPE cible,
   liste des matériaux + quantités, type d'énergie de chauffage.
2. Lance `python carbon_calc.py --surface 100 --avant G --apres B --energie gaz \
     --material bois-clt=80 --material ouate-cellulose-insufflee=200`.
3. Le script imprime un JSON structuré avec :
   - `summary.net_t_co2_eq_horizon` (négatif = vertueux)
   - `summary.emissions_evitees_exploitation_t_horizon`
   - `summary.incorpore_t` (peut être négatif si biosourcés dominent)
   - `summary.evite_horssite_t` (≈ 25% de l'incorporé positif)
   - `summary.biogenic_stored_t` (carbone biogénique séquestré)
4. Cite les sources affichées dans l'UI : Base Carbone ADEME 2023, arrêté DPE 2021,
   INIES FDES n°XXX, CSTB hors-site 2023.

## Convention de signes (CARBON.md §6)

- **emissions_evitees_horizon_kg** (exploitation) : POSITIF = CO₂ qui ne sera PAS émis grâce
  à la rénovation. Plus c'est grand, mieux c'est.
- **total_kg_co2_eq** (incorpore) : ALGÉBRIQUE. Positif = émissions du procédé,
  négatif = bilan biosourcé favorable.
- **net_kg_co2_eq_horizon** : émissions nettes du projet sur l'horizon.
  Plus c'est négatif, plus c'est vertueux.

Ne mélange jamais "incorporé négatif" et "émissions évitées" — ce sont deux concepts
distincts (la première = stockage matière, la seconde = procédé chantier).

## Horizon par défaut

30 ans (rénovation thermique RE2020). Pour les bâtiments neufs : 50 ans. Override via
`--horizon-years`.

## Limites à signaler à l'utilisateur

- Les FDES sont indicatives (numéros TBC-J9 à confirmer base-inies.fr).
- Le coefficient EP électricité 1.9 anticipe la réforme 2026-01-01.
- Le carbone biogénique stocké est affiché séparément (RE2020 prudent, pas d'addition).
- La fraction hors-site évitée (25%) est la médiane CSTB ; fourchette [20%, 40%].
