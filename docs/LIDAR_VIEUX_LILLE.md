# ConX — LiDAR HD IGN sur Vieux-Lille (J15 pré-démo)

## TL;DR

LiDAR HD dpt 59 est en **open data Etalab depuis 2024** (premier dpt livré
avec le 62). Vieux-Lille est couvert. **4 dalles 1 km × 1 km** à télécharger.

---

## 1. Dalles IGN LiDAR HD couvrant le bbox Vieux-Lille

Bbox VL (Lambert-93) : (704038, 7060340) → (705314, 7061678).

Conventions IGN : dalle `LIDARHD_FXX-2024-EEEE_NNNN_LA93_IGN69.copc.laz` où
`EEEE_NNNN` = coin sud-ouest en km. Une dalle couvre 1 km × 1 km.

| Dalle | Coin SO (Lambert-93) | Couvre la portion |
|---|---|---|
| `0704_7060` | (704000, 7060000) | sud-ouest VL (Grand-Place, Vieille Bourse) |
| `0704_7061` | (704000, 7061000) | nord-ouest VL (Esplanade, Citadelle bord) |
| `0705_7060` | (705000, 7060000) | sud-est VL (Quartier Royal) |
| `0705_7061` | (705000, 7061000) | nord-est VL (Magasin, Réduit) |

Taille estimée par dalle : 400-800 Mo en COPC LAZ (classifié sol/bâti/végé).
**Total ~2-3 Go** pour les 4 dalles.

---

## 2. Téléchargement

URL Etalab Géoservices (depuis fin 2024) :
```
https://geopf.fr/telechargement/download/lidarhd/?dalle=<EEEE_NNNN>
```

⚠ Pas testé contre l'API en mode CLI — l'IGN reformatait régulièrement ces
URLs en 2024-2025. **Recommandation au partenaire** :

1. Aller sur https://geoservices.ign.fr/lidarhd → carte interactive
2. Sélectionner le bbox Vieux-Lille
3. Télécharger les 4 dalles ci-dessus en LAZ
4. Déposer dans `./data/storage/lidar/vieux_lille/`

Ensuite, lancer la conversion glTF :
```bash
python scripts/lidar_to_gltf.py \
  --laz-dir ./data/storage/lidar/vieux_lille \
  --output ./data/storage/gltf/vieux_lille \
  --bbox-2154 704038 7060340 705314 7061678
```

(Script J8 stub à compléter en J15.)

---

## 3. Mesh glTF pour les 5-10 bâtiments démo

Pour les 3 candidats principaux du pitch :
- `bdnb-bg-NKGA-DUZ2-J28H` (Grand-Place vicinity)
- `bdnb-bg-JBP7-PFQL-4T69` (Vieux-Lille centre)
- `bdnb-bg-7F6X-1AGX-L22Q` (collectif R+4)

Plus 2-3 bâtiments d'arrière-plan pour le narratif zoom. Total ~5-8 meshes
glTF à pré-générer.

---

## 4. Limites

- L'URL Etalab/Geopf bouge. Le partenaire valide manuellement le
  téléchargement avant la démo.
- COPC LAZ → glTF nécessite PDAL + Open3D ou trimesh — voir `scripts/
  lidar_to_gltf.py` (stub J8).
- Fallback démo : si LiDAR non chargé à temps, on garde la vue extrudée
  BDNB (`hauteur_m` × emprise) qui reste visuellement crédible.

---

## 5. Statut

| Étape | Statut |
|---|---|
| Identifier dalles | ✅ 4 dalles (0704_7060/7061, 0705_7060/7061) |
| Vérifier disponibilité Etalab | ✅ dpt 59 en open data depuis 2024 |
| Télécharger LAZ | ⏳ action partenaire (cf. §2) |
| Convertir glTF | ⏳ J15 |
| Tester rendu Three.js | ⏳ J15 |
