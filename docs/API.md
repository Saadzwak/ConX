# ConX — API Backend FastAPI (J11)

**Statut** : J11 livré — endpoints Mode Stratégie en ligne.
**Base URL dev** : `http://localhost:8000`
**Auth** : JWT Supabase HS256 (D-012) + token interne pour les Managed Agents (D-013).

---

## 1. Authentification

### 1.1 JWT utilisateur (endpoints `/api/buildings`, `/api/exports`)

Le frontend obtient un JWT via Supabase Auth (login email/password ou OAuth).
Toutes les requêtes passent par :

```
Authorization: Bearer <jwt>
```

Le backend décode le JWT **localement** avec `SUPABASE_JWT_SECRET` (HS256), sans
round-trip réseau (cf. D-012). Vérifications :
- Signature HS256.
- `aud == "authenticated"`.
- `exp` non dépassé.
- `sub` présent (= UUID Supabase `auth.users.id`).

Le **rôle** est lu depuis `app_metadata.role`. Rôles valides (D-004) :
- `collectivite`
- `bailleur`
- `architecte`
- `entreprise`

Si le rôle est absent ou inconnu, l'utilisateur est considéré `anonymous` (les
endpoints de lecture l'acceptent ; les endpoints à rôle strict refusent).

### 1.2 Token interne (endpoints `/api/internal/*`)

Appelé par les Managed Agents Anthropic via le tunnel ngrok (D-013). Header :

```
X-Internal-Token: <INTERNAL_SHARED_TOKEN>
```

