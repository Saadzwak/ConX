-- ConX — Migration Supabase Cloud (free tier) : schéma `app`.
-- Cf. CLAUDE.md §6.B (D-011 — split local/cloud).
--
-- ⚠ Cette migration est destinée à l'INSTANCE SUPABASE CLOUD du partenaire,
-- PAS à postgres_local. Le partenaire l'exécute via le dashboard Supabase
-- (SQL editor) avec son compte propriétaire.
--
-- Tables couvertes :
--   app.agent_sessions      (sessions Anthropic Managed Agents)
--   app.renovation_plans    (plans v1, v2, v3... par chat itératif)
--   app.ifc_validations     (rapports Conformité)
--   app.user_preferences    (poids scoring, favoris, dernière bbox)
--
-- RLS activée sur toutes les tables (D-004) : auth.uid() = user_id.
-- Rôles applicatifs (`collectivite`, `bailleur`, `architecte`, `entreprise`)
-- sont stockés dans `auth.users.raw_app_meta_data->>'role'` et lus depuis le
-- JWT côté backend (cf. backend/app/auth.py).

------------------------------------------------------------------------
-- 1. Schema + extensions
------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS app;
GRANT USAGE ON SCHEMA app TO authenticated, service_role;

-- Pas de PostGIS sur Supabase free (gros add-on). Les géometries vivent
-- côté postgres_local. Les FK cross-DB sont impossibles → on stocke des
-- text 'building_id' libres (cf. CLAUDE.md §6 "Lien entre les deux bases").

------------------------------------------------------------------------
-- 2. agent_sessions
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.agent_sessions (
    session_id        text PRIMARY KEY,                       -- id Anthropic
    agent_name        text NOT NULL CHECK (agent_name IN ('conx-selection','conx-plan','conx-conformite')),
    agent_version     int  NOT NULL DEFAULT 1,
    user_id           uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_query        text,                                   -- snippet du 1er message utilisateur
    building_id       text,                                   -- cible (Plan + Conformité)
    events_log_path_local  text,                              -- /data/storage/agent_events/{session_id}.jsonl
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_id ON app.agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_building_id ON app.agent_sessions(building_id) WHERE building_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_sessions_created_at ON app.agent_sessions(created_at DESC);

ALTER TABLE app.agent_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_sessions_user_isolation
    ON app.agent_sessions FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

------------------------------------------------------------------------
-- 3. renovation_plans (versioning v1/v2/v3 par chat itératif — D-005)
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.renovation_plans (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id     text NOT NULL,                             -- FK logique vers public_data.buildings (local)
    session_id      text NOT NULL REFERENCES app.agent_sessions(session_id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    version         int  NOT NULL,                             -- 1, 2, 3... incrémenté par tour de chat
    plan_json       jsonb NOT NULL,                            -- structure définie par Agent Plan (markdown + bilan + sources)
    carbon_t_total  numeric,                                   -- résultat carbon-calc
    carbon_breakdown jsonb,                                    -- {exploitation, incorpore, evite_horssite}
    user_message    text,                                      -- le prompt utilisateur qui a généré ce tour
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, version)                               -- (session, version) unique → plus simple à incrémenter
);
CREATE INDEX IF NOT EXISTS idx_renovation_plans_user_building ON app.renovation_plans(user_id, building_id);
CREATE INDEX IF NOT EXISTS idx_renovation_plans_created_at ON app.renovation_plans(created_at DESC);

ALTER TABLE app.renovation_plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY renovation_plans_user_isolation
    ON app.renovation_plans FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

------------------------------------------------------------------------
-- 4. ifc_validations
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.ifc_validations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    ifc_filename        text NOT NULL,                         -- nom original utilisateur
    ifc_path_local      text NOT NULL,                         -- /data/storage/ifc/<user_id>/<uuid>.ifc
    re2020_pass         boolean,                               -- null = non analysé encore
    pmr_pass            boolean,
    rapport_pdf_path_local text,                               -- /data/storage/pdf/<user_id>/<uuid>.pdf
    rapport_json        jsonb,                                 -- sortie complète Agent Conformité
    session_id          text REFERENCES app.agent_sessions(session_id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ifc_validations_user_id ON app.ifc_validations(user_id);
CREATE INDEX IF NOT EXISTS idx_ifc_validations_created_at ON app.ifc_validations(created_at DESC);

ALTER TABLE app.ifc_validations ENABLE ROW LEVEL SECURITY;
CREATE POLICY ifc_validations_user_isolation
    ON app.ifc_validations FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

------------------------------------------------------------------------
-- 5. user_preferences (poids scoring, favoris, dernière bbox)
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.user_preferences (
    user_id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    scoring_weights   jsonb,                                   -- {w_co2, w_faisa, ...}
    favoris_building_ids text[],                               -- liste de building_id text
    last_bbox         jsonb,                                   -- [W,S,E,N]
    updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app.user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_preferences_user_isolation
    ON app.user_preferences FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

------------------------------------------------------------------------
-- 6. Helper : trigger qui met à jour `updated_at` automatiquement
------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app._touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_sessions_touch ON app.agent_sessions;
CREATE TRIGGER trg_agent_sessions_touch
    BEFORE UPDATE ON app.agent_sessions
    FOR EACH ROW EXECUTE FUNCTION app._touch_updated_at();

DROP TRIGGER IF EXISTS trg_user_preferences_touch ON app.user_preferences;
CREATE TRIGGER trg_user_preferences_touch
    BEFORE UPDATE ON app.user_preferences
    FOR EACH ROW EXECUTE FUNCTION app._touch_updated_at();

------------------------------------------------------------------------
-- 7. Grants explicites pour le rôle `authenticated`
------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON app.agent_sessions     TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.renovation_plans   TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.ifc_validations    TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.user_preferences   TO authenticated;

-- RLS limite déjà strictement les accès. La policy `*_user_isolation` couvre
-- toutes les opérations (SELECT/INSERT/UPDATE/DELETE) avec auth.uid() = user_id.
