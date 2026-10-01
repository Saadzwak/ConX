# ConX — Décisions techniques

Journal des décisions structurantes prises pendant le projet.
Une décision n'est pas supprimée : si elle change, on ajoute une nouvelle entrée qui dit "remplace D-XXX du YYYY-MM-DD".

---

## Modèle d'entrée

```
## D-XXX — [titre court]

**Date** : YYYY-MM-DD
**Statut** : VALIDE / REMPLACE PAR D-YYY / REMISE EN CAUSE
**Catégorie** : Architecture / Lib / Schema / UX / Process / ...

### Décision
[ce qu'on a tranché]

### Options envisagées
- A : ...
- B : ...
- C : ...

### Motif du choix
[arguments pratiques]

### Conséquences
[ce que ça implique : nouveau jalon, lib à apprendre, dépendance externe, etc.]
```

---

## D-001 — Nom du produit : ConX

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Branding

### Décision
Le produit s'appelle **ConX**. Utilisé partout : interface, écrans, PDF rapports, slides, README, footer, métadonnées HTML, repo, code.

### Motif du choix
Décision partenaire, non négociable.

### Conséquences
- `<title>` HTML, manifest PWA, favicon, headers PDF, footer signature.
- Repo nommé `conx` (ou `conx-platform`).
- Pas de variations "ConX-HDF", "ConX Pro", etc.

---

## D-002 — Périmètre données : Hauts-de-France entière

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Scope

### Décision
La plateforme couvre les **5 départements HDF** (59, 62, 80, 60, 02) en données ingérées, ~1,5 M bâtiments (ordre de grandeur à confirmer post-J2). Pas de spécialisation sur un quartier dans le code ni dans l'UX.

### Options envisagées
- A : Un quartier vedette (Wazemmes), démo focalisée, dev court.
- B : Région entière, démo zoom progressif.

### Motif du choix
Décision partenaire : la plateforme doit fonctionner sur n'importe quel bâtiment de la région. La démo profite d'un zoom progressif région → ville → quartier → bâtiment.

### Conséquences
- Tuilage MVT obligatoire (martin ou Tegola) pour la perf 3D régionale.
- LiDAR détaillé impossible à charger en masse : pré-téléchargement de 5-10 bâtiments représentatifs pour la démo + téléchargement à la demande pour le reste.
- Barre de recherche d'adresse avec autocomplétion BAN à intégrer dès J14.

---

## D-003 — Stack data : Supabase (PostgreSQL+PostGIS + Storage + Auth)

**Date** : 2026-05-21
**Statut** : **REMPLACÉ PAR D-011** (2026-05-21, même journée — pivot infra suite à contrainte budget Supabase free tier)
**Catégorie** : Architecture / Infra

### Décision initiale (annulée)
Tout l'infra data passait par Supabase : PostgreSQL+PostGIS + Storage + Auth.

### Pourquoi remplacé
Le partenaire a confirmé que Supabase reste en tier gratuit. Free tier (500 MB BD, 1 GB Storage) ne peut pas accueillir les données publiques massives (BDNB 5-20 GB, BD TOPO 5-10 GB, LiDAR plusieurs GB). Voir D-011 pour la nouvelle approche.

---

## D-004 — Auth dès J11 (et pas J18)

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Process / Jalons

### Décision
Supabase Auth + 4 rôles (`collectivite`, `bailleur`, `architecte`, `entreprise`) en place dès **J11** (auparavant prévu en J18). La persistance des projets utilisateur dépend de l'auth, donc l'auth doit précéder le développement des endpoints qui persistent.

### Motif du choix
Décision partenaire. Cohérence : un utilisateur retrouve ses recherches, plans, validations IFC à la reconnexion.

### Conséquences
- Refactor du plan jalons : J11 inclut auth + RLS, J18 supprimé (ou réutilisé pour autre chose).
- Schéma BD : toutes les tables "projet" portent un `user_id uuid REFERENCES auth.users` + policies RLS.

---

## D-005 — Mode Projet avec chat itératif

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : UX / IA

### Décision
Le Mode Projet propose un chat type ChatGPT à droite du plan affiché. L'utilisateur peut converser ("plutôt en chanvre", "ajoute des panneaux solaires", "réduit le budget de 20 %"). L'agent re-génère le **plan complet** à chaque tour (jamais un diff), avec versioning visible dans l'UI (v1, v2, v3...) et bouton "Revenir à v1".

### Motif du choix
Décision partenaire. C'est le wow moment central de la démo (différenciation vs les outils non conversationnels du secteur).

### Conséquences
- Reprise de session Anthropic Managed Agents à chaque tour utilisateur.
- TTL session à valider à J10 (B-001), fallback "replay-previous-plan" si nécessaire.
- Système prompt explicite : "Régénère le plan COMPLET à chaque tour, ne préserve du tour précédent que ce que l'utilisateur a demandé de garder."

---

## D-006 — Scoring territorial 100 % déterministe

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Architecture / IA

### Décision
La formule de score (potentiel CO₂ × faisabilité × coût × priorité sociale) est **100 % déterministe côté backend Python**, pas générée par l'IA. L'Agent Sélection peut **expliquer** un score en langage naturel ; il ne peut pas le **calculer**.

### Motif du choix
Décision partenaire. Trois raisons :
1. Crédibilité jury (calcul auditable, reproductible).
2. Performance : 1,5 M bâtiments à scorer en batch, IA trop lente et trop chère.
3. Transparence UI (afficher les composantes du score).

### Conséquences
- Formule complète documentée dans `docs/SCORING.md`, à valider avant J11.
- Agent Sélection lit le score depuis l'API backend (`/api/internal/score/:building_id`) et le narre.

---

## D-007 — Jointure DPE ↔ BDNB via RNB ID prioritaire

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Schema / Data quality

### Décision
La jointure entre les tables DPE et BDNB utilise **prioritairement le RNB ID** (Référentiel National Bâtiment). Le matching par adresse n'est utilisé qu'en fallback, avec un **score de confiance** affiché dans l'UI.

