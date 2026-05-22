# ConX — Mode Projet (J12)

**Statut** : code livré, **non testé contre Anthropic** (règle §9.D — pas de
dépense engagée cette nuit).
**Décisions** : D-005 (chat itératif), D-009 (Managed Agents), D-011 (split
local/cloud), D-012 (JWT auth), D-013 (ngrok), R13 (anti-dérive chat).

---

## 1. Vue d'ensemble

Mode Projet = un utilisateur clique un bâtiment → l'IA conçoit un plan de
rénovation hors-site biosourcée → chat itératif pour ajuster ("plutôt en
chanvre", "moins cher", "horizon 50 ans"…) → versionnement v1/v2/v3 visible
dans l'UI.

```
Frontend (React)              Backend (FastAPI)              Anthropic
    │                              │                              │
    │  POST /api/agents/plan/start │                              │
    │ {building_id, target,...}    │                              │
    ├─────────────────────────────►│                              │
    │                              │ create_session(conx-plan)     │
    │                              ├─────────────────────────────►│
    │                              │◄──── session_id ─────────────│
    │                              │ send_user_message(prompt)     │
    │                              ├─────────────────────────────►│
    │                              │ INSERT app.agent_sessions    │
    │                              │                              │
    │◄─── {session_id, status} ────│                              │
    │                              │                              │
    │  EventSource /stream         │                              │
    ├─────────────────────────────►│ poll events.list(after=last) │
    │                              ├─────────────────────────────►│
    │                              │                              │
    │◄═══ SSE: agent.message ══════│◄═══ events =================│
    │◄═══ SSE: tool_use ═══════════│                              │
    │◄═══ SSE: session.idle ═══════│                              │
    │                              │                              │
    │  POST /persist {plan_json}   │                              │
    ├─────────────────────────────►│ INSERT app.renovation_plans │
    │                              │   (version = N+1)            │
    │◄──── PlanVersion ────────────│                              │
    │                              │                              │
    │  Turn 2 : POST .../message   │                              │
    ├─────────────────────────────►│ send_user_message            │
    │                              ├─────────────────────────────►│
    │ ...                          │                              │
```

---

## 2. Endpoints

### 2.1 `POST /api/agents/plan/start`

Body :
```json
{
  "building_id": "bdnb-bg-2DMR-G2ZK-ULHZ",
  "target_class": "B",
  "preferences": {"biosource": true, "budget_max": 200000},
  "initial_message": null
}
```

Réponse :
```json
{
  "session_id": "ses_xxx",
  "agent_name": "conx-plan",
  "building_id": "bdnb-bg-2DMR-G2ZK-ULHZ",
  "status": "working",
  "cost_estimate_eur": [0.2, 0.5]
}
```

Le backend :
1. Charge la fiche light (`_fetch_building_light`).
2. Construit un prompt initial (`_build_initial_prompt`) avec la fiche en JSON
   + cible + préférences.
3. Crée la session Anthropic (`create_session`).
4. Envoie le user_message initial (`send_user_message`).
5. Persiste dans `app.agent_sessions` Supabase (avec RLS).

⚠ **COÛT** : ~0.20-0.50 € pour le 1er tour. Affiché dans la réponse.

### 2.2 `POST /api/agents/plan/{session_id}/message`

Envoie un message utilisateur supplémentaire (turn N). Le system prompt de
l'agent (`agents/system_prompts/plan.md`) le contraint à **REGÉNÉRER le plan
COMPLET** (D-005, anti-dérive R13).

Body :
```json
{ "content": "Plutôt en bois CLT à la place du chanvre ?" }
```

Réponse :
```json
{
  "session_id": "ses_xxx",
  "version": 2,
  "cost_estimate_eur": [0.2, 0.5]
}
```

### 2.3 `GET /api/agents/plan/{session_id}/stream` (SSE)

Streame les events Anthropic en temps réel vers le navigateur. Le frontend
ouvre un `EventSource` et consomme :
- `stream.open` : ack ouverture du canal.
- `agent_message` : fragments de réponse de Claude.
- `tool_use` : appels de skills (carbon-calc, fdes-lookup, …).
- `session.idle` : génération terminée — fermer le stream.
- `stream.error` : erreur backend ou Anthropic.
- `stream.timeout` : 5 min écoulées sans `idle` — backend coupe (anti
  runaway).
- `: keepalive` (commentaire SSE) : toutes les 15s pour traverser les
  proxies.

Reconnexion : `?after=<last_event_id>`.

### 2.4 `POST /api/agents/plan/{session_id}/persist`

Appelé par le frontend une fois la génération SSE terminée et le plan parsé
côté UI. Persiste dans `app.renovation_plans` avec la prochaine version
disponible (incrément monotonique par session).

Body :
```json
{
  "user_message": "Plutôt en bois CLT à la place du chanvre ?",
  "plan_json": {
    "strategie": "Rénovation ITE bois CLT...",
    "procedes": [...],
    "materiaux": [...],
    "carbon": {"exploitation": -123, "incorpore": +45, "evite_horssite": -8}
  },
  "carbon_t_total": -86.0,
  "carbon_breakdown": {"exploitation": -123, "incorpore": 45, "evite_horssite": -8}
}
```

### 2.5 `GET /api/agents/plan/{session_id}/history`

Liste toutes les versions persistées dans l'ordre (v1, v2, v3...).

---

## 3. Anti-dérive chat itératif (R13)

Trois gardes :
1. **System prompt verrouillé** (`agents/system_prompts/plan.md`) :
   > À chaque tour utilisateur, **REGÉNÈRE le plan COMPLET** (jamais un diff).
   > Ne préserve du tour précédent que ce que l'utilisateur a explicitement
   > demandé de garder.
2. **Versioning UI** : `v1, v2, v3...` affichés à droite ; bouton "Revenir à
   la v1" cliquable.
3. **Limite 10 tours** côté backend (à coder en J16 côté frontend) +
   message gentil "Pour aller plus loin, démarre une nouvelle session avec
   des préférences précisées."

---

## 4. Schéma Supabase Cloud (D-011)

Voir `scripts/sql/supabase/001_app_schema.sql`. Le partenaire l'exécute via
le SQL editor Supabase (compte propriétaire du projet).

Tables :
- `app.agent_sessions` (PK : session_id Anthropic)
- `app.renovation_plans` (UNIQUE session_id + version)
- `app.ifc_validations` (J13)
- `app.user_preferences`

**RLS activée partout** : policy `*_user_isolation` avec `auth.uid() = user_id`.
Le backend propage le JWT de l'utilisateur au client supabase-py par requête
(cf. `supabase_for_user()`).

**Lien cross-DB** : `app.renovation_plans.building_id` est un `text` libre.
Pas de FK vers `public_data.buildings` (impossible cross-DB). Intégrité gérée
applicativement par le backend (cf. CLAUDE.md §6 "Lien entre les deux bases").

---

## 5. Variables d'environnement

```bash
# Côté Supabase (D-011)
SUPABASE_URL=https://<project_ref>.supabase.co
SUPABASE_ANON_KEY=<anon key publique>
SUPABASE_JWT_SECRET=<HS256 shared secret>
SUPABASE_SERVICE_ROLE_KEY=<admin>     # optionnel — pour scripts internes

# Côté Anthropic (D-009)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BETA=managed-agents-2026-04-01

# Bypass interne (D-013)
INTERNAL_SHARED_TOKEN=<aléatoire>
```

Si **n'importe lequel** de ces secrets est absent ou en placeholder, les
endpoints `/api/agents/*` retournent **503 Service Unavailable** avec un
message clair. Le backend démarre normalement (mode dégradé).

---

## 6. Tests

Tests offline (sans Anthropic, sans Supabase) :

```bash
cd backend
python -m pytest tests/test_agents_client.py tests/test_supabase_client.py -v
# 18 tests, 0 fail
```

Tests d'intégration (à exécuter par le partenaire post-`agents/sync.py` + `B-001`) :

```bash
python agents/test_ttl.py --agent conx-plan --wait-min 10
```

---

## 7. Limites connues J12

- **Non testé contre Anthropic API.** Les signatures du SDK
  (`client.beta.agents.sessions.create`, `events.create`, `events.list`,
  `retrieve`) sont basées sur la doc beta `managed-agents-2026-04-01` et le
  pattern documenté dans `docs/AGENTS.md`. Le partenaire doit valider à
  l'exécution. Si une signature diffère, le wrapper `agents_client.py`
  s'adapte (1 fichier à patcher).
- **Persistance Supabase non testée en intégration.** Tests offline OK,
  intégration validée par le partenaire après run de la migration
  `scripts/sql/supabase/001_app_schema.sql`.
- **SSE polling au lieu de stream natif.** Anthropic propose probablement un
  endpoint `events.stream` (Server-Sent Events) ; on poll
  `events.list(after=last_id)` pour rester compatible avec la doc actuelle.
  Quand le partenaire confirme l'endpoint stream natif, on bascule.
- **Pas de limite de tours côté backend.** À coder J16 (frontend) — affichage
  d'un compteur + message gentil au 11ème tour.
- **Persistance déclenchée par le frontend.** Le backend ne parse pas le
  `plan_json` produit par l'agent ; c'est le frontend qui décide quand
  persister (après réception de `session.idle` SSE + parsing du dernier
  agent_message en markdown structuré).

---

## 8. Liens

- Architecture cloud + local : `CLAUDE.md` §3 + §6.B
- Décisions : `DECISIONS.md` D-005, D-009, D-011, D-012, D-013
- Système prompts : `agents/system_prompts/plan.md`
- Bloqueurs : B-001 (TTL session), B-009 (Skills upload), B-010 (carbon-calc bundle)
