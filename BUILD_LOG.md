# ConX — Build log

Journal chronologique des sessions de travail.
Format d'entrée : date, durée réelle vs estimée, ce qui a marché, ce qui a coincé, prochaine étape.

---

## Modèle d'entrée

```
## YYYY-MM-DD — Session N (Jalon JX)

**Durée** : Xh réelles (estimé : Yh)
**Tokens consommés** : ~XXk (si pertinent)
**Objectif** : [ce qu'on voulait faire ce jour-là]

### Ce qui a marché
- [point]

### Ce qui n'a pas marché / contournements
- [point + comment résolu]

### Décisions prises
- [voir DECISIONS.md entrée du jour]

### Bloqueurs ouverts
- [voir BLOCKERS.md]

### Prochaine étape
- [jalon suivant + ce qu'il faut résoudre avant]
```

---

## 2026-05-21 — Session 0 (Pré-implémentation)

**Durée** : ~30 min de préparation documentaire
**Objectif** : Plan validé, 7 points préparatoires demandés par le partenaire (CLAUDE.md, SCORING.md, DATA_SOURCES.md, BUILD_LOG.md, BLOCKERS.md, DECISIONS.md, vérif Supabase + Managed Agents + environnement).

### Ce qui a marché
- Plan technique complet rédigé et validé à 95 % par le partenaire (`~/.claude/plans/brief-projet-plateforme-iridescent-bird.md`).
- Décisions utilisateur capturées : nom produit ConX, périmètre HDF entière, Supabase, chat itératif, Supabase Auth, repo privé.
- Environnement local vérifié : Python 3.12.10, Node 24.6.0, Docker 29.3.1, Docker Compose v5.1.0, Git 2.53, 214.9 GB libres → **tout OK**.
- Supabase Storage : 5 GB par fichier en upload standard → **OK pour LAZ et glTF** (avant pivot D-011).
- Managed Agents `managed-agents-2026-04-01` confirmé actif. Sessions ont 4 statuts (idle/running/rescheduling/terminated), environments persistent jusqu'à archive/delete.

### Ce qui n'a pas marché
- TTL session Managed Agents non documenté explicitement → B-001 (test J10).
- Maturité asyncio `supabase-py` non confirmée → B-002 (test J11, sévérité réduite après D-011).

### Décisions prises
- D-001 à D-010 + ajustements ultérieurs (D-011 split local/cloud, D-012 JWT PyJWT HS256, D-013 ngrok).

### Bloqueurs ouverts post-session
- B-001 (TTL session Managed Agents), B-003 (API INIES).
- B-002 → MINEUR confirmé. B-004 → résolu (déploiement post-concours). B-005 → résolu (PyJWT HS256).

### Prochaine étape
- J1 : setup repo + docker-compose + scripts.

---

## 2026-05-21 — Session 1 (Jalon J1)

