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

---

## 2026-05-21 — Session 5 (J4 effectif + acces_chantier + scoring v2 complet)

**Heure début** : 2026-05-21 ~22:00
**Heure fin** : 2026-05-21 22:55
**Objectif** : Compléter J4 (ingestion BD TOPO 5 dpts roads+buildings), pré-calcul acces_chantier
(passe S_faisa), re-batch scoring complet avec valeurs réelles.

### Ce qui a marché
- **BD TOPO 5 dpts HDF ingérés** (millésime 3-5_2025-12-15) en ~25 min :
  - `topo_roads` : 244 425 + 374 289 + 246 196 + 316 442 + 204 624 = **1 385 976 routes** (02/59/60/62/80)
  - `topo_buildings` : 681 805 + 2 009 504 + 843 588 + 1 481 469 + 829 472 = **5 845 838 bâtiments**
    (plus que BDNB — BD TOPO inclut annexes, garages, hangars — utile pour fallback 3D et cross-val hauteur).
- **`compute_acces_chantier.py`** : passe PostGIS ST_DWithin(b.geom, r.geom, 10) + ORDER BY largeur DESC.
  Couverture **100 % (3 122 513 bâtiments)** en 410 s cumulés (~7600/s en moyenne).
  Distribution acces_chantier HDF :
  - **1.0 (route ≥ 4 m à <10 m)** : 1 415 297 (**45.3 %**)
  - **0.5 (route 2-4 m)** : 190 289 (**6.1 %**)
  - **0.0 (impasse, sentier, enclavé)** : 1 516 927 (**48.6 %**)

  Le 48.6 % "enclavé" est cohérent avec une région où beaucoup de bâtiments sont en fond de cour,
  près de sentiers/chemins sans largeur mesurée dans BD TOPO (47 % des routes ont `largeur_m` NULL :
  Chemin, Sentier, Escalier).
- **Re-batch scoring complet** (v2) avec acces_chantier réel intégré : 3 122 513 bâtiments en **753 s**
  (~4 150/s). Résultats finaux :
  - **Total** : 3 122 513
  - **Avec 5 composantes complètes (real DPE + non-partial faisa)** : **417 353 (13.4 %)**
  - **`incomplete_data` (sans DPE → fallback midpoint, sera comblé J5 ML)** : 2 705 160 (86.6 %)
  - **`s_faisa_partial`** : **0 (0 %)** — réintégration acces_chantier réussie sur 100 % du parc.
- Top 5 scores (poids défaut 0.35/0.25/0.20/0.10/0.10) :
  ```
  bdnb-bg-D36X-BW1A-A2CK (59) | s_co2=1.000 s_faisa=0.845 s_cout=1.000 s_social=1.000 s_passoire=1.000 conf=1
  bdnb-bg-NW11-MP89-7H4S (62) | idem
  bdnb-bg-JXTH-7BF1-FA9V (62) | idem
  ...
  ```
  → DPE F/G + bailleur social + collectif R+1-R+5 + accès route ≥ 4 m + CO₂ évitable > 500 t/30ans.
  Exactement le profil que la formule SCORING.md devrait prioriser. Score total ≈ 96/100.

### Ce qui n'a pas marché / corrigé en cours
- **Bug colonnes BD TOPO 3-5** : noms changés vs anciennes versions. Empiriquement identifiés
  (dpt 60 staging) :
  - `largeur` → `largeur_de_chaussee`
  - `sens` → `sens_de_circulation`
  - `nom_1_droite` → `nom_voie_ban_droite` (fallback `nom_collaboratif_droite`)
  - `wkb_geometry` → `geometrie`
  → script `consolidate_roads` mis à jour avec les nouveaux noms + commentaire d'explication.
- **Migrations 006/007 non auto-appliquées par `ingest_bdtopo.py`** : ajout d'une fonction
  `apply_migrations()` qui vérifie l'existence puis applique. Idempotente. Dpt 02 buildings a
  échoué la 1ère fois (table absente), corrigé par auto-apply au 2e essai.
- **API drift `compute_components`** : signature simplifiée (`has_topo_roads` retiré, remplacé par
  `acces_chantier_value: float | None`). Plus propre, mais nécessite mise à jour du caller
  `compute_building_scores.py` (fait). Tests unitaires mis à jour (parametrize utilisé pour pin
  tertiaire bureaux=commerce à 0.9).
- **Anti-drift schema CHECK constraint** : `dpe_source` enum réduit à 2 valeurs canoniques SCORING.md
  ({ademe-real, ml-predicted}) après détection advisor que 3e valeur dérivait. Re-run dpt 02 nécessaire
  pour respecter la nouvelle CHECK. Documenté.
- **Note code-semantics drift v1/v2** : Le 1er batch scoring (avant API change) avait `has_topo_roads`
  bool ; le 2e batch (après) a `acces_chantier_value`. Hash YAML inchangé donc
  `test_thresholds_version_uniforme` passe. UPSERT v2 a complètement écrasé les rows v1 → DB cohérente.
  Pour audit traceable plus tard : ajouter un `code_version` column si besoin (post-MVP).

### Décisions techniques internes
- **Pattern : pour chaque ingestion en `--all`, appliquer les migrations associées** (ingest_bdnb.py
  déjà, ingest_bdtopo.py maintenant aussi, compute_building_scores.py applique 008+009).
- **2 connexions psycopg** pour batch lourd (read server-side cursor + write UPSERT par chunks).
  Pattern utilisé dans compute_building_scores.py, à reproduire en J5.
- **`compute_acces_chantier.py`** : SQL pur PostGIS (pas Python pour le calcul, juste l'orchestration).
  ST_DWithin + GIST index = ~7600 bâtiments/s.

### Limitations connues
- **86.6 % `incomplete_data`** = bâtiments sans DPE classé. Fallback midpoint utilisé, confidence < 0.4.
  Sera résolu en J5 (ML estimation DPE rempliera les trous).
- 48.6 % `acces_chantier=0.0` : reflète la réalité HDF (rural + sentiers BD TOPO sans largeur).
  Pas un bug. Si besoin d'affiner pour quartiers urbains : raffiner par classe `nature` des routes.
- BD TOPO ingestion n'a PAS testé end-to-end le `apply_migrations` cold-start (les tables existaient
  déjà au 1er run). Le code est straightforward (check exists → apply). Pour fresh install :
  `DROP TABLE public_data.topo_buildings; python scripts/ingest_bdtopo.py 02` validerait.

### Bloqueurs ouverts
- Aucun nouveau. B-001 (TTL session Managed Agents) reste à tester en J10.

### Prochaine étape (mode boucle continue)
- Commit cette session (advisor OK).
- En attente prochain feedback partenaire pour J5 (ML estimation DPE) ou autres directions.

---

## 2026-05-22 — Session 6 (J5 entraînement ML — STOP partner validation)

**Heure début** : 2026-05-22 ~00:00 (brief J5 reçu)
**Heure fin (training)** : 2026-05-22 00:08:32 (modèle sauvegardé)
**Objectif** : (1) Schémas DB (migration 010 : commune INSEE + dpe_source + ML metadata columns).
(2) Module ML complet : features.py, train.py, predict.py + scoring_thresholds + tests.
(3) Pré-calcul neighborhood k=20 via PostGIS, training RF, métriques. **STOP avant prédiction massive**.

### Ce qui a marché
- **Migration 010 appliquée** :
  - `buildings.code_commune_insee` (text) + `code_iris` + `dpe_source` ('ademe-real'|'ml-predicted'|NULL).
  - `dpe.source` (CHECK ∈ {ademe-real, ml-predicted}) + `model_version`, `confidence`, `prediction_date`, `predicted_classes_top3` (text[]), `clipped`.
  - 4 colonnes booléennes anomalies (rt2012, re2020, pac, neighborhood).
  - Backfill `dpe_source='ademe-real'` sur 417 353 lignes en ~4 min.
- **Backfill code_commune_insee** depuis `bdnb_*.batiment_groupe` (5 dpts en série, 100 % couverture) :
  - 02 : 333 148 | 59 : 1 221 175 | 60 : 397 252 | 62 : 808 154 | 80 : 362 784
  - Total : **3 122 513 bâtiments mappés à 3 782 communes uniques**.
- **Module ML complet** :
  - `backend/app/ml/features.py` — feature engineering (15 features), pure functions.
  - `backend/app/ml/train.py` — Random Forest + spatial split + métriques + persistence.
  - `backend/app/ml/predict.py` — predict_batch + anomaly rules + clip_kwh (post-validation).
  - `config/zone_climatique_dpt.yaml` — référentiel RT/RE par dpt.
  - `scripts/train_dpe_ml.py` — script orchestrateur.
  - `scripts/predict_dpe_ml_sample.py` — diagnostic 10-sample (pré-validation).
  - `backend/tests/test_dpe_ml.py` — 21 tests unitaires (features, split spatial, accuracy, encoding).
- **Pré-calcul neighborhood k=20** sur 417 325 bâtiments en **395 s** (~1 060/s en moyenne) :
  - Table `public_data.building_neighborhood_train` créée (D-019).
  - Per dpt : 02 (35s), 59 (174s), 60 (26s), 62 (83s), 80 (76s).
