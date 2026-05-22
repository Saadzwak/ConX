# ConX — Pipeline LiDAR HD (J8)

**Statut** : infrastructure créée, scripts paramétrables, **STUB pipeline mesh
glTF** (à finaliser en J15 avec pré-génération hors-ligne des 5-10 bâtiments démo).
**Dernière mise à jour** : 2026-05-22.
**Décisions liées** : D-008 (LiDAR à la demande + pré-gen démo).

---

## 1. Stratégie d'ensemble (D-008)

Plan §2.4 et §3.4 : on **ne télécharge PAS toute la couverture LiDAR HD HDF**
(plusieurs To de LAZ). À la place :

- **Pour la grande majorité des bâtiments HDF** : extrusion BD TOPO (emprise + hauteur)
  suffit pour la vue Stratégie. C'est ce que sert `tiles.buildings_mv` à zoom 14+.
- **Pour 5-10 bâtiments vedettes de la démo** (Wazemmes, Vauban, Lens centre,
  Amiens centre…) : **pré-télécharger** les dalles LAZ + générer les meshes glTF.
- **Pour les autres bâtiments** : téléchargement et conversion **à la demande**
  via job async backend ("préparation 3D — 1-2 min"). Cache permanent sur disque.

Storage : `./data/storage/lidar/<dalle_name>.copc.laz` + `<dalle_name>.gltf`.

Index PostGIS : `public_data.lidar_tiles` (emprise 2154) + `public_data.building_lidar`
(association bâtiment ↔ dalle ↔ mesh).

---

## 2. Source IGN

- **Catalogue** : https://geoservices.ign.fr/lidarhd
- **Carte couverture** : https://macarte.ign.fr/carte/lidar-hd
- **Format dalle** : COPC LAZ (Cloud-Optimized Point Cloud), 1 km × 1 km en
  Lambert-93. Nom : `LHD_FXX_<XKM>_<YKM>_PTS_C_LAMB93_IGN69.copc.laz`.
- **Volumétrie** : 100 MB – 2 GB par dalle (densité variable).
- **Licence** : Etalab 2.0.

**Couverture HDF** (à confirmer au moment du téléchargement) :
- Nord (59) ✅ couvert depuis 2024
- Pas-de-Calais (62) ✅ couvert depuis 2024
- Aisne (02), Oise (60), Somme (80) : à vérifier sur macarte.ign.fr — IGN livre
  progressivement 2021-2026.

---

## 3. Schéma DB (migration 013)

```sql
public_data.lidar_tiles
  (id, dalle_name UNIQUE, emprise geometry(Polygon, 2154), millesime, dept,
   laz_path_local, laz_size_bytes, laz_downloaded_at,
   gltf_path_local, gltf_generated_at, ign_url, notes)
  INDEX GIST(emprise), INDEX(dept)

public_data.building_lidar
  (building_id FK, lidar_tile_id FK, gltf_path_local, gltf_size_bytes, gltf_generated_at)
  PK (building_id, lidar_tile_id)
```

---

## 4. Scripts

### 4.1 `scripts/download_lidar.sh` (paramétrable, prêt)

```bash
# Pour un bâtiment précis (détermine la dalle via PostGIS centroid)
scripts/download_lidar.sh <building_id>

# Pour une dalle nommée explicitement
scripts/download_lidar.sh --dalle LHD_FXX_0700_7050_PTS_C_LAMB93_IGN69

# Pour une bbox Lambert-93
scripts/download_lidar.sh --bbox 700000,7050000,701000,7051000
```

Téléchargement reprenable via `curl -C -`. Indexe automatiquement dans
`public_data.lidar_tiles`.

### 4.2 `scripts/lidar_to_gltf.py` (STUB structurel)

```bash
# Vérifier que PDAL Docker est dispo
python scripts/lidar_to_gltf.py --check-only

# Convertir une dalle entière en mesh glTF
python scripts/lidar_to_gltf.py --dalle LHD_FXX_0700_7050_PTS_C_LAMB93_IGN69
```

