# ConX — Tuilage vectoriel MVT (J7)

**Statut** : pipeline opérationnel, vues 4326 matérialisées avec index GIST.
**Dernière mise à jour** : 2026-05-22.
**Service** : `martin` (Rust, https://martin.maplibre.org/) en sidecar Docker.

---

## 1. Architecture

```
PostgreSQL/PostGIS  (postgres_local)
  └─ schéma `tiles`  ← créé par migration 011/012, séparé de public_data
       ├─ buildings_v / buildings_mv               polygones zoom 14+
       ├─ buildings_centroids_v / _mv              centroïdes zoom 10-13
       └─ commune_passoires_heatmap_v / _mv        agrégats zoom 7-9
                            │
                            ▼  (auto-discovery)
                       martin (Rust)
                       http://localhost:3000
                            │
                            ▼
                  GET /<view>/{z}/{x}/{y}
                  → application/x-protobuf MVT
                            │
                            ▼
                  Frontend deck.gl / MapLibre
```

Les `_v` sont des vues régulières (recalcul à chaque tuile demandée — lent).
Les `_mv` sont des **vues matérialisées** avec **index GIST sur `geom` 4326** — beaucoup
plus rapides (cf. §4).

---

## 2. Schéma `tiles` (migration 011)

### `tiles.buildings_v` / `tiles.buildings_mv`

Polygones 4326 avec score précalculé pour le rendu détaillé (zoom 14+).

| Colonne | Type | Description |
|---|---|---|
| `building_id` | text | PK |
| `geom` | `geometry(MultiPolygon, 4326)` | géométrie projetée 4326 |
| `dept` | text | département (filtre carte) |
| `classe` | text | DPE A-G (réel ou estimé) |
| `dpe_source` | text | `ademe-real` ou `ml-predicted` |
| `hauteur_m` | float | hauteur BDNB (défaut 6m) |
| `type_principal`, `type_proprietaire` | text | filtres |
| `score_total` | int | 0-100 (poids défaut SCORING.md 35/25/20/10/10) |
| `s_passoire` | float | composante 0-1 |
| `is_passoire` | bool | classe in (F, G) |
| `incomplete_data` | bool | fallback midpoint si DPE manquant |

### `tiles.buildings_centroids_v` / `tiles.buildings_centroids_mv`

Identique au-dessus mais avec `geom = Point` (centroïde) pour zooms 10-13.

### `tiles.commune_passoires_heatmap_v` / `_mv`

Agrégats par commune INSEE pour la vue régionale (zooms 7-9).

| Colonne | Type | Description |
|---|---|---|
| `code_commune_insee` | text | PK |
| `dept` | text | département |
| `geom` | `geometry(Point, 4326)` | centroïde commune |
| `n_buildings` | int | total bâtiments commune |
| `n_passoires` | int | total F+G |
| `pct_passoires` | float | densité % |

---

## 3. Configuration martin

`martin.yaml` (monté en /config.yaml dans le container) :

```yaml
listen_addresses: 0.0.0.0:3000
default_srid: 4326

postgres:
  connection_string: "${DATABASE_URL}"
  auto_publish:
    from_schemas: ["tiles"]
    tables:
      source_id_format: "{table}"
  auto_bounds: skip   # évite le calcul ST_Extent coûteux au démarrage
```

**Note** : la directive `from_schemas` n'est pas strictement respectée dans la
version `latest` actuelle de martin (auto-discovery découvre aussi `public_data.*`).
Le service n'est de toute façon pas exposé publiquement — le backend FastAPI
proxifie les requêtes tuiles avec contrôle d'accès J11+.

---

## 4. Performance

Mesures sur HDF (3.12M bâtiments, ~417k avec DPE réel) :

| Source | Zoom | URL exemple | Latence | Taille |
|---|---|---|---|---|
| commune_passoires_heatmap_mv | 8 | `/commune_passoires_heatmap_mv/8/130/87` | **43 ms** | 40 kB |
| buildings_centroids_v (non-mat.) | 12 | `/buildings_centroids_v/12/2086/1393` | 4.6 s | 134 kB |
| buildings_v (non-mat.) | 14 | `/buildings_v/14/8345/5570` | 17 s | (vide) |

→ La matérialisation avec index GIST est obligatoire pour les couches buildings.
L'objectif brief J5 (< 2s à zoom 8 sur HDF entière) est largement atteint.

---

## 5. Refresh des vues matérialisées

Les MV ne sont pas mises à jour automatiquement. Trois cas de refresh :

1. **Après prédiction massive ML** (J5 phase 2 fin) :
   ```sql
   REFRESH MATERIALIZED VIEW tiles.buildings_mv;
   REFRESH MATERIALIZED VIEW tiles.buildings_centroids_mv;
   REFRESH MATERIALIZED VIEW tiles.commune_passoires_heatmap_mv;
   ```
2. **Après recalcul scoring** (compute_building_scores.py --all) : idem.
3. **Après ré-ingestion BDNB millésime** (rare) : idem + recompute neighborhood.

Pour permettre `REFRESH ... CONCURRENTLY` (refresh sans verrou de lecture),
chaque MV a une **UNIQUE INDEX** sur sa PK.

Script wrapper à créer en J7+ : `scripts/refresh_tiles_matviews.py` (sera lancé dans
J5.15).

---

## 6. Endpoints exposés

À `http://localhost:3000/` :

- `GET /catalog` → liste JSON des sources
- `GET /{source_id}` → metadata tilejson
- `GET /{source_id}/{z}/{x}/{y}` → tuile MVT binaire

URLs principales :
- `/commune_passoires_heatmap_mv/{z}/{x}/{y}` (zooms 7-9)
- `/buildings_centroids_mv/{z}/{x}/{y}` (zooms 10-13)
- `/buildings_mv/{z}/{x}/{y}` (zooms 14+)

---

## 7. Stratégie de rendu côté frontend (J14)

deck.gl `MVTLayer` avec une logique de "zoom switch" :

```ts
const layers = [
  // Zoom 7-9 : heatmap densité passoires par commune
  new MVTLayer({
    id: "heatmap",
    data: `http://localhost:3000/commune_passoires_heatmap_mv/{z}/{x}/{y}`,
    visible: zoom >= 7 && zoom < 10,
    getFillColor: (d) => colorByDensity(d.properties.pct_passoires),
  }),
  // Zoom 10-13 : centroïdes colorés par classe
  new MVTLayer({
    id: "centroids",
    data: `http://localhost:3000/buildings_centroids_mv/{z}/{x}/{y}`,
    visible: zoom >= 10 && zoom < 14,
    getFillColor: (d) => colorByDpeClass(d.properties.classe),
  }),
  // Zoom 14+ : polygones extrudés avec hauteur et score
  new MVTLayer({
    id: "polygons",
    data: `http://localhost:3000/buildings_mv/{z}/{x}/{y}`,
    visible: zoom >= 14,
    extruded: true,
    getElevation: (d) => d.properties.hauteur_m,
    getFillColor: (d) => colorByScore(d.properties.score_total),
  }),
];
```

---

## 8. Fichiers et chemins

```
docker-compose.yml             — service martin (config.yaml monté)
martin.yaml                    — auto-publication tiles.*

