# Audit d'inventaire des données bâtiment — ConX

**Date** : 2026-05-23 · **Bâtiment de référence** : Wazemmes `bdnb-bg-81UB-UTZE-ZP7F` (RNB `2D9YFEZTSAC9`, bailleur social R+3 1978, F, 48 logts, 1 084 m² emprise, 3 038 m² SHAB).

**But** : recenser exhaustivement les données disponibles côté ConX avant d'enrichir la fiche bâtiment (BuildingDrawer Mode Stratégie + fiche détaillée 460 px Mode Projet). **Aucun code modifié**, juste un état des lieux pour arbitrage produit.

---

## Section 1 — Ce qui est actuellement affiché

### 1.A — BuildingDrawer (Mode Stratégie, sidebar droite 384 px = `w-96`)

Composant : `frontend/src/components/BuildingDrawer.tsx`. Source de données : `BuildingListItem` issu de `/api/buildings` (liste).

| Label UI | Clé API | Composant / ligne |
|---|---|---|
| Département (`Dpt 59`) | `dept` | L31 |
| Building ID | `building_id` | L32 |
| RNB ID | `rnb_id` | L34 |
| Score ConX (X/100) | `score_total × 100` | L56 |
| Classe DPE (lettre dans tuile colorée) | `dpe_classe` | L52 |
| Badge DPE réel / estimé IA | `dpe_source` | L61 |
| Surface | `surface_m2` | L66 |
| Hauteur ⚠ | `hauteur_m` | L67 |
| Logements | `nb_logements` | L68 |
| Année | `annee_constr` | L71 |
| Type | `type_principal` | L73 |
| Propriétaire | `type_proprietaire` | L74 |
| Consommation (kWh ep/m²/an) ⚠ | `dpe_kwh_ep_m2_an` | L82 |
| Coefficient EP électricité (texte fixe 1.9) | — | L85 |
| Score CO₂ évité (barre) | `s_co2` | L92 |
| Score Faisabilité (barre) | `s_faisa` | L93 |
| Score Coût (barre) | `s_cout` | L94 |
| Score Social (barre) | `s_social` | L95 |
| Score Passoire (barre) | `s_passoire` | L96 |
| CO₂ évité (30 ans) | `co2_evite_t` | L103 |
| Coût estimé | `cout_estime_eur` | L107 |
| ⚠ Monument Historique BDNB | `monument_historique` | L110 |
| Lien Mode Projet | — | L122 |
| Lien externe RNB | `rnb_id` | L129 |

> **⚠ Bug latent #1** : les champs `hauteur_m`, `dpe_kwh_ep_m2_an`, `monument_historique` ne sont PAS retournés par `/api/buildings` (cf. `BuildingListItem` Pydantic backend, `backend/app/routers/buildings.py` L54-74). Ils affichent donc `—` dans le drawer. À corriger lors de l'enrichissement (un simple `bs` join + ajout au `SELECT` + ajout au modèle Pydantic).

### 1.B — Fiche détaillée Mode Projet (sidebar droite 460 px = `w-[460px]`)

Composant : `frontend/src/pages/Projet.tsx`. Source de données : `BuildingDetail` issu de `/api/buildings/:id`.

| Label UI | Clé API | Composant / ligne |
|---|---|---|
| Département + IRIS | `dept`, `code_iris` | L121 |
| Tuile lettre DPE colorée | `dpe_classe` | L127 |
| Building ID | `building_id` | L131 |
| RNB ID | `rnb_id` | L132 |
| Score ConX (X/100) ⚠ | `score_total` (cassé) | L135 |
| Badge DPE réel / estimé IA | `dpe_source` | L141 |
| Surface | `surface_m2` | L159 |
| Hauteur | `hauteur_m` | L160 |
| Logements | `nb_logements` | L161 |
| Année | `annee_constr` | L162 |
| Type | `type_principal` | L163 |
| Période construction | `periode_construction` | L164 |
| Matériau mur | `materiau_mur` | L165 |
| Propriétaire | `type_proprietaire` | L166 |
| Consommation | `dpe_kwh_ep_m2_an` | L174-176 |
| Émissions | `dpe_kg_co2_m2_an` | L178-180 |
| Coefficient EP électricité | `dpe_coefficient_ep_electricite` | L184 |
| Score CO₂ évité (barre) ⚠ | `s_co2` (cassé) | L195 |
| Score Faisabilité (barre) ⚠ | `s_faisa` (cassé) | L196 |
| Score Coût (barre) ⚠ | `s_cout` (cassé) | L197 |
| Score Social (barre) ⚠ | `s_social` (cassé) | L198 |
| Score Passoire (barre) ⚠ | `s_passoire` (cassé) | L199 |
| CO₂ évité (30 ans) ⚠ | `co2_evite_t` (cassé) | L207 |
| Coût estimé ⚠ | `cout_estime_eur` (cassé) | L211 |
| ⚠ Monument Historique | `monument_historique` | L222 |
| ⚠ SPR | `spr` | L223 |
| Footer méthodologie | `bdnb_millesime` (manquant) | L233 |