Utilise `docker run pdal/pdal:latest` pour exécuter le pipeline PDAL
(filtre classification=6 building + triangulation Poisson) puis `trimesh` pour
l'export glTF.

**État actuel** : structure prête, le pipeline finalise à exécuter en J15 hors-ligne
(prend du temps + besoin d'une machine confortable). Le mode `--building <id>` (crop
sur emprise) est marqué TODO.

---

## 5. Workflow J15 hors-ligne pour la démo

À exécuter sur la machine partenaire **avant le pitch jury** :

```bash
# 1. Choisir 5-10 bâtiments vedettes représentatifs (typologie + dpt)
BUILDINGS=(
  "bdnb-bg-XXX-WAZEMMES-1"     # Lille Wazemmes — collectif F
  "bdnb-bg-XXX-VAUBAN-1"       # Lille Vauban — collectif G social
  "bdnb-bg-XXX-LENS-1"         # Lens centre — collectif F
  "bdnb-bg-XXX-AMIENS-1"       # Amiens centre — collectif tertiaire
  # …
)

# 2. Pour chaque bâtiment : télécharger la dalle + convertir
for bid in "${BUILDINGS[@]}"; do
  scripts/download_lidar.sh "$bid"
  python scripts/lidar_to_gltf.py --building "$bid"
done

# 3. Verify
docker exec conx_postgres psql -U conx -d conx -c "
  SELECT building_id, gltf_path_local, gltf_size_bytes
  FROM public_data.building_lidar
  ORDER BY building_id;
"
```

Les `.gltf` se retrouvent dans `./data/storage/lidar/<dalle>/<building_id>.gltf` et
seront servis par FastAPI route `GET /api/lidar/mesh/<building_id>.gltf` (J15).

---

## 6. Limites et alternatives

- **PDAL pas trivial à installer nativement** : on passe par `docker run pdal/pdal:latest`.
  Si le réseau corp interdit Docker Hub, télécharger l'image en local et `docker save`.
- **Triangulation Poisson lente** : ~30-90 s par dalle. Greedy plus rapide mais meshes
  moins propres.
- **Cropping bâtiment** : nécessite une query PostGIS pour récupérer la bbox du bâtiment,
  puis `filters.crop` PDAL avec la polygon WKT. À finaliser en J15.
- **Texture aérienne** : on peut texturer le mesh avec BD Ortho via UV mapping. Hors
  scope J8 — finalisation J15+ si le temps.
- **Pas de COPC streaming** : on télécharge la dalle entière, pas du streaming partiel
  par octree. Acceptable pour 5-10 bâtiments. Sinon `lazperf` + serveur de tiles 3D.

---

## 7. Fallback si pas de LiDAR HD pour un dpt

Pour les dpts non couverts (potentiellement 02/60/80 selon état IGN au moment T) :

- **Mode Stratégie zoom 14+** : extrusion BD TOPO (déjà fonctionnel via
  `tiles.buildings_mv.hauteur_m`). Visuellement crédible.
- **Mode Projet** : afficher un avertissement "LiDAR HD non disponible pour ce
  département — visualisation BD TOPO + photo aérienne uniquement". Pas de mesh
  détaillé.

---

## 8. Fichiers et chemins

```
scripts/sql/migrations/013_lidar_tiles.sql  — table d'index PostGIS

scripts/
  download_lidar.sh           — wrapper curl + insert lidar_tiles
  lidar_to_gltf.py            — pipeline PDAL → glTF (stub J8, finalisation J15)

data/storage/lidar/
  <dalle>.copc.laz            — LAZ téléchargé
  <dalle>.gltf                — mesh global
  <dalle>/<building_id>.gltf  — mesh cropped sur bâtiment (J15)
```

---

## 9. Tests d'intégration

À ajouter en J15 :
- `test_download_lidar_indexes_table` : après download, ligne dans `lidar_tiles`.
- `test_lidar_to_gltf_generates_mesh` : conversion produit un .gltf valide non-vide.
- `test_building_lidar_association` : crop génère bien une ligne `building_lidar`.

Pour cette nuit J8 : pas de test (stub). Les scripts sont paramétrables et documentés.
