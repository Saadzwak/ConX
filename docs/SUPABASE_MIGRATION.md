# ConX — Procédure d'application de la migration Supabase Cloud

**Statut** : migration `001_app_schema.sql` **prête, non appliquée** côté
Supabase Cloud (kvevcricmqijfixsrdpa).

---

## Contexte

Supabase Cloud n'expose **PAS** d'endpoint REST pour exécuter du SQL DDL
arbitraire avec uniquement les credentials API (anon/service_role/JWT_secret).
C'est une décision de sécurité côté Supabase — PostgREST ne fait que CRUD via
les rôles Postgres.

Pour appliquer `scripts/sql/supabase/001_app_schema.sql`, l'une de ces 3 voies
est nécessaire :

### Voie 1 (RECOMMANDÉE) — Mot de passe DB en .env

Le mot de passe Postgres de la base est défini à la création du projet
Supabase. Récupération :

```
Dashboard Supabase → ton projet → Settings → Database → Connection string
```

Le mot de passe apparaît dans la chaîne `postgres://postgres:<PWD>@db.<ref>.supabase.co:5432/postgres`.

Ajouter en `.env` :

```bash
SUPABASE_DB_PASSWORD=<le mot de passe>
```

Puis :

```bash
python scripts/supabase_migrate.py --check         # vérifie connectivité
python scripts/supabase_migrate.py                 # applique toutes les migrations
```

### Voie 2 — Personal Access Token (PAT)

Créer un PAT depuis https://supabase.com/dashboard/account/tokens, puis :

```bash
SUPABASE_PAT=sbp_xxxxxxxxxxxxxxxx
```

Et utiliser l'endpoint Management API `POST https://api.supabase.com/v1/projects/<ref>/database/query`.
(Pas encore implémenté côté ConX — à ajouter si voie 1 indisponible.)

### Voie 3 (DERNIER RECOURS) — SQL Editor manuel

1. Ouvrir https://supabase.com/dashboard/project/kvevcricmqijfixsrdpa/sql/new
2. Copier-coller le contenu de `scripts/sql/supabase/001_app_schema.sql`
3. Cliquer **Run**

---

## Une fois la migration appliquée

Lancer le test de roundtrip RLS :

```bash
python scripts/supabase_rls_roundtrip.py
```

Ce script :
1. Crée 2 users test (`test-a-...@conx.test`, `test-b-...@conx.test`)
2. Génère 2 JWTs HS256 (un par user)
3. INSERT un plan pour User A
4. Vérifie que User B **ne voit pas** ce plan (RLS isole)
5. Vérifie que User B **ne peut pas modifier** ce plan
6. DELETE par User A (sa propre ligne) → OK
7. Cleanup (delete des 2 users)

Sortie attendue : `🎉 RLS roundtrip PASS — l'isolation user_id fonctionne.`

---

## Diagnostic réalisé

Tests faits côté ConX avec les credentials reçus (URL + anon_key +
service_role_key + jwt_secret) :

| Endpoint testé | Résultat |
|---|---|
| `supabase-py admin.list_users()` | ✅ OK — connectivité prouvée |
| `POST /pg/query` | 404 |
| `POST /pg-meta/default/query` | 404 |
| `POST /database/query` | 404 |
| `POST /rest/v1/rpc/exec_sql` | 404 (function not defined) |
| Direct PG `db.<ref>.supabase.co:5432` | Échec auth (JWT ≠ DB password) |

Conclusion : l'authentification API fonctionne (CRUD possible), mais le DDL
nécessite soit le **DB password**, soit un **PAT**, soit le **SQL Editor**.
