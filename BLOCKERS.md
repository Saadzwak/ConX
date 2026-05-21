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
