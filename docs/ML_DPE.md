# ConX — ML estimation DPE (J5)

**Statut** : implémenté, **STOP partenaire avant prédiction massive**.
**Auteur** : ConX, 2026-05-22.
**Décisions** : D-006 (déterminisme scoring), **D-017** (stockage dans `public_data.dpe`), **D-018** (Random Forest, split spatial, hyperparamètres), **D-019** (table `building_neighborhood_train`).

---

## Pourquoi un modèle ML ?

Sur les **3 122 513 bâtiments HDF**, seuls **417 353 (13.4 %)** ont un DPE réel ADEME. Les **2 705 160 (86.6 %)** restants sont actuellement scorés avec un **fallback midpoint par typologie**, flagués `incomplete_data = true` et `confidence < 0.4`.

Le ML estime leur classe DPE et leur consommation `kWh ep/m²/an` à partir de leurs **caractéristiques BDNB + voisinage géographique**. L'objectif : passer de 13.4 % de bâtiments avec scoring complet à **100 %**.

---

## Modèle

- **Algorithme** : `RandomForestClassifier` (cible : classe A-G) + `RandomForestRegressor` (cible : `kWh ep/m²/an`), entraînés en parallèle.
- **Hyperparamètres** (D-018, gravés dans `backend/app/ml/train.TrainingConfig`) :
  - `n_estimators=200`
  - `max_depth=15`
  - `n_jobs=-1`
  - `random_state=42`

---

## Features (15)

Listées dans `backend/app/ml/features.py` :

| # | Feature | Source | Type |
|---|---|---|---|
| 1 | `annee_constr` | BDNB `batiment_groupe_ffo_bat` | numeric |
| 2 | `periode_reglementaire` | dérivé de annee_constr | categorical (8 niveaux : `avant_1948`, `1948_1974`, `1974_1982`, `1982_1989`, `1989_2000`, `2000_2012`, `2012_2020`, `post_2020`) |
| 3 | `surface_m2` | BDNB | numeric |
| 4 | `hauteur_m` | BDNB (à crossvalider avec BD TOPO en J5+) | numeric |
| 5 | `nb_logements` | BDNB | numeric |
| 6 | `type_principal` | BDNB normalisé via `normalize_type_principal` | categorical |
| 7 | `materiau_mur` | BDNB normalisé via `normalize_materiau_mur` | categorical (7 buckets : `beton`, `brique`, `pierre`, `bois`, `parpaing`, `metal`, `autre`, `unknown`) |
| 8 | `type_proprietaire` | BDNB | categorical (`bailleur_social`, `personne_morale_privee`, `particulier`) |
| 9 | `monument_historique` | BDNB | boolean |
| 10 | `spr` | BDNB | boolean |
| 11 | `dept` | BDNB | categorical (5 valeurs HDF) |
| 12 | `zone_climatique` | dérivé de dept (`config/zone_climatique_dpt.yaml`) | categorical (`H1a`, `H1b`) |
| 13 | `ecs_individuelle` | `public_data.dpe.type_installation_ecs` (parsing | None autorisé) | boolean / nullable |
| 14 | `neighborhood_dpe_class_mean` | k=20 voisins PostGIS sur centroid, classe ordinale moyenne (1..7) | numeric |
| 15 | `neighborhood_dpe_class_count` | nombre de voisins (typiquement 20) | numeric |

### Encodage
- Catégorielles → one-hot (`pandas.get_dummies`).
- Numerics → tels quels, imputation par médiane sur les NaN.
- Booleans → 1 / 0 / NaN.

---

## Split spatial (anti-fuite)

Brief J5 §3 + D-018 : **OBLIGATOIRE par commune INSEE**.

- 70 % communes en train, 30 % en test.
- `random_state=42` pour reproductibilité.
- Test invariant `test_spatial_split_no_overlap` : aucune commune en commun entre train et test. Si violation → `RuntimeError`.

**Pourquoi spatial et pas aléatoire ?** La feature `neighborhood_dpe_class_mean` introduit une autocorrélation spatiale forte. Un split aléatoire ferait que des bâtiments du test seraient voisins de bâtiments du train → le modèle "verrait" indirectement les labels du test via leur voisinage. Le split spatial simule le cas réel : prédire dans une commune où le modèle n'a pas vu ce voisinage particulier.

---

## Métriques (brief J5 §4)

Calculées sur le hold-out spatial.

| Métrique | Calcul | Seuil acceptation |
|---|---|---|
| **Accuracy ±1 classe** | Fraction des prédictions à ≤ 1 classe d'écart (ordinal A=1..G=7) | **≥ 75 % objectif** ; 60-75 % acceptable avec avertissement ; < 60 % ne pas déployer |
| Accuracy stricte | Fraction des prédictions classe exacte | reportée pour information |
| MAE consommation | `mean_absolute_error(y_kwh_true, y_kwh_pred)` en kWh ep/m²/an | reportée pour information |
| Matrice de confusion | 7 x 7 (A..G real | A..G predicted) | analyse qualitative |

---

## Anomalies (brief J5 §5)

4 règles déterministes appliquées à chaque prédiction. Si une règle se déclenche, on garde la prédiction mais on flag.

| Règle | Trigger | Flag |
|---|---|---|
| **RT2012 attendue** | Bâtiment post-2012 prédit en F ou G | `anomaly_rt2012_unexpected` |
| **RE2020 attendue** | Bâtiment post-2020 prédit en E, F ou G | `anomaly_re2020_unexpected` |
| **Incohérence PAC** | Prédiction F ou G mais pompe à chaleur identifiée (BDNB) | `anomaly_pac_low_class` |
| **Écart voisinage** | Écart > 3 classes vs `neighborhood_dpe_class_mean` arrondi | `anomaly_neighborhood_outlier` |

