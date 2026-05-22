# ConX — Managed Agents Anthropic (J10)

**Statut** : infrastructure créée sur disque, **aucun agent créé sur Anthropic**
(règle §9.D — aucune dépense sans validation explicite).
**Dernière mise à jour** : 2026-05-22.
**Décisions liées** : D-009 (Skills bundles + HTTP backend pour PostGIS), D-013
(tunnel ngrok pour démo).
**BLOCKERS** : B-001 (TTL session — test à exécuter par le partenaire après création
des agents), B-009 + B-010 (Skills upload).

---

## 1. Architecture (D-009)

3 agents Managed Anthropic + Skills bundles + endpoint HTTP backend pour PostGIS :

```
                       ┌─────────────────────────┐
                       │  Anthropic Cloud         │
                       │  Container managé        │
                       │  ┌─────────────────────┐ │
                       │  │ Agent Sélection     │─┼──── HTTP ────→ Backend FastAPI
  Frontend ─── SSE ───→│  │ skills: scoring    │ │  (via ngrok tunnel)
                       │  └─────────────────────┘ │
                       │  ┌─────────────────────┐ │
                       │  │ Agent Plan          │ │   skills bundles :
                       │  │ skills: carbon-calc,│ │     carbon-calc/, fdes-lookup/,
                       │  │   fdes, horssite,   │ │     horssite-biosource/,
                       │  │   re2020            │ │     re2020-target/
                       │  └─────────────────────┘ │
                       │  ┌─────────────────────┐ │
                       │  │ Agent Conformité    │ │   skills bundles :
                       │  │ env: {pip:ifcopen}  │ │     ifc-check/ (with
                       │  │ skills: ifc, re2020,│ │     ifcopenshell installé),
                       │  │   pmr               │ │     re2020-target/, pmr-checks/
                       │  │ tools: files-api    │ │
                       │  └─────────────────────┘ │
                       └─────────────────────────┘
```

---

## 2. Les 3 agents

### 2.1 Agent Sélection (Mode Stratégie)

- **Mission** : narre le scoring territorial calculé en backend (D-006).
- **Modèle** : `claude-opus-4-7`.
- **Tools** : `agent_toolset_20260401` (bash, file, web_fetch, web_search).
- **Skills** : `selection-scoring` (à créer J10+ post-frontend).
- **Networking** : `allowed_hosts: [${NGROK_PUBLIC_URL_HOST}]` — accès lecture API
  backend uniquement.
- **System prompt** : `agents/system_prompts/selection.md`.

### 2.2 Agent Plan (Mode Projet — chat itératif)

- **Mission** : génère un plan rénovation hors-site biosourcé avec bilan carbone.
- **Modèle** : `claude-opus-4-7`.
- **Tools** : `agent_toolset_20260401`.
- **Skills** : `carbon-calc`, `fdes-lookup`, `horssite-biosource`, `re2020-target`.
- **Networking** : `allowed_hosts: [${NGROK_PUBLIC_URL_HOST}]` — accès lecture fiche
  bâtiment.
- **System prompt** : `agents/system_prompts/plan.md`.
- **⚠ Règle critique** : *"À chaque tour, REGÉNÈRE le plan COMPLET, jamais un diff."*
  (anti-dérive chat — plan §2.5).

### 2.3 Agent Conformité (Validation IFC)

- **Mission** : pré-vérifie un IFC contre RE2020 + PMR (sous-ensemble MVP).
- **Modèle** : `claude-opus-4-7`.
- **Tools** : `agent_toolset_20260401` + `files-api` (upload IFC).
- **Environment** : `packages: {pip: [ifcopenshell]}` — testé OK v0.8.5 (cf. J9).
- **Skills** : `ifc-check`, `re2020-target`, `pmr-checks`.
- **Networking** : aucun — purement local au container (D-009).
- **System prompt** : `agents/system_prompts/conformite.md`.

---

## 3. Fichiers et chemins

```
agents/
  agents.yaml              ← config souhaitée des 3 agents
  skills.yaml              ← (à créer post-upload) mapping nom skill → skill_id
  agents.lock.yaml         ← (généré par sync.py) mapping nom agent → agent_id
  sync.py                  ← synchronisation idempotente create/update
  test_ttl.py              ← test TTL session 10 min (B-001)
  system_prompts/
    selection.md
    plan.md
    conformite.md
```

