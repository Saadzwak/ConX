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
