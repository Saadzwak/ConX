-- ConX — Migration 010 : extensions de schéma pour J5 ML estimation DPE.
--
-- Ajoute :
-- 1. public_data.buildings.code_commune_insee (feature ML + split spatial obligatoire).
-- 2. public_data.buildings.code_iris (zoom infra-communal, optionnel pour ML).
-- 3. public_data.buildings.dpe_source ('ademe-real' | 'ml-predicted' | NULL) pour tracer l'origine.
-- 4. public_data.dpe : colonnes source + métadonnées ML (model_version, confidence, prediction_date,
--    predicted_classes_top3, clipped) + 4 flags d'anomalie déterministes (cf. SCORING.md J5).
--
-- Décision (D-017 à venir) : ML predictions stockées dans public_data.dpe (pas de table séparée)
-- pour conserver l'unicité de la source DPE par bâtiment. Synthetic identifiant_dpe = 'ml-pred-<bg_id>'.
--
-- Idempotent (IF NOT EXISTS).

-- 1) Colonnes buildings
ALTER TABLE public_data.buildings ADD COLUMN IF NOT EXISTS code_commune_insee text;
ALTER TABLE public_data.buildings ADD COLUMN IF NOT EXISTS code_iris text;
ALTER TABLE public_data.buildings ADD COLUMN IF NOT EXISTS dpe_source text;

CREATE INDEX IF NOT EXISTS idx_buildings_commune ON public_data.buildings (code_commune_insee)
    WHERE code_commune_insee IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_buildings_iris ON public_data.buildings (code_iris)
    WHERE code_iris IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_buildings_dpe_source ON public_data.buildings (dpe_source)
    WHERE dpe_source IS NOT NULL;

-- 2) Backfill dpe_source = 'ademe-real' pour les bâtiments qui ont un DPE BDNB
UPDATE public_data.buildings
   SET dpe_source = 'ademe-real'
 WHERE dpe_classe IS NOT NULL
   AND dpe_source IS NULL;

-- 3) Colonnes dpe pour predictions ML
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'ademe-real';
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS model_version text;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS confidence numeric;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS prediction_date timestamptz;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS predicted_classes_top3 text[];
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS clipped boolean NOT NULL DEFAULT false;

-- 4) Flags d'anomalie (4 règles déterministes ; cf. brief J5)
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS anomaly_rt2012_unexpected boolean NOT NULL DEFAULT false;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS anomaly_re2020_unexpected boolean NOT NULL DEFAULT false;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS anomaly_pac_low_class boolean NOT NULL DEFAULT false;
ALTER TABLE public_data.dpe ADD COLUMN IF NOT EXISTS anomaly_neighborhood_outlier boolean NOT NULL DEFAULT false;

-- 5) CHECK source ∈ {ademe-real, ml-predicted}
ALTER TABLE public_data.dpe DROP CONSTRAINT IF EXISTS dpe_source_check;
ALTER TABLE public_data.dpe ADD CONSTRAINT dpe_source_check
    CHECK (source IN ('ademe-real', 'ml-predicted'));

-- 6) Index sur source pour filtrer rapidement les predictions
CREATE INDEX IF NOT EXISTS idx_dpe_source ON public_data.dpe (source);
CREATE INDEX IF NOT EXISTS idx_dpe_anomaly ON public_data.dpe (building_id)
    WHERE anomaly_rt2012_unexpected OR anomaly_re2020_unexpected
       OR anomaly_pac_low_class OR anomaly_neighborhood_outlier;

COMMENT ON COLUMN public_data.dpe.source IS
'Origine du DPE : ademe-real (BDNB / ADEME) ou ml-predicted (modèle ConX, cf. model_version).';
COMMENT ON COLUMN public_data.buildings.dpe_source IS
'Origine du dpe_classe : ademe-real | ml-predicted | NULL (pas de DPE). Mis à jour après predict.';