Stockage : colonnes booléennes dans `public_data.dpe` (cf. migration 010).

UI : badge rouge supplémentaire "Anomalie — écart inhabituel".

---

## Garde-fous (brief J5 §8)

- Écrêtage de `kWh ep/m²/an` à `[0, 800]`. Si en dehors, on remplace par la borne et on flag `clipped=true`.
- **PAS** de clamp dur sur la classe DPE (un bâtiment récent mal isolé peut légitimement être G — la règle d'anomalie le détecte mais ne le réécrit pas).
- `model_version` (hash sha256-8 du `.pkl`) systématique dans `dpe.model_version`.

---

## Affichage UI (brief J5 §6)

Pour chaque bâtiment :

- **DPE réel** (source `ademe-real`) : badge vert *"DPE certifié — diagnostic n°XXX du JJ/MM/AAAA"*.
- **DPE estimé** (source `ml-predicted`) :
  - Accuracy globale ≥ 75 % ET confidence ≥ 0.7 : badge orange *"DPE estimé par IA — classe E probable (confiance 78 %, fourchette D-F) — un diagnostic réel est nécessaire avant travaux"*.
  - 60 % ≤ accuracy < 75 % OU confidence < 0.7 : badge orange + mention "fiabilité moyenne" plus visible.
  - Anomalie détectée : badge rouge supplémentaire.
  - Accuracy globale < 60 % : pas d'affichage de la classe, juste *"DPE inconnu — diagnostic réel requis"*.

---

## Intervalle de confiance par prédiction (brief J5 §7)

Pour chaque bâtiment prédit :

- `classe_predicted` (argmax `predict_proba`)
- `confidence` (probabilité de cette classe)
- `predicted_classes_top3` : 3 classes les plus probables (text[] dans la table dpe), donne la fourchette pour l'UI

Pour la régression `kWh ep/m²/an` : intervalle bootstrap sur les arbres individuels (quantiles 10/90 via `np.percentile` sur `estimator.predict(X)` pour chaque arbre du forêt).

---

## Pipeline

```
seed/                          (one-shot, hors-ML)
  ├─ 5 dpts BDNB → buildings (3.12M)
  └─ DPE réel BDNB → dpe (435 987 rows, source='ademe-real')

ml/                            (J5)
  ├─ scripts/train_dpe_ml.py
  │   ├─ compute_neighborhood_table  (15-30 min, table dédiée)
  │   ├─ load_training_dataframe     (417k rows)
  │   ├─ spatial_split 70/30 par commune INSEE
  │   ├─ encode_features              (one-hot, fillna)
  │   ├─ fit RandomForestClassifier + RandomForestRegressor
  │   ├─ evaluate → 4 metrics + confusion matrix
  │   └─ save_models → data/storage/ml/dpe_estimator_<sha8>.pkl + .json
  │
  │   ⛔ STOP — validation partenaire des métriques
  │
  ├─ scripts/predict_dpe_ml.py        (à activer post-validation)
  │   ├─ load_model
  │   ├─ predict pour les 2.7M sans DPE
  │   ├─ apply 4 règles d'anomalie
  │   ├─ écrêtage + insert dpe (source='ml-predicted')
  │   └─ UPDATE buildings.dpe_classe + dpe_source
  │
  └─ scripts/compute_building_scores.py --all (re-batch)
      → 100 % des bâtiments avec scoring complet
```

---

## Tests d'invariants (brief J5 §10)

| Test | Fichier | Vérifie |
|---|---|---|
| `test_spatial_split_no_overlap` | `backend/tests/test_dpe_ml.py` | aucune commune en commun train/test |
| `test_encode_features_train_test_alignment` | idem | les colonnes du test sont les mêmes que train |
| `test_periode_reglementaire` | idem | bornes RT/RE correctes |
| `test_classe_to_ordinal_and_back` | idem | encodage classe ↔ ordinal stable |
| `test_accuracy_within_n_classes` | idem | métrique calculée correctement |
| `test_training_config_defaults` | idem | hyperparamètres gravés conformes |

Tests à ajouter post-validation (J5 §10) :
- Test couverture : tous les bâtiments avec données suffisantes ont une prédiction.
- Test cohérence : aucun DPE réel écrasé par prédiction.
- Test anomalies : sur 100 échantillons, validation manuelle.
- Test idempotence : relancer 2× ne crée pas de doublons.

---

## Réentraîner

```bash
# Force le recalcul du neighborhood
docker exec ... psql -c "DROP TABLE public_data.building_neighborhood_train;"

# Si tu changes les hyperparamètres ou les features, modifie aussi DECISIONS.md (D-018).
python scripts/train_dpe_ml.py

# Quick test (debug, 50k subsample — NE PAS UTILISER en prod) :
python scripts/train_dpe_ml.py --quick

# Skip neighborhood (déjà calculé) :
python scripts/train_dpe_ml.py --skip-neighborhood
```

---

## Limites connues

- **15 features seulement** : on n'utilise pas tout BDNB (~400 attributs). Features ajoutables en J5+ : matériaux toiture, type isolation murs, nombre niveaux, etc.
- **`hauteur_m` BDNB only** : crossvalidation avec BD TOPO en J5+ (table `topo_buildings` dispo depuis Session 5).
- **Zone climatique grossière** : un par dpt. Raffinement par commune INSEE possible si nécessaire.
- **Pas de balancing des classes** : si la distribution F/G est très minoritaire vs C/D, le modèle peut sous-prédire F/G. À analyser dans la matrice de confusion.
- **Train et prédiction sur les MÊMES communes** : pour la prédiction massive, les communes du train ET du test reçoivent des prédictions. Pas de re-split.