scripts/sql/migrations/
  011_create_tiles_views.sql   — vues tiles.{buildings,centroids,heatmap}_v
  012_materialize_tiles.sql    — vues matérialisées + index GIST

scripts/refresh_tiles_matviews.py  — (à créer J5.15) wrapper REFRESH
```

---

## 9. Limites connues

- **Refresh manuel** : pas de trigger automatique. À orchestrer dans J5.15 et J11+.
- **`from_schemas` non strict** dans martin `latest` : toutes les tables `public_data.*`
  sont aussi exposées. Non bloquant (port 3000 non exposé public en prod, backend
  proxifiera avec auth).
- **`is_passoire` calculé à la projection** : si BDNB change l'enum, regenerate vues.
- **Zoom 7-9 heatmap** : utilisé `code_commune_insee` (3 782 communes HDF), pas EPCI
  (à ingérer post-MVP).
- **DPE NULL** : les bâtiments sans dpe_classe ni ml-predicted apparaissent dans
  `buildings_*_v` mais avec `classe=NULL` et `is_passoire=false`. À filtrer côté UI
  pour ne pas polluer la heatmap.

---

## 10. Tests

Tests d'intégration à ajouter en J11 (backend) :
- HTTP GET sur chaque source retourne 200 ou 204.
- Tuiles non-vides en zone urbaine connue (Lille centre).
- Latence p95 < 1s sur zoom 8 heatmap.