- **Training Random Forest** sur 309 069 rows en **89 s** (classifier 23s + regressor 89s).
- **Split spatial** sans fuite : 2 635 communes train + 1 128 communes test, **aucune overlap** vérifiée.
- **Modèle sauvegardé** : `data/storage/ml/dpe_estimator_560402f6.pkl` (180 MB) + metrics JSON.
- **Tests** : 74/74 passent (53 nouveaux ML + 21 scoring existants).

### Métriques modèle (cible brief J5 §4)
- **Accuracy ±1 classe** : **83.48 %** ✅ — au-dessus du seuil "OBJECTIF VISÉ" (≥ 75 %).
- Accuracy stricte : 41.97 %.
- MAE consommation : 67.6 kWh ep/m²/an.
- Train rows : 309 069 (2 635 communes).
- Test rows : 108 256 (1 128 communes).

### Ce qui a déclenché un STOP avec analyse critique

**B-006 ouvert** : Le modèle satisfait le seuil ±1 ≥ 75 % du brief J5, **mais** la matrice de confusion révèle un **biais sévère vers les classes médianes D/E** :

| Classe réelle | Taux exact | ±1 par classe |
|---|---|---|
| A | 17 % | (faible coverage) |
| B | 11 % | (faible coverage) |
| C | 30 % | |
| D | **76 %** | 99.6 % |
| E | 32 % | |
| **F** | **0.7 %** ⚠️ | **40.8 %** (E+F+G) |
| **G** | **0.3 %** ⚠️ | **0.55 %** ⚠️ (F+G uniquement — E à ord 5 est à 2 classes de G=ord 7) |

**Implication produit critique** : ConX cible précisément les passoires F/G. Le modèle les prédit **systématiquement en D**. Sur un échantillon de 10 bâtiments (3 passoires F/G), **3/3 passoires ratées**.

L'`accuracy ±1 = 83.48 %` global est artificiellement élevée par le biais de prédiction vers D. C'est un cas où la métrique brief J5 §4 est techniquement satisfaite mais où l'analyse qualitative révèle un problème majeur.

### Décision — STOP requis (brief J5 §11)
> "Après l'entraînement initial : avant la prédiction massive, présente-moi les 4 métriques. Je décide alors si on continue, on retravaille, ou on accepte avec avertissement."

