# ConX — Script de démo (5 min, jury CD2E × EuraTechnologies)

> Document opérationnel pour le pitch. Pas un slide-deck — un protocole technique
> avec timings, narratifs, et fallbacks chiffrés. À relire 1 h avant la démo.

**Dernière mise à jour** : 2026-05-22 (vague finale, post B-001+SUP+J16+J17).
**Quartier vedette** : Wazemmes (Lille, 59) — bâtiment `bdnb-bg-81UB-UTZE-ZP7F`
(R+3, 1978, bailleur social, F, 48 logts, **score 96.1/100**, **1727 tCO₂**).
Fallback : Vieux-Lille candidat B `bdnb-bg-JBP7-PFQL-4T69`. Plan C : Lens centre.

---

## 1. Découpage chronométré (5 minutes)

### Slide 0 — 0:00 → 0:30 — Accroche shock figures

**Écran** : slide titre statique (pas de capture live).

**Discours** :
> "32 millions de bâtiments en France. **35 % sont des passoires énergétiques
> F-G**. 1,5 million rien qu'en Hauts-de-France. La filière n'y arrivera pas
> à la main. ConX combine 6 bases publiques françaises et l'IA Claude Opus
> 4.7 pour identifier et concevoir les rénovations prioritaires, en
> transparence totale. Démo en 4 minutes."

**Timing** : 30 s strict. Pas de question, pas d'interruption.

### Slide 1 — 0:30 → 1:15 — Méthode ConX en 3 chiffres

**Écran** : slide statique avec 3 piliers.

**Discours** :
> "Trois choses font ConX. **Un — les données** : BDNB (CSTB, 32 M
> bâtiments), DPE ADEME (avec coefficient EP électricité 1.9 — aligné avec
> la réforme du **1ᵉʳ janvier 2026**), LiDAR HD IGN, BD TOPO, BD Ortho, BAN.
> Tout en Etalab 2.0. **Deux — la formule** : un score ConX déterministe en 5
> composantes — CO₂ évité, faisabilité, coût, social, intensité passoire.
> Calcul transparent, sources affichées dans l'UI partout où apparaît un
> chiffre. **Trois — l'IA** : Claude Opus 4.7 via Managed Agents Anthropic
> pour concevoir le plan rénovation. Calcul carbone resté déterministe — l'IA
> explique, jamais ne calcule."

**Timing** : 45 s.

### Acte 1 — 1:15 → 1:45 — Mode Stratégie : la région se colore

**Écran** : http://localhost:5173/ (page Stratégie ouverte au chargement).

**Actions** :
1. **1:15** Vue Hauts-de-France entière, zoom 8 (heatmap densité passoires
   par EPCI) — déjà chargée. Pointer : "1,5 million de bâtiments. Heatmap des
   passoires."
2. **1:25** Cliquer le preset "**Passoires F-G**" dans la sidebar gauche. La
   carte se recolore. Filtrer aussi "Bailleur social" en chip.
3. **1:35** Zoom sur Lille → Wazemmes en 2 sauts (double-click sur Wazemmes
   ou utiliser la barre de recherche BAN "Wazemmes, Lille"). Les
   bâtiments individuels apparaissent en scatter coloré par classe DPE.
4. **1:42** Pointer le statut bottom-left : "47 bâtiments F-G dans
   Wazemmes". Survol d'un dot pour montrer le tooltip de score.

**Discours** parallèle :
> "Vue régionale, 1,5 million de bâtiments à l'écran. Filtrons les passoires
> F-G et les bailleurs sociaux. La région se colore là où l'action publique
> doit prioritairement aller. Zoomons sur **Wazemmes**, à Lille — un
> quartier représentatif du parc HLM des années 70."

**Timing** : 30 s. Le mouvement de zoom doit être fluide (MVT tuiles
pré-warmées zoom 11-18, cf. `scripts/prewarm_vl_tiles.py --quartier wazemmes`).

**Latence cible** :
- Chargement initial < 2 s (martin sert depuis matview `tiles.buildings_mv`).
- Filtres réactifs < 100 ms (deck.gl GPU-side filtering).
- Zoom Lille → Wazemmes : 2 s d'animation MapLibre.

