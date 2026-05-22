# ConX — Mode Conformité (J13)

**Statut** : livré, **non testé contre IFC réel** dans le container backend
(rebuild de l'image en cours avec libpango + ifcopenshell).
**Décisions** : D-009 (skills + endpoint backend), D-011 (Supabase pour
métadonnées), R5 (try/except global).

---

## 1. Workflow

```
Frontend (drag-and-drop .ifc)         Backend FastAPI                 Volume Docker
    │                                       │                                 │
    │  POST /api/ifc/upload (multipart)     │                                 │
    ├──────────────────────────────────────►│                                 │
    │                                       │ Save → /data/storage/ifc/<u>/   │
    │                                       │   <validation_id>.ifc           │
    │                                       │─────────────────────────────────►│
    │                                       │                                 │
    │                                       │ ifc/validator.py validate_ifc() │
    │                                       │   (IfcOpenShell + règles RE2020/PMR)
    │                                       │                                 │
    │                                       │ ifc/pdf.py render_pdf()         │
    │                                       │   (jinja2 → weasyprint)         │
    │                                       │─────────────────────────────────►│
    │                                       │                            /data/
    │                                       │                       storage/pdf/
    │                                       │                       <u>/<vid>.pdf
    │                                       │                                 │
    │                                       │ INSERT app.ifc_validations      │
    │                                       │   (Supabase, RLS auth.uid())   │
    │                                       │                                 │
    │◄── { validation_id, rapport_json, ────│                                 │
    │     pdf_url, re2020_pass, pmr_pass }  │                                 │
    │                                       │                                 │
    │  GET /api/ifc/pdf/{vid}               │                                 │
    ├──────────────────────────────────────►│                                 │
    │                                       │  Lit /data/storage/pdf/<u>/<v>  │
    │                                       │◄────────────────────────────────│
    │◄── application/pdf ──────────────────│                                 │
```

---

## 2. Endpoints

### 2.1 `POST /api/ifc/upload` (auth requise)

Multipart form-data, champ `file` (`.ifc` ou `.ifczip`, max 200 Mo).

Réponse :
```json
{
  "validation_id": "uuid-v4",
  "ifc_filename": "projet_lille.ifc",
  "rapport_json": {
    "filename": "projet_lille.ifc",
    "valid_syntax": true,
    "ifc_schema": "IFC4",
    "n_entities": 12345,
    "summary": {"n_walls": 18, "n_doors": 24, ...},
    "re2020_checks": {
      "uw_doors_below_1_3": {"pass": true, "n_checked": 24, "n_fail": 0},
      "uw_windows_below_1_3": {"pass": false, "n_checked": 32, "n_fail": 2, "details": [...]},
      "r_walls_above_3_7": {"pass": false, "n_checked_external": 18, "n_fail": 5, "details": [...]}
    },
    "pmr_checks": {
      "door_width_min_900mm": {"pass": false, "n_checked": 24, "n_fail": 3, "details": [...]},
      "ramp_slope_max_5pct": {"pass": false, "n_checked": 1, "n_fail": 1, "details": [{"slope_pct": 7.2}]}
    },
    "anomalies": ["Aucune IfcSpace définie pour 12 zones..."],
    "disclaimer": "Pré-vérification ConX — ne remplace pas un BCT agréé. ..."
  },
  "pdf_url": "/api/ifc/pdf/<validation_id>",
  "re2020_pass": false,
  "pmr_pass": false
}
```

Pipeline : sauvegarde fichier → `validate_ifc()` → `render_pdf()` →
`INSERT app.ifc_validations` (no-op si Supabase pas configuré).

⚠ Cible perf : < 10 s pour un IFC de 50 Mo. Au-delà, code synchrone — file
d'attente prévue J16 si besoin.

### 2.2 `GET /api/ifc/pdf/{validation_id}` (auth requise)

Renvoie le PDF binaire. La vérification d'ownership passe par Supabase RLS
(la query échoue si l'utilisateur n'est pas owner).

### 2.3 `GET /api/ifc/validations` (auth requise)

Liste les validations de l'utilisateur (50 plus récentes).

---

## 3. Contrôles RE2020 (sous-ensemble MVP)

| Code interne | Seuil | Source |
|---|---|---|
| `uw_doors_below_1_3` | U portes ≤ 1.3 W/m².K | RE2020 (décret 2021-1004) |
| `uw_windows_below_1_3` | U fenêtres ≤ 1.3 W/m².K | RE2020 |
| `r_walls_above_3_7` | R murs extérieurs ≥ 3.7 m².K/W | RE2020 |

Lecture des valeurs : `Pset_DoorCommon.ThermalTransmittance`,
`Pset_WindowCommon.ThermalTransmittance`, `Pset_WallCommon.ThermalResistance`
(+ `IsExternal` pour filtrer).

Si un Pset est absent → contrôle ignoré (pas d'échec). L'agent Conformité
(J17 optionnel) commente l'absence.

---

## 4. Contrôles PMR (sous-ensemble MVP)

| Code interne | Seuil | Source |
|---|---|---|
| `door_width_min_900mm` | Largeur ≥ 0.90 m | NF P 99-611 |
| `ramp_slope_max_5pct` | Pente ≤ 5 % | Arrêté 8 déc 2014 |

Conversion radians → degrés si valeur < 1 (heuristique).

---

## 5. Disclaimer obligatoire

Affiché en haut **ET en bas** du rapport PDF :

> ⚠ Pré-vérification ConX — ne remplace pas un bureau de contrôle agréé.
> Le périmètre vérifié est étroit (10-15 contrôles sur ~200 qu'un BCT
> vérifie). L'attestation d'accessibilité PMR (article R.111-19-23 CCH)
> doit être délivrée par un contrôleur technique ou architecte indépendant.

---

## 6. Dépendances système

Container backend (`backend/Dockerfile`) :
- `libgl1`, `libgomp1` : runtime IfcOpenShell C++.
- `libpango-1.0-0`, `libpangoft2-1.0-0`, `libcairo2`, `libffi-dev`,
  `shared-mime-info` : runtime WeasyPrint.

Python (`backend/requirements.txt`) :
- `ifcopenshell==0.8.5` (testé OK en J9).
- `jinja2==3.1.4`, `weasyprint==63.1`.
- `python-multipart==0.0.20` (FastAPI form-data).

---

## 7. Stockage

```
data/storage/ifc/<user_id>/<validation_id>.ifc      # upload
data/storage/pdf/<user_id>/<validation_id>.pdf      # généré
```

Persistance dans `app.ifc_validations` Supabase (RLS).
Pas de FK vers `auth.users` côté backend — c'est Supabase qui gère.

---

## 8. Tests

```bash
cd backend
python -m pytest tests/test_ifc_pdf.py tests/test_ifc_router.py -v
# 11 tests passed, 1 skipped (render_pdf_smoke nécessite weasyprint installé)
```

Le smoke test `test_render_pdf_smoke` tourne dans le container backend
(`docker compose exec backend pytest tests/test_ifc_pdf.py -v`).

---

## 9. Limites connues

- Pas testé contre un IFC réel dans le container backend (rebuild en cours
  pour intégrer libpango + ifcopenshell). Le partenaire devra valider avec
  un fichier test (BIMobject ou github/IfcOpenShell test-files).
- Pas de validation géométrique 3D (intersections, doublons, espaces vides).
- IFC2x3, IFC4, IFC4.3 supportés via IfcOpenShell 0.8.5. Schémas
  propriétaires non gérés.
- Agent Conformité (Anthropic) non branché en J13 — la pré-vérification
  locale + le PDF jinja2 suffisent pour la démo. Branchement possible en
  J17 (~0.10-0.20 € par validation, règle §9.D).

---

## 10. Liens

- `skills/ifc-check/SKILL.md` : règles RE2020/PMR documentées
- `agents/system_prompts/conformite.md` : agent Conformité (J17)
- `DECISIONS.md` : D-009, D-011
- `BUILD_LOG.md` Session 11 : journal J13