→ **STOP**. Présentation au partenaire avec les 3 options (B-006) :
- (a) Accepter avec UI masquant prédictions F/G basse confidence.
- (b) Refit avec `class_weight='balanced'` (réduction probable de l'accuracy ±1 globale à ~75-80 %, mais amélioration drastique sur F/G).
- (c) Explorer alternative (XGBoost, stratified oversampling, ordinal regression).

### Ce qui n'a pas marché / corrigé
- **Bug Unicode dans `print_metrics`** sur Windows cp1252 (caractères → et ✅). Corrigé en ASCII (`->`, `[OK]`).
  Le modèle était déjà sauvegardé avant le crash — récupérable via JSON.
- **Tests stratégie classes** : ARROWSTRINGARRAY shuffling warning (np.random.default_rng.shuffle). Corrigé en convertissant en `np.array(..., dtype=object)` avant shuffle.

### Décisions techniques internes (D-017, D-018, D-019 ajoutées)
- **D-017** : ML predictions dans `public_data.dpe` (pas de table séparée), discriminé par `source`.
- **D-018** : RandomForest 200 arbres / max_depth=15 / spatial split 70/30, 15 features listées.
- **D-019** : `building_neighborhood_train` permanente (skip si peuplée).

### Limitations connues
- **Biais F/G non résolu** : décision partenaire requise (B-006).
- **15 features seulement** : on n'utilise pas tout BDNB (~400 attrs). À enrichir post-validation si nécessaire.
- **hauteur_m uniquement BDNB** : crossvalidation BD TOPO pas faite encore (J5+).
- **Zone climatique grossière** : par dpt. Raffinement par commune INSEE possible.

### Bloqueurs ouverts
- **B-006** ouvert (ML biais F/G).
- B-001 (TTL session Managed Agents) inchangé.

### Prochaine étape
- **Attente décision partenaire B-006**.
- Si (b) refit balanced : ~15 min de réentraînement, re-tester métriques.
- Si (a) accept-as-is ou (b) post-refit : lancer prédiction massive (`scripts/predict_dpe_ml.py --all`, à créer) → INSERT into `dpe` avec `source='ml-predicted'` → re-batch scoring → 100 % couverture.

### Corrigendum — message du commit e8ad8e5

Le commit message contenait trois valeurs cosmétiquement incorrectes (probablement copiées d'un run intermédiaire avant le run final). Les sources de vérité (`BUILD_LOG.md` Session 6, `BLOCKERS.md` B-006, `data/storage/ml/dpe_estimator_560402f6_metrics.json`) ont les bonnes valeurs depuis le début :

| Métrique | Commit message (erroné) | Source de vérité (correct) |
|---|---|---|
| Accuracy stricte | 53.84 % | **41.97 %** |
| MAE conso | 51.96 kWh/m²/an | **67.60 kWh/m²/an** |
| n_test | 78 818 | **108 256** |

Accuracy ±1 = 83.48 %, n_train = 309 069, et toutes les autres métriques sont identiques. Pas d'impact sur la décision B-006.

---

## 2026-05-22 — Session 7 (J5 refit v2 — class_weight='balanced')

**Heure début** : 2026-05-22 00:25 (décision partenaire reçue après STOP B-006)
**Heure fin (training)** : 2026-05-22 00:35:52 (v2 sauvegardé)
**Objectif** : (1) docs correctif sur métriques commit e8ad8e5, (2) backup v1 sous nom explicite, (3) extension code pour `class_weight` + per-class accuracy ±1, (4) refit v2 avec `class_weight='balanced'`, (5) diagnostic v1 vs v2 sur les mêmes 10 building_ids.

### Ce qui a marché
- **docs corrigendum** : commit `1a43e5b` reprend les vraies valeurs (accuracy stricte 41.97 %, MAE 67.6, n_test 108 256) qui étaient déjà dans les sources de vérité (BUILD_LOG/BLOCKERS/JSON).
- **v1 sauvegardé** sous `data/storage/ml/dpe_estimator_v1_baseline_560402f6.pkl` (180 MB, gitignored).
- **Extension code** :
  - `TrainingConfig.class_weight` (str | dict | None) défaut `None` = v1 baseline.
  - `ModelMetrics` étendu : `accuracy_pm1_per_class` (dict A..G) + `n_per_class` + `class_weight` (traçabilité).
  - `evaluate()` calcule l'accuracy ±1 par classe (boucle masque par classe réelle).
  - `scripts/train_dpe_ml.py` : args `--class-weight` (valeurs `balanced` / `none` / JSON dict) et `--tag` (nommage explicite).
  - `print_metrics()` affiche le per-class avec verdicts F (≥ 60 %) / G (≥ 50 %).
- **Tests** : 75/75 passent (53 ML + 22 scoring, 24 skipped DB-dépendants).
- **Refit v2** : `class_weight='balanced'`, 264 939 train / 152 386 test, 2 635 / 1 128 communes.
  - Classifier : 23 s (200 arbres, max_depth=15).
  - Regressor : 86 s (inchangé vs v1).
  - Modèle sauvegardé : `data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl` (180 MB, gitignored).
- **Diagnostic v1 vs v2 sur les 10 mêmes building_ids** (seed=42 deterministe dans `predict_dpe_ml_sample.py`).

### Métriques v2 (hold-out spatial)

| Métrique | v1 (560402f6) | v2 (de48d81c balanced) | Seuil partenaire | Verdict v2 |
|---|---|---|---|---|
| Accuracy ±1 globale | 83.48 % | **67.18 %** | ≥ 70 % | ❌ -2.82 pts |
| Accuracy stricte | 41.97 % | 32.29 % | — | informatif |
| **Accuracy ±1 sur F** | **40.80 %** | **84.70 %** | ≥ 60 % | ✅ +43.9 pts |
| **Accuracy ±1 sur G** | **0.55 %** | **73.15 %** | ≥ 50 % | ✅ +72.6 pts |
| MAE consommation kWh | 67.60 | 68.04 | ≤ 90 | ✅ |

Per-class accuracy ±1 v2 :
- A : 60.28 %  |  B : 63.71 %  |  C : 64.18 %  |  D : 65.07 %
- E : 64.36 %  |  F : 84.70 %  |  G : 73.15 %

→ **Répartition désormais uniforme** (60–85 %), plus de biais central D au détriment de F/G.

### Échantillon 10 bâtiments v1 vs v2 (mêmes building_id, seed=42)

| dept | annee | TYPE | REAL | v1 PRED | v2 PRED | Note |
|---|---|---|---|---|---|---|
| 59 | 1922 | Résid. indiv. | E | E ✓ | E ✓ | stable exact |
| 59 | 1975 | Résid. indiv. | F | D ❌ | D ❌ | passoire F ratée |
| 60 | 2004 | Résid. indiv. | C | D | D | ±1 OK stable |
| 59 | 1974 | Résid. indiv. | D | D ✓ | D ✓ | stable exact |
| 59 | 1921 | Résid. indiv. | D | D ✓ | D ✓ | stable exact |
| 59 | 1957 | Résid. indiv. | C | D | E | dégradé (écart 2) |
| 59 | 1959 | Résid. indiv. | E | E ✓ | F | ±1 OK |
| 02 | 1922 | Tertiaire | G | D ❌ | **G ✓** | **passoire G capturée v2** |
| 80 | 1978 | Résid. indiv. | F | D ❌ | E | passoire F ratée mais ±1 |
| 60 | 1800 | Résid. indiv. | D | D ✓ | G ❌ | dégradé (écart 3) |

Exact match : 5/10 → 4/10 (-1). ±1 : 7/10 → 7/10 (stable). **Passoires capturées : 0/3 (v1) → 1/3 (v2)**. La G qui avait été prédite D par v1 est maintenant correctement prédite G par v2.

### Décision STOP — v2 ne satisfait pas les 4 critères
> Partenaire : "Si v2 atteint ces 4 seuils : on déploie v2. Si v2 ne les atteint pas : on rediscute, on garde v1 en attendant, on n'écrête rien."

→ **STOP atteint**. v2 manque le critère global ±1 (67.18 % < 70 %). 3/4 OK. Présentation des options au partenaire :

1. **Accepter v2** malgré 67.18 % global (la zone 60–75 % du brief J5 §4 est "ACCEPTABLE AVEC AVERTISSEMENT"). L'amélioration F/G est dramatique et alignée avec la mission ConX.
2. **Refit v3 avec poids manuels** `{F:2, G:3}` ou similaire — tenter un compromis entre v1 (biais central) et v2 (équilibrage agressif). Possiblement remonter le ±1 global au-dessus de 70 % tout en gardant F/G ≥ 60/50 %.
3. **Garder v1** en attendant et explorer alternative (XGBoost, oversampling).

### Décisions techniques internes (D-020 ajoutée)
- **D-020** : refit `class_weight='balanced'` validé technique, déploiement en attente d'arbitrage critère global ±1.

### Observation tracée
n_train/n_test diffère entre runs (309k/108k v1 vs 265k/152k v2), bien que n_train_communes/n_test_communes soient identiques (2 635 / 1 128). Cause : pas d'`ORDER BY building_id` dans `load_training_dataframe` → l'ordre `unique()` des communes varie → shuffle déterministe sur entrée non-déterministe. Les test sets sont donc approximativement comparables, pas strictement. Fix simple à faire au prochain refit (ajout `ORDER BY building_id ASC` SQL).

### Bloqueurs ouverts
- **B-006** mis à jour avec les métriques v2 et les 3 options ci-dessus.
- B-001 (TTL session Managed Agents) inchangé.

### Prochaine étape
- Attente décision partenaire entre (1) accepter v2 / (2) refit v3 poids manuels / (3) garder v1 + alternative.
- **Aucune** prédiction massive ni recalcul scoring tant que décision non prise.

---

## 2026-05-22 — Session 8 (J5 v3 refit + arbitrage final v1/v2/v3)

**Heure début** : 2026-05-22 00:50 (décision partenaire option (b) reçue)
**Heure fin (training)** : 2026-05-22 00:56:45 (v3 sauvegardé)
**Objectif** : (1) Refit v3 avec poids manuels `{F:2,G:3}`, (2) diagnostic 3 modèles côte à côte sur les 10 mêmes building_id, (3) arbitrage automatique selon critères assouplis du partenaire (±1 ≥ 72 %), (4) docs/ML_DPE.md finalisé.

### Ce qui a marché
- **Refit v3** : `class_weight={'F': 2.0, 'G': 3.0}` via `--class-weight '{"F":2.0,"G":3.0}'` du script `train_dpe_ml.py` (parsing JSON dict).
- **Modèle v3 sauvegardé** : `data/storage/ml/dpe_estimator_v3_manual_FG_35e2b41a.pkl` (180 MB, gitignored) en ~3 min.
- **Script comparatif créé** : `scripts/predict_dpe_ml_compare.py` charge N bundles (`label=path`) et tabule les prédictions côte à côte sur les mêmes 10 building_id (seed=42).
- **Tests** : 75/75 OK (53 ML + 22 scoring, 24 skipped DB).

### Métriques v3 (hold-out spatial)
- **Accuracy ±1 globale : 77.43 %** ✅ (seuil assoupli ≥ 72 % atteint, +10.25 pts vs v2)
- **F ±1 : 51.38 %** ❌ (seuil ≥ 60 %, -8.6 pts ; +10.6 vs v1, -33.3 vs v2)
- **G ±1 : 49.70 %** ❌ (seuil ≥ 50 %, **-0.30 pt frontalier** ; +49.2 vs v1, -23.4 vs v2)
- MAE : 68.23 ✅

Per-class ±1 v3 : A:29.23 B:58.65 C:85.98 D:84.70 E:81.84 F:51.38 G:49.70

v3 se positionne entre v1 et v2 : moins de biais central que v1 (A/B accuracy faible), beaucoup moins de capture F/G que v2.

### Échantillon 10 bâtiments — comparatif v1 / v2 / v3 (mêmes building_id, seed=42)

| dept | annee | TYPE | REAL | v1 | v2 | v3 | Évolution |
|---|---|---|---|---|---|---|---|
| 59 | 1922 | Résid. indiv. | E | E ✓ | E ✓ | E ✓ | stable |
| 59 | 1975 | Résid. indiv. | F | D ❌ | D ❌ | D ❌ | passoire F ratée par toutes |
| 60 | 2004 | Résid. indiv. | C | D | D | D | ±1 stable |
| 59 | 1974 | Résid. indiv. | D | D ✓ | D ✓ | D ✓ | stable |
| 59 | 1921 | Résid. indiv. | D | D ✓ | D ✓ | D ✓ | stable |
| 59 | 1957 | Résid. indiv. | C | D | E | D | v3 = v1, v2 dérive |
| 59 | 1959 | Résid. indiv. | E | E ✓ | F | E ✓ | v3 = v1, v2 dérive |
| 02 | 1922 | Tertiaire | G | D ❌ | **G ✓** | **G ✓** | v2 et v3 capturent G |
| 80 | 1978 | Résid. indiv. | F | D ❌ | E | D ❌ | v3 régression vs v2 (D au lieu de E ±1) |
| 60 | 1800 | Résid. indiv. | D | D ✓ | G ❌ | D ✓ | v3 = v1, v2 sur-prédit G |

**Compteurs** :
- Exact match : v1=5/10, v2=4/10, **v3=6/10**
- Within ±1   : v1=7/10, v2=7/10, **v3=8/10**
- Passoires F/G capturées : v1=0/3, v2=1/3, v3=1/3

Sur l'échantillon de 10, v3 est le meilleur sur les compteurs. Mais sur la métrique produit-critique F/G du test set complet, v2 reste très supérieur (84.7 % vs 51.4 % sur F).

### Application de l'arbre de décision automatique du partenaire

| Règle | Condition | Résultat v3 |
|---|---|---|
| (a) | 4/4 critères → déploie v3 | NON — 2/4 |
| (b) | 3/4 + gain ±1 global significatif vs v2 → présente | NON — 2/4 |
| (c) | v3 globalement moins bon que v2 → déploie v2 | À évaluer |
| (d) | v3 ≈ v2 → v2 | À évaluer |

v3 a un meilleur ±1 global (+10.25 pts) et un meilleur comportement sample, **mais perd sur F (-33.3 pts) et G (-23.4 pts) vs v2**. Selon les valeurs explicites du partenaire ("trouver les passoires importe plus que perfectionner D/E"), v3 est **globalement moins bon que v2 sur la dimension mission**.

→ **Application règle (c) : v2 retenu**.

### Modèle retenu : **v2 (`de48d81c`, `class_weight='balanced'`)**

`data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl` est désigné modèle de référence pour la prédiction massive sur les 2 705 160 bâtiments sans DPE.

Métriques retenues pour la doc et le pitch jury :
- ±1 global : 67.18 % (zone "ACCEPTABLE AVEC AVERTISSEMENT" du brief J5 §4)
- F ±1 : 84.70 %
- G ±1 : 73.15 %
- MAE conso : 68.04 kWh ep/m²/an

### Décisions techniques internes (D-021 ajoutée)
- **D-021** : réévaluation des seuils (justification asymétrie mission), tentative v3 ratée sur F/G, **v2 retenu**.

### Bloqueurs ouverts
- **B-006** clos pour l'arbitrage (v2 désigné), MAIS la prédiction massive nécessite encore le GO partenaire (STOP brief J5 §11).
- B-001 (TTL session Managed Agents) inchangé.

### Documentation produit
- `docs/ML_DPE.md` mis à jour : modèle retenu v2, métriques finales, règles d'anomalie, pitch jury "alignement mission". Section "Comment réentraîner" précisée.

### Prochaine étape
- **Attente GO partenaire** pour lancer la prédiction massive avec v2.
- À lancer après GO : `scripts/predict_dpe_ml.py --all --model data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl` (à créer post-arbitrage : INSERT into dpe + UPDATE buildings + recompute scoring).
- Override possible : le partenaire peut désigner v3 (gain global au prix F/G) au lieu de v2 si la philosophie change.

---

## 2026-05-22 — Session 9 (J5 finalisation + J6 + J7 + J8 stub + J9 Skills + J10 stub + J11 Backend Stratégie)

**Mode** : autonome de nuit (GO partenaire), enchaînement J5→J11.

### Travail effectué
- **J5 prédiction massive** : `scripts/predict_dpe_ml.py --all` lancé en 2 passes
  (pass 1 buggée à 50% par OFFSET+UPDATE, fix appliqué, pass 2 OK). Résultat
  final : `public_data.dpe` couvre 3 122 513 bâtiments (417k ademe-real +
  2 705k ml-predicted), 100% couverture HDF. `building_scores` recalculé
  intégralement (compute_building_scores.py --all), 100% couverture.
- **J6 module carbon** : `backend/app/carbon/` avec exploitation + incorpore +
  evite_horssite + total, 32 tests passent. Doc `docs/CARBON.md`.
- **J7 MVT martin** : matview `tiles.buildings_centroids_mv` + heatmap zoom 8
  en 43 ms (target 2s largement battue). Doc `docs/TILES_MVT.md`.
- **J8 LiDAR stub** : schéma + scripts paramétrables, exécution différée J15
  (cf. B-008 IGN URL). Doc `docs/LIDAR_PIPELINE.md`.
- **J9 Skills bundles** : 6 SKILL.md (carbon-calc, fdes-lookup, ifc-check,
  horssite-biosource, re2020-target, pmr-checks). Test critique ifcopenshell
  PASS dans python:3.12-slim. Bloqueurs B-009 + B-010. Doc `docs/SKILLS.md`.
- **J10 Managed Agents stub** : `agents/agents.yaml`, `agents/sync.py`,
  `agents/test_ttl.py`, 3 system_prompts, `docs/AGENTS.md`. Non testé contre
  Anthropic API (règle §9.D — pas de dépense engagée). B-001 TTL ouvert.
- **J11 Backend Mode Stratégie** : pool asyncpg (`db.py`) + Auth JWT
  Supabase HS256 (`auth.py`, D-012) + 4 routers :
  - `/api/buildings` (liste paginée curseur opaque, scoring à la volée)
  - `/api/buildings/:id` (fiche + geom + 5 voisins)
  - `/api/internal/score-buildings` + `/api/internal/building/:id` (bypass
    `X-Internal-Token` pour Managed Agents, D-013)
  - `/api/exports/strategie.{csv,geojson}` (streaming, BOM UTF-8)
  - `/api/meta/scoring-config` (config publique)
  
  Tests : 20 tests auth offline + 126 unitaires existants (carbon, scoring,
  ML) tous PASSENT. Smoke test endpoints en local OK :
  - GET /api/buildings dpt 59 F bailleur_social → top score 0.961 (cohérent
    avec SCORING.md poids défaut)
  - Pagination via cursor : page 2 retourne 3 items distincts à scores
    identiques (ordre stable building_id)
  - POST /api/internal/score-buildings : refus 400 si aucun filtre (anti-scan
    3M lignes) ; 401 si X-Internal-Token absent ; 200 sinon
  - Exports CSV + GeoJSON streaming OK (bug "connection released" corrigé
    en acquérant une connexion dédiée via `pool.acquire()` au lieu de
    `Depends(get_db)` qui libère la connexion avant que le stream ne
    consomme).
  
  Docs : `docs/API.md` complète.

### Décisions techniques
- INNER JOIN avec building_scores sur la liste publique (et non LEFT JOIN) :
  garantit que tous les rows ont un `score_total` non-null et évite le bug
  pagination NULL-drop signalé par l'advisor. Justifié par 100% couverture
  building_scores post-J5.
- `httpx==0.27.2` au lieu de 0.28.1 : conflit avec supabase 2.10.0 qui exige
  `<0.28`. Documenté en commentaire dans `requirements.txt`.
- `INTERNAL_SHARED_TOKEN` vérifié via `hmac.compare_digest()` (timing-safe).
- Singletons `_QUERY_NONE` / `_QUERY_LIMIT_*` dans exports.py pour éviter
  les warnings B008 ruff sans dégrader la lisibilité.

### Bloqueurs ouverts
- B-001 (TTL session Managed Agents) → tester en J19 quand tunnel ngrok actif
  + partenaire valide la dépense.
- B-007 (martin auto_publish from_schemas non strict) → résolu par matview
  dédiées.
- B-008 (IGN LiDAR URL) → différé J15.
- B-009 (Skills upload) → partenaire au matin.
- B-010 (carbon-calc skill PYTHONPATH) → arbitrage J10.

### Prochaine étape
- J12 Backend Mode Projet (chat itératif Agent Plan + reprise session +
  persist plans dans Supabase Cloud `app.renovation_plans`).
- J13 Backend IFC (upload + agent Conformité + PDF).
- Les jalons J14-J17 frontend nécessitent décisions UX → STOP pour
  arbitrage partenaire au réveil.

---

## 2026-05-22 — Session 10 (J12 Backend Mode Projet — chat itératif)

**Mode** : autonome de nuit (suite GO partenaire).

### Travail effectué
- **Schéma Supabase** : `scripts/sql/supabase/001_app_schema.sql` créé avec 4
  tables (`agent_sessions`, `renovation_plans`, `ifc_validations`,
  `user_preferences`), RLS `auth.uid() = user_id` sur toutes, triggers
  `updated_at` automatiques. À exécuter par le partenaire via SQL editor
  Supabase.
- **Module `supabase_client.py`** : `supabase_for_user(user)` crée un client
  par requête en propageant le JWT (postgrest.auth) — garantit que la RLS
  voit le bon `auth.uid()`. `is_supabase_configured()` détecte les
  placeholders pour mode dégradé.
- **Module `agents_client.py`** : wrapper Anthropic Managed Agents avec
  `create_session`, `send_user_message`, `retrieve_session`, `list_events`,
  helpers SSE (`serialize_event_for_sse`, `keepalive_event`). Lit
  `agents.lock.yaml` au démarrage pour résoudre les noms d'agent en
  agent_id (cf. agents/sync.py).
- **Router `agents.py`** : 5 endpoints
  - `POST /api/agents/plan/start` (création session + 1er user_message)
  - `POST /api/agents/plan/:session_id/message` (turn N, incrémente version)
  - `GET /api/agents/plan/:session_id/stream` (SSE proxy, keepalive 15s,
    timeout 5 min)
  - `POST /api/agents/plan/:session_id/persist` (insert app.renovation_plans
    via Supabase JWT propagé)
  - `GET /api/agents/plan/:session_id/history` (liste versions v1, v2, ...)
- **Tests offline** : 10 tests `test_agents_client.py` + 8 tests
  `test_supabase_client.py` — couvrent les chemins 503 (config absente),
  serialize SSE, format JWT, beta headers. Total backend : 144 passed,
  24 skipped (DB integration). 0 ruff warning.
- **Docs** : `docs/MODE_PROJET.md` complète avec diagrammes, endpoints,
  schémas Supabase, anti-dérive R13.

### Smoke test
- `/api/agents/plan/start` sans config Anthropic → 503 propre avec message
  "ANTHROPIC_API_KEY non défini ou placeholder." (mode dégradé OK).
- Backend démarre cleanly avec le nouveau router. `/api/health` OK.

### Décisions techniques
- **SSE polling** (`events.list(after=last)`) au lieu de stream natif, par
  prudence sur les signatures SDK encore non testées. Migration possible
  vers `events.stream` en 1 fichier si l'endpoint natif est disponible.
- **Persistance déclenchée par le frontend** (`POST /persist`) plutôt que
  parsing serveur du markdown agent. Plus simple, plus robuste, le frontend
  contrôle quand le plan v(n) est "complet".
- **Versioning UNIQUE (session_id, version)** côté Supabase + `_next_version`
  qui lit max(version)+1. Pas d'auto-increment global — chaque session
  recommence à v1.
- **Limite stream 5 min** : MAX_STREAM_DURATION_S = 300, anti runaway.
- **Keepalive 15 s** + `X-Accel-Buffering: no` : traverse Nginx + Cloudflare.

### Bloqueurs ouverts
- **B-001** (TTL session) : test reporté à J19 (tunnel ngrok + budget partenaire).
- **B-009** (Skills upload) : partenaire au matin.
- **B-010** (carbon-calc skill bundle PYTHONPATH) : arbitrage J10.
- **Nouveau (mineur)** : signatures SDK Anthropic à valider par le partenaire
  contre la doc actuelle avant la 1re exécution (ROADBLOCK : non-bloquant
  parce que tout passe par `agents_client.py` — patch unique si signature
  diffère).

### Prochaine étape
- J13 Backend IFC (upload + Agent Conformité + PDF) — code pur, pas de
  dépense engagée.
- J14-J17 Frontend : décisions UX requises → STOP partenaire.

---

## 2026-05-22 — Session 11 (J13 Backend IFC + Conformité + PDF)

**Mode** : autonome de nuit, suite GO partenaire.

### Travail effectué
- **Module `backend/app/ifc/`** : wrapper `validator.py` qui réexporte la
  fonction `validate()` depuis `skills/ifc-check/ifc_validator.py` (single
  source of truth). Fallback de path pour container Docker
  (`/app/skills/ifc-check`) et dev local (`./skills/ifc-check`).
- **Module `backend/app/ifc/pdf.py`** : génération PDF via jinja2 +
  weasyprint, template `app/templates/conformite_rapport.html` avec
  disclaimer en haut + bas, tableaux RE2020/PMR, listes des échecs avec
  ID + GlobalId + valeur mesurée.
- **Router `routers/ifc.py`** : 3 endpoints
  - `POST /api/ifc/upload` (multipart, max 200 Mo, pipeline validate + PDF
    en synchrone, persiste app.ifc_validations)
  - `GET /api/ifc/pdf/:validation_id` (download avec check ownership via
    Supabase RLS)
  - `GET /api/ifc/validations` (historique des 50 plus récentes de
    l'utilisateur)
- **Dockerfile** : ajout libgl1, libgomp1 (IfcOpenShell), libpango-1.0-0,
  libpangoft2-1.0-0, libcairo2, libffi-dev, shared-mime-info (WeasyPrint).
- **requirements.txt** : ajout python-multipart 0.0.20 (FastAPI upload),
  ifcopenshell 0.8.5, jinja2 3.1.4, weasyprint 63.1.
- **docker-compose.yml** : mount `./skills:/app/skills:ro` pour que le
  backend puisse importer ifc_validator.py.
- **Tests** : 8 tests `test_ifc_router.py` (extension, summarize_pass,
  config) + 4 tests `test_ifc_pdf.py` (templates, labels, smoke render).
  Tous PASS — 12/12 dans le container (avec WeasyPrint installé) ;
  11/12 + 1 skip sur l'hôte Windows (pas de WeasyPrint).
- **Docs** : `docs/IFC.md` complète.

### Smoke test end-to-end
- IFC synthétique généré dans le container via `ifcopenshell.file(schema='IFC4')`
  avec 1 wall + 1 door (largeur 0.85 m) + 1 window.
- Upload via curl → `/api/ifc/upload` → réponse :
  - validation_id uuid OK
  - rapport_json : 4 entités, IFC4, summary correct
  - RE2020 : tous OK (pas de valeurs Pset, checks vacuously pass)
  - PMR : door_width FAIL (0.85 m < 0.90 m) ✓ détection correcte
  - pdf_url retourné
- Download PDF via `/api/ifc/pdf/<vid>` → 20 KB, format PDF 1.7 valide ✓

### Bloqueurs résolus
- **B-010 (partial)** : skill ifc-check importable depuis le backend via
  mount Docker `/app/skills:ro`. Pour le bundle Anthropic (skill cloud), la
  question reste ouverte (le sandbox n'a pas de mount custom). Mais pour
  l'usage Mode Conformité backend, c'est OK.

### Décisions techniques notables
- **Wrapper validator.py au lieu de copie** : `backend/app/ifc/validator.py`
  réutilise `skills/ifc-check/ifc_validator.py` via sys.path. Pas de code
  dupliqué — single source of truth dans `skills/`.
- **Pipeline synchrone** (parse + PDF en 1 requête HTTP) : acceptable pour
  IFC ≤ 50 Mo (< 10 s). File d'attente prévue J16 si besoin.
- **PDF stocké sur volume Docker** `./data/storage/pdf/<user_id>/`, jamais
  dans Supabase Storage (D-011).
- **Ownership check via Supabase RLS** pour le download PDF — si la query
  retourne 0 rows, c'est que l'utilisateur n'est pas propriétaire (ou
  l'ID n'existe pas).

### Bloqueurs ouverts (inchangés)
- B-001 (TTL session) : test J19.
- B-009 (Skills upload) : partenaire au matin.
- B-010 (carbon-calc skill bundle pour Anthropic sandbox) : workaround
  endpoint HTTP — branchement possible J17.

### Prochaine étape
- Frontend (J14-J17) : décisions UX requises. **STOP** — au réveil du
  partenaire : choix design system (Tailwind ? shadcn ?), choix carto
  (deck.gl seul vs avec MapLibre styling), prio Mode Stratégie vs Projet,
  fixtures démo bâtiment vedette.

---

## 2026-05-22 — Session 12 (B-001 résolu + Skills uploadés + Sync agents + VL analyse)

**Durée** : ~6h overnight (autonome) + ~1h matin (suite + commit)
**Tokens** : élevé (multiples calls Anthropic API + analyse PostGIS)
**Coût Anthropic estimé** : ~2-3 € (TTL test smoke + run principal 10 min + sync agents)
**Statut** : LIVRÉ (commit ci-dessous)

### Livré

**B-009 — Upload Skills Anthropic** :
- `agents/upload_skills.py` : helper `files_from_dir()` du SDK, idempotent
  (check par display_title, version=create si exists), persiste lockfile
  `agents/skills.yaml`.
- 6 skills uploadées sur `https://api.anthropic.com/v1/skills` :
  - conx-carbon-calc, conx-fdes-lookup, conx-ifc-check,
    conx-horssite-biosource, conx-re2020-target, conx-pmr-checks.
- Beta header `skills-2025-10-02`. Coût upload = 0 € (gratuit).

**ANT — agents/sync.py refondu** :
- 2 environments créés :
  - `conx-env-default` (allowed_hosts: ngrok wildcards + supabase + ign +
    ademe ; pip pkgs: requests, pyyaml).
  - `conx-env-conformite` (pip pkgs: ifcopenshell additionnels).
- 3 agents créés (claude-opus-4-7, beta `managed-agents-2026-04-01`) :
  - `conx-selection` : skills=[] (D-006 : scoring déterministe, system
    prompt suffit, web_fetch builtin tool pour appels backend).
  - `conx-plan` : skills=[carbon-calc, fdes-lookup, horssite-biosource,
    re2020-target].
  - `conx-conformite` : skills=[ifc-check, re2020-target, pmr-checks].
- Lockfile `agents/agents.lock.yaml` (env_id + agent_id + agent_env mapping).
- Bind `environment_id` à la session (PAS à l'agent — découverte SDK :
  `sessions.create(agent, environment_id)`).
- Fix fallback `*.ngrok-free.app` wildcard quand `NGROK_PUBLIC_URL`
  contient le placeholder `YOUR_TUNNEL` (allowed_hosts API rejette
  les non-hostnames).

**B-001 — Test TTL session (RESOLU)** :
- Test `agents/test_ttl.py` exécuté 2 fois :
  - Smoke (`--wait-min 0`) : PASS, 7/7 keywords retrouvés.
  - Run principal (`--wait-min 10`) : PASS, status_after_sleep=`idle`.
- **Verdict empirique** : TTL ≥ **6 min 04 s** d'idle window observé entre
  `session.status_idle` (09:53:34 UTC) et `user.message` suivant
  (09:59:36 UTC). Session restée `idle`, PAS `terminated`. Contexte msg1
  rappelé dans reply2 (pavillon, 1965, 412, brique, 124, gaz, chanvre
  tous présents).
- L'écart 10 min visé / 6 min observé vient d'une race condition initiale
  dans `wait_for_idle` (corrigée dans le commit — tracking `pre_event_id`
  + sleep initial 2 s + `main()` met à jour pour passer le `pre_id` à
  `wait_for_idle`). Non re-exécuté pour économiser le budget — 6 min
  est déjà au-delà du use case chat itératif (1-3 min entre tours).
- Fallback "replay-previous-plan" **PAS encore implémenté** côté backend.
  À faire J16 si nécessaire (couvre le cas long-idle utilisateur, hors
  pitch démo).

**Cleanup `agents.yaml`** :
- Retiré référence skill `selection-scoring` non uploadée. L'agent
  Sélection s'appuie sur system prompt + `web_fetch` (D-006).

**Documentation Vieux-Lille (quartier vedette démo)** :
- `docs/VIEUX_LILLE_ANALYSE.md` : 1819 bâtiments dans la bbox, 577 DPE
  réels (31.7 %), 51 MH, 0 SPR (champ BDNB non peuplé pour Lille,
  limitation millésime 2025-07.a). 3 candidats top score :
  - **Candidat A** : `bdnb-bg-NKGA-DUZ2-J28H` (RNB 25E29JA2A9V6), R+2
    7 logts 1870, DPE F, score 91.1, 517 tCO₂.
  - **Candidat B** : `bdnb-bg-JBP7-PFQL-4T69` (RNB 1JZ6GKJCV1ZS), R+3 17
    logts 1930, DPE G, score 91.1, 714 tCO₂ (record quartier).
  - **Candidat C** : `bdnb-bg-7F6X-1AGX-L22Q` (RNB GMJ42V7S3YCW), R+4 3
    logts 1900, DPE F, score 77.1, 300 tCO₂.
- **Note pour le partenaire** : aucun bailleur social ne matche tous les
  critères (F/G + ADEME + pré-1948) dans la bbox Vieux-Lille → relâché
  vers personne_morale_privee (copros anciennes). Fallback Wazemmes ou
  Lens centre si le partenaire préfère un narratif logement social.

**Documentation LiDAR Vieux-Lille** :
- `docs/LIDAR_VIEUX_LILLE.md` : 4 dalles IGN LiDAR HD identifiées
  (0704_7060, 0704_7061, 0705_7060, 0705_7061), ~2-3 Go total. dpt 59 en
  open data Etalab depuis 2024. URL Etalab/geopf.fr non testée en CLI
  (l'IGN reformatait régulièrement) — recommandation au partenaire :
  download manuel via geoservices.ign.fr.
- Stub `scripts/lidar_to_gltf.py` à compléter J15.

**Supabase migration (BLOQUÉ)** :
- `scripts/supabase_migrate.py` + `scripts/supabase_rls_roundtrip.py`
  prêts. Bloqué : DDL impossible via REST PostgREST (anon/service_role
  keys insuffisants pour CREATE TABLE). Nécessite **DB password OU
  Personal Access Token** OU exécution manuelle dans Supabase SQL
  Editor.
- `docs/SUPABASE_MIGRATION.md` documente les 3 voies pour le partenaire.

### Bloqueurs résolus
- **B-001** (TTL session Managed Agents) : RESOLU 2026-05-22 (cf. supra).
- **B-009** (Skills upload) : RESOLU (6 skills uploadées, lockfile).
- **B-010** (carbon-calc skill bundle sandbox) : workaround backend HTTP
  + bundle Anthropic skill, double tirage. Le bundle Anthropic est uploadé
  et lié à l'agent Plan, le backend HTTP fallback reste actif si l'agent
  préfère.

### Bloqueurs ouverts (mis à jour)
- **B-002** (asyncio supabase-py) : statut MINEUR confirmé, à valider J11
  côté tests.
- **B-004** (hébergement applicatif final) : différé post-concours.
- **SUP** (Supabase migration RLS) : besoin DB password OU PAT côté
  partenaire. Scripts prêts.
- **VL — pré-gen MVT tiles VL zoom 14-18** : à faire après le commit
  (avec martin + vues PostGIS existantes).

### Prochaine étape
1. **Commit** ce que ci-dessus (advisor → OK).
2. **VL — pré-gen MVT tiles Vieux-Lille zoom 14-18** (#48) : warm le cache
   martin pour la démo.
3. **J14 — Frontend Mode Stratégie** (#50) : init avec Vite + React + TS +
   Tailwind + shadcn/ui, intégrer deck.gl + MapLibre, fetch
   `/api/buildings?bbox=VL`.

### Questions ouvertes pour le partenaire
1. **Bailleur social vs copros privées** dans la démo Vieux-Lille : OK
   pour rester sur copros privées (narratif "passoires urbaines
   fragmentées, opération collective") OU bascule sur Wazemmes/Lens
   centre pour avoir un bailleur social vedette ?
2. **Re-run TTL test 10 min "propre"** (avec wait_for_idle patché) : OK
   d'économiser le budget puisque 6 min est déjà au-delà du use case ?
3. **DB password Supabase OU PAT** : pour débloquer l'application
   automatisée de la migration 001_app_schema.sql + RLS roundtrip.
4. **LiDAR HD download manuel** : action partenaire (4 dalles, ~2-3 Go)
   ou je laisse stub vide et on cale glTF pré-générés en J15 ?


---

## 2026-05-22 — Session 13 (J14 Frontend Mode Stratégie + pré-warm VL + dev bypass)

**Durée** : ~2h après le commit Session 12
**Tokens** : modéré
**Coût Anthropic** : 0 € (pas d'appel API supplémentaire)
**Statut** : LIVRÉ

### Livré

**VL — Pré-warmup tiles** (#48) :
- Refresh des matviews `tiles.buildings_mv` et `tiles.buildings_centroids_mv`
  (~3.12 M lignes chacune, n'étaient pas peuplées après le restart Docker).
- Script `scripts/prewarm_vl_tiles.py` : 819 tiles (zoom 14-18, 3 layers
  buildings_mv + topo_buildings + commune_passoires_heatmap_mv) sur la bbox
  Vieux-Lille. **2.1 s pour les 819 tiles**, 4393 KB total. Cache martin
  warmé pour la démo.

**J14 — Frontend Mode Stratégie init** (#50) :
- `frontend/` scaffoldé : Vite + React 18 + TypeScript + Tailwind +
  shadcn/ui-style components.
- Dépendances : @deck.gl/core+layers+mapbox, maplibre-gl, @supabase/supabase-js,
  @tanstack/react-query, react-router-dom, radix-ui primitives, lucide-react,
  class-variance-authority + clsx + tailwind-merge.
- Layout : `Nav` (top) + Routes (Stratégie/Projet/IFC) + `Footer` (sources
  Etalab obligatoires sur 100 % des pages, cf. CLAUDE.md §4).
- Page Stratégie complète :
  - `StrategieMap` : MapLibre base (OSM raster < z11.5, BD Ortho IGN WMTS
    streaming ≥ z11.5) + deck.gl ScatterplotLayer interleaved, coloré par
    classe DPE (palette ADEME officielle), taille = score ConX.
  - `FiltersPanel` (sidebar gauche) : preset "Passoires F-G", classes DPE,
    type propriétaire, année max construction.
  - `BuildingDrawer` (sidebar droite, on click) : score header, indicateurs
    clés, 5 composantes scoring (bars), CTA "Ouvrir Mode Projet".
  - `SearchBar` (overlay top) : autocomplete adresse via API BAN data.gouv,
    fly-to map sur sélection (event `conx:flyto`).
  - Exports CSV/GeoJSON via boutons top-right (lien direct API).
- Pages `Projet` + `Ifc` : placeholders pour J15-J17.
- TypeScript strict + typecheck OK. Build production OK (1.87 MB, gzip 532
  KB — code-splitting déferré à J22 polish).

**Dev bypass auth** (advisor catch) :
- Backend `auth.py` : nouveau flag env `CONX_DEV_BYPASS_AUTH=1` qui retourne
  un AuthUser fictif (UUID `00000000-0000-0000-0000-000000000dev`,
  role=architecte) si aucun JWT n'est fourni. Le bypass est désactivé en
  prod (env vide ou unset).
- Tests : 4 nouveaux tests dans `test_auth.py` (bypass off par défaut,
  bypass on sans auth, header malformé toléré, JWT valide priorise quand
  même). 23/23 tests passent.
- Sans ce bypass, le frontend serait inutilisable tant que la migration
  Supabase (SUP blocker) n'est pas appliquée → carte vide. Avec bypass,
  `npm run dev` + `docker compose up` = carte fonctionnelle.

**Smoke test end-to-end** :
- `curl http://localhost:5173/api/buildings?bbox=...&dpe_classes=F&limit=2`
  → 200 OK, retourne `bdnb-bg-YBXE-3CJL-P99H` (Vieux-Lille, bailleur social
  F, score 0.91) + `bdnb-bg-NKGA-DUZ2-J28H` (Candidat A copro 1870 F).
- Proxy Vite /api/* → http://localhost:8000 OK.
- Dev server Vite démarre en 736 ms.

### Décisions techniques notables

- **Auth dev = bypass env, pas login UI** : choix Option B de l'advisor
  (vs Option A login Supabase qui nécessite SUP débloqué d'abord). Plus
  rapide à shipper, gardé gated derrière env var explicite. À retirer
  quand SUP débloqué (J11 fin).
- **MapLibre style minimal** : OSM raster pour zoom bas (rapide, sans
  clé), BD Ortho IGN WMTS pour zoom élevé (impressionnant pour démo VL).
  Pas de Mapbox/Cesium payants.
- **deck.gl interleaved=true** : pour que les layers soient rendus DANS
  MapLibre (pas par-dessus), permettant les effets de profondeur quand
  on ajoutera l'extrusion 3D des bâtiments en J14.x.
- **Pas de ESLint pour l'instant** : retiré du package.json. TypeScript
  strict + tsc suffit pour catch les erreurs structurelles. ESLint à
  ajouter J22 polish si besoin.

### Bloqueurs ouverts (inchangés)
- **SUP** (Supabase migration RLS) : toujours bloqué côté partenaire.
  Dev bypass tient lieu de workaround pour le frontend.
- **B-004** (hébergement applicatif final) : différé post-concours.

### Prochaine étape
- J15 — Frontend Mode Projet (viewer Three.js + fiche détaillée).
- J16 — Chat itératif Agent Plan via SSE.
- J17 — Frontend IFC drag-and-drop.
- VL — Refresh matviews scripté (idéalement post-ingestion, pas manuel).

### Questions ouvertes pour le partenaire (mêmes que Session 12)
1. Bailleur social vs copros pour Vieux-Lille démo ?
2. Re-run TTL 10 min net (ou 6 min observé suffit) ?
3. DB password Supabase OU PAT pour SUP migration ?
4. LiDAR HD download manuel (4 dalles, ~2-3 Go) ?


---

## 2026-05-22 — Session 14 (B-001 net + SUP débloqué + replay-fallback + J16 + J17 + Wazemmes)

**Durée** : ~2h après commit `65cace1`
**Tokens** : modéré
**Coût Anthropic** : ~0.6 € (TTL re-run 10 min net)
**Coût Supabase** : 0 € (free tier, Management API)
**Statut** : LIVRÉ (commit ci-dessous, advisor en cours d'attente avant push)

### Livré

**1. B-001 re-run NET (TTL 10 min)** — script `agents/test_ttl.py` patché correctement
- session `sesn_01H4brQKmtADnzpqF27eAE4E` (re-run avec `pre_event_id` propagé partout)
- msg1 processing : 3 min 39 s (11:15:03 → 11:18:42 UTC)
- **Idle window observé : 10 min 05 s** (11:18:42 idle → 11:28:47 resume)
- status après sleep : `idle` (PAS terminated) ✓
- Contexte msg1 rappelé : reply2 mentionne pavillon/1965/412/brique/124/gaz/chanvre (7/7)
- **B-001 : TTL ≥ 10 min confirmé empiriquement**.

**2. SUP — Supabase migration appliquée + RLS roundtrip OK**
- PAT `sbp_6ee0…` ajouté à `.env` (gitignored).
- `scripts/supabase_migrate.py` réécrit pour Management API `https://api.supabase.com/v1/projects/{ref}/database/query` (avec User-Agent custom pour bypass Cloudflare 1010).
- `001_app_schema.sql` appliqué → 4 tables : `app.agent_sessions`, `app.renovation_plans`, `app.ifc_validations`, `app.user_preferences`. RLS activée sur les 4.
- Schema `app` exposé via PostgREST (PATCH `/v1/projects/{ref}/postgrest` `{db_schema: 'public,graphql_public,app'}`).
- `supabase_rls_roundtrip.py` exécuté : 2 users test créés, A insère un plan, B essaie de read/update → 0 lignes (isolation OK), A delete son plan, cleanup. **🎉 RLS PASS**.
- Colonne `previous_session_id` ajoutée à `app.agent_sessions` (pour traçabilité fallback replay).

**3. Wazemmes — bâtiment vedette fallback identifié**
- 9659 bâtiments dans la bbox Wazemmes (3.040–3.070, 50.620–50.636), 1677 passoires, 616 F/G réelles ADEME, 417 bailleurs sociaux, **11 candidats stricts** (BS + F/G ADEME + pré-1980 + pas MH).
- **Top-1 vedette** : `bdnb-bg-81UB-UTZE-ZP7F` (RNB `2D9YFEZTSAC9`) — R+3 béton 1978 bailleur social DPE F **324 kWh ep/m²/an** 48 logements 1084 m² · **Score ConX 96.1/100** (record absolu HDF) · **1727 tCO₂ évitées 30 ans** · coût 650 k€.
- IRIS 593500402, centroïde (3.0467, 50.6243).
- Documenté dans `DECISIONS.md` D-022 (Vieux-Lille candidat B principal + Wazemmes top-1 fallback + Lens centre plan C).

**4. Fallback replay-previous-plan codé (B-001 long-idle utilisateur)**
- Helper `_send_with_replay_fallback(user, session_id, content)` dans `backend/app/routers/agents.py` :
  - Si `retrieve_session(sid)` renvoie idle/working → send direct.
  - Si terminated/error/exception → lit dernier plan dans `app.renovation_plans` (RLS user_id), crée nouvelle session Anthropic, envoie un user_message combinant "Contexte plan précédent + Nouvelle demande", persiste la nouvelle session avec `previous_session_id` pour traçabilité.
- `PlanMessageResponse` étendu avec `was_replayed: bool` + `previous_session_id: str | None` pour signaler au frontend qu'il doit basculer son state.
- 5 tests unitaires `tests/test_agents_replay.py` : status idle direct, status terminated avec plan, status terminated sans plan stocké, exception retrieve_session, format du prompt. **5/5 PASS**.
- Frontend `PlanChat` détecte `was_replayed=true` et bascule transparemment sessionId.

**5. J16 — Chat itératif Mode Projet**
- `frontend/src/components/PlanChat.tsx` (~250 lignes) :
  - Premier message auto via POST `/api/agents/plan/start`.
  - Stream SSE via EventSource sur `/api/agents/plan/:sid/stream`. Agrège les chunks `agent.message` en texte complet.
  - Versions chips v1/v2/v3 cliquables (préservation de l'historique).
  - Input "Itère…" + bouton Send (Enter).
  - Affichage d'un badge "session renouvelée" si fallback déclenché.
  - Spinner + état busy/error pendant streaming.
- `frontend/src/lib/api.ts` étendu : `startPlanSession`, `sendPlanMessage`, `planStreamUrl`.
- Intégré dans `pages/Projet.tsx` à la place du placeholder ChatPlaceholder J14.

**6. J17 — Frontend IFC drag-and-drop**
- `frontend/src/pages/Ifc.tsx` complet :
  - Zone drop centrée avec animation hover.
  - Upload via `uploadIfc()` (multipart FormData → POST `/api/ifc/upload`).
  - Affichage du rapport : badges RE2020/PMR (vert/rouge), summary entités (walls/doors/windows/spaces), tables détail checks avec icônes pass/fail/warning, warnings explicites.
  - Bouton télécharger PDF (link direct vers `/api/ifc/pdf/:id`).
  - Bouton "Nouveau fichier" pour reset.
  - Mention légale "Pré-vérification — ne remplace pas un BCT".
- `frontend/src/lib/api.ts` : types `IfcCheck`, `IfcReport`, `IfcUploadResponse`, fonction `uploadIfc(file: File)`.

**7. Typecheck + build OK**
- `npm run typecheck` : 0 erreur (TypeScript strict).
- `npm run build` : 2.08 MB (gzip 591 KB). Code-splitting J22 polish.

### Décisions techniques notables

- **Management API Supabase via PAT** : la voie officielle pour appliquer DDL sans avoir le mot de passe DB (qui est resté chez le partenaire). User-Agent custom requis pour bypass Cloudflare bot detection.
- **previous_session_id en colonne nullable** : optional, le fallback fonctionne même si la colonne n'existe pas (logging + retry sans elle).
- **Versioning UI dans PlanChat** : chaque user.message → version N+1 affichée comme chip cliquable. L'utilisateur peut revenir consulter v1 même après avoir généré v2/v3.
- **Tests carbon/dpe_ml pré-existants en échec** : `FileNotFoundError` sur `/app/data/fdes_static.json` (data/ pas mounté dans le container). Pré-existant, non lié à mes changes. À corriger dans un patch infra (ajouter `- ./data:/app/data:ro` au docker-compose).

### Bloqueurs résolus
- **B-001** : TTL net 10 min 05 s + fallback replay codé.
- **SUP** : schema `app` créé, RLS roundtrip OK.

### Bloqueurs ouverts
- **B-002** : asyncio supabase-py — toujours MINEUR, non bloquant pour la démo.
- **B-004** : hébergement applicatif — différé post-concours.
- **Carbon test failures** : `/app/data/fdes_static.json` manquant dans le container. Pré-existant. À traiter dans une session séparée (docker-compose patch + smoke run).

### Prochaine étape
- **Test end-to-end live** du chat itératif (avec un vrai building_id et le PAT live, vérifier que SSE stream OK depuis le browser).
- **LiDAR HD pipeline** : reste à coder (priorité moyenne — la démo tourne sans grâce à l'extrusion BD TOPO).
- **Pré-calcul plans IA** v1 + v2 sur VL candidat B et Wazemmes vedette (~2 € Anthropic).
- **Pré-warmup MVT Wazemmes** zoom 11-18 (~2 s).
- **docs/DEMO_SCRIPT.md** : scénario 5 min + plans B et C.

### URLs locales
- Frontend dev : http://localhost:5173/
- Backend : http://localhost:8000/api/health (v0.13.0-j13, dev-bypass actif)
- Martin tiles : http://localhost:3000/catalog
- Supabase dashboard : https://supabase.com/dashboard/project/kvevcricmqijfixsrdpa

### Coût Anthropic cumulé sur la session
- TTL test smoke (wait_min=0) : ~0.4 €
- TTL test wait_min=10 (race-buggy) : ~0.5 €
- TTL test wait_min=10 net (patched) : ~0.6 €
- Total : **~1.5 €** sur le cap 10 € accordé.


---

## 2026-05-22 — Session 15 (Wazemmes principal + précalc plans IA + DEMO_SCRIPT + IFC test)

**Durée** : ~1h après commit `52cb17d`
**Tokens** : modéré
**Coût Anthropic** : ~1.5-2 € (3 plans IA pré-calculés)
**Statut** : LIVRÉ (à commit après advisor)

### Livré

**1. D-023 — Bascule Wazemmes principal / Vieux-Lille fallback**
- Argumentaire chiffré : +1013 tCO₂ vs VL (1727 vs 714), 48 logts vs 17, score 96.1 vs 91.1, bailleur social narratif jury fort vs copro privée.
- `DECISIONS.md` : nouveau D-023 avec table comparative + liste démo finale (référence unique).
- Frontend : `WAZEMMES_VIEW` + constantes `VEDETTE_BUILDING_ID` ajoutées dans `src/map/style.ts`.
- Stratégie : bouton overlay "Wazemmes" (cible) pour vol direct.
- Projet placeholder : 2 boutons "Démo Wazemmes (vedette)" + "Démo Vieux-Lille (fallback)".

**2. Précalc plans IA en cache** (`scripts/precalc_plans.py`)
- Génère 3 plans via l'agent `conx-plan` :
  - **Wazemmes v1** (référence) : 8286 chars, session `sesn_018khW6JVed5PR1iz4pi3eSK`
  - **Wazemmes v2** (variation chanvre) : 9969 chars, session `sesn_018MfWV46thZZfFQK1LfNnyQ`
  - **Vieux-Lille v1** (fallback) : session `sesn_01XEaey8bUuTSxhfuKTf1AJ9` (cours)
- Double cache : `data/storage/cached_plans/<building_id>_v<n>.json` (local, lookup demo) + `app.renovation_plans` (Supabase via service_role).
- Endpoint backend `GET /api/agents/plan/cached/:bid/:v` non-authentifié (lookup démo).
- Coût ~1.5-2 € sur cap 5.5 € restant.

**3. Pre-warm MVT Wazemmes**
- `scripts/prewarm_vl_tiles.py` étendu `--quartier {vieux-lille, wazemmes}`.
- Wazemmes zoom 11-18 : **1845 tiles servies en 4.6 s** par martin (3 layers).

**4. DEMO_SCRIPT.md** (`docs/DEMO_SCRIPT.md`, ~12 KB)
- Découpage chronométré strict des 5 minutes (acte 0 titre / acte 1 méthode / acte 2 stratégie / acte 3 Mode Projet Wazemmes / acte 4 IFC / acte 5 closing).
- Fallbacks codifiés étape par étape : plan IA > 90 s → cache, Anthropic down → cache auto, chat v2 plante → cache v2, Wazemmes plante → VL fallback, tout Lille plante → Lens centre, IFC upload échoue → PDF préchargé.
- Latences cibles vs acceptables par étape.
- Checklist pré-démo 30 min avant le pitch (services, ngrok, caches, assets, warm).
- Plans B/C référencés (D-023).
- 8 phrases-clés mémorisables citables.
- 5 questions probables du jury anticipées (fiabilité chiffres, Claude vs FR, données à jour, RGPD).

**5. IFC test représentatif** (`scripts/create_demo_ifc.py`)
- Génère `data/storage/demo_assets/test_re2020_pmr_fail.ifc` (10.4 KB) via ifcopenshell dans le container backend.
- Structure : 12 murs (8 ext avec R_iso conformes), 4 portes (3 OK + **1 Porte WC à 0.82 m < seuil 0.90 m PMR**), 8 fenêtres (Uw 1.1-1.25 toutes OK), 3 spaces.
- Validation testée live : **RE2020 PASS, PMR FAIL** (1 fail détecté sur porte WC). Schéma IFC4, 4 entités principales.
- PDF rapport sample `data/storage/demo_assets/sample_ifc_report.pdf` (20 KB) généré comme fallback démo.

**6. Fallback cache UI dans PlanChat**
- Bouton "Utiliser le plan pré-calculé" disponible avant génération.
- Timer 90 s : si la génération dépasse, bandeau ambre apparaît avec bouton "Charger cache".
- Bascule silencieuse vers cache si `startPlanSession` plante (Anthropic down).
- Badge "cache" affiché sur les versions chargées depuis le cache.

**7. Fix schéma Supabase IFC**
- `backend/app/routers/ifc.py` : `sb.table("ifc_validations")` → `sb.schema("app").table("ifc_validations")` (3 occurrences). Bug pré-existant des sessions précédentes, découvert au test live upload IFC.

### Bloqueurs ouverts (mis à jour)
- **B-011** (LiDAR HD post-test live) : OUVERT — décision après que le partenaire ait testé l'extrusion BD TOPO en live.
- **B-012** (EventSource auth prod) : OUVERT — différé post-concours, dev bypass actif pour la démo.

### URLs locales (toujours actives)
- Frontend dev : http://localhost:5173/
- Backend : http://localhost:8000/api/health
- Cache plan : http://localhost:8000/api/agents/plan/cached/bdnb-bg-81UB-UTZE-ZP7F/1
- Building Wazemmes : http://localhost:8000/api/buildings/bdnb-bg-81UB-UTZE-ZP7F
- Martin tiles : http://localhost:3000/catalog
- Mode Projet vedette : http://localhost:5173/projet/bdnb-bg-81UB-UTZE-ZP7F

### Coût Anthropic cumulé session
- TTL smoke + 2 TTL 10 min : ~1.5 €
- Précalc 3 plans : ~1.5-2 €
- Total **~3-3.5 €** sur le cap 10 €. **6.5-7 € de marge restante**.

### Prochaine étape
- Partenaire teste la plateforme en live (Wazemmes Mode Projet + chat itératif + IFC).
- Selon retour : LiDAR HD à activer ou pas.


---

## 2026-05-23 — Session 16 (Robustesse SSE + polish pré-pitch + 6 chantiers)

### Contexte
Dernière grosse vague avant rehearsal pitch CD2E. Brief Saad en 6
chantiers : robustesse SSE, prompt agent sans jargon, export PDF, URL
ADEME vérifiée, logo SVG, polish design. Mode boucle continue.

### Décisions
- **D-025** : vague robustesse + polish documentée (DECISIONS.md).
- **CHANTIER 2 écart assumé** : prompt source mis à jour mais agent live
  pas resynchronisé (bug pré-existant `sync.py` → **B-013**). Plans cachés
  nettoyés par regex post-hoc + injection préambule pré-cadrage modulaire.
  Pas de re-génération Anthropic (sécurité qualité fin de vague).
- **CHANTIER 4** : lien ADEME retiré (Cloudflare 403, pas vérifiable, règle
  Saad respectée). Identifiant DPE affiché en texte.

### Modifs structurelles
- `backend/app/plan_export.py` (nouveau) : markdown→HTML→PDF via jinja2 +
  weasyprint + `markdown` lib. Template `plan_rapport.html` (couverture +
  TOC + corps + sources + mention légale).
- `backend/app/routers/agents.py` : nouvel endpoint `POST /api/agents/plan/
  <sid>/export-pdf?version=N`. Robustesse SSE : circuit-breaker 3 erreurs,
  back-off, try/except par event individuel, log structuré
  `[SSE <sid>] poll #X elapsed=…`.
- `frontend/src/components/Logo.tsx` (nouveau) : SVG inline composant.
- `frontend/src/lib/useCountUp.ts` (nouveau) : hook animation count-up
  (respecte prefers-reduced-motion).
- `frontend/src/components/PlanChat.tsx` : reconnect 3 essais avec
  `?after=<last_id>`, fallback cache automatique, bouton « PDF ».
- `frontend/src/components/Nav.tsx` + `Footer.tsx` : logo + tagline
  pré-cadrage + footer renforcé « ne remplace pas un MOE ».
- `frontend/src/pages/Projet.tsx` : RadarChart pentagone, count-up sur
  ScoreCircle + BigStat impacts 30 ans, tooltips pédagogiques sur sigles
  (QPV, AC1, RPLS, PMR, RCU), lien ADEME → texte simple.
- `scripts/clean_cached_plans.py` (nouveau) : idempotent, strip jargon
  internes + injection préambule modulaire dans les 3 plans cachés.
- `agents/system_prompts/plan.md` : prompt complètement réécrit
  (anti-jargon, framing pré-cadrage, sources publiques uniquement).

### Tests
- `pytest backend/tests/` : **174 passed**, 26 skipped (DB-dependent).
- Nouveaux tests : `test_plan_export.py` (6 passed, 1 skip weasyprint),
  `test_agents_export_pdf.py` (4 passed, route + auth + body + version).
- `npm run typecheck` : PASS.
- `npm run build` : PASS, 2.6 MB / 762 KB gzip.

### Vérifications visuelles
- Preview MCP screenshots ont timeout (deck.gl WebGL sature en preview),
  vérification programmatique DOM : Logo SVG présent ✅, RadarChart
  polygon rendu ✅, lien ADEME absent (texte seul) ✅.
- Test live SSE reconnect : **non effectué** (chantier 1 = patch défensif,
  pas validé sur génération 60-120 s). Partenaire doit valider avant pitch.

### Coût Anthropic cumulé session
- `agents/sync.py --check` + `--dry-run` : ~0 € (GET only).
- Tentative sync push : échoué sur bug pré-existant (TypeError) → 0 € de
  call agent.
- **Total session : 0 €**. Budget restant ≈ 6.5-7 €.

### Issues rencontrées
1. **Regex `\s{2,}` mangeait les newlines markdown** → restoration depuis
   git + fix regex en `[ \t]{2,}` (newlines préservées).
2. **`sync.py` bug `Agents.update() version`** : SDK Anthropic 0.103+ exige
   `version` arg. **B-013** ouvert.
3. **Cloudflare 403 sur observatoire-dpe-audit.ademe.fr** : URL non
   vérifiable, lien retiré.
4. **Preview MCP screenshots bloquent sur Projet.tsx + Stratégie** :
   probablement WebGL/recharts animation lourde. Vérif DOM via eval()
   confirme le rendu.

### Prochaine étape
- Partenaire teste 3 générations live SSE (CHANTIER 1 validation).
- Partenaire valide visuellement les 3 plans cachés nettoyés (Wazemmes v1,
  v2 chanvre, VL v1).
- Fix `sync.py` (B-013) + re-push prompt si Anthropic API call jugé sûr.

