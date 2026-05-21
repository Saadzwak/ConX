# ConX — Sources de données

Toutes les sources publiques utilisées par ConX, avec URL exacte, format, licence, millésime, taille estimée et fréquence de mise à jour.

**Mise à jour** : 2026-05-21.

---

## 1. BDNB — Base de Données Nationale des Bâtiments (CSTB)

| Élément | Valeur |
|---|---|
| **URL portail** | https://bdnb.io/ |
| **URL téléchargement** | https://bdnb.io/download/ (page de sélection par département) |
| **URL data.gouv** | https://www.data.gouv.fr/datasets/base-de-donnees-nationale-des-batiments |
| **URL API** | https://www.data.gouv.fr/dataservices/api-bdnb-open |
| **Procédure d'accès** | Téléchargement libre par département. Pour HDF : 59, 62, 80, 60, 02. |
| **Formats disponibles** | `pgdump` (PostgreSQL+PostGIS), `CSV`, `GPKG` (GeoPackage). |
| **Millésime utilisé** | **2025-07.a** (format V0.7.10) — pinné dans `seed_bdnb.py` |
| **Licence** | Licence Ouverte Etalab 2.0 (usage commercial OK). |
| **Taille estimée** | 5 départements ≈ 5-20 GB en pgdump compressé (estimation à confirmer post-J2). |
| **Fréquence MAJ** | Trimestrielle environ (les millésimes 2024-10 et 2025-07 sont récents). |
| **Contenu utile** | Plus de 400 attributs : géométrie, surface, hauteur, année construction, nb logements, matériau dominant, équipements, RNB ID, parcelle cadastrale, classement énergie, typologie propriétaire (jamais d'identité). |

**Note importante** : BDNB ne livre pas le nom des propriétaires, uniquement une **typologie** (`bailleur_social`, `public`, `personne_morale_privee`, `particulier`). Pas de jointure avec le cadastre (restreint).

---

## 2. DPE — Diagnostic de Performance Énergétique (ADEME)

| Élément | Valeur |
|---|---|
| **URL portail** | https://data.ademe.fr/ |
| **URL API logements** | https://www.data.gouv.fr/dataservices/api-dpe-logements |
| **URL API tertiaire** | https://www.data.gouv.fr/dataservices/api-dpe-batiments-tertiaires |
| **URL dump complet** | https://data.ademe.fr/datasets/dpe-france-logements (zip "dpe-france-entiere") |
| **Procédure d'accès** | Téléchargement zip national (filtrer HDF), OU API publique 10 req/s/IP. |
| **Formats** | CSV (dump), JSON (API). |
| **Millésime utilisé** | Dernier disponible à J3 (mise à jour quasi temps réel à mesure que les diagnostics sont déposés). |
| **Licence** | Licence Ouverte Etalab 2.0 (usage commercial OK). |
| **Taille estimée** | Dump France : ~10-15 GB CSV. Après filtre HDF + champs utiles : ~1-2 GB. |
| **Fréquence MAJ** | Continue (l'ADEME enregistre les nouveaux DPE en temps réel). |
| **Contenu utile** | N° DPE, RNB ID (DPE récents), classe énergie A-G, classe GES A-G, kWh ep/m²/an, kgCO₂/m²/an, surface, année construction, adresse, équipements (chauffage, ECS, refroidissement, ventilation), matériaux. |

**Stratégie de jointure** (cf. D-007) : `rnb_id` prioritaire, fallback adresse exacte puis adresse floue (Levenshtein), fallback parcelle cadastrale.

---

## 3. LiDAR HD — IGN

| Élément | Valeur |
|---|---|
| **URL portail** | https://geoservices.ign.fr/lidarhd (redirigé vers cartes.gouv.fr) |
| **URL catalogue** | https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_NUAGES-DE-POINTS-LIDAR-HD |
| **URL architecture** | https://www.ign.fr/lidar-hd-architecture |
| **URL suivi disponibilité** | https://macarte.ign.fr/carte/mThSup/diffusionMNxLiDARHD |
| **Procédure d'accès** | Téléchargement par dalle 1 km × 1 km via interface cartes.gouv.fr ou URL directe. |
| **Formats** | `LAZ` (nuage de points classifié), `ASC`/`TIFF` pour MNT/MNS/MNH. |
| **Couverture HDF** | **Nord (59) et Pas-de-Calais (62)** : open data depuis 2024 (parmi les premiers livrés, source : IGN tweet juillet 2024). **Somme (80), Oise (60), Aisne (02)** : acquisition hiver 2024-2025, livraison progressive en 2025-2026 (à confirmer dépt par dépt sur macarte.ign.fr à J4). |
| **Licence** | Licence Ouverte Etalab 2.0 (usage commercial OK). |
| **Taille estimée** | Une dalle LAZ classifié : 100 MB - 2 GB selon densité. HDF entière : plusieurs To. **Décision D-008** : pas de téléchargement intégral, on charge à la demande. |
| **Fréquence MAJ** | Acquisition unique en 2025-2026 puis périodique selon programme IGN. |
| **Densité** | ~10 points/m² (LiDAR HD). |
| **Classes** : sol, végétation basse/moyenne/haute, bâtiment, eau, pont, sursol pérenne, autre. |

---

## 4. BD TOPO — IGN

| Élément | Valeur |
|---|---|
| **URL portail** | https://geoservices.ign.fr/bdtopo (redirigé vers cartes.gouv.fr) |
| **Procédure d'accès** | Téléchargement par département en Geopackage. |
| **Formats** | `GPKG` (GeoPackage), `Shape`. |
| **Millésime utilisé** | Dernier édition annuelle (2025 ou 2026). |
| **Licence** | Licence Ouverte Etalab 2.0 (usage commercial OK). |
| **Taille estimée** | ~1-2 GB par département en GPKG complet. |
| **Fréquence MAJ** | Annuelle (édition millésimée). |
| **Contenu utile pour ConX** | Couche `BATIMENT` (emprise + hauteur), couche `TRONCON_DE_ROUTE` (largeur, pour scoring accès chantier), couches d'urbanisme. |

**Usage** : Cette base remplit la **couche universelle 3D** sur HDF entière quand le LiDAR n'est pas téléchargé (cf. D-008).

---

## 5. BD Ortho — IGN (streaming WMTS)

| Élément | Valeur |
|---|---|
| **URL WMTS** | https://data.geopf.fr/wmts |
| **Procédure d'accès** | Streaming direct du frontend, pas de stockage local. CORS-enabled, publique. |
| **Couches utiles** | `HR.ORTHOIMAGERY.ORTHOPHOTOS` (orthophotos couleur), `ORTHOIMAGERY.ORTHOPHOTOS` (génération précédente). |
| **Licence** | Licence Ouverte Etalab 2.0 (usage commercial OK). |
| **Résolution** | 20 cm/pixel typiquement. |
| **Fréquence MAJ** | Acquisition département tous les 3-4 ans environ. |

**Décision D-009 corollaire** : pas de proxy backend, appel direct frontend → `data.geopf.fr/wmts`. Pas de coût de bande passante pour notre backend.

---

## 6. BAN — Base Adresse Nationale

| Élément | Valeur |
|---|---|
| **URL API** | https://api-adresse.data.gouv.fr/ |
| **Documentation** | https://adresse.data.gouv.fr/api-doc/adresse |
| **Procédure d'accès** | API REST publique, gratuite, sans clé. |
| **Endpoints utiles** | `/search/?q=...&autocomplete=1` (autocomplétion), `/reverse/?lon=...&lat=...` (géocodage inverse). |
| **Format** | JSON GeoJSON. |
| **Licence** | Licence Ouverte Etalab 2.0. |
| **Rate limit** | Pas de limite stricte communiquée, mais usage raisonnable demandé. Backoff exponentiel recommandé. |

**Usage ConX** : barre de recherche d'adresse en haut de l'écran avec autocomplétion. Au choix d'une adresse, géocodage → identifier le bâtiment BDNB le plus proche du point (PostGIS `ST_DWithin` sur un rayon de 50 m, puis sélection si plusieurs candidats).

---

## 7. INIES — FDES (carbone matériaux construction)

| Élément | Valeur |
|---|---|
| **URL portail** | https://www.inies.fr/ |
| **URL base** | https://base-inies.fr/consultation/recherche |
| **URL web service** | https://www.inies.fr/le-webservice/demander-un-acces/ |
| **Procédure d'accès** | API sur demande d'accès (envoi de formulaire). Pas de garantie de délai. |
| **Stratégie ConX** | (cf. B-003) : demande envoyée en J1. Si pas de réponse à J9, base statique `fdes_static.json` versionnée avec ~30 matériaux clés. |
| **Format** | API : JSON. Base statique : JSON consolidé localement. |
| **Licence** | CGU INIES (à vérifier précisément pour usage commercial — flag pour J1). |
| **Taille** | 5 830 FDES déclarations, ~30 utilisées dans ConX. |
| **Contenu utile** | kgCO₂eq/UF (unité fonctionnelle), poids, durée de vie de référence, kgCO₂ stocké biogénique. |
| **Matériaux prioritaires** | Bois CLT, ouate de cellulose, fibre de bois, chanvre, béton de chanvre, paille, brique terre crue, BTC, brique terre cuite, béton conventionnel, acier, aluminium, isolant minéral, double vitrage, triple vitrage. |

---

## 8. Base Carbone ADEME

| Élément | Valeur |
|---|---|
| **URL** | https://base-empreinte.ademe.fr/ |
| **API publique** | https://data.ademe.fr/datasets/base-carbone(r) |
| **Usage** | Facteurs d'émission CO₂ par kWh selon source d'énergie (électricité, gaz, fioul, bois, RCU). Utilisés dans le scoring (cf. SCORING.md composante 1). |
| **Licence** | Licence Ouverte Etalab 2.0. |

---

## 9. Référentiels complémentaires

| Source | Usage | URL |
|---|---|---|
| **Zones climatiques RT** | Feature ML DPE, calcul Ubat cible RE2020 | Arrêté zones H1a-H3 + carte RT |
| **EPCI / Communes INSEE** | Agrégation territoriale, filtre Mode Stratégie | https://geo.api.gouv.fr/communes |
| **Code postal France** | Géocodage backup | BAN |

---

## Volumétrie totale et split de stockage (D-011)

**Principe** : les données publiques massives restent **en local** (PostgreSQL Docker + volume disque hôte). Supabase Cloud (free tier) ne sert que pour Auth et les petites tables utilisateurs.

### Local — `postgres_local` Docker, schéma `public_data`

| Source | Volume estimé (post-filtre HDF) | Destination |
|---|---|---|
| BDNB 5 dpts | 5-20 GB pgdump | `postgres_local.public_data.buildings` (+ tables annexes) |
| DPE HDF | 1-2 GB CSV → ~1 GB en PG | `postgres_local.public_data.dpe` |
| BD TOPO 5 dpts | 5-10 GB GPKG → ~3-5 GB en PG | `postgres_local.public_data.topo_*` |
| building_scores (1,5 M lignes × 5 composantes) | ~200 MB | `postgres_local.public_data.building_scores` |
| Index spatiaux GIST | ~500 MB | `postgres_local` |

**Total estimé PostgreSQL local** : ~15-30 GB. Largement dans les capacités d'un volume Docker sur la machine du partenaire (214 GB libres).

### Local — volume Docker `./data/storage/`

| Fichiers | Volume estimé | Destination |
|---|---|---|
| LiDAR HD pré-gen (5-10 bât. démo) | 5-15 GB LAZ | `./data/storage/lidar/<dalle_id>/<building_id>.laz` |
| LiDAR à la demande (cache permanent) | variable, +10 GB par tranche d'usage | `./data/storage/lidar/` |
| glTF générés | 10-100 MB par bâtiment | `./data/storage/lidar/<dalle_id>/<building_id>.gltf` |
| IFC uploadés utilisateurs | 50 MB - 500 MB typique | `./data/storage/ifc/<user_id>/<uuid>.ifc` |
| PDF rapports | < 5 MB chacun | `./data/storage/pdf/<user_id>/<uuid>.pdf` |
| Modèles ML DPE | < 100 MB par version | `./data/storage/ml/dpe_estimator_<v>.pkl` |
| Logs événements agents (JSONL) | variable, ~1 MB par session | `./data/storage/agent_events/<session_id>.jsonl` |

**Total estimé volume Docker** : 20-50 GB en régime de croisière, jusqu'à 100 GB en cas d'usage soutenu LiDAR à la demande.

**Servi par** : routes FastAPI authentifiées qui vérifient le rôle + propriétaire avant de retourner le fichier (`/api/storage/lidar/...`, `/api/storage/pdf/...`).

### Cloud — Supabase free tier, schéma `app`

| Table / objet | Volume estimé | Tier free OK ? |
|---|---|---|
| `auth.users` | < 100 KB total (quelques dizaines d'utilisateurs démo) | ✅ |
| `app.agent_sessions` | < 10 KB par session, retention 90 j | ✅ |
| `app.renovation_plans` (plan_json) | 20-100 KB par plan | ✅ tant que < 500 MB total BD |
| `app.ifc_validations` (métadonnées) | < 5 KB par entrée (fichier IFC reste local) | ✅ |
| `app.user_preferences` | < 5 KB par utilisateur | ✅ |

**Limites Supabase free tier** :
- 500 MB BD → largement suffisant pour les données utilisateurs (10 000 plans = ~1 GB cumulé, à surveiller mais OK pour la démo et les premiers mois).
- 1 GB Storage → non utilisé (D-011 : on n'utilise pas Supabase Storage).
- 50 000 utilisateurs auth/mois → largement suffisant.
- 2 projets max → un seul utilisé.

**Quand passer au Pro** : décision partenaire uniquement, après usage réel. Pas avant la démo.

### Avantages du split (D-011)

1. **Coût** : zéro coût Supabase pendant le dev et la démo (free tier suffit).
2. **Performance** : queries spatiales lourdes (1,5 M bâtiments, scoring batch) sur PostgreSQL local — pas de latence réseau cloud.
3. **Souveraineté** : narratif "données publiques françaises restent en local, pas de fuite cloud étranger" cohérent et défendable jury.
4. **Démo offline** : `docker compose up` suffit ; Internet uniquement pour Auth (Supabase), Anthropic API, BAN, BD Ortho WMTS.
5. **Portabilité** : la stack est dockerisée, transposable sur n'importe quelle machine.

### Inconvénients assumés

1. **Déploiement final** (B-004, J19) demandera un hébergeur avec disque persistant volumineux (VPS / Fly.io / Scaleway IaaS) plutôt qu'un serverless.
2. **Pas de backup automatique** des données utilisateurs locales — assumé pour MVP (les vraies données utilisateurs sont déjà côté Supabase).

---

## Affichage légal obligatoire (footer)

```
Données : IGN (LiDAR HD, BD TOPO, BD Ortho), CSTB (BDNB),
ADEME (DPE, Base Carbone), INIES (FDES), DGFiP (BAN),
sous Licence Ouverte Etalab 2.0.
```

À placer dans le footer de toutes les pages, et dans chaque PDF rapport (header + footer).
