# ConX — Source de vérité projet

> **À toi, Claude, qui ouvre ce repo dans une nouvelle session : lis intégralement ce fichier avant tout autre.** Il est la référence unique. Quand quelque chose contredit ce fichier, ce fichier gagne. Quand tu changes quelque chose de structurant, mets ce fichier à jour.

**Dernière mise à jour** : 2026-07-08 (chantier d'améliorations post-audit — voir docs/AUDIT_2026-07-07.md)
**Version plan** : v1 exécuté (jalons J1→J17+ livrés)
**Statut** : **Livré / post-pitch**. Backend FastAPI `0.13.0-j13` (6 routers, 17 endpoints), frontend `0.14.0-j14` (6 pages dont Marketplace), base PostgreSQL locale peuplée (~3,12 M bâtiments + 3,14 M lignes DPE). Le concours CD2E × EuraTechnologies est passé (pitch deck livré). Itérations en cours : corrections issues de l'audit 2026-07-07 (branche `audit-fixes`).

> ⚠ **Runtime au 2026-07-08** : Supabase Cloud (projet free-tier) est **injoignable** (DNS ne résout plus — projet en pause/supprimé). Le backend dégrade proprement (le WOW démo repose sur les plans pré-calculés en cache, sans Supabase). Anthropic reste joignable. Cf. docs/AUDIT_2026-07-07.md.

---

## 1. Identité du produit

**Nom** : `ConX`. Utilisé partout : interface, écrans, PDF rapports, slides, README, footer, métadonnées HTML, nom de repo. Pas de "ConX-HDF", "ConX Pro", "Rénover-HDF", "BatIA". Juste `ConX`.

**Mission** : aider les acteurs publics et privés du bâtiment à identifier et concevoir les rénovations énergétiques hors-site décarbonées prioritaires sur les Hauts-de-France, en s'appuyant sur les données publiques françaises (BDNB, DPE, LiDAR HD, BD TOPO) et l'IA Claude Opus 4.7.

**Cible immédiate** : concours IA pour le Bâtiment CD2E × EuraTechnologies. Pitch de 5 minutes face à un jury de professionnels du bâtiment.

---

## 2. Décisions cadrantes (cf. DECISIONS.md pour l'historique complet)

| ID | Décision |
|---|---|
| **D-001** | Nom produit : ConX (partout) |
| **D-002** | Périmètre : Hauts-de-France entière, 5 dépts (59/62/80/60/02), ~1,5 M bâtiments (ordre de grandeur à confirmer post-J2) |
| ~~D-003~~ | ~~Stack data : Supabase tout-en-un~~ — **REMPLACÉ PAR D-011** (2026-05-21) |
| **D-004** | Auth dès J11 (pas J18) avec 4 rôles : collectivite, bailleur, architecte, entreprise + RLS |
| **D-005** | Mode Projet avec chat itératif (turn N : "plutôt en chanvre") |
| **D-006** | Scoring 100 % déterministe (l'IA explique, jamais ne calcule) |
| **D-007** | Jointure DPE ↔ BDNB via RNB ID prioritaire, fallback adresse + score de confiance UI |
| **D-008** | LiDAR : BD TOPO partout, LiDAR détaillé à la demande + pré-génération 5-10 bâtiments démo |
| **D-009** | Managed Agents : PostGIS (local) via HTTP, reste via Skills bundles |
| ~~D-010~~ | ~~Repo privé, pas d'open source~~ — **REMPLACÉ PAR D-028** (2026-10-01 : repo rendu public, voir DECISIONS.md) |
| **D-011** | **Split stack data** : PostgreSQL+PostGIS local Docker pour données publiques massives, Supabase free tier pour Auth + projets utilisateurs uniquement. Volume Docker `./data/storage/` pour LAZ/glTF/IFC/PDF. |
| **D-012 → D-027** | Voir `DECISIONS.md` (auth JWT HS256, ML DPE retenu, bâtiment vedette Wazemmes, INIES base statique, **D-027 Marketplace HDF**, etc.). Cette table ne liste que les décisions fondatrices ; `DECISIONS.md` est la source complète. |

---

## 3. Architecture (synthèse — split local / cloud)

**Principe** : les données publiques massives restent en local (PostgreSQL Docker + volume disque). Supabase Cloud (tier gratuit) ne sert que pour Auth et les données utilisateurs légères.

```
┌──────────────────────────────────────────────────────────────────────┐
│  NAVIGATEUR — React + TS + Vite                                     │
│    /strategie    deck.gl + MapLibre, BD Ortho WMTS streaming direct │
│    /projet/:id   Three.js (LiDAR + ortho) + chat itératif SSE       │
│    /ifc          drag-and-drop + rapport conformité                 │
│    /marketplace[/commandes-groupees|/:slug]  annuaire entreprises   │
│                  hors-site HDF + commandes groupées (D-027)         │
│    Barre recherche d'adresse globale (BAN autocomplete)             │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTPS / SSE
┌──────────────────────────────▼───────────────────────────────────────┐
│  BACKEND  FastAPI Python 3.12  (docker-compose, local en dev)       │
│  /api/buildings, /api/buildings/:id, /api/agents/*, /api/ifc/*      │
│  /api/exports/*, /api/internal/*                                    │
│  Deux clients DB : asyncpg (local) + supabase-py (cloud)            │
└─┬───────────────┬────────────────┬────────────────┬────────────────┬─┘
  ▼               ▼                ▼                ▼                ▼
┌──────────────┐ ┌───────────────┐ ┌─────────────┐ ┌──────────┐ ┌─────────┐
│ postgres_    │ │ Supabase      │ │ Anthropic   │ │ifcopen   │ │IGN WMTS │
│ local        │ │ Cloud         │ │ Managed     │ │shell +   │ │data.    │
│ (Docker)     │ │ (free tier)   │ │ Agents      │ │RE2020+   │ │geopf.fr │
│              │ │               │ │ Opus 4.7    │ │PMR rules │ │(front)  │
│ PostgreSQL   │ │ Auth + RLS    │ │ 3 agents +  │ │          │ │         │
│ + PostGIS    │ │ + petites     │ │ Skills      │ │          │ │         │
│              │ │ tables app    │ │ bundles     │ │          │ │         │
│              │ │               │ │             │ │          │ │         │
│ Schema:      │ │ Schema: app   │ │             │ │          │ │         │
│ public_data  │ │               │ │             │ │          │ │         │
└──────┬───────┘ └───────────────┘ └─────────────┘ └──────────┘ └─────────┘
       │                                                                   
       │ (lit aussi)                                                       
       ▼                                                                   
┌──────────────┐                                                           
│ martin       │  Sidecar Docker (Rust). Sert les tuiles MVT au navigateur│
│ /tiles/...   │  (deck.gl + MapLibre les consomment).                     
└──────────────┘                                                           

Volume Docker (lu/écrit directement par FastAPI, séparé des bases) :
┌──────────────┐
│ ./data/      │   ├─ lidar/   (LAZ + glTF)
│ storage/     │   ├─ ifc/     (uploads utilisateurs)
│              │   ├─ pdf/     (rapports générés)
│              │   ├─ ml/      (modèles dpe_estimator.pkl)
│              │   └─ agent_events/ (logs JSONL)
└──────────────┘   Servi via FastAPI routes authentifiées.
```

**Pour la démo** : `docker compose up` sur la machine du partenaire suffit. Internet requis uniquement pour : Supabase Auth (cloud), Anthropic API, BAN API, BD Ortho WMTS streaming.

**Narratif souveraineté pour le jury** : les données publiques françaises restent sur sol français en local (pas de fuite cloud étranger). Cloud uniquement pour Auth + projets utilisateurs.

---

## 4. Sources de données (résumé — voir docs/DATA_SOURCES.md pour détail)

| Source | Usage | Licence |
|---|---|---|
| **BDNB** (CSTB) | géométrie, attributs, typo propriétaire, RNB ID | Etalab 2.0 |
| **DPE** (ADEME) | classes énergie réelles, joint sur RNB ID | Etalab 2.0 |
| **LiDAR HD** (IGN) | mesh 3D détaillé, à la demande | Etalab 2.0 |
| **BD TOPO** (IGN) | extrusions universelles HDF | Etalab 2.0 |
| **BD Ortho** (IGN) | habillage photo aérienne WMTS streaming | Etalab 2.0 |
| **BAN** | autocomplétion adresse + géocodage | Etalab 2.0 |
| **INIES** | FDES carbone matériaux — **base statique uniquement** (D-014) | base statique versionnée |
| **Base Carbone ADEME** | facteurs d'émission kWh→kgCO₂ | Etalab 2.0 |

**Footer obligatoire** : `Données : IGN, CSTB (BDNB), ADEME (DPE, Base Carbone), INIES (FDES), DGFiP (BAN), Licence Ouverte Etalab 2.0`.

### Important — coefficient EP électricité 1.9 (anticipation réforme 2026-01-01)

À partir du 1er janvier 2026, le DPE officiel utilise un coefficient EP électricité de **1.9** au lieu de 2.3 ([source DGEC/MTE](https://rt-re-batiment.developpement-durable.gouv.fr/faq-dpe-modification-du-facteur-de-conversion-en-a1021.html?lang=fr)). La **BDNB 2025-07.a anticipe déjà cette réforme** : les classes DPE qu'elle livre utilisent le coefficient 1.9.

**Décision technique** : le pipeline d'ingestion J2 et le scoring ConX adoptent **systématiquement le DPE avec coefficient 1.9** (le futur DPE officiel). Si BDNB livre les deux versions (historique 2.3 et anticipée 1.9), on prend la 1.9. Détails dans [docs/SCORING.md](docs/SCORING.md) composante S_passoire.

**Pitch jury** : "ConX est aligné avec le cadre réglementaire **à venir**, pas avec le passé. Les bâtiments que nous priorisons restent passoires après la réforme."

---

## 5. Stack technique

| Couche | Choix | Pourquoi |
|---|---|---|
| Backend | FastAPI + Python 3.12 | Async, SSE, lecture native PostGIS via asyncpg, écosystème ML/IFC |
| ORM/DB local | SQLAlchemy 2 + asyncpg vers postgres_local (Docker) | Performance maximum sur queries spatiales lourdes BDNB/DPE |
| Client cloud | supabase-py vers Supabase Cloud (free tier) | Auth + petites tables app uniquement (cf. D-011) |
| BD publique (lourd) | PostgreSQL 15 + PostGIS 3, **en local Docker**, schéma `public_data` | Cf. D-011. BDNB, DPE, BD TOPO, building_scores, lidar_tiles ML — restent locaux |
| BD app (léger) | Supabase Cloud free tier, schéma `app` | Cf. D-011. Auth + agent_sessions + renovation_plans + ifc_validations + user_preferences |
| Storage fichiers lourds | Volume Docker `./data/storage/` | LAZ, glTF, IFC uploadés, PDF — pas dans Supabase Storage |
| Auth | Supabase Auth + RLS (sur tables `app` uniquement) | Cf. D-004 |
| ML | scikit-learn Random Forest (classif + régression) | Robuste, interprétable, suffit pour MVP (cf. plan §2.6) |
| IA agents | Anthropic Managed Agents, claude-opus-4-7, beta `managed-agents-2026-04-01` | Sessions persistantes, container managé, plus simple que MCP custom |
| Frontend | React 18 + TypeScript + Vite | Standard |
| Carto | deck.gl + MapLibre GL JS (Stratégie), Three.js (Projet) | Cf. plan §2.1 |
| Tuiles vectorielles | martin (Rust) servant PostGIS → MVT | Performant, simple |
| IFC | IfcOpenShell Python | Référence |
| PDF | jinja2 + weasyprint (HTML → PDF) | Joli, contrôlable |
| Conteneurs | Docker + docker-compose (dev). Déploiement à arbitrer J19 (B-004) | Standard |

---

## 6. Modèle de données (deux bases distinctes)

### 6.A — `postgres_local` (Docker, schéma `public_data`)

Données publiques massives. Pas de RLS (lecture publique pour utilisateurs authentifiés du backend ; le backend met sa propre couche d'autorisation devant).

> ⚠ **Drift schéma documenté vs réel** (constaté audit 2026-07-07) : le schéma ci-dessous est **indicatif**, la base réelle a divergé. En particulier : `public_data.ml_dpe_versions` (décrite plus bas) **n'existe pas** (les versions ML vivent en fichiers `data/storage/ml/*.pkl`) ; la table `public_data.dpe` réelle a **48 colonnes** (dont `raw_json`, flags d'anomalie) et non 9, et n'a pas `match_method`/`match_confidence` ; tables non documentées présentes : `topo_roads`, `topo_buildings`, `building_acces_chantier`, `building_neighborhood_train/predict`, `building_lidar`. Le **backend lit aussi en live** les 19 Go de schémas BDNB bruts `bdnb_2025_07_a_open_data_dep{02,59,60,62,80}` (`_fetch_bdnb_enrichment` — les dropper casse la fiche bâtiment).
>
> **Objets ajoutés au chantier post-audit (2026-07)** — cf. docs/AUDIT_2026-07-07.md :
> - `public_data.schema_migrations(version, applied_at)` : suivi des migrations (Lot 3b) — empêche de rejouer 011/012 qui vidaient les tuiles.
> - schéma `tiles_pub` : contient désormais les 3 vues matérialisées MVT (migration 014) ; martin publie `tiles_pub` uniquement (les vues `tiles.*_v` lentes ne sont plus exposées). Les `source_id` restent le nom de table → URLs frontend `/tiles/buildings_mv` inchangées.
> - Tuning Postgres appliqué via docker-compose (`shared_buffers=1GB`, `work_mem=32MB`, `shm_size=1g`).

```
public_data.buildings
  (building_id PK = batiment_groupe_id BDNB, rnb_id, dept, geom 2154,
   surface_m2, hauteur_m, nb_logements, annee_constr, periode_construction,
   type_principal, materiau_mur, type_proprietaire,
   monument_historique (single boolean — BDNB open ne distingue pas inscrit/classé),
   spr, dpe_classe, dpe_kwh_ep_m2_an, dpe_kg_co2_m2_an,
   dpe_coefficient_ep_electricite DEFAULT 1.9, bdnb_millesime, ingested_at)
  INDEX GIST(geom), INDEX(rnb_id), INDEX(dept), INDEX(dpe_classe),
  INDEX(type_proprietaire), INDEX(annee_constr), INDEX(monument_historique) WHERE = true

public_data.dpe
  (id, building_id FK, rnb_id, source 'ademe-real'|'ml-predicted',
   classe A..G, kwh_ep_m2_an, kg_co2_m2_an, match_method, match_confidence)

public_data.building_scores            -- cf. docs/SCORING.md
  (building_id PK FK,
   s_co2, s_faisa, s_cout, s_social, s_passoire,    -- 5 composantes [0,1]
   co2_evite_t, cout_estime_eur, cout_eur_par_t_co2, -- valeurs brutes
   confidence, dpe_source,
   thresholds_version, computed_at)
  -- score_total NON stocké, calculé à la volée en SQL pur

public_data.lidar_tiles
  (id, emprise geom, path_local, millesime)
  -- path_local pointe vers /data/storage/lidar/... (volume Docker)

public_data.ml_dpe_versions
  (version, trained_at, metrics jsonb, model_path_local)
```

### 6.B — Supabase Cloud (schéma `app`, free tier)

Données utilisateurs et projets. RLS activée sur **toutes** les tables, `auth.uid() = user_id`.

```
app.agent_sessions
  (session_id PK Anthropic, agent_name, agent_version,
   user_id FK auth.users, user_query, events_log_path_local,
   created_at)
  -- events_log_path_local pointe vers /data/storage/ également

app.renovation_plans
  (id PK uuid, building_id text,             -- pas de FK vers postgres_local
   session_id FK app.agent_sessions, user_id FK auth.users,
   plan_json jsonb, version int,
   carbon_t_total, carbon_breakdown jsonb,
   created_at)

app.ifc_validations
  (id PK uuid, user_id FK auth.users,
   ifc_filename, ifc_path_local, re2020_pass, pmr_pass,
   rapport_pdf_path_local, rapport_json jsonb, created_at)

app.user_preferences
  (user_id PK FK auth.users, scoring_weights jsonb,
   favoris_building_ids text[], last_bbox jsonb, updated_at)
```

### Lien entre les deux bases

Il n'y a **pas de foreign key cross-DB** (impossible techniquement). Le backend gère l'intégrité référentielle applicativement :

- `app.renovation_plans.building_id` est un `text` libre. Quand le backend sert le plan, il fait une jointure logique en allant chercher la fiche dans `public_data.buildings` via asyncpg.
- Si un bâtiment disparaît côté `public_data` (ré-ingestion BDNB), les plans associés restent valides côté `app` (snapshot dans `plan_json`) mais peuvent perdre le contexte temps réel — affichage UI "Bâtiment non retrouvé dans la base actuelle".

### Fichiers (volume Docker `./data/storage/`)

```
./data/storage/
  lidar/<dalle_id>/<building_id>.laz     -- LAZ téléchargés
  lidar/<dalle_id>/<building_id>.gltf    -- meshes générés
  ifc/<user_id>/<uuid>.ifc                -- uploads utilisateurs
  pdf/<user_id>/<uuid>.pdf                -- rapports générés
  ml/dpe_estimator_<version>.pkl          -- modèles ML
  agent_events/<session_id>.jsonl         -- logs d'événements agents
```

Tous servis par routes FastAPI authentifiées (vérification rôle + propriétaire avant de retourner le fichier).

---

## 7. Plan de jalons (résumé)

> **État 2026-07-08** : ce plan est **exécuté** — J1→J17 livrés + Marketplace (cf. §12). Seul **J21** (tests E2E Playwright) n'a pas été fait. Le tableau ci-dessous est conservé comme plan historique.

Ordre : **données → moteur → IA → frontend → polish**. Détail dans `~/.claude/plans/brief-projet-plateforme-iridescent-bird.md` Section 4.

| Jalons | Sujet |
|---|---|
| J1 | Setup repo + docker-compose (postgres_local + PostGIS) + vérification connexion à l'instance Supabase existante du partenaire + lancement async download BDNB. *INIES : pas de demande API, base statique uniquement (D-014).* |
| J2-J4 | Ingestion BDNB / DPE / BD TOPO sur HDF dans `postgres_local.public_data` |
| J5 | Modèle ML estimation DPE (split spatial par commune), modèle stocké dans `./data/storage/ml/` |
| J6 | Calcul carbone déterministe |
| J7 | Tuilage MVT régional via martin (lit `postgres_local` directement) |
| J8 | Pipeline LiDAR (download + tile + glTF on-demand, pré-gen 5-10 bât. démo), fichiers dans `./data/storage/lidar/` |
| J9 | Skills bundles : carbon-calc, **fdes-lookup (lecture directe de `data/fdes_static.json`, pas de fallback API — D-014)**, ifc-check, horssite-biosource, re2020-target, pmr-checks. **Test critique ifcopenshell** : créer un environment Anthropic test avec `packages: {pip: ['ifcopenshell']}` et vérifier `import ifcopenshell; print(ifcopenshell.version)`. Si échec (binaire C++/OpenCASCADE non-trivial), bascule en endpoint backend HTTP (comme PostGIS), pas en skill bundle. **Création de `data/fdes_static.json`** : 30 matériaux clés (bois CLT, ouate cellulose, fibre bois, chanvre, béton de chanvre, paille, brique terre crue, BTC, brique terre cuite, béton, acier, aluminium, isolants minéraux, vitrages) avec numéros de déclaration FDES. |
| J10 | 3 Managed Agents créés + **test TTL session 10 min** (B-001) |
| J11 | Backend Mode Stratégie + Supabase Auth + RLS sur les tables `app` (côté Supabase Cloud uniquement) |
| J12 | Backend Mode Projet (chat itératif, reprise session). Plans persistés dans `app.renovation_plans` (Supabase) ; fiche bâtiment lue depuis `public_data.buildings` (local) |
| J13 | Backend IFC + Agent Conformité + PDF. IFC dans `./data/storage/ifc/`, métadonnées dans `app.ifc_validations` (Supabase) |
| J14 | Frontend Mode Stratégie + barre recherche BAN |
| J15 | Frontend Mode Projet (viewer Three.js + fiche) |
| J16 | Frontend Mode Projet chat itératif (versioning visible v1, v2, v3) |
| J17 | Frontend IFC drag-and-drop |
| J18 | *(supprimé — auth est faite en J11)* |
| J19 | Tunnel ngrok + script `update_tunnel_url.py` + écran "À propos" + "Méthodologie" + footer légal (cf. D-013). **Plus de déploiement cloud** (B-004 résolu : démo locale, déploiement post-concours). |
| J20 | *(supprimé — déploiement cloud post-concours)* |
| J21 | **Tests E2E Playwright renforcés** (5 parcours clés au lieu de 3) + observabilité (logs structurés loguru) |
| J22 | **Polish démo renforcé** : animations, transitions, micro-interactions, copy soigné, données seed propres, fixtures IFC variées (3-4 fichiers test : standard OK, RE2020 OK, PMR à corriger, IFC corrompu) |
| J23 | Pitch + slides + fallback vidéo (4 séquences enregistrées) |

---

## 8. Plan de démo (5 min)

Narratif visuel : **zoom progressif région → ville → quartier → bâtiment**.

| Temps | Écran | Discours |
|---|---|---|
| 0:00-0:30 | Slide titre | Chiffre choc 32M / 35 % passoires |
| 0:30-1:15 | Vue régionale HDF (1,5 M bât.) | Heatmap densité passoires par EPCI |
| 1:15-1:45 | Zoom Lille → quartier | "47 bâtiments F-G dans Wazemmes", filtre bailleur social, export CSV |
| 1:45-3:45 | **WOW Mode Projet** sur immeuble F | Three.js LiDAR + photo aérienne. IA génère plan biosourcé en live. Bilan carbone progressive (3 composantes, sources cliquables). **Chat : "plutôt en chanvre"** → plan v2, bilan recalculé. |
| 3:45-4:30 | IFC drag-and-drop | Validation auto 5 s. "RE2020 OK, PMR à corriger (pente 7 % > 5 %)". PDF. |
| 4:30-5:00 | Slide fin | "Données 100 % publiques. IA française. Pour la Région, les bailleurs, chaque architecte." |

**Plan de secours** : 4 vidéos courtes (45-60 s) + session pré-warmée + plan v1/v2 en cache + IFC test en cache navigateur.

---

## 9. Règles de travail

Établies par le partenaire. **Lis-les à chaque session.**

### A. Documentation continue

- `BUILD_LOG.md` : journal à chaque session (durée réelle vs estimée, tokens, ce qui a marché/foiré, prochaine étape).
- `BLOCKERS.md` : un bloqueur ouvert = un point à arbitrer avec le partenaire. Quand tu hésites entre deux approches, tu m'écris dans BLOCKERS plutôt que de deviner.
- `DECISIONS.md` : chaque décision technique majeure (lib, schéma, pattern) avec date, options envisagées, motif.

### B. Code & process

- **N'invente jamais une API, une fonctionnalité ou un comportement qui n'existe pas.** Lis la doc officielle avant toute intégration.
- **Tests au fur et à mesure**, pas à la fin. Avant chaque commit important : `pytest` (backend), `npm test` (frontend).
- **Commits atomiques**, messages descriptifs : `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- **Pas de --no-verify** sur les hooks git. Si un hook échoue, on corrige la cause, pas on bypasse.
- **Pas de force push** sans demande explicite du partenaire.
- **Toujours** afficher les sources et les hypothèses dans l'UI quand un chiffre apparaît.

### B-bis. Règle advisor obligatoire (à partir de J1)

À chaque **substantive change**, appelle l'`advisor` AVANT de commiter. Un substantive change c'est :

- Nouveau module backend ou frontend.
- Nouveau schéma de table (création, modification de colonnes structurantes).
- Nouvelle intégration de lib externe (ajout dans `requirements.txt` ou `package.json`).
- Nouveau pattern d'architecture (nouvelle couche, nouveau service, nouveau type d'agent).
- Tout commit qui touche **plus de 200 lignes** (somme additions + suppressions).
- Toute modification du système prompt d'un agent ou d'une skill bundlée.

Workflow obligatoire :
1. Code la modification.
2. Appelle `advisor`.
3. Si l'advisor flagge un problème : tu corriges et tu refais valider. Pas de "je sais mieux".
4. Quand l'advisor donne OK : tu commits.

**Pas de substantive change non revu.** C'est la règle qui empêche les dettes techniques silencieuses.

Pour les changements triviaux (typo, déplacement de fichier, mise à jour version mineure non-breaking, fix de test) : pas besoin d'advisor.

### C. Communication

- Si une partie du CLAUDE.md devient obsolète ou contradictoire avec une découverte technique : **préviens le partenaire**, on le met à jour ensemble.
- Avant un substantive change ou un commit important : appelle `advisor` (modèle reviewer plus fort).
- À chaque démarrage de session : lire CLAUDE.md, BLOCKERS.md, et le dernier BUILD_LOG.md.

### D. Décisions partenaire à demander explicitement

Tu ne décides JAMAIS seul sur :
- **Toute action qui engage un coût, même mineur** :
  - Passage Supabase Free → Pro / Team.
  - Abonnement ngrok / cloudflared / tunnel payant.
  - Achat de domaine.
  - Hébergement payant (VPS, Fly.io paid, etc.).
  - API tierce payante (Mapbox, Stripe, etc.).
  - **Modèle Claude plus cher que ce qui est prévu en config par défaut** (par défaut on utilise claude-opus-4-7 pour les agents Plan/Conformité/Sélection ; tout autre modèle ou paramètre coûteux — ex. `thinking` extended, gros volumes — doit être validé).
  - Toute consommation cloud non triviale (ex. télécharger un dataset payant, lancer un gros job GPU).

  **Aucune dépense, même mineure, n'est engagée sans validation explicite du partenaire.** Si tu as un doute, tu demandes.

- Changement de scope (ajout/retrait de fonctionnalité ou jalon).
- Changement de stack majeur (changer une lib structurante).
- Toute action destructive non-locale (push, deploy, drop DB cloud).
- Hébergement applicatif final (B-004 — différé post-concours, démo locale).

---

## 10. Risques actifs (résumé — détail dans le plan §5)

| ID | Risque | Statut |
|---|---|---|
| R1 | Volume LiDAR HD HDF | Mitigation D-008 active |
| R2 | Schéma BDNB millésime change | Pinné 2025-07.a |
| R3 | ML DPE prédictions absurdes | Garde-fous + split spatial |
| R4 | Bilan carbone faux | Calcul déterministe + sources affichées |
| R5 | IFC plante sur fichier réel | Try/except + fichier test démo |
| R6 | Perf viewer 3D 1,5 M bât. | LOD strict + MVT pré-générées |
| R7 | Limites API Anthropic | Pré-warmup démo + cache fallback |
| R8 | Latence Agent Plan > 60 s | SSE visible en live + cache pré-démo |
| R9 | ~~INIES API inaccessible~~ | **Résolu D-014** : pas d'API, base statique uniquement |
| R10 | DPE réels manquants | ML estimation + matching RNB |
| R11 | CGU IGN modifiées | Etalab 2.0 confirmé |
| R12 | Coût Anthropic | Budget + monitoring quotidien |
| R13 | Chat itératif dérive | Régénération complète + versioning UI + limit 10 tours |
| R14 | DL BDNB long | Lancement async en J1 |

---

## 11. Bloqueurs actifs (résumé — détail dans BLOCKERS.md)

> **État 2026-07-08** : B-004 est **résolu** (démo locale, déploiement post-concours — BLOCKERS.md). B-012 (auth SSE) reste ouvert mais **contourné** en dev (voir Lot 2 audit : dégradation JWT-only). **Nouveau bloqueur runtime** : Supabase Cloud injoignable (projet free-tier en pause) — l'app dégrade proprement, mais la persistance sessions/plans/validations est HS tant que Supabase n'est pas réactivé. Cf. docs/AUDIT_2026-07-07.md.

| ID | Sujet | Sévérité | Pour quand |
|---|---|---|---|
| ~~B-001~~ | ~~TTL session Managed Agents~~ | RESOLU 2026-05-22 | TTL ≥ **10 min 05 s** confirmé (run net), contexte retenu. Fallback replay-previous-plan **implémenté** (`_send_with_replay_fallback` + 5 tests). |
| B-002 | Maturité asyncio supabase-py | MINEUR | J11 (test) |
| ~~B-003~~ | ~~Accès API INIES~~ | RESOLU 2026-05-21 | — (cf. D-014) |
| B-004 | Hébergement applicatif final | MINEUR | J19 (arbitrage partenaire) |
| ~~SUP~~ | ~~Supabase migration RLS~~ | RESOLU 2026-05-22 | Schema `app` créé via PAT, RLS roundtrip OK (4 tables isolées par user_id). |
| B-011 | Arbitrage LiDAR HD post-test live | MINEUR | Après test live partenaire (BD TOPO suffit ou pas) |
| B-012 | Auth EventSource SSE (cookie ou polyfill) | MINEUR | Post-concours hardening prod |
| ~~B-013~~ | ~~`agents/sync.py` plante sur `Agents.update() version` arg~~ | RESOLU 2026-05-23 | Fix : retrieve agent puis update avec `version=<current>`. Push effectif. |

---

## 12. Livrables présentés au partenaire (état)

1. ✅ Ce fichier (`CLAUDE.md`) — à jour avec D-011 (split local / Supabase)
2. ✅ `docs/SCORING.md` — **validé** partenaire 2026-05-21 (5 composantes, normalisation absolue, pré-calcul composantes)
3. ✅ `docs/DATA_SOURCES.md` — à jour avec D-011 (volumétrie split local / Supabase)
4. ✅ Rapport Supabase + Managed Agents (BUILD_LOG.md session 0)
5. ✅ Rapport environnement (Python 3.12.10, Node 24.6, Docker 29.3, Git 2.53, 214.9 GB libres — **OK**)

**J1 livré** (commit `e5da883`) : docker-compose `postgres_local` + PostGIS + backend stub + martin, scripts d'amorçage, CI. INIES : pas de demande API, base statique D-014.

**J2 livré partiel** (commit `e748e64` puis `b498f38`) : ingestion BDNB dpts HDF, table `public_data.buildings` peuplée. 5 dpts en cours/finalisés (cf. BUILD_LOG Session 3).

**J3 intégré dans J2** (D-015) : BDNB millésime 2025-07.a embarque déjà les DPE ADEME 2025-09. Pas d'ingestion ADEME séparée. Table `public_data.dpe` peuplée depuis `batiment_groupe_dpe_representatif_logement` et `batiment_groupe_dpe_tertiaire`.

**J4 prêt** (commit `b498f38`) : table `public_data.topo_roads`, script `ingest_bdtopo_roads.py` (ogr2ogr via container GDAL), `download_bdtopo.sh`. URLs IGN BD TOPO à compléter par le partenaire dans `scripts/bdtopo_urls.txt` (non exposées en API).

**J5 → J17 LIVRÉS** (état réel au 2026-07-08 — l'ancienne mention « Prochain : J5, STOP demandé » était périmée de ~6 semaines) :
- **J5** ML estimation DPE : modèle Random Forest retenu (D-020/D-021), **2 705 160 lignes `ml-predicted`** en base (`public_data.dpe`) + 435 987 `ademe-real`. Doc `docs/ML_DPE.md`.
- **J6** carbone déterministe (`backend/app/carbon/`), **J7** tuiles MVT martin, **J8** LiDAR (différé post-test — BD TOPO suffit), **J9** skills + IfcOpenShell, **J10** agents + test TTL (B-001), **J11-J13** backend Stratégie/Projet/Conformité, **J14-J17** frontend (carte, fiche, chat SSE, IFC), **Marketplace HDF** (post-J17).
- **J19 partiel** (tunnel ngrok), **J23** pitch deck livré (`ConX_pitch_deck_*.pdf`).
- **J21 non fait** : tests E2E Playwright jamais implémentés (cf. docs/AUDIT_2026-07-07.md).

**Chantier en cours (2026-07-08)** : corrections de l'audit `docs/AUDIT_2026-07-07.md` sur branche `audit-fixes` (sécurité démo, robustesse runtime, fiabilité data/build, qualité frontend, cette doc).
