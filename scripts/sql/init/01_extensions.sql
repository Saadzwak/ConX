-- ConX — extensions PostgreSQL requises.
-- Exécuté automatiquement au premier démarrage du container postgres_local.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
-- Fuzzy matching pour le fallback de jointure DPE ↔ BDNB par adresse (cf. D-007)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
