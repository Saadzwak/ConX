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
