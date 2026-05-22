---
name: pmr-checks
description: Règles d'accessibilité PMR (Personnes à Mobilité Réduite) appliquées à la rénovation et à la construction — largeurs portes, pentes rampes, dimensions sanitaires, hauteurs. À utiliser quand l'agent Conformité analyse un IFC ou que l'agent Plan inclut des contraintes d'accessibilité dans la rénovation.
---

# pmr-checks — Règles PMR (accessibilité)

## Quand utiliser cette skill

- L'agent Conformité analyse un IFC et doit lister les non-conformités PMR.
- L'agent Plan doit intégrer des contraintes d'accessibilité (ERP, logement
  adapté, rénovation pour vieillissement).
- L'utilisateur demande "ce plan est-il PMR ?" ou cite la loi handicap 2005.

## Cadre réglementaire

- **Loi du 11 février 2005** pour l'égalité des droits et des chances.
- **Arrêté du 8 décembre 2014** (ERP-IOP existants).
- **Arrêté du 24 décembre 2015** (logements neufs + accessibilité ascenseurs).
- **Norme NF P 99-611** (accessibilité voirie et espaces publics).

## Règles MVP appliquées (10 contrôles)

### Circulations horizontales

1. **Largeur porte d'accès** ≥ 0.90 m (passage utile 0.83 m). Code : `door_width_min_900mm`.
2. **Largeur couloir** ≥ 1.40 m (couloir circulation). Code : `corridor_width_min_1_4m`.
3. **Largeur palier devant porte** ≥ 1.50 × 1.20 m. Code : `door_landing_min`.

### Circulations verticales

4. **Pente rampe** ≤ 5 % (8 % toléré sur 0.50 m). Code : `ramp_slope_max_5pct`.
5. **Présence ascenseur** dans ERP > R+1 ou habitat collectif > R+2.
   Code : `lift_required_above_2floors`.
6. **Largeur escalier accessible** ≥ 1.20 m + main courante. Code : `stair_width_min_1_2m`.

### Sanitaires et sanitaires accessibles

7. **WC accessible** : 1 cabine PMR par tranche de 10 WC dans ERP. Code : `accessible_wc_ratio`.
8. **Dimensions cabine PMR** : 1.50 × 2.10 m mini (transfert latéral). Code : `pmr_wc_dimensions`.

### Stationnement

9. **Place handicapé** : 2 % des places (mini 1 par 50). Code : `accessible_parking_ratio`.
10. **Largeur place handicapé** ≥ 3.30 m. Code : `accessible_parking_width`.

## Mappings vers les Psets IFC

| Check | Pset IFC source | Property | Seuil |
|---|---|---|---|
| door_width | `IfcDoor.OverallWidth` | (m) | ≥ 0.90 |
| ramp_slope | `Pset_RampCommon` | `Slope` (rad ou %) | ≤ 5 % |
| corridor_width | géométrie `IfcSpace` ou `IfcWallStandardCase` | distance | ≥ 1.40 |
| accessible_wc | `IfcSpace.LongName='WC PMR'` | count | ratio 1/10 |

## Recommandations Plan rénovation

Pour un bâtiment cible PMR :
- **ITE chanvre + pose ouvrants larges** : nouvelles portes 0.93 m (passage 0.87 m).
- **Surélévation accessible** : intégrer un ascenseur léger (Stannah ou équivalent) ou rampes.
- **Salle d'eau PMR** : kit préfabriqué transferts latéraux (Geberit, Pellet).
- **Sols antidérapants** : R10 minimum, R12 dans les zones humides.

## Limites importantes

- **MVP étroit** : 10 contrôles sur ~50 requis pour une attestation PMR complète.
- **Géométrie 3D non vérifiée** : on lit les Psets IFC, pas la cohérence spatiale
  (ex: croisement de rampes, espaces de manœuvre devant chaque porte).
- **Modèles BIM lacunaires** : si l'IFC ne porte pas les Psets PMR, on signale
  "Pset_DoorCommon absent — vérifier manuellement la largeur".
- **Pas de validation contre les CCT (cahier des charges techniques)** d'une opération.

## Citation UI obligatoire

> Pré-vérification PMR ConX — ne remplace pas l'attestation d'accessibilité requise
> par l'article R.111-19-23 du Code de la construction. Pour les ERP, l'attestation
> doit être délivrée par un contrôleur technique agréé ou un architecte indépendant.

## Liens

- Guide PMR ADEME 2022.
- Norme NF P 99-611 "Accessibilité voirie et espaces publics".
- Service Public — https://www.service-public.fr/professionnels-entreprises/vosdroits/F32477