### Acte 2 — 1:45 → 3:45 — Mode Projet sur Wazemmes vedette (le WOW)

**Écran** : Cliquer sur le bâtiment vedette `bdnb-bg-81UB-UTZE-ZP7F` directement
sur la carte (il est le plus gros dot du quartier — taille proportionnelle au
score). Le drawer droit s'ouvre.

**Actions** :
1. **1:45** Bâtiment cliqué. Drawer fiche affiche : DPE F (badge orange),
   **score 96.1/100**, badge "DPE réel", 8 stats clés (48 logements, 1978,
   béton, etc.), 5 ScoreBars composantes, **1727 tCO₂** dans le bilan.
2. **1:55** Cliquer "**Ouvrir Mode Projet**" → navigation vers `/projet/...`
   après ~1 s. Le viewer 3D s'affiche avec pitch 50°, le bâtiment cible
   extrudé coloré F (orange-rouge), les voisins en MVTLayer extrudé gris
   clair. **Premier effet wow**.
3. **2:05** Pointer la fiche complète à droite (gauche dans le drawer
   chat) — "*matériau béton 1978, 48 logements, DPE réel certifié ADEME*".
4. **2:15** Cliquer "**Générer un plan rénovation IA**" → le chat s'active.
   Streaming SSE token-par-token visible en direct. **Deuxième effet wow**.
   Pointer : "*L'agent Claude Opus 4.7 réfléchit en temps réel. C'est lui
   qui construit le plan, pas nous qui le récitons.*"
5. **2:55** Le plan v1 est complet (~45 s à 1 min de génération). Pointer
   les sections : "Bilan carbone 3 composantes, sources FDES citées par
   numéro, coût estimé 650 k€."
6. **3:05** Dans l'input chat, taper : "**plutôt en chanvre dominant ?**"
   → Entrée. Nouveau stream, v2 chip apparaît. **Troisième effet wow** :
   chat itératif sur le plan complet.
7. **3:35** Le plan v2 (chanvre) est généré. Pointer les variations vs v1
   (matériaux substitués, carbone recalculé). Cliquer la chip v1 pour
   montrer que l'historique est conservé.

**Discours** parallèle (synchronisé avec les actions) :
> "Un clic sur le bâtiment vedette. Score 96 sur 100. **1 727 tonnes de CO₂
> évitées sur 30 ans** si on rénove cet immeuble. 48 logements de bailleur
> social, années 70 — typique du parc à requalifier en HDF."
>
> [Click Mode Projet] "On bascule en mode atelier. Mesh 3D du bâtiment, ses
> voisins. **L'IA va concevoir le plan rénovation hors-site biosourcé**."
>
> [Click Générer] "**Voilà l'IA qui réfléchit en direct.** Sources FDES,
> bilan carbone, coût. Tout sortie de Claude Opus 4.7. Le calcul carbone
> lui-même reste déterministe — l'IA explique, jamais ne calcule."
>
> [Chat plutôt chanvre] "L'utilisateur peut **converser avec le plan**. Et
> régénérer une variante en chanvre dominant. Tour 2, plan v2, bilan
> recalculé. Chaque version est conservée."

**Timing** : 2 min strict. Si le plan v1 met > 90 s à se générer, on bascule
sur le **plan v1 pré-calculé en cache** (cf. fallback §3).

**Latence cible** :
- Fiche affichée < 800 ms (DB local PostGIS query).
- Viewer 3D rendu < 1.5 s (deck.gl + MVT cached).
- Plan v1 stream : premier token < 5 s, plan complet < 90 s.
- Plan v2 stream : premier token < 5 s, plan complet < 60 s.

### Acte 3 — 3:45 → 4:30 — Mode Conformité IFC

**Écran** : Cliquer sur "Conformité IFC" dans la nav top.

**Actions** :
1. **3:45** Page IFC ouverte. Pointer la zone drop : "*Une entreprise vous
   renvoie sa proposition en IFC, le standard du bâtiment*".