---

## 4. Procédure pour le partenaire (au matin)

### Pré-requis

1. **Clé API Anthropic** dans `.env` : `ANTHROPIC_API_KEY=sk-ant-...`
2. **Validation dépense** (règle §9.D) : ~ 0.5-1 € pour le test TTL.
3. **Skills uploadées** : voir `docs/SKILLS.md` §5 + résoudre B-010 (bundle flattening).
4. **Tunnel ngrok actif** : `ngrok http 8000` → exporter `NGROK_PUBLIC_URL` dans .env.

### Étapes

```bash
# 1. Upload des Skills (B-009 validé par partenaire)
python -c "$(cat docs/SKILLS.md | sed -n '/```python/,/```/p' | sed '1d;$d')" > skills_uploaded.log
# (Voir docs/SKILLS.md §5 pour le script complet)
# Puis renseigner agents/skills.yaml manuellement avec les IDs retournés

# 2. Vérification dry-run
python agents/sync.py --check

# 3. Création/update effective des 3 agents
python agents/sync.py
# Les agent_ids sont persistés dans agents/agents.lock.yaml

# 4. Test TTL session (B-001)
python agents/test_ttl.py --agent conx-plan --wait-min 10
# Si PASS → on continue J11+
# Si FAIL → activer fallback replay-previous-plan dans J12 backend Mode Projet

# 5. Smoke-test : appel d'un agent
python -c "
import yaml, anthropic, os
lock = yaml.safe_load(open('agents/agents.lock.yaml'))
client = anthropic.Anthropic(
    api_key=os.environ['ANTHROPIC_API_KEY'],
    default_headers={'anthropic-beta': 'managed-agents-2026-04-01,skills-2025-10-02'}
)
s = client.beta.agents.sessions.create(agent_id=lock['agents']['conx-selection'])
client.beta.agents.sessions.events.create(
    session_id=s.id, type='user_message',
    content='Combien de passoires F-G dans le dpt 59 ?'
)
# Wait for idle puis lire les events
"
```

---

## 5. System prompts

Voir `agents/system_prompts/{selection,plan,conformite}.md`.

Principes :
- **Citation systématique des sources** pour chaque chiffre (D-006).
- **Pas d'invention** : "ne calcule jamais, lis le backend ou utilise carbon-calc".
- **Convention signes carbone** explicite (cf. CARBON.md §6).
- **Disclaimers** réglementaires (PMR, RE2020, pré-vérification ≠ BCT).
- **Anti-dérive chat itératif** : *"REGÉNÈRE le plan COMPLET à chaque tour"*.

---

## 6. Test TTL session (B-001)

`agents/test_ttl.py` automatise :
1. Création session sur agent Plan.
2. Envoi msg1 ("plan pour bâtiment X en chanvre").
3. `wait_for(idle)`.
4. `sleep(10 min)`.
5. Vérification : session encore vivante ? (statut ≠ terminated)
6. Envoi msg2 ("et en bois CLT ?").
7. Test : la réponse contient-elle des keywords du msg1 (pavillon, 1965, brique…) ?

Verdict :
- **PASS** : session vivante + contexte rappelé → chat itératif viable nativement.
- **FAIL** : session terminated ou contexte oublié → activer fallback "replay-previous-plan"
  dans J12 backend (re-créer session + injecter le dernier plan en user_message
  avec préfixe explicite).

---

## 7. Limites et coûts

- **Coût création/update agent** : gratuit (config storage).
- **Coût session** : facturé à l'usage Claude Opus 4.7 (~0.20-0.50 € par session
  complète avec génération de plan).
- **Pré-warmup démo** : créer les sessions en amont du pitch (cf. plan §6).
- **Cache fallback** : plan v1/v2 pré-calculés en cache pour le bâtiment vedette
  (au cas où latence Anthropic > 90s).

---

## 8. Limites importantes (non bloquantes)

- **Pas d'agent créé cette nuit** (règle §9.D — coût ≠ engagé sans validation
  partenaire). Toute l'infra est prête, l'exécution se fait au matin.
- **Skills `selection-scoring` à créer en J11** (dépend du backend FastAPI Mode
  Stratégie qui n'existe pas encore).
- **TTL test consomme** ~ 0.5-1 € (validation partenaire). Si refus : on assume
  le fallback "replay-previous-plan" sans le tester côté Anthropic.
