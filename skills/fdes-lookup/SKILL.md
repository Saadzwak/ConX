---
name: fdes-lookup
description: Recherche dans la base FDES statique ConX (30 matériaux clés biosourcés/conventionnels). À utiliser quand l'utilisateur cherche les caractéristiques carbone d'un matériau, ou quand l'agent Plan veut comparer des options matériaux pour un projet.
---

# fdes-lookup — Base FDES statique ConX (D-014)

## Quand utiliser cette skill

Quand tu dois :
- Donner le kgCO2eq/UF d'un matériau précis.
- Lister les options biosourcées pour une fonction (isolation, structure, vitrage…).
- Comparer plusieurs matériaux côté empreinte carbone et stockage biogénique.
- Citer un numéro de déclaration FDES pour la traçabilité UI.

## Source

`references/fdes_static.json` (D-014) : 30 matériaux clés compilés depuis INIES,
documentation publique et rapports ADEME. Pas d'API INIES — base statique.

## 30 matériaux indexés (catégories)

- **biosource** (8) : bois CLT, MOB, lamellé-collé, ouate cellulose, fibre bois,
  laine chanvre, béton chanvre, paille, liège
- **mineral** (8) : terre crue BTC, pisé, brique terre cuite monomur, brique
  perforée, béton C25/30, béton bas-carbone CEM-III, béton de chaux, mortier chaux
- **metal** (2) : acier construction, aluminium menuiserie
- **synthétique** (4) : laine de verre, laine de roche, PSE, PIR
- **vitrage / menuiserie** (5) : double vitrage 4/16/4 argon, triple vitrage,
  menuiserie bois, menuiserie PVC
- **enduit / parement** (3) : membrane EPDM, plaque BA13, enduit terre

## Schéma JSON

```json
{
  "id": "bois-clt",
  "name": "Bois lamellé-croisé (CLT)",
  "fdes_declaration_id": "TBC-J9",
  "category": "biosource",
  "kgCO2eq_per_uf": -28.5,
  "uf_description": "1 m² de paroi CLT 100 mm d'épaisseur, durée de vie 100 ans",
  "duration_years": 100,
  "biogenic_co2_stored_kg": 73.0,
  "thermal_conductivity_lambda": 0.13,
  "density_kg_m3": 470,
  "notes": "Carbone biogénique stocké important. Préfa hors-site standard."
}
```

## Utilisation

Lecture directe du JSON :
```python
import json
fdes = json.load(open("references/fdes_static.json"))
for m in fdes["materials"]:
    if "chanvre" in m["name"].lower():
        print(m["id"], m["kgCO2eq_per_uf"], m["uf_description"])
```

Ou via `python lookup.py --by-id bois-clt`, `--by-category biosource`,
`--search chanvre`.

## Citation UI obligatoire

Chaque fois qu'un chiffre FDES apparaît dans la réponse à l'utilisateur, cite :

> Source : INIES, FDES n°<fdes_declaration_id> (base ConX consultée le <date>).

Pour les `TBC-J9` (à confirmer), précise : *"Numéro de déclaration FDES à confirmer
manuellement sur base-inies.fr — valeur indicative compilée depuis documentation
publique INIES."*

## Limites

- 30 matériaux seulement (vs ~5800 sur INIES). Si un matériau hors base est demandé,
  signale à l'utilisateur : *"Matériau non répertorié dans la base ConX. Consulte
  base-inies.fr directement pour la FDES officielle, et signale-nous le besoin
  d'ajout."*
- `kgCO2eq_per_uf` exprimé en UF du matériau (m² ou m³ selon `uf_description`).
- Pour isolants : R=5 m².K/W sauf mention. Adapter si épaisseur différente.
