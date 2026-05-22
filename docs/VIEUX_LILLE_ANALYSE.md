# ConX — Analyse quartier Vieux-Lille (démo)

**Date** : 2026-05-22.
**Périmètre choisi** : bbox WGS84 `(3.057, 50.640) — (3.075, 50.652)` couvrant
Grand-Place, Quartier Royal, Magasin, Réduit, Esplanade.

---

## 1. Statistiques de couverture

| Indicateur | Valeur |
|---|---|
| Total bâtiments BDNB | 1 819 |
| DPE réel (ADEME) | 577 (31.7 %) |
| DPE ML estimé | 1 242 (68.3 %) |
| Passoires (F/G) toutes sources | 266 |
| Passoires F/G **certifiées ADEME** | 65 |
| Construits avant 1948 | 1 069 (58.8 %) |
| **Monuments Historiques** | **51** (classés/inscrits, BDNB monument_historique=true) |
| **SPR** | **0** (champ BDNB non peuplé pour Lille, malgré le SPR Vieux-Lille existant — limitation BDNB millésime 2025-07.a) |
| Bailleurs sociaux | 68 |
| Personnes morales privées | 366 (copros + foncières) |
| Particuliers | 1 385 |

⚠ **SPR=0** : la BDNB 2025-07.a n'a pas peuplé le champ `spr` pour Lille,
alors que le quartier Vieux-Lille EST un SPR réel. Le scoring repose donc
sur `monument_historique` seul pour la composante patrimoine côté démo.

---

## 2. Distribution par IRIS (top 6, MH décroissants)

Les IRIS qui composent Vieux-Lille (centre + nord) :

| IRIS | Centre (lon, lat) | n bât. | MH | Pré-1948 | Zone |
|---|---|---|---|---|---|
| 593500204 | (3.0589, 50.6389) | 361 | **39** | 346 | Grand-Place / Vieille Bourse |
| 593500202 | (3.0662, 50.6425) | 115 | **24** | 107 | Magasin / Réduit nord |
| 593500203 | (3.0635, 50.6403) | 240 | **21** | 236 | Vieux-Lille centre |
| 593500112 | (3.0606, 50.6356) | 121 | 18 | 113 | Quartier Royal sud |
| 593500111 | (3.0685, 50.6373) | 91 | 12 | 87 | Royal est |
| 593500207 | (3.0607, 50.6440) | 48 | 7 | 43 | Citadelle bord |

---

## 3. Trois candidats bâtiment d'atterrissage (atterrissage final démo)

### Pré-requis demandés (relâché pour matcher la réalité urbaine du Vieux-Lille)

| Critère | Demandé | Réalité Vieux-Lille |
|---|---|---|
| Type | Logement collectif R+2 à R+4 | ✓ |
| Propriétaire | Bailleur social préf. ou copro ancienne | Bailleurs sociaux = 68 dans bbox, AUCUN avec F/G ADEME pré-1948. Copros privées dominent. |
| DPE | F ou G réel | ✓ (65 candidats) |
| Année | Avant 1948 | ✓ (1820-1930) |
| Score ConX | > 90 | ✓ pour top 2, ~60-77 pour les autres |
| Accès chantier | ≥ 4 m | ✓ tous à 4.0 m (rues étroites du quartier) |
| Pas patrimoine | MH=false, SPR=false | ✓ MH, SPR trivial (cf §1) |

### Top 3 candidats

#### Candidat A — `bdnb-bg-NKGA-DUZ2-J28H` (RNB `25E29JA2A9V6`)
- **Type** : Résidentiel collectif R+2 (hauteur 8 m)
- **Surface** : 233 m² / 7 logements
- **Année** : 1870
- **Propriétaire** : copro privée (personne_morale_privee)
- **DPE F** (416 kWh ep/m²/an) — **certifié ADEME**
- **Score ConX** : **91.1/100** (top du quartier)
- **Bilan rénovation** : 517 tCO₂ évitées sur 30 ans, 140 k€ estimés
- **Accès chantier** : 4.0 m (voie étroite mais accessible hors-site)
- **Profile narratif** : copro de quartier ancien, F notoire, fort levier
  carbone, prête pour pilote MaPrimeRénov'Sérénité (gain ≥ 35 %).

#### Candidat B — `bdnb-bg-JBP7-PFQL-4T69` (RNB `1JZ6GKJCV1ZS`)
- **Type** : Résidentiel collectif R+3 (hauteur 9 m)
- **Surface** : 233 m² / **17 logements** (densité plus élevée)
- **Année** : 1930
- **Propriétaire** : copro privée
- **DPE G** (540 kWh ep/m²/an) — **certifié ADEME** (passoire intense)
- **Score ConX** : **91.1/100**
- **Bilan rénovation** : **714 tCO₂** évitées sur 30 ans (record du
  quartier), 140 k€ estimés
- **Accès chantier** : 4.0 m
- **Profile narratif** : immeuble années 30 G dense — le gros levier
  carbone d'une seule opération.

#### Candidat C — `bdnb-bg-7F6X-1AGX-L22Q` (RNB `GMJ42V7S3YCW`)
- **Type** : Résidentiel collectif R+4 (hauteur 13 m)
- **Surface** : 146 m² / 3 logements
- **Année** : 1900
- **Propriétaire** : copro privée
- **DPE F** (392 kWh ep/m²/an) — certifié ADEME
- **Score ConX** : **77.1/100**
- **Bilan rénovation** : 300 tCO₂ évitées, 88 k€ estimés
- **Accès chantier** : 4.0 m
- **Profile narratif** : petit collectif typique du début XXe, R+4 typique
  de la rue belge.

---

## 4. Note pour le pitch

- **Aucun bailleur social** ne matche TOUS les critères F/G+ADEME+pré-1948
  dans le bbox Vieux-Lille. Pour démo "logement social", il faut basculer
  sur Wazemmes (Lille sud) ou un IRIS différent. Les 3 candidats ci-dessus
  sont des **copros privées anciennes** — narratif "rénovation hors-site
  contre la passoire urbaine, propriétaires fragmentés mais opération
  collective".
- **Score ConX 91.1/100** pour les 2 meilleurs : valeur narrativement
  forte ("plus de 9/10 selon notre indice", citable directement par le
  jury).
- **517 et 714 tCO₂ évitées** sur 30 ans : ordre de grandeur compréhensible
  (~équivalent du carbone routier d'1 voiture neuve pendant 30 ans × 50
  voitures). À utiliser dans le narratif.

---

## 5. Fallback si Vieux-Lille pose problème

Le partenaire a indiqué : **Vauban-Esquermes** (Lille, 59) ou **Lens centre**
(62, narratif post-minier). Ces fallbacks ne sont pas pré-analysés —
relancer la requête avec une nouvelle bbox.
