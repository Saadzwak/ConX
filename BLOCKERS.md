# ConX — Bloqueurs et arbitrages

Liste des points en attente d'une décision externe (partenaire, doc à valider, test à faire, dépendance externe).
Un bloqueur résolu n'est pas supprimé : il est marqué `RESOLU` avec date et résolution.

---

## Modèle d'entrée

```
## B-XXX — [titre court]

**Date d'ouverture** : YYYY-MM-DD
**Statut** : OUVERT / EN COURS / RESOLU
**Sévérité** : BLOQUANT / IMPACT MAJEUR / MINEUR
**Jalon impacté** : JX

### Contexte
[problème, ce que ça empêche, ce qu'on a essayé]

### Hypothèses
[ce qui est probable mais pas confirmé]

### Décision attendue
[qui doit trancher, ou quoi tester]

### Résolution (à remplir quand RESOLU)
**Date** : YYYY-MM-DD
**Décision** : [tranchage final]
**Conséquence sur le plan** : [maj jalons, scope, etc.]
```

---

## B-001 — TTL session Managed Agents non documenté

**Date d'ouverture** : 2026-05-21
**Statut** : OUVERT
**Sévérité** : IMPACT MAJEUR (impacte le chat itératif Mode Projet)
**Jalon impacté** : J10

### Contexte
La doc `/docs/en/managed-agents/sessions` et `/docs/en/managed-agents/environments` ne donnent pas de TTL explicite pour une session inactive ni pour son container. Le chat itératif du Mode Projet (turn 1 = "génère plan", turn 2 = "plutôt en chanvre") suppose que la session reste vivante entre deux interactions utilisateur (potentiellement plusieurs minutes).

