# ConX — Scoring territorial déterministe

**Statut** : VALIDÉ par le partenaire (2026-05-21).
**Auteur** : ConX, 2026-05-21.
**Référence décision** : `DECISIONS.md` D-006 (scoring 100 % déterministe, l'IA explique mais ne calcule pas).

---

## Principe

Chaque bâtiment de la base reçoit un **score composite** entre 0 et 100 mesurant son **potentiel de rénovation hors-site décarbonée**. Plus le score est élevé, plus le bâtiment est prioritaire.

Le score combine **5 composantes indépendantes** normalisées dans [0,1], pondérées :

```
score = 100 × (w_co2 · S_co2 + w_faisa · S_faisa + w_cout · S_cout + w_social · S_social + w_passoire · S_passoire)
```

Poids par défaut (validés partenaire, ajustables via sliders UI) :

| Composante | Poids défaut | Sens |
|---|---|---|
| `w_co2` | **0.35** | Potentiel CO₂ évité |
| `w_faisa` | **0.25** | Faisabilité technique hors-site |
| `w_cout` | **0.20** | Efficience coût (inversée) |
| `w_social` | **0.10** | Priorité sociale (typologie propriétaire) |
| `w_passoire` | **0.10** | Urgence réglementaire (classe DPE F/G) |

Somme = **1.00**. Les sliders UI garantissent la somme = 1 (renormalisation auto si l'utilisateur déplace un slider).

---

## Composante 1 — Potentiel CO₂ évité sur 30 ans (`S_co2`)

### Calcul brut (tCO₂ sur 30 ans)

```
co2_evite_t = ((conso_kwh_actuelle - conso_kwh_cible_classeB) × surface_m2 × facteur_emission_kWh × 30) / 1000
```

- `conso_kwh_actuelle` = consommation actuelle (kWh ep/m²/an), DPE réel ou prédiction ML.
- `conso_kwh_cible_classeB` = seuil classe B (= 90 kWh ep/m²/an par défaut, configurable selon zone climatique).
- `surface_m2` = surface utile BDNB.
- `facteur_emission_kWh` = kgCO₂/kWh selon source d'énergie (Base Carbone ADEME) :
  - Électricité (mix France) : 0.057
  - Gaz naturel : 0.227
  - Fioul : 0.324
  - Réseau de chaleur : 0.110 (moyenne nationale)
  - Bois : 0.030
- `30` = horizon d'amortissement standard (ADEME). **Affiché partout dans l'UI** comme hypothèse globale modifiable.

### Normalisation absolue (seuils fixes)

```
S_co2 = clip(co2_evite_t / 500, 0, 1)
```

- **0 tCO₂/30ans → score 0**
- **500 tCO₂/30ans → score 1 (plafonné au-delà)**

Le seuil 500 t correspond à un immeuble collectif passoire d'environ 2 000 m² bien rénové — référence du marché. Au-delà, on plafonne (pas d'avantage marginal à un immeuble plus gros sur ce critère).

### Sources
- Facteurs émissions : Base Carbone ADEME (https://base-empreinte.ademe.fr/), consultée 2026-05.
- Seuils DPE classes : arrêté du 31 mars 2021 modifié, articles relatifs aux classes énergétiques DPE.

---

## Composante 2 — Faisabilité hors-site (`S_faisa`)

Score [0,1] composite d'indicateurs binaires et continus extraits de BDNB + BD TOPO + LiDAR + voirie. **Déjà borné [0,1] par construction**, pas de normalisation supplémentaire.

### Sous-indicateurs

| Sous-indicateur | Pondération interne | Calcul |
|---|---|---|
| **Toiture régulière** | 0.25 | 1 si pente uniforme, 0.5 si toiture complexe, 0 si toiture indéterminée. Détection via MNH/MNS LiDAR ou type BDNB. |
| **Accès chantier** | 0.20 | 1 si rue ≥ 4 m de large à moins de 10 m du bâtiment (BD TOPO + BDNB), 0.5 si rue 2-4 m, 0 si impasse étroite ou bâtiment enclavé. |
| **Hauteur compatible préfabrication** | 0.15 | 1 si ≤ R+4 (modules grutables), 0.7 si R+5/R+8, 0.3 si > R+8. |
| **Absence de protection patrimoniale** | 0.20 | 0 si Monument Historique (champ BDNB `monument_historique`, inscrit/classé non distingué dans BDNB open) ou Site Patrimonial Remarquable (`spr` = `zone_plu_bati_patrimonial`). 1 sinon. |
| **Géométrie simple** | 0.10 | Ratio périmètre² / surface : 1 si proche du carré (faible), 0 si très allongé/découpé. |
| **Type compatible hors-site** | 0.10 | Résidentiel collectif R+1 à R+5 = 1 ; pavillon = 0.8 ; tertiaire ≤ R+4 = 0.9 ; industriel = 0.3 ; spécifique (église, gare…) = 0. |

```
S_faisa = Σ (poids_interne_i × valeur_i)
```

---

## Composante 3 — Efficience coût (`S_cout`)

Coût estimé en €/m² puis exprimé en **€ par tCO₂ évité**, et normalisé inversement.

### Coût estimé brut

```
cout_estime_eur = surface_m2 × cout_m2_par_typologie(type, periode_construction, complexite)
```

Table `cout_m2_par_typologie` (valeurs indicatives ADEME, ajustables) :

| Type bâtiment | Période | Coût/m² (€ TTC) |
|---|---|---|
| Résidentiel collectif | < 1948 | 600 |
| Résidentiel collectif | 1948-1974 | 550 |
| Résidentiel collectif | 1975-2000 | 450 |
| Résidentiel collectif | > 2000 | 350 |
| Pavillon | < 1948 | 800 |
| Pavillon | 1948-1974 | 700 |
| Pavillon | 1975-2000 | 550 |
| Pavillon | > 2000 | 400 |
| Tertiaire bureaux | toutes | 500 |
| Tertiaire commerce | toutes | 450 |

Modulations :
- × 1.00 si géométrie simple (`S_faisa.geometrie_simple` ≥ 0.5)
- × 1.15 si géométrie complexe
- × 1.30 si protection patrimoniale

### Normalisation absolue inversée

```
cout_eur_par_t_co2 = cout_estime_eur / co2_evite_t
S_cout = clip((5000 - cout_eur_par_t_co2) / (5000 - 500), 0, 1)
```

- **5 000 €/tCO₂ → score 0** (peu efficient, limite haute de l'acceptable)
- **500 €/tCO₂ → score 1** (très efficient, limite basse de l'excellent)
- Entre les deux : interpolation linéaire.
- En dehors : clip aux bornes.

Ces seuils encadrent ce que la profession considère comme acceptable à excellent pour la rénovation thermique en France.

### Sources
- Coûts indicatifs : "Études coûts ADEME rénovation énergétique 2024" + retours d'expérience CD2E hors-site.
- Affichage UI : "Valeurs indicatives — ajustables dans les paramètres".

---

## Composante 4 — Priorité sociale (`S_social`)

Score [0,1] basé sur la typologie de propriétaire BDNB (jamais d'identité réelle). **Déjà borné par construction.**

| `type_proprietaire` BDNB | `S_social` |
|---|---|
| `bailleur_social` | 1.00 |
| `public` (collectivité, État) | 0.80 |
| `personne_morale_privee` (copropriété, foncière) | 0.50 |
| `particulier` | 0.30 |
| inconnu | 0.40 |

**Rationale** : les bailleurs sociaux et collectivités sont prioritaires pour aligner l'action publique. Les particuliers ont moins de levier collectif. **Pas de boost passoire ici** — cette dimension est isolée dans `S_passoire` (composante 5) pour éviter une asymétrie injuste.

### Sources
- `type_proprietaire` BDNB : champ typologique, pas d'identité.

---

## Composante 5 — Urgence réglementaire passoire thermique (`S_passoire`)

Score [0,1] discret, indépendant des autres composantes.

| Classe DPE | `S_passoire` |
|---|---|
| A, B, C, D | 0.00 |
| E | 0.50 |
| F, G | 1.00 |

### Rationale

L'urgence réglementaire (loi Climat & Résilience : interdiction location classe G depuis 2025, classe F depuis 2028, classe E depuis 2034) est un critère **distinct** du potentiel CO₂ (qui mesure le gain absolu) et de la priorité sociale (qui mesure le levier d'action publique).

Le séparer dans sa propre composante :
1. **Évite les biais** d'agrégation injuste (un bailleur social passoire et un particulier passoire bénéficient maintenant du même boost passoire, à priorité sociale par ailleurs distincte).
2. **Améliore la lisibilité** dans le breakdown UI : on voit explicitement "ce bâtiment marque haut parce qu'il est passoire".
3. **Permet l'ajustement indépendant** du poids `w_passoire` selon le contexte (un audit "urgence loi Climat" mettrait `w_passoire = 0.40`, un audit "patrimoine touristique" mettrait `w_passoire = 0.0`).

### ⚠️ Coefficient d'énergie primaire électricité 1.9 (BDNB 2025-07.a — anticipation réforme 2026-01-01)

À partir du **1er janvier 2026**, le calcul officiel du DPE utilise un coefficient d'énergie primaire pour le vecteur électricité de **1.9** (au lieu de 2.3 précédemment). Cette réforme réduit mécaniquement la consommation EP des logements chauffés électriquement et **diminue donc le nombre de bâtiments classés F/G**.

**Source officielle** : [Ministère de la Transition Écologique — FAQ DPE modification du facteur de conversion](https://rt-re-batiment.developpement-durable.gouv.fr/faq-dpe-modification-du-facteur-de-conversion-en-a1021.html?lang=fr).

**Implication pour ConX** :
- La BDNB millésime **2025-07.a anticipe déjà cette réforme** : les simulations DPE qu'elle livre utilisent le coefficient 1.9. Confirmé par le changelog officiel BDNB.
- ConX adopte **systématiquement le DPE coefficient 1.9** (= le futur DPE officiel). Si la BDNB livre les deux versions (2.3 historique et 1.9 anticipée), le pipeline d'ingestion (J2) prend la 1.9.
- **Conséquence chiffrée** : `S_passoire` colonisera moins de bâtiments en HDF qu'avec le coefficient 2.3. C'est cohérent avec le cadre réglementaire **à venir**.
- **Pitch jury** : argumentaire prêt — "ConX est aligné avec le futur cadre réglementaire 2026, pas avec le passé. Les bâtiments que nous priorisons sont ceux qui resteront passoires après la réforme."

L'UI affiche explicitement dans la fiche bâtiment : *"Classe DPE basée sur le coefficient EP électricité 1.9 (cadre réglementaire 2026)."*

### Sources
- Loi Climat & Résilience du 22 août 2021.
- [FAQ DPE — coefficient 1.9 (DGEC, MTE)](https://rt-re-batiment.developpement-durable.gouv.fr/faq-dpe-modification-du-facteur-de-conversion-en-a1021.html?lang=fr).
- BDNB 2025-07.a changelog (CSTB).
- Classe DPE : DPE réel (`source = 'ademe-real'`) ou prédiction ML (`source = 'ml-predicted'`). En cas de prédiction, on affiche dans l'UI "estimation — DPE réel à confirmer".

---

## Configuration globale — `scoring_thresholds.yaml`

Tous les seuils sont externalisés dans un fichier YAML versionné, modifiable sans recompiler :

```yaml
# scoring_thresholds.yaml
co2:
  max_tonnes_30ans: 500      # seuil saturation S_co2

cost:
  min_eur_per_tco2: 500       # score 1 (très efficient)
  max_eur_per_tco2: 5000      # score 0 (peu efficient)

target_class:
  default: "B"
  kwh_ep_m2_an: 90            # cible classe B par défaut

horizon_amortissement_ans: 30

energy_emission_factors:      # kgCO₂/kWh (Base Carbone ADEME)
  electricite: 0.057
  gaz: 0.227
  fioul: 0.324
  rcu: 0.110
  bois: 0.030

cost_table_eur_m2:
  # voir tableau ci-dessus, structure imbriquée {type: {periode: cout}}

weights_default:
  w_co2: 0.35
  w_faisa: 0.25
  w_cout: 0.20
  w_social: 0.10
  w_passoire: 0.10
```

---

## Implémentation backend

### Pré-calcul des composantes (batch)

À l'ingestion initiale (J2-J5) et à chaque MAJ amont (nouveau millésime BDNB, nouveau DPE ADEME, nouveau modèle ML) : recalcul **batch** des 5 composantes pour tous les bâtiments concernés. Stockage dans `building_scores`.

```sql
CREATE TABLE building_scores (
  building_id      text PRIMARY KEY REFERENCES buildings,
  -- Composantes [0,1]
  s_co2            numeric NOT NULL CHECK (s_co2 BETWEEN 0 AND 1),
  s_faisa          numeric NOT NULL CHECK (s_faisa BETWEEN 0 AND 1),
  s_cout           numeric NOT NULL CHECK (s_cout BETWEEN 0 AND 1),
  s_social         numeric NOT NULL CHECK (s_social BETWEEN 0 AND 1),
  s_passoire       numeric NOT NULL CHECK (s_passoire BETWEEN 0 AND 1),
  -- Valeurs brutes pour affichage UI et debug
  co2_evite_t      numeric NOT NULL,
  cout_estime_eur  numeric NOT NULL,
  cout_eur_par_t_co2 numeric,
  -- Métadonnées
  confidence       numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  dpe_source       text NOT NULL CHECK (dpe_source IN ('ademe-real','ml-predicted')),
  thresholds_version text NOT NULL,    -- hash du scoring_thresholds.yaml utilisé
  computed_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON building_scores (dpe_source);
-- pas d'index sur le score total : on le calcule à la volée
```

### Calcul à la volée du score total (SQL pur)

Quand l'utilisateur modifie les poids via sliders UI : envoi des nouveaux poids au backend, qui exécute une requête paramétrée :

```sql
SELECT
  bs.building_id,
  b.geom,
  (
    $1::numeric * bs.s_co2 +
    $2::numeric * bs.s_faisa +
    $3::numeric * bs.s_cout +
    $4::numeric * bs.s_social +
    $5::numeric * bs.s_passoire
  ) * 100 AS score_total,
  bs.s_co2, bs.s_faisa, bs.s_cout, bs.s_social, bs.s_passoire,
  bs.co2_evite_t, bs.cout_estime_eur, bs.confidence
FROM building_scores bs
JOIN buildings b USING (building_id)
WHERE ST_Intersects(b.geom, ST_MakeEnvelope($6, $7, $8, $9, 2154))
  AND ($10::text[] IS NULL OR b.dept = ANY($10))   -- filtres facultatifs
ORDER BY score_total DESC
LIMIT $11;
```

Sur 1,5 M lignes avec un index GIST spatial, c'est instantané (< 50 ms typiquement). **Pas de chargement en RAM, pas de recalcul Python.**

### Module Python (calcul batch uniquement)

```python
# backend/scoring/compute.py — utilisé uniquement en batch
@dataclass
class ScoringThresholds:
    co2_max_tonnes_30ans: float = 500
    cost_min_eur_per_tco2: float = 500
    cost_max_eur_per_tco2: float = 5000
    target_class_kwh: float = 90
    horizon_ans: int = 30
    # ... autres

@dataclass
class BuildingScoreComponents:
    s_co2: float; s_faisa: float; s_cout: float; s_social: float; s_passoire: float
    co2_evite_t: float; cout_estime_eur: float; cout_eur_par_t_co2: float | None
    confidence: float; dpe_source: str

def compute_components(building: Building, dpe: DPE, thresholds: ScoringThresholds) -> BuildingScoreComponents:
    """Calcul des 5 composantes pour un bâtiment. Sans poids — les poids s'appliquent en SQL."""
    ...
```

---

## Affichage UI

Pour chaque bâtiment sélectionné :

```
Score 78 / 100              (poids actifs : 35/25/20/10/10)
  CO₂ évitable                ████████░░  82
  Faisabilité hors-site       ██████░░░░  64
  Efficience coût             ████████░░  78
  Priorité sociale            ██████████  100   (bailleur social)
  Urgence passoire            ██████████  100   (DPE F estimé)

  Détail :
    – CO₂ évité estimé : 187 tCO₂ sur 30 ans
    – Coût estimé : 412 000 € HT
    – €/tCO₂ : 2 204
    – Confiance : 0.78 (DPE réel, RNB ID confirmé)
    – Seuils utilisés : scoring_thresholds.yaml v1.0
```

L'agent IA (Sélection) **narre** ce score en langage naturel : *"Cet immeuble bailleur social années 50 cumule un fort potentiel CO₂, une priorité sociale élevée, l'urgence loi Climat (DPE F estimé) et un coût d'évitement compétitif à 2 200 €/tCO₂ — il devrait être dans votre top 10 du quartier."* L'agent ne recalcule jamais le score.

---

## Récapitulatif décisions partenaire (2026-05-21)

| Question | Décision |
|---|---|
| Poids défaut | 0.35 / 0.25 / 0.20 / 0.10 / 0.10 (5 composantes) |
| Grille tarifaire €/m² | Table ADEME ci-dessus, marquée "valeurs indicatives — ajustables" |
| Boost passoire | **Remplacé par 5e composante S_passoire indépendante** |
| Horizon | 30 ans (standard ADEME), affiché et configurable globalement |
| Normalisation | **Seuils absolus** (S_co2: 0-500 tCO₂ ; S_cout: 500-5000 €/tCO₂) |
| Stockage | **Pré-calcul des 5 composantes en batch**, recalcul du total à la volée en SQL pur |
