# ConX — Build log

Journal chronologique des sessions de travail.
Format d'entrée : date, durée réelle vs estimée, ce qui a marché, ce qui a coincé, prochaine étape.

---

## Modèle d'entrée

```
## YYYY-MM-DD — Session N (Jalon JX)

**Durée** : Xh réelles (estimé : Yh)
**Tokens consommés** : ~XXk (si pertinent)
**Objectif** : [ce qu'on voulait faire ce jour-là]

### Ce qui a marché
- [point]

### Ce qui n'a pas marché / contournements
- [point + comment résolu]

### Décisions prises
- [voir DECISIONS.md entrée du jour]

### Bloqueurs ouverts
- [voir BLOCKERS.md]

### Prochaine étape
- [jalon suivant + ce qu'il faut résoudre avant]
```

---

## 2026-05-21 — Session 0 (Pré-implémentation)

**Durée** : ~30 min de préparation documentaire
**Objectif** : Plan validé, 7 points préparatoires demandés par le partenaire (CLAUDE.md, SCORING.md, DATA_SOURCES.md, BUILD_LOG.md, BLOCKERS.md, DECISIONS.md, vérif Supabase + Managed Agents + environnement).

### Ce qui a marché
- Plan technique complet rédigé et validé à 95 % par le partenaire (`~/.claude/plans/brief-projet-plateforme-iridescent-bird.md`).
- Décisions utilisateur capturées : nom produit ConX, périmètre HDF entière, Supabase, chat itératif, Supabase Auth, repo privé.
- Environnement local vérifié : Python 3.12.10, Node 24.6.0, Docker 29.3.1, Docker Compose v5.1.0, Git 2.53, 214.9 GB libres → **tout OK**.
- Supabase Storage : 5 GB par fichier en upload standard → **OK pour LAZ et glTF** (avant pivot D-011).
- Managed Agents `managed-agents-2026-04-01` confirmé actif. Sessions ont 4 statuts (idle/running/rescheduling/terminated), environments persistent jusqu'à archive/delete.

### Ce qui n'a pas marché
- TTL session Managed Agents non documenté explicitement → B-001 (test J10).
- Maturité asyncio `supabase-py` non confirmée → B-002 (test J11, sévérité réduite après D-011).

### Décisions prises
- D-001 à D-010 + ajustements ultérieurs (D-011 split local/cloud, D-012 JWT PyJWT HS256, D-013 ngrok).

### Bloqueurs ouverts post-session
- B-001 (TTL session Managed Agents), B-003 (API INIES).
- B-002 → MINEUR confirmé. B-004 → résolu (déploiement post-concours). B-005 → résolu (PyJWT HS256).

### Prochaine étape
- J1 : setup repo + docker-compose + scripts.

---

## 2026-05-21 — Session 1 (Jalon J1)

**Durée** : ~1 h réelle (estimé : 6 h, mais setup minimal et l'environnement était déjà prêt)
**Tokens consommés** : non mesuré précisément
**Objectif** : Setup repo + docker-compose (postgres_local + PostGIS + backend stub + martin stub) + scripts (download_bdnb, verify_supabase, update_tunnel_url) + CI GitHub Actions + mail INIES rédigé.

### Ce qui a marché
- Structure repo créée : `backend/`, `frontend/` (stub), `scripts/`, `docs/`, `.github/workflows/`, `data/storage/` (volume Docker).
- `docker-compose.yml` validé : `docker compose config` passe sans erreur (3 services : postgres_local, backend, martin).
- Backend stub FastAPI : `GET /api/health` répond `{"status": "ok", ...}`. Test pytest passe (1/1).
- Ruff lint passe (1 fix appliqué : `datetime.timezone.utc` → `datetime.UTC` UP017).
- Ruff format passe (4 fichiers déjà formatés).
- `.gitignore` complet (Python, Node, Docker, data, env, OS).
- `.env.example` complet avec toutes les variables : `POSTGRES_LOCAL_*`, `SUPABASE_*`, `ANTHROPIC_API_KEY`, `AGENT_*_ID`, `NGROK_PUBLIC_URL`, `BACKEND_*`, `BAN_API_URL`, `IGN_WMTS_URL`, `LOG_*`.
- `scripts/verify_supabase_connection.py` : 4 vérifications NON destructives (env présentes, endpoint joignable, JWT décodables, service role lecture admin/users). À lancer par le partenaire avec son `.env` rempli.
- `scripts/download_bdnb.sh` : reprenable (`curl -C -`), 5 départements paramétrables, marker `.done` par fichier. URLs à compléter au premier run (manuellement depuis https://bdnb.io/download/ — le pattern d'URL n'est pas exposé en API).
- `scripts/update_tunnel_url.py` : stub J1, implémentation réelle à J10 quand les agents seront créés.
- CI GitHub Actions : ruff lint + format + pytest + `docker compose config` + `docker compose build`.
- Init PostgreSQL : `01_extensions.sql` (postgis, fuzzystrmatch, pg_trgm, btree_gist) + `02_schemas.sql` (`public_data`, `staging`).

### Ce qui n'a pas marché / contournements
- **URLs de téléchargement BDNB par département non exposées** sur la page data.gouv.fr ni sur la page bdnb.io que j'ai consultée — il faudra une visite manuelle de https://bdnb.io/download/ pour récupérer les URLs exactes et les coller dans `scripts/download_bdnb.sh`. Le script est prêt techniquement, il manque juste les URLs.
- Tests Docker `compose build` non exécuté en local (long, ~5 min) — délégué à la CI.
- `ifcopenshell` n'est PAS encore installé dans le `Dockerfile` du backend (sera ajouté à J9 après le test critique dans le container Anthropic — cf. CLAUDE.md §7).

### Décisions prises
- Aucune nouvelle décision structurante. Applique D-001 à D-013 du jour.
- Choix de stack mineurs documentés dans le code : PostgreSQL 16 + PostGIS 3.4 (image `postgis/postgis:16-3.4`), martin v0.13.0, Python 3.12-slim.

### Bloqueurs ouverts post-session
- B-001 (TTL session Managed Agents, J10).
- B-003 (API INIES — voir mail ci-dessous).

### INIES
Décision **D-014** (2026-05-21) : **pas de demande d'accès API INIES, base statique uniquement** (`data/fdes_static.json` versionné dans le repo). 30 matériaux clés FDES, citation par numéro de déclaration dans l'UI. B-003 résolu. Le mail INIES initialement rédigé a été supprimé de ce log — la décision documentée suffit.

### Prochaine étape
- Téléchargement BDNB : à lancer par le partenaire après complétion des URLs dans `scripts/download_bdnb.sh` (visite manuelle de https://bdnb.io/download/ pour récupérer les URLs exactes par département).
- Vérification connexion Supabase à lancer par le partenaire (`python scripts/verify_supabase_connection.py`) après remplissage du `.env`.
- Sur OK : J2 (ingestion BDNB dans `postgres_local.public_data`).