> **⚠ Bug latent #2** : l'API `/api/buildings/:id` **niche** les composantes scoring dans un objet `score` (cf. `BuildingDetail.score: dict[str, Any]`). Côté frontend, `BuildingDetail extends BuildingListItem` qui les attend à plat → tous les champs `score_total`, `s_*`, `co2_evite_t`, `cout_estime_eur` sont **`undefined`** dans `building.<field>`. Affichage final : score = `0/100`, barres à 0, CO₂ évité `—`. Le bon accès serait `building.score?.s_co2` etc. À corriger lors de l'enrichissement (soit en aplatissant côté API, soit en lisant `score.*` côté frontend).
>
> Ce bug n'apparaît pas sur le drawer Stratégie car les scoring sont déjà à plat dans `/api/buildings` (liste).

> **⚠ Bug latent #3** : `bdnb_millesime` est utilisé en L233 du footer mais n'est jamais renvoyé par `/api/buildings/:id` (absent du modèle Pydantic). Affichage final : "BDNB CSTB undefined".

---

## Section 2 — Ce que l'API `/api/buildings/:id` retourne aujourd'hui

Endpoint : `GET /api/buildings/:id`, défini dans `backend/app/routers/buildings.py` L405-481. Modèle Pydantic `BuildingDetail` L337-364.

Réponse réelle pour Wazemmes (capture du 2026-05-23, geom tronqué) :

| Clé API | Type | Valeur Wazemmes | Source | Affiché ? |
|---|---|---|---|---|
| `building_id` | str | `bdnb-bg-81UB-UTZE-ZP7F` | BDNB | ✅ Drawer + Fiche |
| `rnb_id` | str\|null | `2D9YFEZTSAC9` | BDNB | ✅ |
| `dept` | str | `59` | BDNB | ✅ |
| `code_commune_insee` | str\|null | `59350` | BDNB | ❌ Non utilisé |
| `code_iris` | str\|null | `593500402` | BDNB | ✅ Fiche (L121) |
| `surface_m2` | float\|null | `1084.0` | BDNB (= emprise au sol) | ✅ |
| `hauteur_m` | float\|null | `11.0` | BDNB / BD TOPO | ✅ Fiche, ⚠ Drawer cassé |
| `nb_logements` | int\|null | `48` | BDNB | ✅ |
| `annee_constr` | int\|null | `1978` | BDNB | ✅ |
| `periode_construction` | str\|null | `1975-1981` | BDNB | ✅ Fiche |
| `type_principal` | str\|null | `Résidentiel collectif` | BDNB | ✅ |
| `materiau_mur` | str\|null | `BETON` | BDNB | ✅ Fiche |
| `type_proprietaire` | str\|null | `bailleur_social` | BDNB | ✅ |
| `monument_historique` | bool | `false` | BDNB / Mérimée | ✅ |
| `spr` | bool | `false` | BDNB | ✅ Fiche |
| `dpe_classe` | str\|null | `F` | DPE ADEME (via BDNB) | ✅ |
| `dpe_kwh_ep_m2_an` | float\|null | `324.0` | DPE ADEME | ✅ |
| `dpe_kg_co2_m2_an` | float\|null | `71.0` | DPE ADEME | ✅ Fiche |
| `dpe_coefficient_ep_electricite` | float | `1.9` | Réforme 2026 | ✅ |
| `dpe_source` | str\|null | `ademe-real` | calculé | ✅ (badge) |
| `geom_geojson` | object | MultiPolygon EPSG:4326 (1 ring, 60+ vertices) | BDNB | ✅ Carte 3D Projet uniquement |
| `centroid_lon` | float | `3.046703133419712` | BDNB | ❌ Non affiché (utilisé pour map) |
| `centroid_lat` | float | `50.624350301368295` | BDNB | ❌ |
| `score` | object\|null | (voir détail ci-dessous) | calculé | ⚠ Fiche cassée |
| `neighbors` | array | 5 voisins (DPE A, E, D, C, D à 33-58 m) | calculé (KNN PostGIS) | ❌ **Non affiché du tout** |

### 2.A — Détail de l'objet `score` (15 sous-clés)

| Sous-clé | Type | Valeur Wazemmes | Affiché ? |
|---|---|---|---|
| `score.s_co2` | float | `1.0` | ⚠ Fiche cassée |
| `score.s_faisa` | float | `0.845` | ⚠ Fiche cassée |
| `score.s_cout` | float | `1.0` | ⚠ Fiche cassée |
| `score.s_social` | float | `1.0` | ⚠ Fiche cassée |
| `score.s_passoire` | float | `1.0` | ⚠ Fiche cassée |
| `score.co2_evite_t` | float | `1727.39736` | ⚠ Fiche cassée |
| `score.cout_estime_eur` | float | `650400.0` | ⚠ Fiche cassée |
| `score.cout_eur_par_t_co2` | float\|null | `376.52` | ❌ **Non affiché** |
| `score.confidence` | float | `1.0` | ❌ **Non affiché** |
| `score.dpe_source` | str | `ademe-real` | ✅ (déjà à plat) |
| `score.thresholds_version` | str | `6605264c05ce` | ❌ Non affiché |
| `score.incomplete_data` | bool | `false` | ❌ **Non affiché** (utile pour disclaimer) |
| `score.s_faisa_partial` | bool | `false` | ❌ Non affiché |
| `score.missing_fields` | array | `[]` | ❌ Non affiché |
| `score.computed_at` | iso8601 | `2026-05-21T20:48:07Z` | ❌ Non affiché (transparence) |

