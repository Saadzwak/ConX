---
name: ifc-check
description: Validation syntaxique d'un fichier IFC + pré-vérification RE2020/PMR (largeur portes, pente rampes, R/U des parois, présence d'IfcEntities clés). À utiliser quand l'utilisateur uploade un IFC pour pré-validation conformité, ou demande un check qualité d'un projet BIM.
---

# ifc-check — Validation IFC + pré-vérification RE2020/PMR

## Quand utiliser cette skill

- L'utilisateur drop un fichier IFC dans le mode Conformité.
- L'agent Conformité doit produire un rapport "RE2020 OK / PMR à corriger".
- Pré-vérification rapide d'un projet BIM avant remise au bureau de contrôle.

**Pas un remplacement du bureau de contrôle**. L'UI doit afficher en gros :
*"Pré-vérification — ne remplace pas un bureau de contrôle agréé"*.

## Pré-requis package

L'environment Anthropic doit avoir :
```yaml
packages:
  pip:
    - ifcopenshell
```

Test validé en local 2026-05-22 : `pip install ifcopenshell` dans python:3.12-slim
vanilla fonctionne, `import ifcopenshell; print(ifcopenshell.version)` → 0.8.5.
**Skill bundle viable**, pas besoin de bascule HTTP backend (B-001 résolu).

## Fonctionnalités

`ifc_validator.py` produit un rapport JSON structuré :

```json
{
  "filename": "projet.ifc",
  "ifc_schema": "IFC4",
  "valid_syntax": true,
  "n_entities": 12345,
  "summary": {
    "n_walls": 124,
    "n_doors": 28,
    "n_windows": 56,
    "n_stairs": 4,
    "n_ramps": 1,
    "n_spaces": 67
  },
  "re2020_checks": {
    "uw_doors_below_1_3": {"pass": true, "min": 1.1, "max": 1.4, "count_fail": 2},
    "uw_windows_below_1_3": {"pass": true},
    "r_walls_above_3_7": {"pass": false, "count_fail": 5, "details": [...]}
  },
  "pmr_checks": {
    "door_width_min_900mm": {"pass": false, "count_fail": 3, "details": [...]},
    "ramp_slope_max_5pct": {"pass": false, "count_fail": 1, "details": [{"id":"#42", "slope_pct": 7.2}]}
  },
  "anomalies": ["Aucune IfcSpace définie", ...],
  "rapport_pdf_recommended": true
}
```

## Règles RE2020 vérifiées (sous-ensemble MVP)

- `uw_doors_below_1_3` : U fenêtre/porte ≤ 1.3 W/m².K (Pset_DoorCommon/WindowCommon).
- `r_walls_above_3_7` : R mur ≥ 3.7 m².K/W (cible MaPrimeRénov niveau "isolation efficace").
- `r_toiture_above_6_0` : R toiture ≤ 6.0 m².K/W.
- Présence de `IfcSpace` (sinon l'agent ne peut pas calculer le SHAB/SHON).
- Présence de Psets cohérents (Pset_WallCommon, Pset_DoorCommon, …).

Voir `references/re2020_thresholds.md` pour les seuils complets.

## Règles PMR vérifiées (sous-ensemble MVP)

- `door_width_min_900mm` : largeur portes accessibles ≥ 0.90 m.
- `ramp_slope_max_5pct` : pente rampes ≤ 5 % (8 % toléré pour 0.5 m de long).
- `corridor_width_min_1_4m` : couloirs accessibles ≥ 1.40 m.

Voir `references/pmr_rules.md` pour les règles complètes.

## Limites importantes (signaler à l'utilisateur)

- **Périmètre étroit** : seuls les 10-15 contrôles ci-dessus sont vérifiés. Un bureau
  de contrôle en vérifie ~200.
- **Schémas IFC supportés** : IFC2x3, IFC4, IFC4.3. Schémas propriétaires (Revit
  natif sans export IFC) non gérés.
- **Try/except global** : si un fichier IFC est mal formé, on retourne un rapport
  d'erreur graceful avec message "Fichier IFC non parseable — vérifier la version
  IFC".
- **Pas de validation du modèle géométrique** : on vérifie la PRÉSENCE et les Psets,
  pas la cohérence géométrique 3D (intersections, doublons, etc.).

## Exemple d'usage

```bash
python ifc_validator.py /chemin/projet.ifc > rapport.json
```

Puis l'agent Conformité résume le JSON en langage naturel et l'UI affiche les
non-conformités cliquables avec liens vers la documentation MaPrimeRénov / Service
Public PMR.