### Motif du choix
Décision partenaire. RNB IDs sont les identifiants stables nationaux, intégrés à la BDNB (45M+ entrées) et aux DPE récents. Matching adresse fragile (variations d'écriture, géocodage approximatif).

### Conséquences
- Schéma `dpe` porte `rnb_id` indexé.
- Colonne `match_method` ∈ {`rnb_id`, `address_exact`, `address_fuzzy`, `cadastre_parcel`} et `match_confidence float [0,1]`.
- UI affiche un badge "DPE certain" (rnb_id) vs "DPE probable" (autres méthodes).

---

## D-008 — LiDAR : BD TOPO partout, LiDAR détaillé à la demande

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Architecture / Perf

### Décision
- **Couche universelle 3D** : BD TOPO (emprise + hauteur) pour les 1,5 M bâtiments HDF, suffisant pour extrusion fluide deck.gl partout.
- **LiDAR détaillé à la demande** : quand un utilisateur entre en Mode Projet sur un bâtiment, job async télécharge la dalle, extrait le mesh, génère un glTF, stocke dans Supabase Storage. Cache permanent par bâtiment.
- **Pré-génération** pour 5-10 bâtiments démo (mix typologique et géographique).

### Motif du choix
Décision partenaire. Téléchargement intégral LiDAR HDF impossible (plusieurs To). BD TOPO suffit visuellement à l'échelle régionale.

### Conséquences
- Pipeline LiDAR async (worker `pdal` + `py3dtiles` ou équivalent).
- UI Mode Projet : "Préparation 3D détaillée — 1 à 2 min la première fois, instantané ensuite".
- Job queue (Supabase Queues, ou simple worker Celery/Dramatiq) pour async.

---

## D-009 — Backend Managed Agents : PostGIS via HTTP, reste via Skills bundles

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Architecture / IA

### Décision
Les agents Managed Agents tournent dans un container cloud Anthropic, isolé. Choix par capacité :

| Capacité | Voie | Raison |
|---|---|---|
| Queries PostGIS / scoring | HTTP endpoint FastAPI via `web_fetch` (URL publique, en démo via tunnel ngrok) | Stateful, données vivantes |
| Calcul carbone déterministe | Skill bundle `carbon-calc` (Python via bash) | Calcul pur, données statiques |
| Lookup FDES INIES | Skill bundle `fdes-lookup` (JSON statique ou API si dispo) | Données statiques |
| Validation IFC | Skill bundle `ifc-check` (IfcOpenShell installable via `pip` à l'init du container) | Calcul local sur fichier uploadé |
| Catalogue hors-site / RE2020 / PMR | Skills "knowledge" (markdown progressif) | Prompts spécialisés |

### Motif du choix
Évite l'écriture de 4 serveurs MCP custom. Skills suffisent là où il n'y a pas besoin de réseau interne.

### Conséquences
- Définir le système prompt de chaque agent pour qu'il sache quand utiliser quelle skill.
- Environment Anthropic `cloud` avec `packages: { pip: ["ifcopenshell", ...] }` pour pré-installer.
- En prod : passer le networking en `limited` avec `allowed_hosts: ["api.conx.fr"]`.

---

## D-010 — Repo privé, pas d'open source

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Process

### Décision
Le repo reste **privé** pendant et après le concours. Pas d'open source.

### Motif du choix
Décision partenaire.

### Conséquences
- Pas de section "Contribuer" dans le README.
- Pas de CI publique GitHub Actions exposant des secrets.
- Pour le pitch jury : "code propriétaire, données 100 % publiques".

---

## D-011 — Split stack data : PostgreSQL local (Docker) + Supabase free tier (Auth + app uniquement)

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Architecture / Infra
**Remplace** : D-003

### Décision
Architecture data à deux bases distinctes :

**1. `postgres_local` (Docker, schéma `public_data`)** — données publiques massives :
- `buildings` (BDNB), `dpe` (ADEME), `topo_*` (BD TOPO)
- `building_scores` (5 composantes pré-calculées, cf. SCORING.md)
- `lidar_tiles` (index spatial des LAZ disponibles)
- `ml_dpe_versions` (métadonnées du modèle ML)

Pas de RLS sur `postgres_local` — accès géré par la couche backend.

**2. Supabase Cloud (tier gratuit, schéma `app`)** — données utilisateurs légères :
- `auth.users` (managed par Supabase Auth)
- `agent_sessions` (Anthropic session IDs + métadonnées)
- `renovation_plans` (plans JSON par utilisateur, lien logique vers `buildings` via `building_id` text)
- `ifc_validations` (métadonnées des fichiers IFC uploadés)
- `user_preferences` (poids scoring favoris, bbox dernier, etc.)

RLS activée sur **toutes** les tables `app` : `auth.uid() = user_id`.

**3. Volume Docker `./data/storage/`** — fichiers lourds :
- `lidar/` : LAZ + glTF
- `ifc/<user_id>/` : uploads
- `pdf/<user_id>/` : rapports générés
- `ml/` : modèles `dpe_estimator_<v>.pkl`
- `agent_events/` : logs JSONL

Servis par routes FastAPI authentifiées (vérification rôle + propriétaire).

### Options envisagées
- A : Tout Supabase (D-003 initiale) — blocant car free tier insuffisant
- B : Supabase Pro (~25 €/mois) — partenaire ne veut pas payer en MVP
- C : Tout local PostgreSQL + Keycloak/Authentik — alourdit J1, repousse auth de plusieurs jours
- **D : Split local (massif) + Supabase free (Auth + app léger) — retenu**

### Motif du choix
- **Coût zéro** sur Supabase tant que les données utilisateurs restent légères.
- **Performance** : queries spatiales lourdes sur PostgreSQL local, latence ~0.
- **Auth pro** sans réimplémenter (Supabase Auth + RLS).
- **Souveraineté** : narratif jury cohérent ("données publiques restent en local").
- **Démo locale** : `docker compose up` suffit, Internet optionnel sauf pour Auth + Anthropic + APIs IGN/BAN.

### Conséquences
- **Backend** : deux clients DB. `asyncpg` direct vers `postgres_local` (queries lourdes). `supabase-py` vers Supabase Cloud (Auth + tables `app`).
- **Pas de Foreign Key cross-DB** : `app.renovation_plans.building_id` est un `text` libre, intégrité gérée applicativement.
- **B-002** (asyncio supabase-py) → sévérité réduite à MINEUR : Supabase n'est plus dans le chemin chaud.
- **B-004** (hébergement) → cible probable révisée : VPS / Fly.io plutôt que serverless (postgres_local doit voyager).
- **J1** : docker-compose monte `postgres_local`, le backend valide la connexion à l'instance Supabase existante du partenaire.
- **J11** : RLS définies uniquement sur les tables `app` Supabase.

---

## D-012 — Authentification JWT : PyJWT HS256 local + propagation aux clients supabase-py

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Sécurité / Auth
**Résout** : B-005

### Décision
Tranchée en avance (avant J11) :
- Le backend FastAPI vérifie les JWT Supabase **localement** avec `PyJWT` en **HS256** + secret partagé `SUPABASE_JWT_SECRET` (variable d'environnement, jamais commitée).
- Middleware FastAPI qui :
  - Lit `Authorization: Bearer <token>`.
  - Décode + vérifie signature HS256 + claim `aud` + claim `exp`.
  - Expose `request.state.user_id` (= `sub`), `request.state.role`, `request.state.jwt` aux routes.
- Pour appeler Supabase Cloud avec respect de la RLS : on crée un client `supabase-py` par requête en propageant le JWT (`create_client(SUPABASE_URL, jwt_token)`) afin que PostgREST/Postgres voie le bon `auth.uid()`.
- Cache LRU optionnel sur le décodage pour éviter de re-vérifier sur chaque sous-requête d'une même session (gain marginal, à arbitrer au profilage).

### Options envisagées
- A : **PyJWT local HS256** (retenu) — rapide, offline, standard.
- B : Appel `auth/v1/user` Supabase par requête — 1 round-trip réseau par requête, ralentit fortement.
- C : Vérification asymétrique RS256 + JWKS Supabase — possible mais inutile tant qu'on contrôle le secret partagé.

### Motif du choix
Performance + simplicité + standard de l'écosystème Supabase. Pas de dépendance réseau dans le chemin auth.

### Conséquences
- Dépendance ajoutée : `PyJWT[crypto]` (Python).
- Variable d'env obligatoire : `SUPABASE_JWT_SECRET`.
- Tests d'auth : JWT mockés en pytest (génération locale avec le même secret).
- Décision documentée pour le pitch jury si question sécurité ("standard Supabase, vérification offline, JWT signature symétrique HS256").

---

## D-013 — Tunnel ngrok pour exposer le backend à Anthropic pendant la démo

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Infra / Démo
**Résout en partie** : B-004 (avec décision démo locale)

### Décision
- L'Agent Sélection (cloud Anthropic) appelle l'endpoint HTTP `/api/internal/*` du backend FastAPI via un tunnel **ngrok gratuit**.
- L'URL publique ngrok est **toujours en variable d'environnement** `NGROK_PUBLIC_URL`, **jamais codée en dur** dans le code ou la config Anthropic.
- Un script `scripts/update_tunnel_url.py` permet de pousser l'URL courante dans la config de l'Agent Sélection (via `client.beta.agents.update(...)`) en **10 secondes**. À relancer après chaque nouveau démarrage ngrok.
- Au jour du pitch : le partenaire arbitrera ngrok gratuit (URL changeante) vs ngrok payant temporaire (URL fixe) selon son confort. **Aucun engagement de coût sans validation explicite** (cf. règle §9.D CLAUDE.md).

### Workflow type session de dev
```bash
# Terminal 1
docker compose up
# Terminal 2
ngrok http 8000      # affiche https://xyz123.ngrok-free.app
# Terminal 3
export NGROK_PUBLIC_URL=https://xyz123.ngrok-free.app
python scripts/update_tunnel_url.py
# → Agent Sélection appelle maintenant la bonne URL
```

### Conséquences
- `scripts/update_tunnel_url.py` à créer (J1 ou J10 selon priorité — créé en stub à J1).
- `.env.example` documente `NGROK_PUBLIC_URL`.
- En prod (hors démo) : on remplace ngrok par l'URL réelle de l'hébergement, sans changer le code (juste la variable d'env).
- Pas d'engagement payant ngrok pour le MVP.

---

## D-014 — Pas d'accès API INIES, base statique FDES uniquement

**Date** : 2026-05-21
**Statut** : VALIDE
**Catégorie** : Data / Process
**Résout** : B-003

### Décision
On **n'demande pas** l'accès au web service INIES. La plateforme utilise **uniquement** une base statique versionnée `data/fdes_static.json` contenant les 30 matériaux clés pour la rénovation hors-site biosourcée. Citation FDES par numéro de déclaration dans l'UI.

### Options envisagées
- A : Demande API INIES en J1, fallback statique si pas de réponse → complexifie le code (logique de fallback), introduit une dépendance externe et un risque calendaire.
- B : **Base statique uniquement** (retenu) → autonomie complète, code simple, pas d'engagement administratif.
- C : Scraping INIES → exclu (CGU pas claires, fragile, risque juridique).

### Motif du choix
- **Autonomie complète** : aucune dépendance externe au déploiement ni à la démo.
- **Pas d'engagement administratif** : pas de mail à envoyer, pas d'attente de réponse, pas de CGU commerciale à négocier en MVP.
- **Plan B largement suffisant** pour le MVP : 30 matériaux clés couvrent l'essentiel des choix biosourcés que l'Agent Plan recommandera.
- **Code simplifié** : skill `fdes-lookup` lit directement le JSON, pas de logique de fallback.
- **Traçabilité** : citation systématique du numéro de déclaration FDES + date de consultation dans l'UI et les PDF rapports.

### Conséquences
- **B-003 RÉSOLU**.
- **J9 simplifié** : skill `fdes-lookup` = lecture directe `fdes_static.json`, pas de branche API.
- **Mail INIES abandonné** : retiré de BUILD_LOG.md J1.
- **Format `data/fdes_static.json`** à définir en J9. Structure prévue :
  ```json
  {
    "version": "1.0",
    "source": "INIES (https://base-inies.fr/)",
    "consulted_at": "2026-MM-DD",
    "materials": [
      {
        "id": "bois-clt",
        "name": "Bois CLT",
        "fdes_declaration_id": "XXX-X-XX",
        "kgCO2eq_per_uf": 12.5,
        "uf_description": "1 m² de paroi de 100 mm d'épaisseur",
        "duration_years": 100,
        "biogenic_co2_stored_kg": -45.0,
        "category": "biosource",
        "notes": "..."
      }
    ]
  }
  ```
- **Maintenance** : pour ajouter un matériau, on modifie le JSON et on commit. PR review obligatoire (cohérence avec la doctrine déterministe).
- **Mention UI** : "Source FDES : INIES (base statique consultée le YYYY-MM-DD). Pour des données temps réel, consulter base-inies.fr."

---

## D-015 — J3 (DPE détaillé) intégré dans J2 (BDNB), pas d'ingestion ADEME séparée

**Date** : 2026-05-21
**Contexte** : J3 du plan initial = ingestion DPE depuis le dump ADEME (dpe-france-entiere.zip). Mais BDNB millésime 2025-07.a embarque déjà les DPE ADEME 2025-09 dans deux tables : `batiment_groupe_dpe_representatif_logement` et `batiment_groupe_dpe_tertiaire`.

### Décision
Consolider `public_data.dpe` directement depuis BDNB, sans ingestion ADEME séparée.

### Justifications
- **Pas de duplication** : un seul flux de données à maintenir.
- **Cohérence des identifiants** : `building_id` consistant entre `buildings` et `dpe` (même source BDNB).
- **Millésime DPE récent** : ADEME 2025-09, soit ~2 mois avant le millésime BDNB. Acceptable pour MVP.
- **`arrete_2021=true` à 100 %** des DPE logements confirmé empiriquement sur dpt 02 (cf. BUILD_LOG Session 2) → coefficient 1.9 garanti.

### Conséquences
- Migration `004_create_dpe_detail.sql` : table `public_data.dpe` créée pendant J2.
- Template `005_consolidate_dpe_dept.sql.template` : INSERT logements + tertiaires, ON CONFLICT DO NOTHING (contrainte UNIQUE `(building_id, identifiant_dpe)`).
- `consolidate_dept()` dans `ingest_bdnb.py` applique 003 (buildings) puis 005 (DPE) successivement.
- Plan jalons : J3 disparaît, J4 (BD TOPO routes) suit directement J2.
- Si on a besoin de DPE plus récents post-démo (millésime ADEME postérieur au BDNB), on remettra une ingestion ADEME séparée.

### Validation empirique
- Dpt 02 : 34 960 DPE logement + 1 634 DPE tertiaire = 36 594 lignes, idempotent (UPSERT/ON CONFLICT DO NOTHING).
- Dpt 60 : 50 937 DPE.
- Test `test_dpe_arrete_2021_logements` : 100 % des logements `arrete_2021=true`.
- Test `test_dpe_idempotence` : aucun duplicate `(building_id, identifiant_dpe)`.

---

## D-016 — Bornes sanity `annee_constr` : [1000, 2030], pas [1800, 2030]

**Date** : 2026-05-21
**Contexte** : tests d'invariants initialement bornés à `[1800, 2030]`. Inspection des données montre min=1200, max=2024 sur 3 dpts. 20 617 bâtiments pré-1800 (251 pré-1500) — patrimoine HDF légitime (abbayes cisterciennes, fermes flamandes, beffrois, églises romanes/gothiques).

### Décision
Bornes sanity de `annee_constr` : `[1000, 2030]`. Test `test_annee_constr_plausible` mis à jour. `scripts/db_status.py` affiche aussi un compteur séparé "patrimoine pré-1800" pour visibilité.

### Justifications
- **Réalité du parc bâti HDF** : la région compte ~80 abbayes médiévales (Saint-Bertin, Vaucelles, Loos…), ~120 beffrois UNESCO, des milliers de fermes en torchis/chaume du XVe-XVIIe.
- **Données BDNB** : la BDNB hérite de `mut_date_creation_min` (cadastre) qui inscrit ces dates anciennes par tradition.
- **Borne basse 1000** : antérieur = ruines/archéologie, pas du bâti habitable.

### Conséquences
- Test `test_annee_constr_plausible` borné `[1000, 2030]`.
- `scripts/db_status.py` distingue "années hors borne" (= aberrant) et "patrimoine pré-1800" (= légitime).
- **Pattern à retenir** : pour les seuils sanity, dériver de la donnée empirique (`min`/`max`/distribution), pas d'a priori. Les a priori projettent les habitudes du dev sur la réalité du domaine.

---

## D-017 — ML predictions DPE stockées dans `public_data.dpe` (pas de table séparée)

**Date** : 2026-05-21
**Contexte** : brief J5 partner — "Source mention obligatoire dans la table dpe : source = 'ml-predicted', model_version, confidence, prediction_date". Le partenaire impose la table `dpe` comme cible.

### Décision
Stocker les prédictions ML dans la même table `public_data.dpe` que les DPE réels (BDNB), discriminés par une colonne `source` ∈ {`ademe-real`, `ml-predicted`}. Identifiant synthétique `'ml-pred-<building_id>'` pour respecter la contrainte UNIQUE `(building_id, identifiant_dpe)`.

### Conséquences (migration 010)
- Ajout colonnes à `public_data.dpe` : `source` (NOT NULL DEFAULT 'ademe-real'), `model_version` (hash sha256-8 du `.pkl`), `confidence` (probabilité de la classe prédite), `prediction_date`, `predicted_classes_top3` (text[], fourchette), `clipped` (boolean).
- 4 colonnes booléennes anomalies (brief J5 §5) : `anomaly_rt2012_unexpected`, `anomaly_re2020_unexpected`, `anomaly_pac_low_class`, `anomaly_neighborhood_outlier`.
- CHECK constraint : `source IN ('ademe-real', 'ml-predicted')`.
- Index sur `source` + index partiel sur `building_id WHERE anomaly_*`.
- Ajout `public_data.buildings.dpe_source` text pour tracer l'origine du `dpe_classe` denormalisé.

### Justifications
- **Symétrie** : un bâtiment a UN DPE valide à un instant donné (réel OU estimé). Une table unique reflète cela.
- **Cross-source filtering UI** : `WHERE source = 'ademe-real'` pour le mode "DPE certifié uniquement", `WHERE source = 'ml-predicted'` pour le mode "estimations".
- **`building_scores.dpe_source`** déjà aligné sur ces 2 valeurs (SCORING.md §Implémentation).

### Alternative écartée
Table `dpe_predictions` séparée. Avantage : schémas distincts pour réel vs prédit. Inconvénient : duplication des jointures, complexité accrue, et conflit avec la directive explicite du partenaire.

---

## D-018 — ML : Random Forest scikit-learn (200 arbres, max_depth=15), split spatial 70/30 par commune INSEE

**Date** : 2026-05-21
**Contexte** : brief J5 partner — choix de modèle pour estimation DPE des ~2.7 M bâtiments sans DPE réel HDF.

### Décision
- **Modèle** : RandomForestClassifier (cible classe A-G) + RandomForestRegressor (cible kWh ep/m²/an), entraînés en parallèle.
- **Hyperparamètres** : `n_estimators=200, max_depth=15, n_jobs=-1, random_state=42` (gravés dans `backend/app/ml/train.TrainingConfig`).
- **Split spatial** : par commune INSEE, 70 % communes en train / 30 % en test, `random_state=42` pour reproductibilité.
- **Features** : 15 features (cf. `backend/app/ml/features.py` docstring) — annee_constr + période réglementaire, surface_m2, hauteur_m, nb_logements, type_principal, materiau_mur, type_proprietaire, monument_historique, spr, dept, zone_climatique, ECS individuelle/collective, neighborhood_dpe_class_mean (k=20 PostGIS), neighborhood_dpe_class_count.

### Justifications
- **Random Forest** : robuste, interprétable, gère bien les categorical mélangées avec numeric, pas d'hyperparamètre tuning agressif nécessaire. Le brief J5 le spécifie explicitement.
- **Split spatial OBLIGATOIRE** : éviter la fuite via autocorrélation spatiale (neighborhood_mean). Un split aléatoire ferait que test = voisins du train, sur-estimation accuracy.
- **k=20 voisinage** (au lieu du k=5 historique du plan) : brief J5 §2 explicite.
- **`zone_climatique` par dpt** : approximation acceptable au MVP (les 5 dpts HDF sont en H1a/H1b). Raffinement par commune INSEE possible post-MVP si besoin.

### Conséquences
- Module `backend/app/ml/{features,train,predict}.py` créés.
- Script `scripts/train_dpe_ml.py` lance le pipeline complet, avec STOP obligatoire à la fin pour validation partenaire.
- Métriques calculées sur hold-out spatial : accuracy ±1 classe, accuracy stricte, MAE kWh, matrice de confusion 7 x 7.
- Sauvegarde `data/storage/ml/dpe_estimator_<sha8>.pkl` + JSON metrics.

### Seuils d'acceptation (brief J5 §4)
- accuracy ±1 ≥ 75 % : déploiement normal (badge orange "DPE estimé par IA").
- 60 % ≤ accuracy ±1 < 75 % : déploiement avec avertissement "fiabilité moyenne".
- accuracy ±1 < 60 % : NE PAS DÉPLOYER. Stockage en base avec flag, masqué en UI.

### Risques tracés
- Risque R3 (ML DPE prédictions absurdes) mitigé par : 4 règles d'anomalie déterministes (brief J5 §5), écrêtage kWh à [0, 800], pas de clamp dur sur classe, affichage UI explicite "estimation".

---

## D-019 — Features ML : neighborhood_dpe_class_mean stockée dans `public_data.building_neighborhood_train`

**Date** : 2026-05-21
**Contexte** : la feature `neighborhood_dpe_class_mean` (k=20 voisins PostGIS) est coûteuse à calculer (~15-30 min sur 417k bâtiments avec DPE réel). Recalculer à chaque entraînement serait inefficient.

### Décision
Pré-calculer la classe DPE moyenne du voisinage k=20 (ordinale, sur les voisins avec DPE réel) dans une table dédiée `public_data.building_neighborhood_train`, indexée sur `building_id`. Réutilisée par : (1) entraînement, (2) prédiction massive (J5 phase 2).

### Schéma
```sql
public_data.building_neighborhood_train (
  building_id text PRIMARY KEY REFERENCES buildings,
  mean_ordinal numeric,         -- moyenne sur 1..7 (A=1..G=7)
  count int,                    -- nb voisins effectifs (typiquement k=20)
  computed_at timestamptz DEFAULT now()
);
```

### Justifications
- **Performance** : 15-30 min de pré-calcul, < 1 sec de lookup en JOIN ensuite.
- **Cohérence** : training et prediction utilisent la MÊME définition de voisinage.
- **Recalcul** : si on ajoute de nouveaux DPE réels (ré-ingestion BDNB), DROP TABLE + recompute. Idempotent via PRIMARY KEY.

### Conséquences
- Migration nouvelle requise (à créer en cours d'exécution si table absente — fait directement par le script).
- Table à DROP manuellement pour forcer un recalcul.

---

## D-020 — Refit Random Forest avec `class_weight='balanced'` pour corriger biais F/G (v2)

**Date** : 2026-05-22
**Statut** : VALIDE — arbitrage partenaire suite à B-006.
**Catégorie** : ML
**Contexte** : v1 (`560402f6`) atteignait l'accuracy ±1 globale (83.48 %) mais sous-prédisait massivement les passoires F/G (F ±1 = 40.8 %, G ±1 = 0.55 %). Décision partenaire : refit avec `class_weight='balanced'` (option B de B-006).

### Décision
- `RandomForestClassifier.class_weight='balanced'` sur le classifier uniquement (le regressor n'a pas ce concept).
- Reste des hyperparamètres identiques à D-018 (200 arbres, max_depth=15, random_state=42).
- Nouvelles métriques exposées et persistées : `accuracy_pm1_per_class` (par classe A..G) + `n_per_class` + `class_weight` (traçabilité).
- v1 conservé sous `data/storage/ml/dpe_estimator_v1_baseline_560402f6.pkl` (fallback).
- v2 sauvegardé sous `data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl`.

### Critères d'acceptation partenaire
| # | Critère | Seuil | v2 mesuré | Verdict |
|---|---|---|---|---|
| 1 | Accuracy ±1 globale | ≥ 70 % | 67.18 % | ❌ |
| 2 | Accuracy ±1 classe F | ≥ 60 % | 84.70 % | ✅ |
| 3 | Accuracy ±1 classe G | ≥ 50 % | 73.15 % | ✅ |
| 4 | MAE consommation | ≤ 90 kWh ep/m²/an | 68.04 | ✅ |

**3/4 critères atteints, le critère global est manqué de 2.82 points.** Décision déploiement v2 : différée — attente arbitrage partenaire (cf. B-006 mise à jour).

### Justifications du choix `balanced` (rejet des alternatives)
- **`balanced` (retenu)** : pondération automatique sklearn `n_samples / (n_classes * np.bincount(y))`. Simple, reproductible, paramètre unique, recommandé par les manuels en première ligne.
- **Poids manuels `{F:3, G:5}` (en réserve)** : optionnel si v2 jugé sous-optimal. Plus dirigé, mais ad hoc.
- **XGBoost avec `scale_pos_weight`** : pas dans le brief J5, change la lib. Reporté.
- **Stratified oversampling F/G** : risque overfitting + complique le split spatial. Écarté.
- **Ordinal regression** : respect natif A→G mais hors brief J5, plus de temps.

### Conséquences
- `TrainingConfig.class_weight` ajouté (défaut `None` = v1 baseline).
- `ModelMetrics` étendu : `accuracy_pm1_per_class`, `n_per_class`, `class_weight`.
- `evaluate()` calcule l'accuracy ±1 par classe (boucle masque par classe réelle).
- `scripts/train_dpe_ml.py` : nouveaux args `--class-weight` et `--tag` (nommage explicite des bundles).
- Pas de modification du regressor (la régression n'a pas ce concept).
- Si v2 rejeté par partenaire : v1 reste utilisable (pkl conservé) ou option (c) — exploration alternative.

### Observation tracée (non bloquante)
Le n_train/n_test diffère entre v1 (309 069 / 108 256) et v2 (264 939 / 152 386) bien que les communes/sizes (2 635 / 1 128) soient identiques. Cause : `load_training_dataframe` n'a pas d'`ORDER BY building_id`, donc l'ordre des `unique()` communes varie d'un run à l'autre → le shuffle pioche d'autres communes. Test sets approximativement comparables (méthodologie 70/30 spatiale identique, n_test_communes = 1 128 fixé), mais sélection précise non reproductible. À corriger en J5+ pour reproductibilité parfaite (ajout `ORDER BY building_id ASC` dans la requête SQL).

---

## D-021 — Réévaluation seuils ±1 (asymétrie mission produit), tentative v3 poids manuels, modèle retenu

**Date** : 2026-05-22
**Statut** : VALIDE
**Catégorie** : ML — arbitrage seuils
**Contexte** : v2 (D-020) atteignait F=84.7 % et G=73.2 % en ±1 mais manquait le seuil global ±1 ≥ 70 % (67.18 %, -2.82 pts). Le partenaire a réévalué la priorité après lecture des chiffres.

### Décision (en deux temps)

**1. Réévaluation des seuils** (justification asymétrie mission produit) :
- Sur les 152 386 lignes de test v2, v2 capture ~13 700 passoires F/G de plus que v1 en ±1. Extrapolé aux 2.7 M bâtiments à prédire, l'ordre est de plusieurs centaines de milliers de passoires correctement identifiées.
- Le coût (-16 pts en ±1 global) est concentré sur les classes médianes (D/E) où l'enjeu carbone est moindre.
- Décision partenaire : assouplir le seuil global ±1 de **70 % → 72 %** pour l'évaluation de v3, parce que la mission ConX prime sur la précision globale.

**2. Tentative v3 avec poids manuels** `{F: 2.0, G: 3.0}` (plus doux que `balanced`), tag `v3_manual_FG`, version hash `35e2b41a`.

### Critères v3 vs résultats mesurés

| # | Critère | Seuil partenaire | v3 mesuré | Verdict |
|---|---|---|---|---|
| 1 | Accuracy ±1 globale | ≥ 72 % | 77.43 % | ✅ +5.4 pts |
| 2 | Accuracy ±1 sur F | ≥ 60 % | 51.38 % | ❌ -8.6 pts |
| 3 | Accuracy ±1 sur G | ≥ 50 % | 49.70 % | ❌ -0.30 pt (frontière) |
| 4 | MAE consommation | ≤ 90 | 68.23 | ✅ |

**2/4 critères atteints.** Les deux critères ratés sont F et G — les classes critiques pour la mission ConX. v3 n'atteint pas le compromis recherché.

### Arbitrage final entre v1, v2, v3

Lecture comparative complète :

| Métrique | v1 baseline | **v2 balanced** | v3 manual {F:2,G:3} |
|---|---|---|---|
| ±1 globale | 83.48 % | 67.18 % | 77.43 % |
| ±1 sur F | 40.80 % | **84.70 %** | 51.38 % |
| ±1 sur G | 0.55 % | **73.15 %** | 49.70 % |
| MAE kWh | 67.60 | 68.04 | 68.23 |
| Exact match (sample 10) | 5/10 | 4/10 | 6/10 |
| ±1 (sample 10) | 7/10 | 7/10 | 8/10 |
| Passoires capturées (sample 3) | 0/3 | 1/3 | 1/3 |

Application des règles d'arbitrage automatique du partenaire :
- v3 n'atteint pas 4/4 (donc pas de déploiement direct).
- v3 n'atteint pas 3/4 (donc pas la voie "présentation pour décision").
- v3 a un meilleur ±1 global et un meilleur comportement sur l'échantillon, mais perd contre v2 sur F (-33.3 pts) et G (-23.4 pts) — qui sont les classes prioritaires de la mission.

→ **Per les valeurs explicites du partenaire "trouver les passoires importe plus que perfectionner D/E", v3 est globalement moins bon que v2 (lecture mission-centric).**

### Modèle retenu : **v2 (`de48d81c`, `class_weight='balanced'`)**

Le modèle qui satisfait les critères produit-critiques (F ≥ 60 % et G ≥ 50 %) au prix d'un ±1 global dans la zone "ACCEPTABLE AVEC AVERTISSEMENT" du brief J5 §4.

### Conséquences
- `data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl` devient le modèle de référence pour la prédiction massive (en attente du GO partenaire).
- v1 et v3 conservés sur disque pour traçabilité (gitignored).
- UI : badge orange "DPE estimé par IA — fiabilité moyenne" + masquage des prédictions de confidence < seuil à définir.
- Pour le pitch jury : narrer le choix méthodologique (3 modèles testés, sélection finale alignée avec la mission "passoires").

### Cadre de mon arbitrage (judgment call, pas règle mécanique)

L'arbre de décision du partenaire couvre 4/4, 3/4, "globalement moins bon", "équivalent". **v3 a 2/4 — ce cas n'est pas explicitement dans l'arbre**. J'ai inféré "v3 globalement moins bon que v2 *sur la dimension mission produit*" en re-interprétant "global" via les valeurs explicites du partenaire ("trouver les passoires importe plus que perfectionner D/E"). C'est un judgment call, pas une lecture mécanique des règles. Le partenaire peut tout à fait reformuler.

### Note sur l'espace de recherche `class_weight`

v3 manque G de 0.30 pt — frontalière. Un v4 avec poids plus agressifs (par ex. `{F: 3.0, G: 5.0}` ou `{F: 2.5, G: 4.5}`) pourrait plausiblement atteindre 4/4 (gagner sur G sans dégrader F/global). L'espace n'est pas exploré au-delà de v3, donc je ne défends pas v2 comme l'optimum absolu — seulement comme le meilleur des trois modèles testés selon les critères F/G prioritaires. ~5 min de réentraînement pour tester un v4 si le partenaire le souhaite.

### Possibilité d'override partenaire
Trois choix possibles à ce stade :
1. **Confirmer v2** (mon choix par défaut) → prédiction massive.
2. **Désigner v3** (préférer le ±1 global au prix des F/G) → prédiction massive.
3. **Tenter v4** avec poids manuels plus agressifs (par ex. `{F:3,G:5}`) avant de figer le choix.

Tous les modèles sont sur disque ; le code de prédiction massive est paramétrable par chemin du `.pkl`.


## D-022 — Choix des bâtiments vedettes démo : Vieux-Lille (copros) + Wazemmes (bailleur social)

**Date** : 2026-05-22
**Statut** : DÉCIDÉ par le partenaire

### Contexte
Le pitch de 5 min nécessite un atterrissage final sur un bâtiment précis pour générer un plan rénovation IA en direct. Deux questions ouvertes :
1. Lequel des 3 candidats Vieux-Lille (cf. `docs/VIEUX_LILLE_ANALYSE.md`) choisir comme vedette principale ?
2. Quel quartier de fallback prévoir si Vieux-Lille pose un problème global le jour J ?

### Décision

**Quartier vedette principal** : Vieux-Lille (Lille, 59).
**Bâtiment vedette principal** : `bdnb-bg-JBP7-PFQL-4T69` (RNB `1JZ6GKJCV1ZS`) — candidat B
- R+3, 1930, copro privée, DPE **G** (540 kWh ep/m²/an, certifié ADEME)
- 233 m² · 17 logements (densité élevée)
- Score ConX **91.1/100**
- **714 tCO₂ évitées sur 30 ans (record du quartier VL)**
- Coût estimé 140 k€
- Pas MH, pas SPR

**Narratif Vieux-Lille** : "Passoires urbaines fragmentées en copropriété privée, l'angle mort de la rénovation française. La densité (17 logements) donne un effet de levier carbone exceptionnel pour une seule opération."

**Quartier vedette fallback** : Wazemmes (Lille, 59), bbox WGS84 `(3.040, 50.620) — (3.070, 50.636)`.
**Bâtiment vedette fallback** : `bdnb-bg-81UB-UTZE-ZP7F` (RNB `2D9YFEZTSAC9`)
- R+3 (hauteur 11 m), 1978, **bailleur social** (vs copros à VL)
- Résidentiel collectif, DPE **F** (324 kWh ep/m²/an, certifié ADEME)
- 1084 m² · **48 logements** (~3× la densité de VL)
- Mur béton (cohérent années 70)
- Score ConX **96.1/100** (top score Wazemmes)
- **1 727 tCO₂ évitées sur 30 ans (record absolu)**
- Coût estimé 650 k€
- Pas MH, pas SPR
- IRIS 593500402, centroïde (3.0467, 50.6243)

**Narratif Wazemmes** : "Patrimoine bailleur social des années 70, dense et homogène. Une rénovation hors-site biosourcée à l'échelle de l'immeuble = bilan carbone considérable et reproductible sur l'ensemble du parc."

**Pourquoi les 2 sont à Lille (et pas l'un à Lille + l'autre à Lens centre)** : terrain connu du partenaire pour sécuriser la démo. Le partenaire peut citer des contacts (bailleurs, AMO, BE) à 10 km de l'écran si le jury creuse. Lens centre reste un 3ᵉ fallback (narratif post-minier) mais sans pré-cache MVT/LiDAR — à activer manuellement si Lille pose un problème global.

### Critères d'inclusion validés

Pour Wazemmes (le brief le plus exigeant) :
- ✅ Logement collectif R+2 à R+4 (R+3 ici)
- ✅ Bailleur social (priorité satisfaite)
- ✅ DPE F ou G **réel** ADEME (F)
- ✅ Année avant 1980 (1978)
- ✅ Score ConX > 85 (96.1)
- ✅ Pas patrimoine (MH=false, SPR=false)
- ⚠ Accès chantier ≥ 4 m : colonne `acces_chantier_m` non présente dans `public_data.buildings` (validé pour VL : tous à 4.0 m car contrainte urbaine homogène). À considérer comme satisfait par défaut pour Wazemmes (rues plus larges qu'au Vieux-Lille).

Pour Vieux-Lille, **aucun bailleur social** ne match les critères stricts (F/G + ADEME + pré-1948) dans la bbox — d'où le repli sur copros privées documenté `VIEUX_LILLE_ANALYSE.md` §3.

### Conséquences sur le plan

- **Pré-calcul plans IA** : v1 + v2 ("plutôt chanvre") sur VL candidat B + v1 sur Wazemmes vedette → cache local + Supabase. Coût ~2 € Anthropic.
- **Pré-warmup MVT** : Vieux-Lille déjà chaud (cf. `scripts/prewarm_vl_tiles.py`). Wazemmes à warmer post-merge (~2 s).
- **LiDAR HD** : 2 bâtiments à mesh-er (VL candidat B + Wazemmes vedette). Dalles IGN différentes par quartier.
- **Script démo `docs/DEMO_SCRIPT.md`** : Vieux-Lille en chemin nominal, Wazemmes en plan B au tour 2 ("Pour le narratif logement social, on regarde un autre exemple — Wazemmes"), Lens en plan C global.

### Liste démo finale (référence unique)

| Rôle | Quartier | Bâtiment | ID | Score | tCO₂ | Propriétaire | DPE |
|---|---|---|---|---|---|---|---|
| Vedette PRINCIPAL | Vieux-Lille | Candidat B | `bdnb-bg-JBP7-PFQL-4T69` | 91.1 | 714 | Copro privée | G |
| Vedette FALLBACK | Wazemmes | top-1 | `bdnb-bg-81UB-UTZE-ZP7F` | 96.1 | 1727 | Bailleur social | F |
| Quartier PLAN C | Lens centre | (à identifier J22) | — | — | — | — | — |


## D-023 — Bascule Wazemmes en quartier vedette PRINCIPAL, Vieux-Lille en fallback

**Date** : 2026-05-22 (vague PM)
**Statut** : DÉCIDÉ par le partenaire

### Contexte
D-022 avait positionné Vieux-Lille candidat B comme vedette principal et Wazemmes comme fallback. Après identification effective du bâtiment Wazemmes (`bdnb-bg-81UB-UTZE-ZP7F`), les chiffres ont rendu la décision évidente :

| Critère | Wazemmes vedette | Vieux-Lille candidat B |
|---|---|---|
| ID BDNB | `bdnb-bg-81UB-UTZE-ZP7F` | `bdnb-bg-JBP7-PFQL-4T69` |
| Type propriétaire | **Bailleur social** | Copro privée |
| DPE | F (324 kWh/m²/an, ADEME) | G (540 kWh/m²/an, ADEME) |
| Nb logements | **48** | 17 |
| Année | 1978 | 1930 |
| Score ConX | **96.1/100** | 91.1/100 |
| CO₂ évité (30 ans) | **1 727 tCO₂** | 714 tCO₂ |
| Coût estimé | 650 k€ | 140 k€ |

### Décision

**Bascule des rôles** :
- **Quartier vedette PRINCIPAL** : **Wazemmes** (Lille, 59), bbox `(3.040, 50.620) — (3.070, 50.636)`, bâtiment `bdnb-bg-81UB-UTZE-ZP7F`. Le pitch jury atterrit ici.
- **Quartier vedette FALLBACK** : Vieux-Lille (Lille, 59), bâtiment `bdnb-bg-JBP7-PFQL-4T69` (candidat B). À activer si Wazemmes pose un problème pendant la démo.
- **Quartier PLAN C** : Lens centre (62), terrain inconnu — dernier recours uniquement.

### Argumentaire chiffré
1. **+1 013 tCO₂ évitées** (1727 − 714) = effet de levier x 2,4 — l'argument carbone est plus impressionnant.
2. **Bailleur social = narratif jury plus fort** : la rénovation des passoires des bailleurs sociaux est un objectif POPH (Plan Pluriannuel de Rénovation des Logements Sociaux) explicite + un sujet jury récurrent (financements ANRU, subventions Région HDF). Une copro privée raconte un autre récit (intéressant, mais plus minoritaire dans le débat public).
3. **Score 96.1/100** > **91.1** = "plus de 9 5/100 selon notre indice" est citable directement par le pitch.
4. **48 logements** vs 17 = densité d'impact x ~3, narratif "une opération = un immeuble entier rénové".
5. **Année 1978** : générique d'une vague de construction massive (HLM années 70 → reproductible sur des milliers de bâtiments similaires en HDF). 1930 = beaucoup plus daté, moins réplicable.

### Conséquences sur le plan

- **Pré-warmup MVT Wazemmes** : zoom 11-18 (1845 tiles servies en 4.6 s par martin) ✓ fait.
- **Pré-calcul plans IA** : Wazemmes v1 (référence) + Wazemmes v2 (variation chanvre) + Vieux-Lille v1 (fallback) → cache local + Supabase.
- **DEMO_SCRIPT.md** : pitch atterrit sur Wazemmes (le chat itératif "plutôt chanvre" devient le wow moment 1:45-3:45).
- **Frontend** : par défaut, le bouton "Ouvrir Mode Projet" en bas de la sidebar Stratégie pointe vers le bâtiment vedette du moment. À paramétrer dans un fichier de config démo.

### Liste démo finale (référence unique — révision D-022)

| Rôle | Quartier | Bâtiment | ID | Score | tCO₂ | Propriétaire | DPE |
|---|---|---|---|---|---|---|---|
| **Vedette PRINCIPAL** | **Wazemmes** | top-1 | `bdnb-bg-81UB-UTZE-ZP7F` | **96.1** | **1727** | **Bailleur social** | F |
| Vedette FALLBACK | Vieux-Lille | candidat B | `bdnb-bg-JBP7-PFQL-4T69` | 91.1 | 714 | Copro privée | G |
| Quartier PLAN C | Lens centre | (à identifier J22) | — | — | — | — | — |

---

## D-024 — Aplatissement de l'objet `score` au top-level de `BuildingDetail` + refonte fiche en dashboard hiérarchisé

**Date** : 2026-05-23 · **Session** : J18 · **Statut** : appliqué (commit `<this>`)

### Contexte

L'audit `docs/BUILDING_DATA_INVENTORY.md` (2026-05-23) a révélé :

1. Un **bug latent** côté Mode Projet : le frontend lisait `building.score_total`, `building.s_co2`, etc. à plat, mais l'API `/api/buildings/:id` les retournait nichés dans `building.score.*`. Résultat : `0/100` affiché, barres à 0, CO₂ évité `—`.
2. **80 colonnes BDNB exploitables** non remontées à l'API (DPE détaillé U-values, conso DLE 7 ans, RPLS distribution, QPV, réseau chaleur, risques, urbanisme, fiabilité).
3. La fiche Projet était une longue liste de champs, pas un dashboard hiérarchisé.

### Décision

**Refonte complète** de l'endpoint `/api/buildings/:id` et de la fiche Mode Projet en deux temps :

1. **Aplatir** les composantes scoring au top-level de `BuildingDetail` Pydantic (avec rétrocompat : l'objet `score` nesté reste exposé pour les scripts internes). Le calcul de `score_total` à la volée (formule pondérée standard `0.35·s_co2 + 0.25·s_faisa + 0.20·s_cout + 0.10·s_social + 0.10·s_passoire`) est aussi exposé.
2. **Enrichir** l'endpoint avec une jointure dynamique sur le schéma `bdnb_2025_07_a_open_data_dep{dept}` (whitelist HDF stricte = anti-injection) qui remonte :
   - Adresse BAN, identifiant DPE ADEME, dates
   - QPV + Réseau de chaleur + Urbanisme AC1
   - Diagnostic technique complet (U-values, chauffage, ECS, ventilation, vitrage, déperditions par poste)
   - RPLS bailleurs sociaux (distribution DPE par logement, accessibilité PMR)
   - Conso réelle 7 ans (DLE Enedis + GRDF)
   - Risques naturels (radon, argile, sismique)
   - Fiabilité BDNB par axe (emprise, hauteur, adresse)
   - Accès chantier (largeur voirie + distance)
3. **Calculer en backend** : coût énergie annuel + 30 ans (tarif pondéré 0.15 €/kWh), émissions totales 30 ans, période thermique réglementaire, date d'expiration DPE, aides éligibles (matrice règles Eco-PLS / ANRU / CEE / MPR Copro / RCU / Fonds vert).
4. **Nouvel endpoint** `GET /api/buildings/:id/rank` (lazy) qui retourne le classement IRIS + commune via 2 CTE MATERIALIZED (dept abandonné pour perf : 600k rows × formule = 5+s, IRIS+commune suffisent narrativement).
5. **Refonte UI** : fiche compacte par défaut (identité, score, badges contextuels, perf, voisins) + bouton "Voir tout le dashboard" qui déplie 6 sections expert (A Diagnostic technique, B Conso 7 ans, C RPLS distribution, D Coût + classement, E Aides, F Risques + urbanisme).

### Justification du choix d'aplatissement vs propagation `score.*`

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| Aplatir côté API | 1 endroit, frontend simple, plus de bug latent | Casse rétrocompat si script externe lit `score` | **Retenu** + on garde `score` nesté en parallèle |
| Propager `score.*` côté frontend | 0 changement API | Touche tous les composants qui consomment `BuildingDetail`, risque de bug similaire ailleurs | Écarté |

Le doublon `score` (à plat + nesté) coûte ~150 bytes de payload supplémentaires. Acceptable.

### Performance

- `/api/buildings/:id` Wazemmes : ~250 ms (1 query public_data + 2 queries BDNB séquentielles, asyncpg ne supporte pas opérations concurrentes sur 1 conn).
- `/api/buildings/:id/rank` Wazemmes : ~1.7 s (IRIS rapide, commune Lille 80k rows × formule = bottleneck, mais "lazy" donc invisible au first paint).
- Optimisation post-démo si besoin : matérialiser `score_total` comme colonne générée dans `building_scores` avec index → rank en < 100ms.

### Anti-pattern à ne PAS faire

- **Schéma BDNB en string-interpolation sans whitelist** : risque SQL injection. La whitelist `_BDNB_DEPTS = {"02","59","60","62","80"}` doit rester stricte. Tout nouveau dpt doit être ajouté ici explicitement.
- **`asyncio.gather` sur deux queries asyncpg avec la même connexion** : tentation logique → exception `cannot perform operation: another operation is in progress`. Le code les séquence correctement.


---

## D-025 — Vague robustesse + polish pré-pitch (2026-05-23)

**Date** : 2026-05-23
**Statut** : appliqué (commit à venir)
**Périmètre** : SSE robustness, system prompt agent Plan, export PDF, logo, polish design

### Contexte

Dernière vague avant rehearsal pitch. Six chantiers traités en un commit :

1. **CHANTIER 1 — SSE** : « Connexion SSE interrompue. » s'est manifesté en
   prod. Backend : try/except autour de chaque event, circuit-breaker à 3
   erreurs consécutives + back-off, log structuré (event_id, n_events, poll
   counter). Frontend : reconnexion automatique 3 essais (1s, 2s, 4s) avec
   `?after=<last_event_id>`, fallback automatique sur cache à l'épuisement.
2. **CHANTIER 2 — Prompt agent** : strip du jargon interne (skills, FDES
   placeholder `TBC-J9`, références internes ConX). Préambule pré-cadrage
   modulaire imposé.
3. **CHANTIER 3 — Export PDF du plan** : nouvel endpoint `POST
   /api/agents/plan/<sid>/export-pdf?version=N`, template Jinja2 dédié
   (couverture + sommaire + corps markdown→HTML + sources), weasyprint.
4. **CHANTIER 4 — URL ADEME** : lien retiré (Cloudflare 403 — pas
   vérifiable, règle Saad « tout ce qui n'est pas vérifié ne doit pas
   figurer »). Identifiant DPE affiché en texte seul.
5. **CHANTIER 5 — Logo ConX SVG** : composant React SVG inline
   (« Con » regular + « X » bold accent vert). Réutilisé header + couverture
   PDF.
6. **CHANTIER 6 — Polish design** : tagline pré-cadrage dans header,
   count-up animé sur score circle + BigStat impacts 30 ans
   (`useCountUp` custom, respecte `prefers-reduced-motion`), RadarChart
   pentagone des 5 composantes (recharts), tooltips pédagogiques sur sigles
   (`<title>` natif via prop `tooltip` de ChipBadge), footer renforcé avec
   mention pré-cadrage.

### Écart assumé — CHANTIER 2

Le brief Saad demandait : « tester le nouveau prompt sur Wazemmes en live,
re-générer les 3 plans pré-cachés avec le nouveau prompt » (budget ~2 €
autorisé). **Ce qui a été fait à la place** :

- Le fichier source `agents/system_prompts/plan.md` est à jour (nouveau prompt
  professionnel sans jargon).
- Les 3 plans cachés ont été **nettoyés par regex post-hoc** via
  `scripts/clean_cached_plans.py` (strip TBC-J9 / horssite-biosource §X /
  base ConX / SKILL.md / CARBON.md), + injection du préambule pré-cadrage
  modulaire après le H2 titre.
- `agents/sync.py` (push prompt vers Anthropic) **n'a pas pu tourner** :
  bug pré-existant `Agents.update() missing 1 required keyword-only
  argument: 'version'`. Tracké comme B-013.

Conséquences :
- L'agent live (si le cache est bypassé) continuera d'utiliser l'ANCIEN
  prompt jusqu'à fix du sync + re-push.
- Les plans cachés ont le préambule + sont strippés de jargon, mais leur
  structure / ton restent ceux générés par l'ancien prompt.

Pourquoi cette voie : la voie complète (fix sync.py + push + 3
re-générations Anthropic) ajoutait un risque qualité non maîtrisé en fin de
vague (mauvaise sortie en live = pire que la sortie nettoyée existante).
Le partenaire devra valider visuellement les plans cachés + lancer une
re-génération live quand sync.py sera fixé.

### Test live SSE — non effectué

Le code de reconnexion + heartbeat est défensif et compile, mais aucun
test live n'a été lancé sur un bâtiment non-caché (génération 60-120 s). À
valider par le partenaire avant le pitch :
- 3 plans complets en live sur 3 bâtiments différents
- Couper / reconnecter le wifi pendant la génération → reconnect doit
  reprendre
- Vérifier les logs backend `[SSE <sid>] poll #X elapsed=…`

### Anti-pattern à ne PAS faire

- **`useCallback([])` capture une closure avec deps externes** : OK
  uniquement si le composant remount sur changement de la variable externe
  (cas ici : `loadFromCache` capture `building`, et `PlanChat` remount au
  changement de bâtiment via route param). Documenté en commentaire dans
  `PlanChat.tsx`.
- **Regex `\s{2,}` sur du markdown** : mange les sauts de ligne, casse la
  structure. Toujours utiliser `[ \t]{2,}` pour ne toucher que
  espaces/tabs, jamais newlines. Bug rencontré et corrigé dans
  `scripts/clean_cached_plans.py`.


---

## D-026 — Démo en LIVE par défaut + plans cachés en fallback (2026-05-23)

**Date** : 2026-05-23
**Statut** : appliqué
**Contexte** : ré-arbitrage de l'usage du cache après push effectif du
nouveau system prompt agent (B-013 résolu).

### Décision

Le pitch de 5 min Mode Projet **utilise la génération LIVE Anthropic par
défaut**. Le cache (`docs/demo_assets/cached_plans/`) est positionné en
**fallback de sécurité uniquement** (R7/R8 : Anthropic down, latence
> 90s, rate limit).

Conséquence UX :
- Le bouton « Générer un plan rénovation IA » reste l'action primaire.
- Le bouton « Utiliser le plan pré-calculé » reste visible MAIS sa mention
  reste discrète (cache = backup, pas chemin nominal).
- Le message d'erreur SSE est reformulé non-anxiogène : « L'agent prend
  plus de temps que prévu. Vous pouvez patienter ou revenir au menu pour
  utiliser un plan pré-calculé si disponible. »

### Raison

Le rendu pitch d'une **génération en direct** (60-120 s de streaming
SSE token-par-token) est le wow moment principal. Servir d'emblée un
plan caché tuerait la démonstration de l'IA-en-action. Le cache reste
indispensable comme filet de sécurité (Anthropic peut tomber pendant la
démo, ngrok peut hoqueter, etc.).

### Pré-requis techniques validés ce jour

- **B-013 résolu** : `agents/sync.py` poussé avec succès, l'agent live
  `conx-plan` est en version 2 avec le nouveau system prompt anti-jargon.
  Vérifié via `client.beta.agents.retrieve(agent_id).system` qui contient
  bien « Tu rédiges comme un cabinet d'architecte ou un BE thermicien ».
- **3 plans cachés regénérés en LIVE** via `scripts/precalc_plans.py`
  (Wazemmes v1, v2 chanvre, Vieux-Lille v1). Zéro jargon résiduel
  vérifié programmatiquement sur les 15 patterns interdits (TBC-J9,
  horssite-biosource, re2020-target, carbon-calc, fdes-lookup, base ConX,
  CARBON.md, SKILL.md, D-014, D-010, B-010, B-006, pmr-checks, ifc-check,
  XXX-001).
- **PDF export fonctionnel** : `markdown==3.7` dans le container Docker,
  weasyprint OK, template Jinja2 enrichi (CSS pro, sauts de page,
  tableaux stylés, blockquote vert, hiérarchie de titres). 3 PDF de
  référence dans `docs/demo_assets/pdf/`.

### Anti-pattern résolu

L'agent peut wrapper sa sortie complète dans un fence ` ```markdown ...
``` `. Si on n'enlève pas le fence avant conversion HTML, tout le plan
se retrouve rendu en bloc de code monospace dans le PDF. `_strip_code_fence`
ajouté dans `plan_export.py` ET `precalc_plans.py` (idempotent).

---

## D-027 — Marketplace entreprises hors-site HDF (2026-06, décision rétroactive)

**Date** : 2026-06-02/03 (loguée rétroactivement le 2026-07-08 — l'implémentation
avait précédé la décision, écart process §9.A relevé par l'audit).
**Statut** : appliqué

### Décision

Ajout d'une **Marketplace** d'entreprises de construction hors-site / biosourcé
des Hauts-de-France, reliée aux plans de rénovation IA (l'agent cite des
fournisseurs via des liens `[Nom](marketplace:slug)`).

- 3 routes frontend : `/marketplace` (annuaire), `/marketplace/commandes-groupees`
  (mutualisation d'achats entre bâtiments), `/marketplace/:slug` (fiche entreprise).
- Pages : `Marketplace.tsx`, `MarketplaceCompany.tsx`, `MarketplaceGroupOrders.tsx`
  + composant `CompanyAvatar.tsx`. Données statiques : `frontend/src/data/marketplace_companies.json`.
- ~39 liens marketplace insérés dans les plans pré-calculés.

### Raison

Boucler la chaîne de valeur : après le pré-cadrage IA (« quoi rénover et
comment »), orienter vers le « avec qui » — filière hors-site régionale.
Argument fort pour le jury (impact économique territorial concret).

### Dette relevée (audit 2026-07-07)

- Métadonnées de catégories dupliquées dans 4 fichiers (dedup `lib/marketplace.ts`
  **reportée**, cf. docs/AUDIT_2026-07-07.md carried-forward).
- Sécurité : les liens `marketplace:` du markdown IA sont désormais assainis via
  un `urlTransform` allowlist (Lot 4a M6) — l'ancien passthrough autorisait `javascript:`.

---

## Chantier d'améliorations post-audit (2026-07-08)

Voir `docs/AUDIT_2026-07-07.md` (rapport consolidé de 5 audits) et l'historique git
de la branche `audit-fixes` : Lot 1 sécurité démo (LFI/SSRF PDF, bypass auth),
Lot 2 robustesse runtime (offload async, IDOR SSE), Lot 3 fiabilité data/build
(migrations versionnées, refresh tuiles, martin `tiles_pub`, tuning PG, CI),
Lot 4 qualité frontend (XSS, remount, races). Les décisions structurantes de ce
chantier (schéma `schema_migrations`, schéma `tiles_pub`, dégradation fail-open
de la vérif ownership sur panne Supabase) sont tracées dans le rapport d'audit.

---

## D-028 — Repo rendu PUBLIC (2026-10-01)

**Date** : 2026-10-01
**Statut** : appliqué
**Remplace** : D-010 (« Repo privé, pas d'open source », 2026-05-21).

### Décision

Le dépôt est publié en **public** sur GitHub (demande explicite du propriétaire,
en connaissance du caractère irréversible d'une publication publique).

### Garde-fous appliqués

- **Secrets** : `.env` (clés Anthropic / Supabase service_role / JWT) jamais
  committé (vérifié sur tout l'historique) et gitignoré. Aucun secret dans les
  fichiers suivis.
- **Protection tiers** : le pitch deck `ConX_pitch_deck_*.pdf` (noms personnels
  de Saad EL BABIDI **et de la co-autrice Oumaima ELMALIHI**) a été **purgé de
  TOUT l'historique git** (`git filter-repo`), pas seulement supprimé du dernier
  commit — sinon il resterait récupérable via les anciens commits. La co-autrice
  n'ayant pas consenti à une publication GitHub, son nom ne doit apparaître nulle
  part dans le dépôt public.
- **Licence** : aucune licence open-source ajoutée → droit d'auteur par défaut
  (« tous droits réservés »). Le code reste **propriétaire** : visible mais non
  réutilisable sans autorisation. Cohérent avec l'esprit de D-010.
- Sauvegarde de l'historique pré-réécriture conservée hors dépôt (bundle git).

### Raison

Choix du propriétaire. Le revirement par rapport à D-010 est tracé ici (log
append-only) plutôt qu'en réécrivant D-010.

