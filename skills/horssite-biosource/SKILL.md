---
name: horssite-biosource
description: Catalogue des solutions de rénovation hors-site biosourcées (CD2E, ADEME, retours filière HDF). À utiliser quand l'utilisateur demande des options de plan rénovation, un comparatif de procédés, ou des références concrètes pour des produits biosourcés préfabriqués.
---

# horssite-biosource — Catalogue solutions hors-site biosourcées HDF

## Quand utiliser cette skill

Quand l'agent Plan doit :
- Proposer un plan de rénovation biosourcé avec des solutions concrètes (pas génériques).
- Comparer 2 options (ex: ITE chanvre vs ITE fibre bois) pour un bâtiment donné.
- Référencer un fabricant français/HDF (souveraineté + écologie + circuit court).
- Justifier un choix carbone sur des retours d'expérience.

## Référentiel CD2E

CD2E (https://www.cd2e.com/) coordonne la filière construction écologique en HDF :
- Cluster bâtiment durable.
- Catalogue de produits biosourcés régionaux.
- Référentiels pour la rénovation.

Sources canoniques :
- ADEME — Guide rénovation biosourcée 2023.
- CSTB — Construction hors-site 2023.
- Filière française du chanvre (interchanvre.com), filière paille (RFCP).

## Catalogue (8 procédés clés)

### 1. ITE chanvre projeté (béton de chanvre)
- **Usage** : isolation thermique extérieure de murs maçonnés (brique, pierre, parpaing).
- **Empreinte carbone** : ~-3 kgCO2eq/m² pour 25 cm d'épaisseur (carbone négatif).
- **R obtenu** : 4–5 m².K/W.
- **Préfabrication** : caissons préfabriqués en atelier, pose 30-40 % plus rapide qu'en humide.
- **Fabricants HDF** : Hemp Block (Tilloy), filière chanvre régionale (Audomarois).
- **Cibles bâtiment** : pavillons des années 50-80, immeubles brique.

### 2. ITE panneau ouate de cellulose insufflée (panneau préfabriqué bois)
- **Usage** : façade rapportée bois + ouate insufflée en atelier.
- **Empreinte carbone** : ~+1.8 kgCO2eq/m² (R=5).
- **R obtenu** : 5–7 m².K/W.
- **Préfabrication** : 80 % de gain temps chantier vs traditionnel.
- **Fabricants** : Sytane (Lorraine), AB Construction (Nord).
- **Cibles** : copropriétés F/G post-1948, bailleurs sociaux.

### 3. Mur ossature bois (MOB) préfabriqué avec isolation chanvre
- **Usage** : surélévation, extension, ou bardage rapporté complet.
- **Empreinte carbone** : ~-42 kgCO2eq/m² (FDES collective MOB).
- **R obtenu** : 5–6 m².K/W.
- **Préfabrication** : ~100 % en atelier, pose en grues 1-2 jours pour un pavillon.
- **Fabricants HDF** : Pavibois (Aulnoy), Maisons Cariou, Schmidt Construction.

### 4. ITE paille (botte ou caisson préfabriqué)
- **Usage** : ITE et MOB densifiée. Filière artisanale exigeante.
- **Empreinte carbone** : ~-3.5 kgCO2eq/m² (paille 36 cm).
- **R obtenu** : 7 m².K/W.
- **Préfabrication** : caissons paille-bois (CMB Paille, Picardie).
- **Cibles** : maisons individuelles, ERP de petite taille.

### 5. Isolation soufflée fibre de bois (combles + cloisons)
- **Usage** : combles perdus + parois intérieures.
- **Empreinte carbone** : ~+4.5 kgCO2eq/m² (R=5).
- **R obtenu** : 5–6 m².K/W.
- **Préfabrication** : faible (pose sur site), mais préparation atelier des
  encadrements.

### 6. Triple vitrage à châssis bois local (frêne, douglas HDF)
- **Usage** : remplacement menuiseries bâtiment <1975.
- **Empreinte carbone** : ~25 kgCO2eq/m² (vs alu ~50, PVC ~35).
- **Uw obtenu** : 0.9–1.1 W/m².K.
- **Fabricants** : Menuiseries Riché (Wervicq), Pavillon Bois (Cambrai).

### 7. VMC double-flux préfabriquée + récupérateur de chaleur
- **Usage** : système de ventilation intégré au plan préfabriqué.
- **Empreinte carbone** : ~150 kgCO2eq/équipement (incorporé), gain expl. >>.
- **Performance** : récup 80 %, RT2012/RE2020 compatible.

### 8. PAC air-eau + ECS thermodynamique (système préfabriqué module technique)
- **Usage** : remplacement chaudière fuel/gaz. Module technique préfabriqué hors-site.
- **Empreinte carbone exploitation** : 0.011 kgCO2eq/kWh ep (COP 3).
- **Pose** : 1-2 jours vs 1 semaine en chantier traditionnel.

## Règles de prescription

1. **Diagnostic typologique** : maison individuelle vs collectif → MOB préfa vs ITE
   panneau ouate.
2. **Compatibilité matériau existant** : brique → ITE chanvre OK ; béton armé → MOB +
   isolation rapportée OK ; pisé/pierre → ITE perspirante chanvre/paille obligatoire.
3. **Climat HDF (zone H1a-H1b)** : R cible mur extérieur ≥ 4 m².K/W, toiture ≥ 7.
4. **Budget moyen** : 200-350 €/m² pour ITE chanvre, 350-500 €/m² pour MOB complet.
5. **Délais** : préfa hors-site = 30-80 % de gain vs traditionnel.

## Lien avec le scoring ConX (D-006)

Le scoring `S_faisa` (faisabilité hors-site) intègre déjà le type_compatible (1.0
pavillon, 0.8 collectif, 0.9 tertiaire). L'agent Plan recommande les solutions
ci-dessus en cohérence avec le type du bâtiment.

## Citation UI obligatoire

Quand un produit/fabricant est mentionné, ajouter :
> Source : CD2E filière HDF — référencement non contractuel, demande de devis
> séparée nécessaire.
