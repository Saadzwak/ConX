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
**Statut** : OUVERT
**Sévérité** : MINEUR (plan B en place)
**Jalon impacté** : J9

### Contexte
INIES propose un web service sur demande d'accès (https://www.inies.fr/le-webservice/demander-un-acces/). Pas de garantie de délai de réponse.

### Hypothèses
- Demande envoyée en J1.
- Si pas de réponse à J9, on bascule sur `fdes_static.json` versionné dans le repo (30 matériaux clés, numéros de déclaration FDES cités dans l'UI).

### Décision attendue (à J9)
- Si accès API obtenu : skill `fdes-lookup` consomme l'API.
- Sinon : skill `fdes-lookup` lit le JSON statique. L'UI cite "Source : INIES, FDES n°XXX-X-XX (consulté le YYYY-MM-DD)".

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