> ⚠ Côté Stratégie (liste), il manque `score_total` calculé à la volée — la fiche ne l'expose pas du tout, alors que c'est la première métrique attendue par l'utilisateur. **Marge d'enrichissement gratuite** : ajouter `score_total` au modèle Pydantic + au SQL_DETAIL en réutilisant la même formule pondérée.

### 2.B — Champs `neighbors` (déjà calculé, non affiché)

5 voisins KNN à ≤ 200 m de centroide :

| building_id | dpe_classe | distance_m |
|---|---|---|
| `bdnb-bg-EF7U-RPV1-DFZE` | A | 33.7 |
| `bdnb-bg-X92J-R6MV-A5GP` | E | 46.5 |
| `bdnb-bg-WTKV-RZ7Q-T89Y` | D | 50.5 |
| `bdnb-bg-E2E8-SW1W-BC51` | C | 54.9 |
| `bdnb-bg-GMPT-GWBZ-6XM1` | D | 58.0 |

**Marge d'enrichissement gratuite** : ajouter un widget "Bâtiments voisins" sur la fiche (mini-tableau avec lettres DPE colorées + distance). Le narratif IA peut s'en servir (~"vos voisins sont déjà mieux classés que vous").

---

## Section 3 — Ce qui est dans `public_data.building_scores` mais pas exposé par l'API

**Conclusion** : **rien**. Les 16 colonnes de `building_scores` sont toutes exposées par l'API via le top-level (`dpe_source`) ou nichées dans `score`. Pas de marge d'enrichissement directe ici.

Schéma rappel :
```
building_id text PK FK
s_co2, s_faisa, s_cout, s_social, s_passoire    numeric [0,1] NOT NULL
co2_evite_t, cout_estime_eur                    numeric NOT NULL
cout_eur_par_t_co2                              numeric (peut être null)
confidence                                      numeric [0,1] NOT NULL
dpe_source                                      text NOT NULL ('ademe-real'|'ml-predicted')
thresholds_version                              text NOT NULL
incomplete_data, s_faisa_partial                bool NOT NULL
missing_fields                                  text[]
computed_at                                     timestamptz
```

