# ConX — Skills Anthropic (J9)

**Statut** : 6 Skills définies sur disque (`skills/`), **NON uploadées** sur Anthropic
(règle §9.D — aucune dépense sans validation explicite).
**Dernière mise à jour** : 2026-05-22.
**Test critique ifcopenshell** : ✅ PASS (cf. §3).

---

## 1. Architecture des Skills

Une Skill Anthropic est un dossier avec :
- `SKILL.md` — frontmatter YAML (`name`, `description`) + corps Markdown (instructions).
- Scripts Python optionnels (bash-exécutables par l'agent).
- `references/` — fichiers statiques (JSON, MD) chargés à la demande par l'agent.

Modèle ConX :

```
skills/
  carbon-calc/
    SKILL.md
    carbon_calc.py
    references/fdes_static.json
  fdes-lookup/
    SKILL.md
    lookup.py
    references/fdes_static.json
  ifc-check/
    SKILL.md
    ifc_validator.py
  horssite-biosource/
    SKILL.md
  re2020-target/
    SKILL.md
  pmr-checks/
    SKILL.md
```

---

## 2. Les 6 Skills

| # | Nom | Type | Usage agent |
|---|---|---|---|
| 1 | **carbon-calc** | code | Bilan carbone déterministe (exploit 30 ans + FDES + hors-site) |
| 2 | **fdes-lookup** | code + JSON | Recherche dans la base FDES statique 30 matériaux (D-014) |
| 3 | **ifc-check** | code (ifcopenshell) | Validation IFC + pré-checks RE2020 + PMR |
| 4 | **horssite-biosource** | knowledge | Catalogue 8 procédés clés (chanvre, MOB, paille, PAC, …) avec fabricants HDF |
| 5 | **re2020-target** | knowledge | Indicateurs RE2020 + seuils + logique de cible classe DPE |
| 6 | **pmr-checks** | knowledge | Règles PMR (10 contrôles MVP) + mapping Psets IFC |

---

## 3. Test critique ifcopenshell (2026-05-22)

Lancé dans un container Python 3.12-slim vanilla :

```bash
docker run --rm python:3.12-slim sh -c \
  "pip install ifcopenshell && python -c 'import ifcopenshell; print(ifcopenshell.version)'"
```

Résultat :
```
Successfully installed ifcopenshell-0.8.5 ...
VERSION: 0.8.5
```

**Conclusion** : `pip install ifcopenshell` fonctionne en environnement Python vanilla
(pas besoin d'apt install OpenCASCADE séparément). L'environnement Anthropic Managed
Agents avec `packages: {pip: ['ifcopenshell']}` peut donc embarquer la skill `ifc-check`
en bundle direct, **sans bascule vers un endpoint HTTP backend**. Bonne nouvelle pour
la simplicité d'architecture (D-009 confirmé).

---

## 4. Mapping Skills ↔ Agents

| Agent | Skills attachées |
|---|---|
| **Sélection** | `selection-scoring` (à créer J10, lit le scoring backend via HTTP) |
| **Plan** | `carbon-calc`, `fdes-lookup`, `horssite-biosource`, `re2020-target` |
| **Conformité** | `ifc-check`, `re2020-target`, `pmr-checks` |

---

## 5. Upload sur Anthropic (NON FAIT cette nuit — voir B-009)

La Skills API requiert :
1. Une clé API Anthropic active (`ANTHROPIC_API_KEY` dans .env).
2. Un compte avec accès **beta `skills-2025-10-02`**.
3. Le SDK `pip install anthropic`.

Procédure d'upload (à exécuter par le partenaire en J10) :

```python
import os, anthropic, pathlib

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    default_headers={
        "anthropic-beta": "skills-2025-10-02,files-api-2025-04-14,code-execution-2025-08-25",
    },
)

# Pour chaque dossier dans skills/, zipper et uploader
import zipfile, io
for skill_dir in pathlib.Path("skills").iterdir():
    if not skill_dir.is_dir():
        continue
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in skill_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(skill_dir))
    buf.seek(0)
    skill = client.beta.skills.create(
        name=skill_dir.name,
        zip_file=buf,
    )
    print(skill.id, skill.name)
```

Le partenaire stocke les `skill_id` retournés dans `agents/skills.yaml`
(à créer) pour les passer aux agents (D-009 + plan §2.5).

**Coût estimé upload** : négligeable (< 1 €). Mais comme c'est une dépense, validation
explicite du partenaire requise avant exécution (règle §9.D).

---

## 6. Détails par Skill

### 6.1 carbon-calc
- **Wrapper léger** autour de `backend/app/carbon/` (D-006 : un seul calcul).
- CLI : `python carbon_calc.py --surface 100 --avant G --apres B --energie gaz \
   --material bois-clt=80`.
- Sortie JSON structurée pour parsing direct par l'agent.

### 6.2 fdes-lookup
- Lecture directe de `references/fdes_static.json`.
- CLI : `python lookup.py --by-id bois-clt | --by-category biosource | --search chanvre`.
- 30 matériaux indexés (D-014).

### 6.3 ifc-check
- ifcopenshell + 10-15 contrôles RE2020/PMR (sous-ensemble MVP).
- CLI : `python ifc_validator.py /chemin/projet.ifc`.
- Sortie JSON avec `re2020_checks`, `pmr_checks`, `anomalies`, `disclaimer`.
- ⚠ Ne remplace pas un BCT.

### 6.4 horssite-biosource (knowledge pure)
- Catalogue 8 procédés clés : ITE chanvre, MOB ouate, MOB chanvre, ITE paille,
  fibre bois soufflée, triple vitrage bois local, VMC DF préfa, PAC modulaire.
- Fabricants HDF référencés (Hemp Block Tilloy, Sytane, Pavibois Aulnoy, …).
- Règles de prescription par typologie + climat HDF.

### 6.5 re2020-target (knowledge pure)
- Bbio, Cep_nr, Ic_construction, Ic_energie, DH avec seuils 2025/2028/2031.
- DPE 2026 coef EP 1.9 (CLAUDE.md).
- Logique de cible classe DPE post-rénovation selon classe avant.

### 6.6 pmr-checks (knowledge pure)
- 10 contrôles MVP (largeurs portes/couloirs, pente rampes, dim WC PMR, …).
- Mapping Psets IFC pour ifc-check.
- Recommandations Plan (kit préfa WC PMR, sols R10/R12, etc.).

---

## 7. État actuel et next steps

| Item | État |
|---|---|
| 6 SKILL.md créés | ✅ |
| 2 scripts Python (carbon_calc, lookup, ifc_validator) | ✅ |
| Test ifcopenshell | ✅ pass v0.8.5 |
| references/fdes_static.json copié dans 2 skills | ✅ |
| Upload Anthropic Skills API | ⏸ DIFFÉRÉ — validation partenaire requise (coût, même mineur) |
| Mapping skill_ids ↔ agents.yaml (J10) | ⏸ Après upload |
| Tests d'intégration skills depuis Managed Agent | ⏸ J10 |

---

## 8. BLOCKERS

- **B-009** (à ouvrir) : upload Skills API nécessite validation explicite partenaire
  (règle §9.D — aucune dépense même mineure sans accord). Coût attendu : très faible
  (< 1 €). Action partenaire : valider via DECISIONS.md ou message directe.

---

## 9. Fichiers et chemins

```
skills/
  carbon-calc/
    SKILL.md, carbon_calc.py, references/fdes_static.json
  fdes-lookup/
    SKILL.md, lookup.py, references/fdes_static.json
  ifc-check/
    SKILL.md, ifc_validator.py
  horssite-biosource/SKILL.md
  re2020-target/SKILL.md
  pmr-checks/SKILL.md

docs/SKILLS.md  ← ce document
```