**Durée** : ~1 h réelle (estimé : 6 h, mais setup minimal et l'environnement était déjà prêt)
**Tokens consommés** : non mesuré précisément
**Objectif** : Setup repo + docker-compose (postgres_local + PostGIS + backend stub + martin stub) + scripts (download_bdnb, verify_supabase, update_tunnel_url) + CI GitHub Actions + mail INIES rédigé.

### Ce qui a marché
- Structure repo créée : `backend/`, `frontend/` (stub), `scripts/`, `docs/`, `.github/workflows/`, `data/storage/` (volume Docker).
- `docker-compose.yml` validé : `docker compose config` passe sans erreur (3 services : postgres_local, backend, martin).
- Backend stub FastAPI : `GET /api/health` répond `{"status": "ok", ...}`. Test pytest passe (1/1).
- Ruff lint passe (1 fix appliqué : `datetime.timezone.utc` → `datetime.UTC` UP017).
- Ruff format passe (4 fichiers déjà formatés).
- `.gitignore` complet (Python, Node, Docker, data, env, OS).
- `.env.example` complet avec toutes les variables : `POSTGRES_LOCAL_*`, `SUPABASE_*`, `ANTHROPIC_API_KEY`, `AGENT_*_ID`, `NGROK_PUBLIC_URL`, `BACKEND_*`, `BAN_API_URL`, `IGN_WMTS_URL`, `LOG_*`.
- `scripts/verify_supabase_connection.py` : 4 vérifications NON destructives (env présentes, endpoint joignable, JWT décodables, service role lecture admin/users). À lancer par le partenaire avec son `.env` rempli.
- `scripts/download_bdnb.sh` : reprenable (`curl -C -`), 5 départements paramétrables, marker `.done` par fichier. URLs à compléter au premier run (manuellement depuis https://bdnb.io/download/ — le pattern d'URL n'est pas exposé en API).
- `scripts/update_tunnel_url.py` : stub J1, implémentation réelle à J10 quand les agents seront créés.
- CI GitHub Actions : ruff lint + format + pytest + `docker compose config` + `docker compose build`.
- Init PostgreSQL : `01_extensions.sql` (postgis, fuzzystrmatch, pg_trgm, btree_gist) + `02_schemas.sql` (`public_data`, `staging`).

### Ce qui n'a pas marché / contournements
- **URLs de téléchargement BDNB par département non exposées** sur la page data.gouv.fr ni sur la page bdnb.io que j'ai consultée — il faudra une visite manuelle de https://bdnb.io/download/ pour récupérer les URLs exactes et les coller dans `scripts/download_bdnb.sh`. Le script est prêt techniquement, il manque juste les URLs.
- Tests Docker `compose build` non exécuté en local (long, ~5 min) — délégué à la CI.
- `ifcopenshell` n'est PAS encore installé dans le `Dockerfile` du backend (sera ajouté à J9 après le test critique dans le container Anthropic — cf. CLAUDE.md §7).

### Décisions prises
- Aucune nouvelle décision structurante. Applique D-001 à D-013 du jour.
- Choix de stack mineurs documentés dans le code : PostgreSQL 16 + PostGIS 3.4 (image `postgis/postgis:16-3.4`), martin v0.13.0, Python 3.12-slim.

### Bloqueurs ouverts post-session
- B-001 (TTL session Managed Agents, J10).
- B-003 (API INIES — voir mail ci-dessous).

### INIES
Décision **D-014** (2026-05-21) : **pas de demande d'accès API INIES, base statique uniquement** (`data/fdes_static.json` versionné dans le repo). 30 matériaux clés FDES, citation par numéro de déclaration dans l'UI. B-003 résolu. Le mail INIES initialement rédigé a été supprimé de ce log — la décision documentée suffit.

### Prochaine étape
- Téléchargement BDNB : à lancer par le partenaire après complétion des URLs dans `scripts/download_bdnb.sh` (visite manuelle de https://bdnb.io/download/ pour récupérer les URLs exactes par département).
- Vérification connexion Supabase à lancer par le partenaire (`python scripts/verify_supabase_connection.py`) après remplissage du `.env`.
- Sur OK : J2 (ingestion BDNB dans `postgres_local.public_data`).

---

## 2026-05-21 — Session 2 (Jalon J2 partiel — dpt 02 validé, 4 autres en cours)

**Heure début** : 2026-05-21 19:30 (le partenaire a fourni les 5 URLs BDNB)
**Heure fin partielle** : 2026-05-21 20:19 (dpt 02 ingéré et validé)
**Objectif** : J2 — ingestion BDNB 5 départements HDF. Schéma observé/adapté/testé sur dpt 02. Code prêt pour les 4 autres.

### Ce qui a marché
- **5 URLs BDNB** fournies (Scaleway Object Storage) intégrées dans `scripts/bdnb_urls.txt`. `scripts/download_bdnb.sh` refactoré pour lire ce fichier (séparation données/code).
- **Download** : 5 départements téléchargés en ~7 min (total ~2.67 GB compressé).
- **Décompression** : 4 dpts décompressés en parallèle (~5 min, total ~12.5 GB décompressé).
- **Restore dpt 02** : SQL plain 1.39 GB → 56 tables + 333 148 bâtiments en ~10 min via `docker exec psql -f`. Idempotent (skip si schéma déjà peuplé).
- **Schéma BDNB confirmé** : 57 tables dans `bdnb_2025_07_a_open_data_dep02`. Tables clés identifiées (batiment_groupe, batiment_groupe_ffo_bat, batiment_groupe_bdtopo_bat, batiment_groupe_dpe_representatif_logement, batiment_groupe_urbanisme, batiment_groupe_rpls, batiment_groupe_rnc).
- **Consolidation `public_data.buildings`** : 333 148 lignes ingérées en ~70 s. Distribution DPE A-G plausible (218 A → 3691 G). 0 géométrie invalide. SRID 2154 confirmé.
- **Coefficient 1.9 validation empirique** : `SELECT count(*) FILTER (WHERE arrete_2021 = true)` sur les DPE non-nuls dpt 02 = **34 960 / 34 960 (100%)**. Donc `classe_bilan_dpe` est garanti coefficient 1.9. Affiché dans le commentaire SQL.
- **Type propriétaire** : 326 201 particuliers (97.9 %), 5 582 bailleurs sociaux (1.7 %), 1 365 copropriétés (0.4 %). Cohérent pour Aisne rurale.
- **Monuments Historiques** : 448 bâtiments / 333 148 = 0.13 %. Plausible (églises classées + château).
- **CHANGELOG BDNB lu** : confirme officiellement le coefficient 1.9 (ligne 87) + millésimes sources (DPE ADEME 2025-09, BD TOPO 2025-06-15, RNB 2025-07).

### Ce qui n'a pas marché / corrigé en cours
- **Port 5432 occupé** sur la machine (PostgreSQL natif probable). Bascule sur **5433 hôte** dans docker-compose.yml + `.env.example` (`POSTGRES_LOCAL_PORT_HOST=5433`). Port interne 5432 inchangé.
- **Docker Desktop non démarré** au lancement → démarré programmatiquement (Start-Process).
- **rnb_id pas dans `batiment_construction`** comme initialement supposé, mais dans `rel_batiment_construction_rnb`. Sous-requête de jointure ajustée.
- **Schéma `mh_inscrit` + `mh_classe`** initialement prévu → BDNB open ne distingue pas inscrit/classé (`batiment_groupe_merimee` n'a que distance/nom du MH proche). Schéma simplifié : `monument_historique boolean` unique. Décision documentée.
- **`type_proprietaire = 'public'`** : pas dérivable de BDNB open avec qualité suffisante. Set canonique réduit à {bailleur_social, personne_morale_privee, particulier}. Documenté.

### Décisions techniques internes
- **Idempotence ingestion** : `find_zip` détecte `.zip.done`, `extract_zip` détecte `.extracted.done`, `restore_dump` skip si schéma déjà peuplé. Recommençable.
- **psql via docker exec** : pas de client PG natif sur Windows. Variable `CONX_USE_DOCKER_EXEC=1` (défaut).
- **Format BDNB millésime 2025-07.a** : **SQL plain** (pas pg_restore custom). 1 fichier `pgdump/bdnb.sql` par dpt + 1 fichier `referentiel_administratif.sql` (non ingéré dans v1).

### Limitations connues (documentées, non bloquantes)
- 108 k bâtiments dpt 02 sans `ffo` (pas dans Fichiers Fonciers) → NULL pour annee_constr, materiau_mur, nb_logements. C'est attendu — annexes, bâtiments légers, etc.
- `type_proprietaire = 'public'` non distinguable des particuliers. Limitation BDNB open. UI `S_social` sous-pondérera collectivités. Acceptable pour MVP.
- `surface_utile_m2`, `nb_etages`, `sous_type` retirés du schéma (toujours NULL si non sourcés).
- `monument_historique` boolean unique (BDNB open ne distingue pas inscrit/classé).

### Bloqueurs ouverts
- Aucun bloqueur nouveau. B-001 (TTL session Managed Agents) reste à tester en J10.

### Prochaine étape
- Lancer les 4 autres dpts (59, 60, 62, 80) en série. Restore + consolidation. Estimation : 60-90 min total (dpt 59 Nord est le plus gros, 4.7 GB décompressé).
- Une fois 5 dpts ingérés : commit J2 final avec count total + entrée BUILD_LOG.
- Puis J3 : DPE — selon CHANGELOG, BDNB 2025-07.a intègre déjà DPE ADEME 2025-09. À évaluer s'il faut un ingestion DPE séparée ou si BDNB suffit.

### Questions ouvertes pour le partenaire (non bloquantes — à traiter au retour)
1. Limitation `type_proprietaire = 'public'` : OK pour MVP, ou doit-on chercher une source complémentaire (DGFIP MAJIC PM, fichiers fonciers) ? (Cf. SCORING.md composante S_social.)
2. Pour les 108 k bâtiments dpt 02 sans `ffo` : on les inclut dans le scoring quand même (avec NULL) ou on les filtre ?
3. Le `materiau_mur` BDNB est en texte libre (mat_mur_txt) — il faudra probablement le normaliser pour le ML/scoring. Mapping à faire en J5 ?
4. Pour J3 : si BDNB intègre déjà DPE ADEME 2025-09, ai-je besoin d'ingestion DPE séparée ? Avantage : DPE plus récents que millésime BDNB. Inconvénient : duplique le travail.
5. Vérification connexion Supabase (`scripts/verify_supabase_connection.py`) : à toi de la lancer quand tu rempliras le `.env` avec tes vraies credentials.

---

## 2026-05-21 — Session 3 (Jalons J2 finalisation + J3 intégré + J4 prep)

**Heure début** : 2026-05-21 20:21 (lancement batch 4 dpts en arrière-plan)
**Heure fin** : 2026-05-21 21:07 (dpt 59 re-run pour DPE + tests OK)
**Objectif** : Finir J2 (4 dpts restants), ajouter DPE détaillé (J3) et préparer J4 (BD TOPO routes).

### Totaux finaux J2 (5 dpts HDF)
- **public_data.buildings : 3 122 513 lignes**
  - 02 : 333 148 | 59 : 1 221 175 | 60 : 397 252 | 62 : 808 154 | 80 : 362 784
- **public_data.dpe : 435 987 lignes** (417 353 logements + 18 634 tertiaires)
  - 02 : 36 594 | 59 : 184 620 | 60 : 50 937 | 62 : 124 737 | 80 : 39 099
- Distribution classes DPE : A=3 813, B=7 342, C=74 683, D=153 347, E=109 148, F=42 445, G=26 575 (passoires F+G = 69 020 = 2.2 %).
- Distribution propriété : particulier 95 %, bailleur_social 4.2 %, personne_morale_privee 0.8 %.
- Monuments Historiques : 2 346 (0.075 %).
- Patrimoine pré-1800 : 28 922 bâtiments (médiéval/Renaissance, légitime en HDF).
- Sanity : 0 géométrie invalide, SRID 2154, 0 année hors `[1000, 2030]`.
- **14/14 tests d'invariants pytest passent en 29 s**.

### Ce qui a marché
- **J2 batch 4 dpts** lancé en arrière-plan, processus séparé par dpt (PID 1863). Dpt 59 : 1 221 175 bâtiments. Dpt 60 : 397 252 buildings + 50 937 DPE.
- **J3 intégré dans J2** : table `public_data.dpe` créée (migration `004_create_dpe_detail.sql`) avec contrainte `UNIQUE (building_id, identifiant_dpe)`. Template `005_consolidate_dpe_dept.sql.template` insère logements + tertiaires depuis BDNB (qui embarque DPE ADEME 2025-09 — pas besoin d'ingestion ADEME séparée). 4 tests ajoutés : table+index, type_dpe canonique, `arrete_2021=true` à 100 % logements, idempotence via ON CONFLICT.
- **J4 prep** : table `public_data.topo_roads` (migration `006`), script `ingest_bdtopo_roads.py` (ogr2ogr dans container `ghcr.io/osgeo/gdal:alpine-small-latest` joint au `conx_net`), `download_bdtopo.sh` + `bdtopo_urls.txt` (URLs à fournir par le partenaire).
- **Refactor `consolidate_dept`** : split en `_apply_template` helper + appels successifs 003 (buildings) puis 005 (DPE). Testé bout-en-bout sur dpt 02 avant commit (333 148 buildings + 36 594 DPE = 34 960 logement + 1 634 tertiaire).
- **`scripts/db_status.py`** : rapport read-only sur public_data (counts par dpt, distribution DPE, sanity).
- **Disque** : 195 GB libres après batch en cours (seuil 30 GB largement respecté).

### Ce qui n'a pas marché / corrigé en cours
- **Bornes d'années [1800, 2030] erronées** : présumées a priori, sanity check montre min=1200, max=2024 dans la donnée réelle. 251 bâtiments pré-1500 (médiéval), 20 617 pré-1800 (patrimoine HDF légitime : abbayes, fermes, églises). Bornes corrigées en `[1000, 2030]` dans `test_annee_constr_plausible` et `scripts/db_status.py`. **Pattern à retenir : dériver les seuils sanity de la donnée, pas d'a priori.**
- **Dpt 59 traité avec code ancien** : le batch démarré à 20:21 a importé l'ancien `consolidate_dept` (sans DPE) pour dpt 59. Les dpts 60/62/80 (processus Python fresh par itération `for`) ont importé le NOUVEAU. → dpt 59 à re-traiter post-batch (skip restore via idempotence, ~3 min consolidation pure).
- **Émoji Unicode dans `db_status.py`** : `UnicodeEncodeError` sur Windows console cp1252 (📊 → '\U0001f4ca'). Remplacés par tags ASCII `[buildings]`, `[dpe]`, etc.

### Décisions techniques internes
- **J3 = sous-étape de J2**, pas un jalon distinct. BDNB millésime 2025-07.a contient déjà les DPE ADEME 2025-09 dans les tables `batiment_groupe_dpe_representatif_logement` et `batiment_groupe_dpe_tertiaire`. Pas de double ingestion.
- **`arrete_2021=true` à 100 %** des DPE logements dpt 02 → confirme empiriquement le coefficient EP électricité 1.9 (cf. D-006 et BUILD_LOG Session 2).
- **DPE tertiaire** : la colonne classe est `classe_conso_energie_dpe_tertiaire`, pas `classe_bilan_dpe`. Template 005 traite logements et tertiaires séparément.

### Limitations connues (documentées, non bloquantes)
- Dpt 59 a buildings sans DPE en `public_data.dpe` jusqu'à la re-passe (correction post-batch).
- BD TOPO routes (J4) : URLs IGN non exposées en API publique, à compléter manuellement par le partenaire dans `scripts/bdtopo_urls.txt`. Le pipeline ogr2ogr est prêt.

### Bloqueurs ouverts
- Aucun nouveau. B-001 (TTL session Managed Agents) reste à tester en J10.

### Prochaine étape (post-batch)
- Re-runner `python scripts/ingest_bdnb.py 59` pour consolider DPE dpt 59 (~3 min). Vérifier log line `Schéma bdnb_*_dep59 déjà peuplé — restore skip` avant de s'engager.
- Commit J2 final avec totaux 5 dpts.
- J4 effectif : nécessite URLs BD TOPO du partenaire (5 dpts).
- **STOP avant J5** (ML training) — arbitrage produit demandé.

---

## 2026-05-21 — Session 4 (Jalon J4 prep + scoring batch infra)

**Heure début** : 2026-05-21 ~21:30 (réception URLs BD TOPO + relance loop)
**Objectif** : (1) Refactor BD TOPO ingestion (couches TRONCON_DE_ROUTE + BATIMENT, 7z, millésime pinné).
(2) Infrastructure scoring : table `building_scores`, module `app.scoring.compute`, batch runner,
config YAML, tests unitaires + invariants DB. (3) Téléchargement BD TOPO en arrière-plan.

### Ce qui a marché
- **URLs BD TOPO HDF reçues du partenaire** (5 dpts, millésime 3-5_2025-12-15) → injectées dans
  `scripts/bdtopo_urls.txt`. Variable d'env `BDTOPO_MILLESIME` (défaut `3-5_2025-12-15`) pour pinning.
- **Refactor ingest_bdtopo_roads.py → ingest_bdtopo.py** : extrait **les 2 couches demandées**
  (`troncon_de_route` ET `batiment`), gère 7z (via `py7zr` ou binaire `7z`), tourne via container
  `ghcr.io/osgeo/gdal:alpine-small-latest` sur le réseau `conx_net`. Idempotent par dpt
  (DELETE WHERE dept + INSERT). L'ancien script roads-only est supprimé.
- **Migration 007** : table `public_data.topo_buildings` (MultiPolygon 2154, GIST + dept + hauteur
  + cleabs indexes).
- **Téléchargement BD TOPO** lancé en arrière-plan (PID 2444 → log
  `data/raw/bdtopo/logs/download.log`). 4/5 dpts terminés au moment de ce commit (1.77 GB).
- **Migration 008** : table `public_data.building_scores` (5 composantes + valeurs brutes +
  metadata + flags `incomplete_data` / `s_faisa_partial`). CHECK constraint sur composantes [0,1]
  + dpe_source ∈ {`ademe-real`, `ml-predicted`} (SCORING.md §Implémentation).
- **Module `backend/app/scoring/compute.py`** : pure function, charge thresholds depuis YAML,
  retourne `BuildingScoreComponents` figé. SHA256-12 du YAML stocké dans `thresholds_version`.
- **Config externalisée** : `config/scoring_thresholds.yaml` (toutes les valeurs SCORING.md).
- **Batch runner `scripts/compute_building_scores.py`** : 2 connexions psycopg (read server-side
  cursor + write UPSERT par chunks), idempotent via `ON CONFLICT (building_id) DO UPDATE`.
- **Tests** : 17 unit tests (formule, bornes, fallbacks) + 10 tests d'invariants DB (correlations
  classe DPE↔S_passoire, type_proprietaire↔S_social, FK building_id, thresholds_version uniforme).
- **Validation empirique dpt 02** : 333 148 bâtiments scorés en 79.9 s (4 171/s). Top 5 scores
  sont des DPE F/G bailleurs sociaux résidentiel collectif — exactement ce que la formule devrait
  prioriser. confidence 0.9 sur DPE réels, < 0.4 sur fallback.
- **Distribution dpt 02 post-scoring** :
  - `ademe-real` : 34 960 (10.5 %) — DPE issu de l'ADEME directement.
  - `ml-predicted` : 298 188 (89.5 %, `incomplete_data=true`) — fallback midpoint de classe
    en attendant J5 ML. Confidence basse, sera réécrasé en J5.
  - `s_faisa_partial=true` : 333 148 (100 %) — BD TOPO pas encore ingérée, acces_chantier neutralisé.

### Ce qui n'a pas marché / corrigé en cours
- **Dérive SCORING.md détectée par advisor** :
  - `tertiaire_commerce = 0.6` → corrigé à `0.9` (SCORING.md liste UNE seule valeur tertiaire = 0.9).
  - `dpe_source = 'fallback-typology'` (3e enum) → bascule sur `'ml-predicted'` (SCORING.md grave
    2 valeurs seulement). Le batch dpt 02 a été drop + recréé pour respecter la nouvelle CHECK.
  - Test parametrize ajouté pour pin tertiaire bureaux/commerce/magasin/bureau à la même valeur
    (garde-fou anti-drift).
- **Server-side cursor perdu sur commit** (psycopg) → bascule sur 2 connexions distinctes
  (read autocommit=False long-lived, write autocommit=False par chunks).
- **`db_status.py` Unicode crash** sur Windows cp1252 (déjà corrigé Session 3 — n/a ici).
- **py7zr installé via pip user** (1.1.0) — déclaré dans `backend/requirements.txt`.
- **PyYAML déclaré** dans `backend/requirements.txt` (6.0.2).
- **download_bdtopo.sh** : flag `-s` à la place de `--progress-bar` (la progress curl spammait
  le log). Pris effet sur les runs futurs (run en cours utilise l'ancienne version, sans impact).
- **Risque silent drift sur `apply_migration_008`** : la fonction skip si la table existe.
  Si la table avait été créée avec une CHECK plus laxe précédemment, le code ne forcerait pas
  la nouvelle CHECK. Mitigation prise : drop table + re-créer manuellement avant re-run dpt 02.
  Pas un problème en CI/CD propre, mais à surveiller dans les machines de dev. Documenté ici.

### Décisions techniques internes
- **Notes d'implémentation vs SCORING.md gravé** documentées dans `compute.py` docstring de tête :
  (1) midpoints kWh par classe (fallback pré-J5), (2) redistribution poids S_faisa quand
  acces_chantier indispo, (3) fallback type_compatible=0.5 sur type inconnu.
- **`thresholds_version`** : SHA256-12 du YAML brut. Test `test_thresholds_version_uniforme`
  garantit qu'on ne mélange pas deux versions dans `building_scores`.
- **2 connexions psycopg** dans le batch runner : pattern à reproduire pour autres batchs ML.

### Limitations connues (documentées, non bloquantes)
- Au moment du commit : seul dpt 02 (333 148 lignes) est dans `building_scores`. Le batch full
  5 dpts sera lancé immédiatement après ce commit.
- BD TOPO routes (J4 effectif) : 4/5 dpts téléchargés au moment du commit. Ingestion à lancer
  dès que dpt 80 termine.
- `S_faisa.acces_chantier` calcul exact : reste neutralisé jusqu'à ingestion BD TOPO. Passe de
  mise à jour à lancer après. Sera fait via PostGIS distance ST_DWithin(b.geom, r.geom, 10) +
  largeur_m.

### Bloqueurs ouverts
- Aucun nouveau. B-001 (TTL session Managed Agents) reste à tester en J10.

### Prochaine étape (mode boucle continue)
1. Commit cette session (advisor OK).
2. Lancer scoring batch sur les 4 dpts restants (59, 60, 62, 80) en arrière-plan.
3. Attendre dpt 80 BD TOPO → ingestion 5 dpts.
4. Passe de mise à jour S_faisa avec acces_chantier (PostGIS ST_DWithin + largeur).
5. Tests d'invariants finaux + commit.