Le secret est stocké côté config Anthropic (variable d'env de l'agent) et côté
`.env` du backend. Rotation possible sans redéploiement (juste éditer le .env
de l'agent + redémarrer le backend).

---

## 2. Endpoints

### 2.1 `GET /api/health` (public)

Health-check basique. Retourne `{status, service, version, timestamp}`. Pas d'auth.

### 2.2 `GET /api/meta/scoring-config` (public)

Retourne la config publique du scoring : version, version_hash, weights_default,
target_class, horizon, ranges. Sert au frontend pour pré-remplir les sliders.

Exemple :
```json
{
  "version": "1.0",
  "version_hash": "6605264c05ce",
  "weights_default": {"w_co2": 0.35, "w_faisa": 0.25, "w_cout": 0.2, "w_social": 0.1, "w_passoire": 0.1},
  "target_class": {"kwh_ep_m2_an": 90.0, "label": "B"},
  "horizon_amortissement_ans": 30,
  "co2_max_tonnes_30ans": 500.0,
  "cost_eur_per_tco2_range": [500.0, 5000.0]
}
```

### 2.3 `GET /api/buildings` (auth requise)

Liste paginée de bâtiments avec filtres et scoring à la volée.

**Query params** :
| Nom | Type | Défaut | Description |
|---|---|---|---|
| `bbox` | string | — | `"west,south,east,north"` WGS84 (degrés) |
| `dept` | list[str] | — | Codes dpt (`59`, `62`, `80`, `60`, `02`) |
| `dpe_classes` | list[str] | — | Lettres DPE (`A`..`G`), répétable |
| `typo_proprietaire` | list[str] | — | `bailleur_social`, `personne_morale_privee`, `public`, `particulier` |
| `annee_max` | int | — | Construits avant cette année |
| `annee_min` | int | — | Construits après cette année |
| `surface_min_m2` | float | — | Surface SHAB plancher en m² |
| `w_co2`, `w_faisa`, `w_cout`, `w_social`, `w_passoire` | float [0,1] | 0.35/0.25/0.20/0.10/0.10 | Pondération des 5 composantes (SCORING.md) |
| `limit` | int [1, 5000] | 200 | Max items par page |
| `cursor` | string | — | Curseur opaque pour pagination (issu du `next_cursor` précédent) |

**Réponse** : `BuildingsListResponse`.

Exemple :
```bash
curl -H "Authorization: Bearer $JWT" \
  "http://localhost:8000/api/buildings?dept=59&dpe_classes=F&dpe_classes=G&typo_proprietaire=bailleur_social&limit=10"
```

Le **score total est calculé à la volée en SQL pur** (SCORING.md §"Calcul à la
volée") avec les poids fournis. Les 5 composantes sont stockées dans
`public_data.building_scores`.

### 2.4 `GET /api/buildings/{id}` (auth requise)

Fiche détaillée d'un bâtiment :
- attributs BDNB complets (typo, géom, matériau, etc.) ;
- DPE (réel ou estimé ML) ;
- 5 composantes scoring + co2_evite_t + cout_estime_eur + cout_eur_par_t_co2 ;
- géometrie MultiPolygon GeoJSON EPSG:4326 ;
- 5 plus proches voisins (distance + DPE) dans un rayon de 200 m.

### 2.5 `GET /api/exports/strategie.csv` (auth requise)

Export CSV streaming de la liste filtrée. Mêmes filtres que `/api/buildings`.
Encodage UTF-8 BOM (Excel friendly), séparateur `;`.

**Query params** : identiques à `/api/buildings` + `limit` (défaut 50 000, max 100 000).

### 2.6 `GET /api/exports/strategie.geojson` (auth requise)

Export GeoJSON streaming, FeatureCollection EPSG:4326. Limite par défaut 10 000
(les MultiPolygon BDNB pèsent ~1-5 KB chacun).

### 2.7 `POST /api/internal/score-buildings` (token interne)

Appelé par **Agent Sélection** (Anthropic) pour obtenir la liste scorée du
périmètre extrait du prompt utilisateur.

**Body** :
```json
{
  "bbox": [3.0, 50.5, 3.2, 50.7],
  "dept": ["59"],
  "dpe_classes": ["F", "G"],
  "typo_proprietaire": ["bailleur_social"],
  "annee_max": 1975,
  "w_co2": 0.35, "w_faisa": 0.25, "w_cout": 0.20, "w_social": 0.10, "w_passoire": 0.10,
  "top_n": 50,
  "order": "score_desc"
}
```

**Garde-fou** : au moins UN filtre requis (refuse de scanner 3 M lignes sans
périmètre). Renvoie HTTP 400 sinon.

**Ordres disponibles** :
- `score_desc` (défaut) : tri par score total décroissant.
- `co2_evite_desc` : tri par tCO₂ évitées sur 30 ans.
- `cout_eur_par_t_co2_asc` : tri par €/tCO₂ évitée (efficience croissante).

### 2.8 `GET /api/internal/building/{id}` (token interne)

Appelé par **Agent Plan** pour obtenir une fiche light (sans geometry) du
bâtiment cible avant génération de plan. Réduit le contexte envoyé à Claude.

---

## 3. Codes HTTP

| Code | Sens |
|---|---|
| 200 | OK |
| 400 | Mauvais paramètre (bbox invalide, périmètre absent en internal, etc.) |
| 401 | Auth manquante / JWT invalide / token interne incorrect |
| 403 | Auth OK mais rôle insuffisant |
| 404 | Bâtiment introuvable |
| 503 | Backend mal configuré (`SUPABASE_JWT_SECRET` ou `INTERNAL_SHARED_TOKEN` absent) |

---

## 4. Variables d'environnement requises

```bash
# DB
POSTGRES_LOCAL_HOST=postgres_local
POSTGRES_LOCAL_PORT=5432
POSTGRES_LOCAL_DB=conx
POSTGRES_LOCAL_USER=conx
POSTGRES_LOCAL_PASSWORD=<secret>

# JWT (D-012)
SUPABASE_JWT_SECRET=<secret ≥32 caractères, HS256>

# Bypass Managed Agents (D-013)
INTERNAL_SHARED_TOKEN=<secret aléatoire>

# Frontend CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Scoring config (lecture seule)
SCORING_THRESHOLDS_PATH=/app/config/scoring_thresholds.yaml
```

---

## 5. Tests

```bash
cd backend
python -m pytest tests/test_auth.py tests/test_health.py -v
# 21 tests, 0 fail attendu
```

Pour tester un endpoint avec auth en local :
```bash
JWT=$(python -c "
import jwt, time
print(jwt.encode({
  'sub': 'test', 'aud': 'authenticated', 'exp': int(time.time())+3600,
  'app_metadata': {'role': 'architecte'}
}, '<SUPABASE_JWT_SECRET>', algorithm='HS256'))")
curl -H "Authorization: Bearer $JWT" "http://localhost:8000/api/buildings?dept=59&limit=2"
```

---

## 6. Limites connues J11

- **Pas d'OFFSET** sur `/api/buildings` : pagination par curseur opaque
  (`next_cursor`). Acceptable parce que tri stable `(score DESC, id ASC)`.
- **Score total à la volée** : si les composantes ne sont pas pré-calculées
  (`incomplete_data=true`), le score peut être `null`. Le frontend doit gérer
  l'affichage (badge "Données incomplètes").
- **Voisinage 200 m** : si bâtiment isolé en zone rurale, peut retourner < 5
  voisins (acceptable — l'IA narratrice doit le gérer).
- **Mojibake UTF-8** dans `type_principal` (héritage ingestion BDNB) : à
  re-encoder côté pipeline J2 ou frontend. Pas bloquant pour J11.
- **Endpoints `/api/internal/*` non testés en intégration** avec un vrai
  appel agent — couvert par tests unitaires verify_internal_token + smoke test
  curl manuel. À valider en J19 quand le tunnel ngrok est actif.

---

## 7. Liens

- Architecture globale : `CLAUDE.md` §3
- Décisions auth/network : `DECISIONS.md` D-004, D-009, D-012, D-013
- Formule scoring : `docs/SCORING.md`
- Agents qui appellent l'API : `docs/AGENTS.md`