2. **3:50** Drag-and-drop du fichier `docs/demo_assets/ifc/test_re2020_pmr_fail.ifc`
   (prêt à l'avance dans le dossier `Téléchargements` du laptop démo).
3. **4:00** Upload + validation backend (~5 s). Affichage du rapport :
   - Badge RE2020 **OK** (vert), badge PMR **à corriger** (rouge).
   - Summary : 12 walls, 4 doors, 8 windows, 3 spaces.
   - Détail PMR : "**porte n°2** — largeur 0.82 m < seuil 0.90 m".
   - Détail RE2020 : tous les checks passent (Uw, R isolation).
4. **4:20** Cliquer "**PDF**" → ouverture rapport téléchargé dans onglet
   navigateur. Pointer la mise en page sobre, sources INIES, mention "*Pré-
   vérification — ne remplace pas un BCT*".

**Discours** :
> "Mode Conformité. Drag-and-drop d'un fichier IFC. Cinq secondes plus tard,
> **rapport automatisé** : RE2020 OK, **PMR à corriger** — la porte 2 fait
> 82 cm, le seuil est 90 cm. PDF généré, prêt à signer. Pré-vérification —
> on ne remplace pas un bureau de contrôle agréé."

**Timing** : 45 s.

### Closing — 4:30 → 5:00 — Transparence + roadmap

**Écran** : retour Mode Stratégie ou slide closing.

**Discours** :
> "**Données 100 % publiques** : IGN, CSTB BDNB, ADEME, INIES, DGFiP, BAN
> — Etalab 2.0 partout. **IA Claude Opus 4.7** via Anthropic. **Code source
> ConX** : produit complet, frontend deck.gl + MapLibre + Tailwind, backend
> FastAPI + PostGIS, IA Managed Agents avec Skills versionnées, RLS Supabase.
> **Post-concours** : intégration BIM standardisée, partenariats bailleurs,
> élargissement à toutes les régions françaises. Merci."

**Timing** : 30 s. Fin pile à 5:00.

---

## 2. Fallbacks étape par étape

### Si le plan IA met > 90 s à se générer en live (acte 2)
1. **Détection** : timer JS affiche un compteur visible. À 90 s, le bouton
   "**Utiliser plan v1 cache**" apparaît dans le drawer chat.
2. **Action** : cliquer le bouton → le composant `PlanChat` lit
   `./docs/demo_assets/cached_plans/bdnb-bg-81UB-UTZE-ZP7F_v1.json` via la route
   backend `/api/agents/plan/cached/:building_id/:version` (chemins de
   recherche dans `agents.py::get_cached_plan` : docs/demo_assets puis
   data/storage, host puis container) et affiche le plan instantanément.
3. **Narratif** : "*Le plan v1 que ConX a généré ce matin sur ce même
   bâtiment. Démo offline pour la rigueur.*" — Pas de honte, c'est cohérent
   avec un mode "preview" ou un cache de prévisualisation.

### Si Anthropic plante complètement (réseau, rate-limit, API down)
1. **Détection** : `startPlanSession` retourne 503 ou network error.
2. **Action** : afficher un toast "*L'API IA est en attente — utilisation du
   cache pré-calculé*" + charger plan v1 cache local automatiquement.
3. **Narratif** : "*Cache pré-calculé pour la démo. En production le plan se
   régénère à la demande, mais on a fait nos devoirs.*"

### Si le chat v2 (plutôt chanvre) plante
1. **Détection** : `sendPlanMessage` timeout > 90 s ou error.
2. **Action** : charger `bdnb-bg-81UB-UTZE-ZP7F_v2.json` depuis le cache local.
   v2 chip s'affiche normalement, plan v2 cache.
3. **Narratif** : invisible côté jury (même bascule silencieuse que cas 2).

### Si Wazemmes plante visuellement (carto ou backend lent)
1. **Détection** : la fiche `bdnb-bg-81UB-UTZE-ZP7F` met > 3 s à charger ou
   ne charge pas.
2. **Action** : URL alternative `/projet/bdnb-bg-JBP7-PFQL-4T69` (Vieux-Lille
   candidat B fallback). Bâtiment équivalent narratif, score 91.1, 714 tCO₂.
3. **Narratif** : "*On va sur un autre exemple — copro privée en cœur
   historique de Lille. Même méthode, narrative différente.*"

### Si tout Lille plante
1. **Détection** : impossible de charger la carte Lille / Wazemmes / VL.
2. **Action** : navigation vers `/strategie?bbox=2.825,50.41,2.85,50.44`
   (Lens centre). Carto fonctionne, score sur les bâtiments, **mais pas de
   plan IA en cache local** sur Lens. Si le plan IA fonctionne en live → on
   continue. Sinon → bascule à un screenshot de plan IA généré ce matin.
3. **Narratif** : "*Lens, terrain historique post-minier. Notre méthode
   passe à l'échelle.*"

### Si IFC upload échoue (acte 3)
1. **Détection** : upload bloque ou retourne 500.
2. **Action** : ouvrir directement le PDF
   `./docs/demo_assets/ifc/sample_ifc_report.pdf` dans un onglet du
   navigateur (préchargé en cache).
3. **Narratif** : "*Voici un rapport déjà généré ce matin sur le même
   fichier — même structure.*"

---

## 3. Checklist pré-démo (30 min avant le pitch)

Cocher chaque ligne. Si une ligne échoue, **ne pas lancer la démo en live**.

### Stack en marche
- [ ] `docker compose ps` → 3 services healthy (postgres_local, backend, martin)
- [ ] `curl -s http://localhost:8000/api/health` → `{"status":"ok",...}`
- [ ] `curl -s http://localhost:3000/catalog` → liste tiles incluant `buildings_mv`
- [ ] `curl -s http://localhost:5173/` → HTML Vite (frontend en `npm run dev` actif)

### ngrok tunnel (si agents Sélection l'utilisent côté Anthropic)
- [ ] `ngrok http 8000` lancé dans un terminal séparé
- [ ] URL ngrok propagée dans `.env` (`NGROK_PUBLIC_URL=...`) → `python scripts/update_tunnel_url.py`
- [ ] `curl https://<ngrok-url>/api/health` répond OK depuis l'extérieur

### Caches IA et tuiles
- [ ] Précalcul fait : `ls docs/demo_assets/cached_plans/` doit contenir 3 fichiers (committés en repo) :
  - `bdnb-bg-81UB-UTZE-ZP7F_v1.json` (Wazemmes v1)
  - `bdnb-bg-81UB-UTZE-ZP7F_v2.json` (Wazemmes chanvre)
  - `bdnb-bg-JBP7-PFQL-4T69_v1.json` (Vieux-Lille fallback)
- [ ] MVT Wazemmes zoom 11-18 chaud : `python scripts/prewarm_vl_tiles.py --quartier wazemmes`
- [ ] MVT Vieux-Lille zoom 14-18 chaud : `python scripts/prewarm_vl_tiles.py --quartier vieux-lille`
- [ ] Bâtiment vedette Wazemmes affiché dans le browser pour cacher localement :
  - navigateur → http://localhost:5173/projet/bdnb-bg-81UB-UTZE-ZP7F (laisser charger entièrement, fermer)
  - idem `/projet/bdnb-bg-JBP7-PFQL-4T69`

### Assets démo
- [ ] Fichier IFC test `docs/demo_assets/ifc/test_re2020_pmr_fail.ifc` présent (committé en repo)
- [ ] Copie locale du PDF rapport fallback `docs/demo_assets/ifc/sample_ifc_report.pdf` (committé en repo)
- [ ] Slides titre + closing chargés en plein écran sur un 2ᵉ écran ou onglet

### Session Anthropic warm
- [ ] (Optionnel, à 5 min du pitch) Lancer 1 fois Mode Projet sur Wazemmes
  pour que le warmup containers Anthropic soit fait → la 1ère vraie génération
  pendant la démo sera ~30 % plus rapide.

### Sécurité réseau démo
- [ ] Wi-Fi salle testé OK (latence < 200 ms vers api.anthropic.com).
- [ ] 4G mobile en backup connecté au laptop (au cas où le Wi-Fi salle plante).

---

## 4. Latences cibles (résumé)

| Étape | Cible | Acceptable | Fallback déclenché si |
|---|---|---|---|
| Chargement initial Stratégie | < 2 s | < 4 s | > 6 s → recharger page |
| Filtre passoires | < 100 ms | < 300 ms | > 1 s → screenshot |
| Zoom Lille → Wazemmes | 1.5-2 s | < 3 s | > 5 s → recharger |
| Fiche bâtiment | < 800 ms | < 1.5 s | > 3 s → fallback `/projet/...` |
| Plan IA v1 stream | premier token < 5 s | < 10 s | > 90 s plan complet → cache |
| Plan IA v2 stream | premier token < 5 s | < 10 s | > 90 s → cache |
| IFC upload + validation | < 7 s | < 15 s | > 20 s → PDF préchargé |
| PDF download | instant | < 2 s | > 5 s → fichier local |

---

## 5. Plans B et C (rappel D-023)

| Niveau | Quartier | Bâtiment | Quand le déclencher |
|---|---|---|---|
| A — Principal | Wazemmes | `bdnb-bg-81UB-UTZE-ZP7F` | défaut |
| B — Fallback | Vieux-Lille | `bdnb-bg-JBP7-PFQL-4T69` | Si Wazemmes plante visuellement |
| C — Plan C | Lens centre | (carto seule) | Si tout Lille plante |

---

## 6. Phrases-clés à mémoriser (citables si le jury creuse)

- "Score ConX **96 sur 100** — plus de neuf sur dix selon notre indice."
- "**1 727 tonnes de CO₂ évitées sur 30 ans** — équivalent du carbone routier
  d'une voiture neuve sur 30 ans, multiplié par 170."
- "**48 logements** dans un seul immeuble — densité d'impact par opération."
- "**Coefficient EP électricité 1.9** — DPE aligné avec la réforme du 1ᵉʳ
  janvier 2026."
- "**Six bases publiques** : BDNB, DPE ADEME, LiDAR HD, BD TOPO, BD Ortho,
  BAN. **Une seule licence : Etalab 2.0**."
- "Le **scoring est déterministe** — l'IA explique, l'IA jamais ne calcule
  les chiffres."
- "**Claude Opus 4.7** — l'IA la plus récente d'Anthropic, accédée via
  Managed Agents."
- "**Skills versionnées** — chaque agent a son catalogue de procédés
  rénovation hors-site, carbone, FDES, RE2020, PMR."

---

## 7. Questions probables du jury (anticipées)

**Q1** : *Comment vous garantissez la fiabilité du chiffre 1727 tCO₂ ?*
> "Calcul déterministe sur 3 composantes — exploitation (Base Carbone ADEME),
> incorporé (FDES INIES par matériau, statique versionnée 30 matériaux clés),
> évité hors-site (fraction CSTB 25 %). Toutes les formules dans
> `docs/SCORING.md` et `docs/CARBON.md` du repo. L'IA ne calcule pas — elle
> explique."

**Q2** : *Pourquoi Claude Opus et pas un modèle français ?*
> "Mistral Large évalué en parallèle pour la rénovation, on a retenu Opus
> 4.7 pour la qualité du raisonnement sur des problèmes structurés
> (FDES, RE2020). L'architecture reste agnostique — Skills + system prompts
> sont portables. Post-concours, on benchmark sur des sorties française
> souveraine."

**Q3** : *Et si Wazemmes a déjà été rénové ?*
> "Le score est mis à jour à chaque millésime BDNB (annuel). Si Wazemmes a
> été rénové en 2027, le DPE bascule en C ou D, le score chute, le bâtiment
> sort des priorités. Le scoring est dynamique."

**Q4** : *Vos données BDNB sont à jour ?*
> "Millésime **2025-07.a** (juillet 2025), le plus récent à ce jour. Pipeline
> d'ingestion paramétrable pour le millésime suivant."

**Q5** : *RGPD / souveraineté des données ?*
> "Données BDNB/DPE/IGN/BAN restent **en local** (postgres_local Docker), pas
> de fuite cloud étranger. Seuls les projets utilisateurs (plans rénovation
> générés) sont stockés sur Supabase (UE, RGPD-compatible). Anthropic Managed
> Agents traite les requêtes sur leur cloud avec une politique data ZDR
> activable. Pour un déploiement public sectoriel, on bascule sur self-hosted
> sandbox."

---

## 8. Post-mortem (à remplir après le pitch)

Section laissée vide intentionnellement. À remplir post-pitch pour
capitaliser :

- Ce qui a marché en live :
- Ce qui a posé problème :
- Questions reçues (et réponses données) :
- Réactions jury :
- Prochaines étapes immédiates :