> **Marge réelle** : exposition côté frontend uniquement (la donnée est dans la réponse mais ignorée par l'UI). Cf. Section 2.A.

---

## Section 4 — Ce qui est dans les tables BDNB sources mais **pas** dans `building_scores`

La BDNB millésime 2025-07.a a été ingérée dans les schémas `bdnb_2025_07_a_open_data_dep{02,59,60,62,80}`. 56 tables par dpt, dont **24 contiennent une (ou plusieurs) lignes pour Wazemmes**.

Détail table par table avec valeurs réelles Wazemmes (interrogé via `SELECT` direct sur `dep59`).

### 4.1 — `batiment_groupe_dpe_representatif_logement` ⭐ TRÉSOR PRINCIPAL

Le DPE détaillé d'un logement représentatif du groupe. Identifiant DPE officiel ADEME + tous les paramètres physiques.

| Colonne BDNB | Valeur Wazemmes | Signification |
|---|---|---|
| `identifiant_dpe` | `2259E0904747H` | Identifiant officiel ADEME (lien profond observatoire DPE) |
| `arrete_2021` | `true` | DPE nouvelle génération |
| `type_batiment_dpe` | `appartement` | Granularité du DPE (logt vs immeuble) |
| `surface_habitable_immeuble` | `3038` | SHAB cumulée 48 logts (vs 1084 m² emprise au sol) |
| `surface_habitable_logement` | `81` | Logement représentatif moyen |
| `nombre_niveau_logement` | `1` | Logt en plain-pied |
| `conso_5_usages_ep_m2` | `324` | Conso EP (déjà exposé via `dpe_kwh_ep_m2_an`) |
| `conso_5_usages_ef_m2` | `319` | **Conso ÉNERGIE FINALE** (≠ EP) — utile pour le coût |
| `emission_ges_5_usages_m2` | `71` | Émissions (déjà exposé via `dpe_kg_co2_m2_an`) |
| `classe_emission_ges` | `F` | Classe GES distincte de la classe énergie |
| `type_installation_chauffage` | `collectif` | **Confirme chauffage collectif** |
| `type_energie_chauffage` | `gaz` | **Confirme énergie gaz** |
| `type_generateur_chauffage` | `chaudiere gaz standard` | Précision technique |
| `type_generateur_chauffage_anciennete` | `très ancien` | **Très ancien → bonne cible substitution** |
| `chauffage_solaire` | `false` | Pas de solaire |
| `type_installation_ecs` | `collectif` | ECS collective |
| `type_energie_ecs` | `gaz` | ECS gaz aussi |
| `type_generateur_ecs` | `chaudiere gaz standard` | — |
| `type_generateur_ecs_anciennete` | `très ancien` | — |
| `ecs_solaire` | `false` | — |
| `type_ventilation` | `Ventilation par ouverture des fenêtres` | **AUCUNE VMC** (énorme cible rénovation) |
| `type_production_energie_renouvelable` | `null` | Pas d'EnR |
| `type_vitrage` | `double vitrage` | Déjà rénové côté menuiseries |
| `type_materiaux_menuiserie` | `pvc` | — |
| `type_gaz_lame` | `argon ou krypton` | Vitrage relativement performant |
| `vitrage_vir` | `true` | Vitrage isolant renforcé |
| `epaisseur_lame` | `16` mm | — |
| `uw` | `1.4` | Uw menuiseries (DV correct) |
| `facteur_solaire_baie_vitree` | `0.38` | — |
| `surface_vitree_nord` | `2.17` | m² par orientation |
| `surface_vitree_ouest` | `13.07` | (orientations nord et ouest dominantes) |
| `l_orientation_baie_vitree` | `[nord, ouest]` | — |
| `pourcentage_surface_baie_vitree_exterieur` | `0.214` | 21 % de la façade vitrée |
| `traversant` | `est ouest` | Bâtiment traversant |
| `type_isolation_mur_exterieur` | `inconnu` | **PAS D'ITE** (cible n°1) |
| `epaisseur_isolation_mur_exterieur_estim` | `0` | Confirmé 0 mm |
| `materiaux_structure_mur_exterieur` | `murs en béton banché` | Confirme support |
| `epaisseur_structure_mur_exterieur` | `20.0` cm | Béton banché 20 cm |
| `surface_mur_totale` | `108` m² | Surface murs |
| `surface_mur_exterieur` | `54` m² | — |
| `surface_mur_deperditif` | `60` m² | — |
| `u_mur_exterieur` | `1.0` W/m²K | **U_mur = 1.0 — catastrophique** |
| `l_orientation_mur_exterieur` | `[nord, ouest]` | — |
| `type_isolation_plancher_bas` | `inconnu` | **PAS ISOLÉ** |
| `type_plancher_bas_deperditif` | `dalle béton` | — |
| `surface_plancher_bas_deperditif` | `81` m² | — |
| `u_plancher_bas_final_deperditif` | `0.44` | — |
| `u_plancher_bas_brut_deperditif` | `0.9` | (avant prise en compte du terre-plein) |
| `type_adjacence_principal_plancher_bas` | `terre-plein` | Adjacence |
| `type_isolation_plancher_haut` | `inconnu` | **PAS ISOLÉ** (toit) |
| `type_plancher_haut_deperditif` | `dalle béton` | — |
| `u_plancher_haut_deperditif` | `0.5` | — |
| `type_adjacence_principal_plancher_haut` | `extérieur` | = toiture-terrasse |
| `type_porte` | `porte simple en métal porte opaque pleine` | — |
| `surface_porte` | `1.81` m² | — |
| `u_porte` | `5.8` | **U_porte = 5.8 — catastrophique** |
| `classe_inertie` | `Légère` | — |
| `deperdition_mur` | `55.2` | W/K (poste 1) |
| `deperdition_plancher_haut` | `40.5` | W/K (poste 2) |
| `deperdition_plancher_bas` | `35.64` | W/K |
| `deperdition_baie_vitree` | `21.34` | W/K |
| `deperdition_porte` | `2.10` | W/K |
| `date_etablissement_dpe` | `2022-04-27` | — |
| `date_reception_dpe` | `2022-04-28` | — |
| `version` | `2.1` | Version DPE |

**Marge d'enrichissement** : section "Diagnostic technique" dans la fiche (Uw, U_mur, U_plancher, type_chauffage, type_ventilation, déperditions par poste). Ces données justifient le plan IA et permettent au jury de creuser : "pourquoi prioriser l'ITE ? regardez U_mur=1.0".

### 4.2 — `batiment_groupe_rpls` ⭐ NARRATIF BAILLEUR SOCIAL

| Colonne | Valeur Wazemmes | Signification |
|---|---|---|
| `rpls_open` | `true` | **Confirmé bailleur social via RPLS officiel** (≠ déduction BDNB) |
| `nb_log` | `48` | — |
| `s_log_hab` | `3038` | SHAB cumulée |
| `type_construction` | `["Collectif"]` | — |
| `l_annee_construction` | `["1978"]` | — |
| `classe_ener_principale` | `D` | **DPE déclaratif bailleur = D, ≠ DPE ADEME repr. = F** (intéressant) |
| `nb_classe_ener_a` | `2` | 2 logts déjà rénovés en A |
| `nb_classe_ener_d` | `43` | 43 logts en D |
| `nb_classe_ener_f` | `1` | 1 logt en F (= celui audité par l'ADEME) |
| `classe_ges_principale` | `E` | — |
| `nb_classe_ges_e` | `43` | 43 logts en GES E |
| `accessible_pmr` | `false` | **Non accessible PMR — vrai problème** |
| `dans_qpv` | `true` | **DANS UN QPV (Quartier Politique Ville)** |

**Marge d'enrichissement** : badge "QPV", badge "Non accessible PMR", barre stack "Distribution DPE par logement (RPLS)" qui montre que 43/48 logts ne sont **pas** F → narratif "le bailleur a déclaré D moyen mais le DPE détaillé ressort F = enjeu réel pour 1 logt + représentativité à creuser".

### 4.3 — `batiment_groupe_dle_elec_multimillesime` + `dle_gaz_multimillesime` ⭐ CONSOMMATIONS RÉELLES

Conso réelles par millésime 2018-2024 (énergie facturée, source Enedis/GRDF) :

| Année | PDL résidentiels | Conso résidentielle | kWh/PDL/an |
|---|---:|---:|---:|
| **Électricité** | | | |
| 2018 | 47 | 83 607 kWh | 1 779 |
| 2019 | 48 | 81 664 kWh | 1 701 |
| 2020 | 48 | 85 830 kWh | 1 788 |
| 2021 | 48 | 83 708 kWh | 1 744 |
| 2022 | 50 | 78 735 kWh | 1 575 |
| 2023 | 50 | 75 228 kWh | 1 505 |
| 2024 | 48 | 73 837 kWh | 1 538 |
| **Gaz** | | | |
| 2018 | 40 | 23 285 kWh | 582 |
| 2019 | 40 | 23 890 kWh | 597 |
| 2020 | 39 | 25 468 kWh | 653 |
| 2021 | 37 | 25 622 kWh | 692 |
| 2022 | 36 | 21 295 kWh | 592 |
| 2023 | **20** | 13 025 kWh | 651 |
| 2024 | **20** | 13 376 kWh | 669 |

**Observations** :
- Élec : tendance baisse 2018-2024 (-12 %) — sobriété + post-COVID.
- Gaz résidentiel : effondrement PDL 2023 (40 → 20). Probable bascule partielle PAC ou raccordement réseau de chaleur sur la moitié du bâtiment.
- Le chauffage collectif gaz du DPE (4.1) est donc en cours de transition côté usagers.

**Marge d'enrichissement** : graphique de tendance conso réelle sur 7 ans (sparkline ou bar chart) → différencie le narratif "DPE = donnée déclarative théorique" vs "conso réelle facturée". Très utile pour pitch jury.

### 4.4 — `batiment_groupe_indicateur_reseau_chaud_froid` ⭐ RÉSEAU DE CHALEUR

| Colonne | Valeur Wazemmes | Signification |
|---|---|---|
| `id_reseau` | `5910C` | Identifiant officiel réseau chaleur urbain |
| `id_reseau_bdnb` | `rcu_442` | — |
| `reseau_en_construction` | `false` | Réseau opérationnel |
| `perimetre_developpement_prioritaire` | **`true`** | **Dans le périmètre de raccordement obligatoire/prioritaire** (loi Énergie-Climat) |
| `indicateur_distance_au_reseau` | `entre 100 et 200m` | Raccordement faisable techniquement |

**Marge d'enrichissement majeure** : badge "Raccordable au réseau de chaleur urbain de Lille (rcu_442) — périmètre prioritaire". Argument décarbonation à l'échelle quartier qui complète parfaitement le narratif rénovation (combo : isoler + se raccorder). Lille a un réseau performant qui inclut de la biomasse + récupération de chaleur fatale.

### 4.5 — `batiment_groupe_qpv`

| Colonne | Valeur Wazemmes |
|---|---|
| `nom_quartier` | `Secteur Sud` |

**Marge** : afficher le nom du QPV. Permet pitch "patrimoine bailleur social en QPV → éligible Eco-PLS bonifié + crédits ANRU".

### 4.6 — `batiment_groupe_ffo_bat` (Fichiers Fonciers)

| Colonne | Valeur Wazemmes | Signification |
|---|---|---|
| `nb_niveau` | `5` | **R+4 ≠ R+3 estimé** depuis hauteur ! Confirmation officielle nb niveaux |
| `annee_construction` | `1978` | Confirme |
| `usage_niveau_1_txt` | `Résidentiel collectif` | RDC = résidentiel |
| `mat_mur_txt` | `BETON` | Confirme |
| `mat_toit_txt` | `BETON` | **Nouvelle info : toiture béton** (cohérent toiture-terrasse) |
| `nb_log` | `48` | Confirme |

**Marge** : indiquer "R+4" au lieu de "R+3" sur la fiche (basé sur `nb_niveau=5`, plus précis que hauteur/3m).

### 4.7 — `batiment_groupe_adresse`

| Colonne | Valeur Wazemmes |
|---|---|
| `libelle_adr_principale_ban` | **`98 Rue des Sarrazins 59000 Lille`** |
| `cle_interop_adr_principale_ban` | `59350_8224_00098` |
| `nb_adresse_valid_ban` | `2` |
| `fiabilite_cr_adr_niv_1` | `données croisées à l'adresse fiables` |

**Marge d'enrichissement majeure** : **afficher l'adresse postale réelle** au lieu du seul `building_id`. C'est ce que le jury et un opérateur de rénovation veulent voir en premier (98 Rue des Sarrazins est dans Wazemmes Sud).

### 4.8 — `batiment_groupe_urbanisme`

| Colonne | Valeur Wazemmes | Signification |
|---|---|---|
| `contrainte_urbanisme_ac1` | **`true`** | **Contrainte d'urbanisme (AC1) : périmètre patrimoine** |
| `zone_plu_bati_patrimonial` | `false` | Pas en zone patrimoniale stricte |
| `monument_historique` | `false` | Confirme |
| `source_monument_historique` | `merimee + geoportail_urbanisme` | — |
| `denomination_monument_historique` | `Maison 32-32 bis rue d'Antin` | MH le plus proche |
| `distance_monument_historique` | `345` m | Pas dans le périmètre 500m → modulo zone AC1 |

**Marge d'enrichissement** : ⚠ disclaimer "AC1 : périmètre de servitude urbanisme — toute intervention en façade nécessite avis du Service urbanisme + ABF si dans 500m d'un MH". À ajouter au plan IA pour précaution.

### 4.9 — `batiment_groupe_risques` (+ argiles + radon redondants)

| Colonne | Valeur |
|---|---|
| `alea_radon` | `Faible` |
| `alea_argile` | `Faible` (retrait-gonflement argiles) |
| `alea_sismique` | `Faible` |

**Marge** : section "Risques naturels" avec 3 mini-badges (radon, argile, sismique). Rassure sur la stabilité avant ITE lourde (l'ITE rapportée sur béton avec aléa argile élevé impose études géotechniques).

### 4.10 — `batiment_groupe_bdtopo_bat`

| Colonne | Valeur Wazemmes | Signification |
|---|---|---|
| `l_nature` | `["Indifférenciée"]` | Type BD TOPO |
| `l_usage_1` | `["Résidentiel"]` | — |
| `l_usage_2` | `["Annexe"]` | — |
| `l_etat` | `["En service"]` | Bâtiment occupé |
| `hauteur_mean` | `11` m | Confirme |
| `max_hauteur` | `11` m | — |
| `altitude_sol_mean` | `25` m | Altitude IGN du terrain |

**Marge** : modeste, sauf pour la géoréf altimétrique 3D.

### 4.11 — `batiment_groupe_geospx`

| Colonne | Valeur Wazemmes |
|---|---|
| `fiabilite_emprise_sol` | `BONNE` |
| `fiabilite_hauteur` | `BONNE` |
| `fiabilite_adresse` | `true` |

**Marge** : indicateur "Fiabilité des données BDNB" sur la fiche (Bonne/Moyenne/Faible). Renforce la crédibilité du diagnostic.

### 4.12 — `batiment_groupe_merimee`

| Colonne | Valeur Wazemmes |
|---|---|
| `distance_batiment_historique_plus_proche` | `366` m |
| `nom_batiment_historique_plus_proche` | `Maison` |

Redondant avec 4.8. Pas de marge.

### 4.13 — `batiment_groupe_hthd` (Hauteur Très Haute Densité ?)

| Colonne | Valeur |
|---|---|
| `nb_pdl` | `2` |
| `l_type_pdl` | `["IM"]` (immeuble) |

Marge faible, peu lisible pour la fiche.

### 4.14 — `batiment_groupe_synthese_propriete_usage`

| Colonne | Valeur |
|---|---|
| `usage_principal_bdnb_open` | `Résidentiel collectif` |

Redondant avec `type_principal`. Pas de marge.

### 4.15 — `batiment_groupe` (base + métadonnées commune/EPCI)

| Colonne | Valeur Wazemmes |
|---|---|
| `s_geom_groupe` | `1084` (m² emprise — déjà exposé via `surface_m2`) |
| `code_iris` | `593500402` (déjà exposé) |
| `code_commune_insee` | `59350` (déjà exposé) |
| `libelle_commune_insee` | **`Lille`** (non exposé) |
| `code_epci_insee` | **`200093201`** (MEL — non exposé) |
| `contient_fictive_geom_groupe` | `false` |

**Marge** : afficher le **nom de commune en clair** ("Lille" plutôt que "INSEE 59350") + nom EPCI ("Métropole Européenne de Lille") via une jointure annexe sur table INSEE.

### 4.16 — `public_data.building_acces_chantier` (déjà calculée, pas exposée)

| Colonne | Valeur Wazemmes |
|---|---|
| `acces_chantier` | `1.0` (booléen score) |
| `nearest_largeur_m` | `4` m |
| `nearest_distance_m` | `7.01` m |

**Marge** : ajouter section "Faisabilité chantier" (largeur voirie 4m à 7m, ✅ accessible aux camions). Justifie la composante `s_faisa = 0.845`.

### 4.17 — Autres tables ignorées (Wazemmes a 0 ligne)

- `batiment_groupe_dpe_tertiaire` (0 ligne, c'est résidentiel)
- `batiment_groupe_dvf_open_representatif` / `_statistique` (0 ligne — pas de vente DVF récente)
- `batiment_groupe_bpe` (0 ligne — pas d'équipement public)
- `batiment_groupe_dle_reseaux_multimillesime` (0 ligne — n'utilise pas le réseau de chaleur)

---

## Section 5 — Données dérivables côté backend (sans nouvelle source)

| Donnée | Formule | Faisabilité | Effort |
|---|---|---|---|
| **Coût énergie annuel actuel** (€) | `dpe_kwh_ep_m2_an × surface_m2 × tarif_moyen_kWh` (tarif gaz 0.10€ + élec 0.20€ pondéré) | Donnée déjà en main | 30 min (constante tarif dans `config/`) |
| **Coût énergie évité 30 ans** (€) | Δ_conso × surface × 30 × tarif | Idem | 30 min |
| **Émissions CO₂ totales actuelles 30 ans** (tCO₂) | `dpe_kg_co2_m2_an × surface_m2 × 30 / 1000` | Idem | 15 min |
| **Position dans classement IRIS / commune / dpt** | Window function `RANK() OVER (PARTITION BY code_iris ORDER BY score_total DESC)` sur `building_scores` | Nouvelle requête, ~50 ms | 1h (endpoint dédié `/api/buildings/:id/rank`) |
| **Moyenne scoring IRIS / commune / dpt** | `AVG(s_*)` group by code_iris | Idem | 1h |
| **Liste bâtiments voisins du même propriétaire** (bailleur social) | `SELECT building_id FROM buildings b JOIN batiment_groupe_rpls r USING(building_id) WHERE r.rpls_open AND b.geom <-> ref.geom < 1000 LIMIT 10` | Nouvelle requête, ~200 ms | 2h |
| **Distribution DPE par classe sur l'IRIS / commune** | GROUP BY `dpe_classe` filtré sur `code_iris` | Idem | 1h |
| **Trajectoire conso réelle 7 ans (graphique tendance)** | Lecture directe `dle_elec_multimillesime` + `dle_gaz_multimillesime` | Donnée déjà en main | 1h |
| **Type d'aides éligibles** (MaPrimeRénov' Copro, Eco-PLS, CEE bailleur social, ANRU si QPV) | Logique métier sur `type_proprietaire`, `dans_qpv`, `nb_logements`, `dpe_classe` | Pas de nouvelle requête | 2h (matrice règles dans `config/aides.yaml`) |
| **Période réglementaire thermique** (avant 1948, 1948-74, 74-82, 82-89, 89-2000, 2000-2012, RT2012, RE2020) | Bucket sur `annee_constr` | Donnée déjà en main | 15 min |
| **Estimation surface façade rénovable** | `2 × hauteur_m × √(surface_m2 × ratio_compacité)` — heuristique | Calcul pur | 30 min |

> **Total quick-wins déductibles** : ~10h backend pour la moitié de ces enrichissements. Le frontend a un peu plus de travail pour les afficher proprement.

---

## Section 6 — Données qu'on n'a PAS (et qu'on n'aura pas pour le pitch)

Soyons explicites — pour ne pas inventer d'affirmation dans la fiche :

| Donnée manquante | Pourquoi | Décision référencée |
|---|---|---|
| **Mesh LiDAR HD** détaillé par bâtiment | Téléchargement non lancé, différé jusqu'au test live partenaire | B-011 |
| **Géométrie 3D détaillée façades** (nb fenêtres, balcons, hauteur étage) | Pas de scan 3D, BDNB ne descend pas à ce niveau | — |
| **FDES INIES dynamique** (base entière 5800 FDES) | Pas d'accès API garanti, on utilise la base statique 30 matériaux clés | D-014 |
| **Audit énergétique réglementaire détaillé** | Nécessite passage d'un thermicien sur place. Le DPE BDNB est un proxy déclaratif | — |
| **Identité du propriétaire** (nom bailleur) | Refusé par BDNB open data (RGPD) — seule la typo (bailleur_social/particulier/etc.) est dispo. Pour identifier "Lille Métropole Habitat" il faudrait croisement DRIHL ou contact opérateur | CLAUDE.md §6, RGPD |
| **Données financières du propriétaire** (capacité d'emprunt, trésorerie) | Données privées, pas dans les sources publiques | — |
| **Historique des travaux** déjà réalisés (sauf ce qui transparait dans le DPE) | Pas de base nationale. BDNB ne distingue pas un bâtiment rénové d'un bâtiment d'origine sauf via les attributs DPE | — |
| **Conso réelle individuelle par logement** | RGPD — DLE n'expose qu'au PDL agrégé par bâtiment | — |
| **Loyer / occupation / vacance** | Pas dans BDNB. RPLS donne `accessible_pmr` mais pas les loyers | — |
| **Date du prochain DPE obligatoire** | Pas calculé. Le DPE actuel date du 27/04/2022, valide 10 ans → expire 27/04/2032 (déductible) | Marge si pertinent |
| **Diagnostics amiante / plomb** | Réglementaires pour bât. < 1997. Pas dans les sources publiques nationales | — |
| **Photos de façade** | Pas d'API photo nationale pour 1.5M bâtiments. BD Ortho IGN couvre mais pas par bâtiment | — |
| **Plan cadastral détaillé** (servitudes, mitoyennetés) | Pas dans BDNB open data. Cadastre.gouv.fr possible mais hors scope | — |
| **Coût réel chantier antérieur** sur bâtiments comparables | Référentiel CSTB Hors-site existe mais pas open data. On utilise des fourchettes filière HDF 2025 dans le scoring (cf. SCORING.md) | — |
| **Avis ABF** pour zone AC1 | Décision réglementaire au cas par cas, pas prédictible | — |

---

## Récap quantitatif

| Catégorie | Champs |
|---|---|
| **Affichés Drawer Stratégie** | 21 (dont 3 cassés) |
| **Affichés Fiche Projet** | 28 (dont 9 cassés `score.*` + 1 cassé `bdnb_millesime`) |
| **Renvoyés par `/api/buildings/:id` mais non affichés** | 5 (`neighbors`, `centroid_*`, `cout_eur_par_t_co2`, `confidence`, `incomplete_data`, `score.thresholds_version`, `score.missing_fields`, `score.computed_at`) |
| **Disponibles dans BDNB pour Wazemmes, pas remontés à l'API** | **~80 colonnes utiles** réparties sur 16 tables actives |
| **Dérivables sans nouvelle source** | ~10 indicateurs (coût énergie, classement IRIS, aides éligibles, etc.) |
| **Indisponibles définitivement** | 14 catégories listées Section 6 |

## Priorisation suggérée (à arbitrer)

**Tranche 1 — bugs latents à corriger en priorité (rends fonctionnel ce qui est déjà branché)** :
1. Corriger l'accès `building.score.*` côté Projet.tsx (ou aplatir côté API) — débloque 9 champs.
2. Ajouter `hauteur_m`, `dpe_kwh_ep_m2_an`, `monument_historique` à `BuildingListItem` API + Drawer fonctionne.
3. Ajouter `score_total` au modèle `BuildingDetail` (la métrique-titre de la fiche).
4. Ajouter `bdnb_millesime` à `BuildingDetail`.

**Tranche 2 — enrichissements à coût zéro (utiliser ce qui est déjà dans la réponse)** :
5. Widget "Voisins" (5 bâtiments + DPE + distance) déjà calculé.
6. Indicateur "Fiabilité données" basé sur `score.confidence`.
7. Disclaimer "Estimation incomplète" si `score.incomplete_data` true.

**Tranche 3 — quick win avec join BDNB (forte valeur narrative)** :
8. **Adresse postale** (`98 Rue des Sarrazins 59000 Lille`).
9. **Identifiant DPE ADEME** (`2259E0904747H`) + bouton lien observatoire-dpe.ademe.fr.
10. **Badge QPV** ("Wazemmes — Secteur Sud").
11. **Badge réseau de chaleur** ("Raccordable RCU Lille rcu_442 — périmètre prioritaire").
12. **Diagnostic technique** (U_mur, U_porte, type chauffage/ECS, ventilation, DV/triple).
13. **Conso réelle 7 ans** (sparkline élec + gaz).
14. **Distribution DPE par logement (RPLS)** (bar stack).
15. **Risques naturels** (3 badges Faible/Moyen/Fort).
16. **Accessibilité PMR** (rouge si `accessible_pmr=false`).

**Tranche 4 — déductibles (coût modéré, gros impact pitch)** :
17. Coût énergie annuel actuel + évité 30 ans (€).
18. Classement IRIS / commune (position N° X sur Y bâtiments).
19. Aides éligibles (matrice règles).

---

## Annexe — Sources consultées

- `backend/app/routers/buildings.py` (endpoints liste + fiche)
- `frontend/src/components/BuildingDrawer.tsx` (Mode Stratégie)
- `frontend/src/pages/Projet.tsx` (fiche Mode Projet)
- `frontend/src/lib/api.ts` (types frontend)
- `postgres_local` schémas : `public_data.*` + `bdnb_2025_07_a_open_data_dep59.*`
- Réponse réelle `GET /api/buildings/bdnb-bg-81UB-UTZE-ZP7F` (date 2026-05-23)
