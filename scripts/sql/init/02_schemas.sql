-- ConX — schémas applicatifs (postgres_local uniquement).
-- Cf. CLAUDE.md §6.A.

CREATE SCHEMA IF NOT EXISTS public_data;
COMMENT ON SCHEMA public_data IS 'Données publiques massives : BDNB, DPE, BD TOPO, building_scores, lidar_tiles, ml_dpe_versions.';

-- Schéma stub pour les migrations à venir (J2+).
CREATE SCHEMA IF NOT EXISTS staging;
COMMENT ON SCHEMA staging IS 'Tables temporaires d''ingestion (truncate à chaque seed).';