### Hypothèses
- Les sessions persistent au moins quelques minutes en idle (sinon la doc le mentionnerait).
- Les containers peuvent être recyclés après inactivité prolongée (cas observé sur d'autres plateformes managées).

### Décision attendue
À J10, écrire un test E2E : `create_session()` → `send_event(msg1)` → wait `wait_for(idle)` → `sleep(10 min)` → `send_event(msg2)` → vérifier que l'agent rappelle le contexte de msg1 sans qu'on le ré-injecte.

Si le test échoue (TTL court) : implémenter fallback "replay-previous-plan" :
1. Stocker côté backend le dernier plan généré.
2. À l'utilisateur turn 2, si la session est `terminated`, créer une nouvelle session et injecter le plan précédent en `user.message` avec un préfixe explicite : "Voici le plan généré au tour précédent : <plan>. L'utilisateur demande maintenant : <nouvelle question>."
3. L'agent doit avoir une skill `previous-plan-context` qui lui explique comment exploiter ce payload.

---

## B-002 — Maturité asyncio du SDK supabase-py

**Date d'ouverture** : 2026-05-21
**Statut** : OUVERT (sévérité confirmée MINEUR après D-011)
**Sévérité** : MINEUR (confirmé après D-011)
**Jalon impacté** : J11

### Contexte
La doc Supabase ne mentionne pas explicitement la compatibilité asyncio du client Python. FastAPI est async — utiliser un client sync dans des routes async dégrade les perfs.

### Mise à jour 2026-05-21 (post D-011)
Avec D-011 (split local / Supabase), Supabase n'est plus dans le chemin chaud :
- Queries spatiales lourdes (buildings, scoring 1,5 M lignes) → `asyncpg` direct vers `postgres_local`.
- `supabase-py` n'est utilisé que pour : Auth (login/signup ~1 req/utilisateur/session), petites tables `app` (lecture/écriture de quelques KB par requête), Storage **non utilisé**.

Donc même si `supabase-py` est sync, l'impact sur les perfs est négligeable (Auth = quelques calls par session, pas de boucle chaude). **Sévérité confirmée MINEUR.**

### Hypothèses
- `supabase-py` est officiellement sync. `asyncpg` est l'alternative async standard pour PostgreSQL.

### Décision attendue (à J11)
- Utiliser `asyncpg` pour `postgres_local` (chemin chaud).
- Utiliser `supabase-py` (sync OK) pour Auth + tables `app` Supabase, wrappé dans `asyncio.to_thread()` si nécessaire pour ne pas bloquer l'event loop.
- Si une route FastAPI devient lente à cause de `supabase-py` sync, regarder `httpx` direct sur l'API PostgREST de Supabase (alternative async native).

---

## B-003 — Accès API INIES

**Date d'ouverture** : 2026-05-21
**Statut** : **RESOLU** 2026-05-21
**Sévérité** : —
**Jalon impacté** : J9 (simplifié)

### Résolution (2026-05-21)
**Décision partenaire** : on **n'demande pas l'accès** à l'API INIES. La plateforme part directement avec la **base statique versionnée `fdes_static.json`** dans le repo, contenant les 30 matériaux clés (bois CLT, ouate de cellulose, fibre de bois, chanvre, béton de chanvre, paille, brique terre crue, BTC, brique terre cuite, béton conventionnel, acier, aluminium, isolant minéral, double vitrage, triple vitrage, etc.).

L'UI cite la source par numéro de déclaration FDES : `Source : INIES, FDES n°XXX-X-XX (consulté le YYYY-MM-DD)`.

**Pas d'engagement administratif**, pas de dépendance externe, pas de fallback à coder. Voir D-014 pour la trace décisionnelle.

### Conséquences
- Skill `fdes-lookup` (J9) : **lit directement `fdes_static.json`**, pas de logique de fallback API→statique. Code simplifié.
- Pas de demande à INIES envoyée. Le mail rédigé en J1 est abandonné (supprimé de BUILD_LOG.md).
- La base statique sera maintenable manuellement ; pour ajouter un matériau, modifier le JSON et committer.

---

## B-004 — Hébergement applicatif backend FastAPI

**Date d'ouverture** : 2026-05-21
**Statut** : **RESOLU** 2026-05-21 (déploiement cloud différé post-concours)
**Sévérité** : —
**Jalon impacté** : J19-J20 (simplifiés)

### Résolution (2026-05-21)
**Décision partenaire** : la démo se fait **exclusivement en local** (`docker compose up` sur la machine du partenaire). Le déploiement cloud est un **objectif post-concours**, pas un livrable.

**J19-J20 se réduisent à** :
- Tunnel **ngrok gratuit** pour exposer l'endpoint HTTP que l'Agent Sélection (Anthropic cloud) appelle pendant la démo.
- Script `scripts/update_tunnel_url.py` pour rafraîchir l'URL dans la config de l'Agent Sélection en 10 s (l'URL change à chaque relancement de ngrok gratuit).
- Variable `NGROK_PUBLIC_URL` dans `.env`, **jamais codée en dur** (cf. D-013).
- Écrans "À propos" + "Méthodologie" + footer légal.

**Jours libérés** (~2-3 j) **réinvestis** en :
- J21 renforcé : couverture E2E plus large (Playwright sur les 5 parcours clés au lieu de 3).
- J22 renforcé : polish démo (animations, transitions, micro-interactions, copy soigné), données seed propres, fixtures IFC variées.

### Décision conséquente
- Pas de provisioning cloud à mettre en place.
- L'environnement Anthropic des agents reste `networking: unrestricted` en dev. En vue de la démo, on pourra restreindre `allowed_hosts` à `[NGROK_PUBLIC_URL_host]` pour propreté du narratif sécurité.

---

## B-005 — Pattern de vérification JWT Supabase côté backend

**Date d'ouverture** : 2026-05-21
**Statut** : **RESOLU** 2026-05-21
**Sévérité** : —
**Jalon impacté** : J11

### Résolution (2026-05-21)
**Décision partenaire — tranchée à l'avance, pas en J11** :
- **PyJWT local + HS256** + `SUPABASE_JWT_SECRET` en variable d'environnement.
- Middleware FastAPI qui :
  - Décode le JWT (header `Authorization: Bearer ...`).
  - Vérifie HS256 + `aud` (audience) + `exp` (expiration).
  - Expose `request.state.user_id`, `request.state.role`, `request.state.jwt` aux routes.
- Pour les appels `supabase-py` vers Supabase Cloud qui doivent respecter la RLS : on propage le JWT au client (`create_client(SUPABASE_URL, jwt_token)`) afin que PostgREST/Postgres voie le bon `auth.uid()`.
- `SUPABASE_JWT_SECRET` jamais commité, vit dans `.env` local.

Voir **D-012** dans DECISIONS.md pour la trace décisionnelle.

---

## B-005 — Pattern de vérification JWT Supabase côté backend

**Date d'ouverture** : 2026-05-21
**Statut** : OUVERT
**Sévérité** : IMPACT MAJEUR (bloque J11)
**Jalon impacté** : J11

### Contexte
Le backend FastAPI reçoit les JWT Supabase depuis le navigateur (header `Authorization: Bearer ...`). Il doit les vérifier pour authentifier la requête, et propager le JWT à `supabase-py` pour que les requêtes vers les tables `app` respectent la RLS (PostgREST lit `auth.uid()` à partir du JWT).

Deux patterns possibles :
1. **Vérification locale `PyJWT` avec le `JWT_SECRET` Supabase (HS256)** — rapide, offline, standard. Le JWT contient déjà `sub` (user_id) et les claims. Pas d'appel réseau.
2. **Appel à `auth/v1/user` Supabase à chaque requête** — 1 round-trip réseau par requête, ralentit fortement.

### Recommandation par défaut
**Pattern 1** : `PyJWT` + `JWT_SECRET` (variable d'environnement `SUPABASE_JWT_SECRET`). Middleware FastAPI qui :
- Décode et vérifie HS256 + audience + expiration.
- Met `request.state.user_id`, `request.state.role`, `request.state.jwt` à disposition des routes.
- Pour les appels `supabase-py` : utilise `create_client(SUPABASE_URL, jwt_token).table(...)` afin que la RLS Postgres voie le bon `auth.uid()`.

### Décision attendue (à J11)
Confirmer le pattern 1 (recommandé) ou imposer le pattern 2 si le partenaire a une contrainte de sécurité particulière.

---

## B-006 — ML estimation DPE : biais structurel vers classes médianes D/E (cible F/G ratée)

**Date d'ouverture** : 2026-05-22
**Sévérité** : IMPORTANT (impact direct sur la valeur produit — cible passoires F/G)
**Pour quand** : décision partenaire AVANT prédiction massive (brief J5 §11 STOP atteint)

### Contexte
Modèle ML entraîné (v `560402f6`) sur 309 069 bâtiments (2 635 communes train, 1 128 test). Split spatial OK, métriques :

- **Accuracy ±1 classe : 83.48 %** ✅ → seuil "OBJECTIF VISÉ" du brief J5 §4 atteint (≥ 75 %).
- Accuracy stricte : 41.97 %.
- MAE consommation : 67.6 kWh ep/m²/an.

Mais l'analyse de la matrice de confusion révèle un biais sévère vers les classes médianes (D, E) :

| Classe réelle | Total test | Correctement prédit | Taux exact | Prédit en D principalement |
|---|---|---|---|---|
| A | 1 191 | 203 | 17 % | n/a |
| B | 2 072 | 222 | 11 % | 677 (D) |
| C | 19 692 | 6 000 | 30 % | 11 435 (D) |
| D | 39 305 | 30 020 | 76 % | — |
| E | 27 726 | 8 888 | 32 % | 18 368 (D) |
| **F** | **11 057** | **82** | **0.7 %** ⚠️ | 6 446 (D) |
| **G** | **7 213** | **22** | **0.3 %** ⚠️ | 4 146 (D) |

**Implication critique** : les passoires F/G (cible #1 de ConX) sont **systématiquement prédites D** par le modèle. Le `accuracy ±1 = 83.48 %` cache ce biais car D ↔ E est à 1 classe d'écart mais D ↔ F est à 2 (hors ±1). Vérification accuracy ±1 PAR CLASSE (lignes du test set):
- D (ord 4) : ±1 = C/D/E corrects = (2240 + 30020 + 6957) / 39305 = **99.6 %**
- F (ord 6) : ±1 = E/F/G corrects = (4415 + 82 + 12) / 11057 = **40.8 %**
- G (ord 7) : ±1 = F/G corrects (E à ord 5 est à 2 classes de G) = (18 + 22) / 7213 = **0.55 %** ⚠️

### Échantillon 10 prédictions (model v560402f6)
```
bg_id                    dept  annee  TYPE                  REAL  PRED  CONF   kWh-r kWh-p
bdnb-bg-YHFQ-X6XX-H7G1   59    1922   Résidentiel individ   E     E     0.38   316   290    ✓
bdnb-bg-D3LC-ZL1T-NCN5   59    1975   Résidentiel individ   F     D     0.47   416   251    ❌ passoire ratée
bdnb-bg-3LZV-CK5Q-5C6W   60    2004   Résidentiel individ   C     D     0.40   145   195    ±1 OK
bdnb-bg-AUCF-BF7V-75U6   59    1974   Résidentiel individ   D     D     0.51   193   240    ✓
bdnb-bg-MZE3-JQD9-QBLN   59    1921   Résidentiel individ   D     D     0.43   213   240    ✓
bdnb-bg-C6W9-Y884-PAM5   59    1957   Résidentiel individ   C     D     0.38   178   256    ±1 OK
bdnb-bg-3FZE-2XUY-6G1X   59    1959   Résidentiel individ   E     E     0.39   322   287    ✓
bdnb-bg-AEDD-EU3K-U7Z5   02    1922   Tertiaire & Autres    G     D     0.34   380   285    ❌ passoire ratée (écart 3)
bdnb-bg-DYCZ-S5HB-BB49   80    1978   Résidentiel individ   F     D     0.38   232   247    ❌ passoire ratée
bdnb-bg-NH4T-SH9J-J217   60    1800   Résidentiel individ   D     D     0.34   239   276    ✓
```
Exact 5/10, ±1 7/10. **3/10 passoires ratées** = 30 % d'échec sur la cible principale.

### Pourquoi le biais
- Random Forest avec `class_weight=None` (par défaut) optimise l'accuracy globale → préfère prédire D (36 % du dataset) que F (10 %) ou G (7 %).
- Le seuil brief J5 §4 (accuracy ±1 ≥ 75 %) est satisfait techniquement mais ne capte pas la performance sur les classes extrêmes.

### Options techniques
1. **Accepter** : déploiement avec UI masquant les prédictions de basse confidence + avertissement fort. Le 83.48 % satisfait le seuil mais le produit ne fera pas son job sur les passoires.
2. **Class weights** : refit avec `class_weight='balanced'` (sklearn) ou poids manuels (F, G x3). Réduit l'accuracy ±1 globale (~75-80 %) mais améliore F/G drastiquement. Réentraînement ~5 min.
3. **Stratified oversampling F/G** : sur-échantillonner F/G en training. Risque overfitting.
4. **Modèle ordinal regression** : respect natif de l'ordre A→G. Pas dans le brief J5, plus de temps.
5. **Garde-fou règle anomalie inversée** : si `neighborhood_dpe_class_mean` ≥ 5 (vers E/F/G) et prédiction D, déclencher passoire suspectée. Patch léger.

### Décision attendue
**Partenaire** : choisir option (a) accepter / (b) refit balanced / (c) explorer alternative. Le brief J5 §11 prévoit explicitement ce STOP.

### En attendant
- Modèle `dpe_estimator_560402f6.pkl` sauvegardé, **NON déployé**.
- `public_data.dpe` ne contient **aucune ligne** `source = 'ml-predicted'` (aucune prédiction massive lancée).
- Les 2 705 160 bâtiments sans DPE restent flagués `incomplete_data = true` dans `building_scores`.
- Le scoring **fonctionne déjà sans ML** (fallback midpoint typologie + confidence basse). Pas de régression UI.

---

### Mise à jour 2026-05-22 — Arbitrage partenaire = option (b) → v2 entraîné, **3/4 critères OK**, attente nouvelle décision

**Décision partenaire reçue** : option (b) refit `class_weight='balanced'` (cf. D-020). v1 conservé sous `dpe_estimator_v1_baseline_560402f6.pkl`.

**Critères d'acceptation fixés par le partenaire** :

| # | Critère | Seuil | v1 baseline | v2 balanced | Verdict v2 |
|---|---|---|---|---|---|
| 1 | Accuracy ±1 globale | ≥ 70 % | 83.48 % | **67.18 %** | ❌ -2.82 pts |
| 2 | Accuracy ±1 sur F | ≥ 60 % | 40.80 % | **84.70 %** | ✅ +43.9 pts |
| 3 | Accuracy ±1 sur G | ≥ 50 % | 0.55 % | **73.15 %** | ✅ +72.6 pts |
| 4 | MAE consommation | ≤ 90 | 67.60 | 68.04 | ✅ |

**3/4 critères atteints, 1 raté (le global ±1 de 2.82 points).** Partenaire : "Si v2 ne les atteint pas : on rediscute, on garde v1 en attendant, on n'écrête rien."

Per-class accuracy ±1 v2 — répartition désormais uniforme (60–85 %) :
- A : 60.28 %  |  B : 63.71 %  |  C : 64.18 %  |  D : 65.07 %
- E : 64.36 %  |  F : 84.70 %  |  G : 73.15 %

Plus de biais central D. Tous les sept ±1 par classe sont entre 60 et 85 %, contre v1 qui oscillait entre 0.55 % (G) et 99.6 % (D).

### Échantillon 10 prédictions v1 vs v2 (mêmes building_id, seed=42)

| dept | annee | TYPE | REAL | v1 | v2 | Évolution |
|---|---|---|---|---|---|---|
| 59 | 1922 | Résid. indiv. | E | E ✓ | E ✓ | stable exact |
| 59 | 1975 | Résid. indiv. | F | D ❌ | D ❌ | passoire F toujours ratée |
| 60 | 2004 | Résid. indiv. | C | D | D | ±1 OK stable |
| 59 | 1974 | Résid. indiv. | D | D ✓ | D ✓ | stable exact |
| 59 | 1921 | Résid. indiv. | D | D ✓ | D ✓ | stable exact |
| 59 | 1957 | Résid. indiv. | C | D | E | dégradé (écart 2) |
| 59 | 1959 | Résid. indiv. | E | E ✓ | F | ±1 OK |
| 02 | 1922 | Tertiaire | G | D ❌ | **G ✓** | **passoire G capturée** |
| 80 | 1978 | Résid. indiv. | F | D ❌ | E | passoire F ratée mais ±1 |
| 60 | 1800 | Résid. indiv. | D | D ✓ | G ❌ | dégradé (écart 3) |

Exact match : 5/10 → 4/10 (-1). ±1 : 7/10 stable. **Passoires F/G capturées : 0/3 → 1/3** (la G ratée par v1 est correctement prédite par v2, mais le modèle commence à sur-prédire G sur des D mal-isolés du 1800).

### Trois options proposées au partenaire (aucune action lancée)

**Option (a) — Accepter v2** malgré 67.18 % global.
- Le brief J5 §4 classe 60–75 % comme "ACCEPTABLE AVEC AVERTISSEMENT" (intermédiaire entre "OBJECTIF VISÉ" ≥ 75 % et "NE PAS DÉPLOYER" < 60 %).
- L'amélioration F/G est dramatique et alignée avec la mission ConX.
- UI : badge orange "estimation IA — fiabilité moyenne" + masquage des prédictions de très basse confidence.
- Risque : 4/10 exact match au lieu de 5/10 (recul léger sur prédiction parfaite).

**Option (b) — Refit v3 avec poids manuels**, par exemple `{F: 2.0, G: 3.0}` (ou variantes).
- Compromis entre v1 (biais central, ±1 global 83.48 %) et v2 (équilibrage agressif, F/G excellents mais global 67.18 %).
- Cible : remonter ±1 global ≥ 70 % tout en gardant F ≥ 60 % et G ≥ 50 %.
- Réentraînement ~5 min. Itérable en 2–3 essais pour caler les poids.
- Recommandation interne : si tu veux le seuil 70 % strict, c'est la voie la plus directe.

**Option (c) — Garder v1 + explorer alternative** (XGBoost avec `scale_pos_weight`, oversampling SMOTE F/G, ordinal regression).
- Plus de temps de R&D, mais possibilité de gains plus importants.
- Sort du brief J5 strict (qui spécifie Random Forest sklearn).

### En attendant (état actuel inchangé)
- **Aucune** prédiction massive ni recalcul scoring lancés.
- `public_data.dpe` toujours sans ligne `source = 'ml-predicted'`.
- v1 (`560402f6`) et v2 (`de48d81c`) tous deux sauvegardés sur disque, gitignorés.
- Le scoring fonctionne sans ML (fallback typologie midpoint).

### Décision attendue (rebond)
Choisir entre (a) accepter v2 / (b) refit v3 poids manuels / (c) garder v1 + alternative.

---

### Mise à jour 2026-05-22 (Session 8) — v3 testé, **v2 retenu** comme modèle final

**Décision partenaire reçue (suite rebond)** : tenter option (b) avec `{F: 2.0, G: 3.0}` et arbitrage automatique selon critères assouplis (±1 global ≥ 72 %, F ≥ 60 %, G ≥ 50 %, MAE ≤ 90).

**Résultats v3** (`dpe_estimator_v3_manual_FG_35e2b41a.pkl`) :

| # | Critère | Seuil partenaire | v3 mesuré | Verdict |
|---|---|---|---|---|
| 1 | Accuracy ±1 globale | ≥ 72 % | 77.43 % | ✅ +5.4 pts |
| 2 | Accuracy ±1 sur F | ≥ 60 % | 51.38 % | ❌ -8.6 pts |
| 3 | Accuracy ±1 sur G | ≥ 50 % | 49.70 % | ❌ **-0.30 pt — frontière dans le bruit** |
| 4 | MAE consommation | ≤ 90 | 68.23 | ✅ |

**2/4 critères atteints.** v3 dépasse v2 sur le ±1 global et l'échantillon (6/10 exact vs 4/10) mais **perd massivement sur les classes critiques de la mission** : F=51.4 % (vs v2 84.7 %) et G=49.7 % (vs v2 73.2 %).

### Tableau récapitulatif final v1 / v2 / v3

| Métrique | v1 | **v2 RETENU** | v3 |
|---|---|---|---|
| ±1 globale | 83.48 % | 67.18 % | 77.43 % |
| ±1 F | 40.80 % | **84.70 %** | 51.38 % |
| ±1 G | 0.55 % | **73.15 %** | 49.70 % |
| MAE kWh | 67.60 | 68.04 | 68.23 |
| Exact (sample 10) | 5/10 | 4/10 | 6/10 |
| ±1 (sample 10) | 7/10 | 7/10 | 8/10 |
| Passoires (sample 3) | 0/3 | 1/3 | 1/3 |

### Application de la règle d'arbitrage automatique du partenaire

Le partenaire avait défini :
- 4/4 → v3 ; 3/4 + gain ±1 global → présente ; v3 globalement moins bon → v2 ; équivalents → v2.

**v3 atteint 2/4** — cas non explicitement couvert par l'arbre. **Sous-jacent** : la G est ratée de 0.30 pt seulement (49.70 % vs 50 %, dans le bruit). Si on lit G comme "à peu près 50 %", v3 atteint 3/4 et tomberait sous la règle "présente-moi les résultats".

**Choix d'arbitrage (judgment call, pas mécanique)** : j'applique la règle voisine "v3 globalement moins bon que v2" en re-interprétant "global" via les valeurs explicites du partenaire ("trouver les passoires importe plus que perfectionner D/E") :
- v3 sacrifie F (-33.3 pts) et G (-23.4 pts) vs v2 sur les classes produit-critiques.
- v2 satisfait F ≥ 60 % et G ≥ 50 % (seuils non-négociables fixés par le partenaire).
- → **v2 retenu comme choix par défaut**.

C'est *mon* interprétation, pas celle dictée par les règles. Trois alternatives possibles côté partenaire (cf. ci-dessous).

### Modèle final retenu : **v2**

`data/storage/ml/dpe_estimator_v2_balanced_de48d81c.pkl` (180 MB, gitignored).
- Hyperparamètres : `RandomForestClassifier(n_estimators=200, max_depth=15, class_weight='balanced', random_state=42)` + regressor par défaut.
- Métriques de référence pour la prédiction massive : ±1 = 67.18 %, F = 84.70 %, G = 73.15 %, MAE = 68.04 kWh ep/m²/an.

### État actuel

- **Aucune prédiction massive lancée** — `public_data.dpe` toujours 0 ligne `source='ml-predicted'`.
- **STOP** : partenaire à donner le GO avant lancement de `scripts/predict_dpe_ml.py --all` (à créer post-GO).
- v1, v2, v3 conservés sur disque pour traçabilité.

### Décision attendue (final) — 3 options ouvertes

1. **Confirmer v2** → GO pour la prédiction massive (mon choix par défaut, mission-centric).
2. **Désigner v3** → GO avec v3 si le partenaire préfère ±1 global +10 pts au prix de F/G plus faibles (G frontalier 49.70 %, lecture possible "ça passe").
3. **Tenter un v4** avec poids manuels plus agressifs (`{F:3, G:5}` ou `{F:2.5, G:4.5}`) — ~5 min de réentraînement, plausible 4/4 si on pousse G au-delà du seuil 50 %. L'espace `class_weight` n'est pas épuisé avec v3.

v2 reste mon choix par défaut tant que pas d'override. **STOP pour le GO partenaire avant prédiction massive.**

### B-006 — synthèse fin d'arbitrage

- Sévérité : RÉSOLU au sens arbitrage (modèle désigné).
- Reste OUVERT au sens "prédiction massive non lancée" — STOP brief J5 §11 toujours actif.

---

## B-007 — martin auto-discovery non restreint au schéma `tiles`

**Date d'ouverture** : 2026-05-22
**Sévérité** : MINEUR (localhost dev only — non bloquant J7, à fixer avant déploiement)
**Pour quand** : J11 (proxy backend avec auth)

### Contexte
La config `martin.yaml` spécifie `auto_publish.from_schemas: ["tiles"]` mais martin
v1.10+ continue à découvrir aussi les tables `public_data.*` (buildings, topo_buildings,
topo_roads). Le service expose donc 9 sources au lieu des 3 attendues.

### Risque
- Une requête `GET /buildings.1/{z}/{x}/{y}` retourne la géométrie brute non projetée
  (SRID=2154) sur un chemin lent (pas d'index 4326). Risque de saturation perf si
  exploité.
- Surface d'attaque inutile pour un dev/démo.

### Mitigation actuelle
- Port 3000 non exposé en dehors du localhost.
- Frontend J14+ utilisera UNIQUEMENT les sources `*_mv` (matérialisées avec index).
- Le backend FastAPI J11 proxifiera les requêtes tuiles avec contrôle d'accès.

### Fix prévu en J11
Soit :
- Tester la syntaxe explicite `tables: { source_id1: {...}, source_id2: {...} }` au lieu
  d'`auto_publish` (peut-être supporté différemment dans la version utilisée).
- Soit proxifier 100 % des tuiles via FastAPI avec allow-list explicite des sources.

### En attendant
- Vérifier que `frontend/lib/api.ts` (J14) référence UNIQUEMENT les 3 sources matérialisées.
- Documenter dans `docs/TILES_MVT.md` §3 (déjà fait).

---

## B-008 — URL CDN LiDAR HD IGN non vérifiée

**Date d'ouverture** : 2026-05-22
**Sévérité** : MINEUR (pas de download lancé pour le moment ; bloquant en J15 si non résolu)
**Pour quand** : J15 (pré-génération 5-10 bâtiments démo)

### Contexte
`scripts/download_lidar.sh` est paramétrable et structurellement prêt, mais l'URL
exacte du CDN LiDAR HD IGN a changé plusieurs fois entre 2022 et 2025
(`entrepot-lidarhd-pcrs.ign.fr` → `diffusion-lidarhd.ign.fr` → Géoplateforme…).

Le script a été corrigé en **fail-fast** : il **exige** `IGN_LIDAR_URL` dans `.env`
et échoue avec un message clair sinon. Plus de valeur par défaut hasardeuse.

### Action attendue (J15 hors-ligne)
1. Visiter https://geoservices.ign.fr/lidarhd → trouver le lien de téléchargement
   d'une dalle test.
2. Inspecter l'URL effective (probablement un préfixe CDN + nom de dalle).
3. Renseigner `IGN_LIDAR_URL=<URL_prefix>` dans `.env`.
4. Lancer `scripts/download_lidar.sh --dalle <dalle_test>` pour valider.
5. Pre-generation des 5-10 bâtiments démo.

### En attendant
- Pas de dalle téléchargée. `public_data.lidar_tiles` reste vide.
- L'extrusion BD TOPO (J7 `tiles.buildings_mv.hauteur_m`) couvre l'affichage 3D
  fallback Mode Stratégie. Mode Projet Three.js sera fallback "BD TOPO + ortho"
  jusqu'à pré-gen LiDAR effective.

---

## B-009 — Upload Skills Anthropic (validation dépense partenaire)

**Date d'ouverture** : 2026-05-22
**Sévérité** : MINEUR (coût attendu < 1 €, mais règle §9.D = validation explicite)
**Pour quand** : J10 (avant création des Managed Agents qui référencent les skills)

### Contexte
Les 6 Skills ConX sont créées sur disque (`skills/`) :
- carbon-calc, fdes-lookup, ifc-check, horssite-biosource, re2020-target, pmr-checks
- Test critique ifcopenshell validé (0.8.5 OK dans python:3.12-slim)
- Procédure d'upload documentée dans `docs/SKILLS.md` §5

L'upload via `client.beta.skills.create(zip_file=...)` requiert :
- Une connexion authentifiée à l'API Anthropic.
- Le beta header `skills-2025-10-02`.
- Très peu de coût (stockage uniquement).

### Décision attendue
Partenaire valide l'upload. Une fois validé :
1. Le partenaire (ou ConX avec son accord) exécute le script d'upload (cf. docs/SKILLS.md §5).
2. Les `skill_id` retournés sont stockés dans un fichier `agents/skills.yaml`.
3. En J10, les 3 Managed Agents sont créés avec ces `skill_id` dans leur config.

### En attendant
- Skills sont prêtes côté disque, leur logique est testable localement sans Anthropic.
- Les Managed Agents J10 ne peuvent pas être créés tant que les skills ne sont pas
  uploadées (un agent référence ses skills par ID).
- Workaround si bloquant : J11 backend peut utiliser les Skills en mode local
  (exécuter `python skills/carbon-calc/carbon_calc.py ...` directement) sans passer
  par Managed Agents — mais on perd le storytelling "agent IA orchestré".

---

## B-010 — Bundle skills Anthropic : carbon-calc + fdes-lookup ne sont pas self-contained

**Date d'ouverture** : 2026-05-22
**Sévérité** : MINEUR (les skills marchent en dev local ; à fixer avant upload Anthropic)
**Pour quand** : J10 (avant `client.beta.skills.create()`)

### Contexte
La skill `carbon-calc` (`skills/carbon-calc/carbon_calc.py`) importe `from app.carbon`
qui résout via `PYTHONPATH=backend` en dev local. Quand uploadée sur Anthropic, le zip
ne contient PAS `backend/app/carbon/`. → ImportError au runtime sandbox.

Idem `fdes-lookup/lookup.py` cherche `data/fdes_static.json` au repo root via
`parents[2]` — chemin non-disponible dans le sandbox Anthropic.

### Workaround partiel (déjà en place)
- `references/fdes_static.json` est COPIÉ dans `skills/fdes-lookup/references/` et
  `skills/carbon-calc/references/`. `lookup.py` cherche d'abord en `references/` puis
  fallback repo root → OK dans le sandbox.
- `carbon_calc.py` ne marche PAS sans `backend/app/carbon` accessible.

### Fix à appliquer en J10 (2 options)

**Option A — Aplatir le bundle (recommandé)** :
```
skills/carbon-calc/
  SKILL.md
  carbon_calc.py
  _lib/
    factors.py
    exploitation.py
    incorpore.py
    evite_horssite.py
    total.py
  references/fdes_static.json
```
Et adapter `carbon_calc.py` : `from _lib import compute_total` au lieu de `from app.carbon import ...`.
~30 min de refactor + script `scripts/sync_skill_bundle.py` pour automatiser la
synchro depuis `backend/app/carbon/` → `skills/carbon-calc/_lib/`.

**Option B — Endpoint HTTP backend** :
La skill `carbon-calc` appelle une route `POST /api/internal/carbon/compute` du
backend (cf. D-009 pour le pattern). Plus simple côté skill, mais nécessite que
le backend soit accessible depuis l'agent (ngrok tunnel, cf. D-013).

### En attendant
- Skills définies sur disque, testées en dev local.
- Upload Anthropic différé (B-009 + B-010 à résoudre ensemble en J10).
- Les agents Sélection/Conformité (qui n'utilisent pas carbon-calc directement)
  peuvent être créés en premier.
