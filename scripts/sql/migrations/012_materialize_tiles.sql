-- ConX — J7 perf : matérialise les vues tiles en tables avec index GIST 4326.
-- Migration 011 a créé les vues. Performance martin trop lente sans index sur ST_Transform.
-- Solution : MATERIALIZED VIEW + index GIST sur geom (4326).
-- À refresh après la prédiction massive ML (script refresh_tiles_matviews.py).

-- =============================================================================
-- tiles.buildings_mv — polygones 4326 zoom 14+
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS tiles.buildings_mv CASCADE;
CREATE MATERIALIZED VIEW tiles.buildings_mv AS SELECT * FROM tiles.buildings_v WITH NO DATA;

CREATE INDEX idx_buildings_mv_geom ON tiles.buildings_mv USING GIST (geom);
CREATE INDEX idx_buildings_mv_dept ON tiles.buildings_mv (dept);
CREATE INDEX idx_buildings_mv_score ON tiles.buildings_mv (score_total);
CREATE INDEX idx_buildings_mv_passoire ON tiles.buildings_mv (is_passoire);
-- PK explicite pour pouvoir faire REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX idx_buildings_mv_pk ON tiles.buildings_mv (building_id);


-- =============================================================================
-- tiles.buildings_centroids_mv — points 4326 zoom 10-13
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS tiles.buildings_centroids_mv CASCADE;
CREATE MATERIALIZED VIEW tiles.buildings_centroids_mv AS SELECT * FROM tiles.buildings_centroids_v WITH NO DATA;

CREATE INDEX idx_buildings_centroids_mv_geom ON tiles.buildings_centroids_mv USING GIST (geom);
CREATE INDEX idx_buildings_centroids_mv_dept ON tiles.buildings_centroids_mv (dept);
CREATE INDEX idx_buildings_centroids_mv_passoire ON tiles.buildings_centroids_mv (is_passoire);
CREATE UNIQUE INDEX idx_buildings_centroids_mv_pk ON tiles.buildings_centroids_mv (building_id);


-- =============================================================================
-- tiles.commune_passoires_heatmap_mv — agrégats communaux zoom 7-9
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS tiles.commune_passoires_heatmap_mv CASCADE;
CREATE MATERIALIZED VIEW tiles.commune_passoires_heatmap_mv AS
  SELECT * FROM tiles.commune_passoires_heatmap_v WITH NO DATA;

CREATE INDEX idx_commune_passoires_mv_geom ON tiles.commune_passoires_heatmap_mv USING GIST (geom);
CREATE INDEX idx_commune_passoires_mv_dept ON tiles.commune_passoires_heatmap_mv (dept);
CREATE UNIQUE INDEX idx_commune_passoires_mv_pk ON tiles.commune_passoires_heatmap_mv (code_commune_insee);


-- =============================================================================
-- Note : POPULATION initiale via REFRESH (séparée pour éviter timeout migration).
-- Lancer après la prédiction massive ML + recalcul scoring :
--   REFRESH MATERIALIZED VIEW tiles.buildings_mv;
--   REFRESH MATERIALIZED VIEW tiles.buildings_centroids_mv;
--   REFRESH MATERIALIZED VIEW tiles.commune_passoires_heatmap_mv;
-- (Ou via scripts/refresh_tiles_matviews.py)
-- =============================================================================

COMMENT ON MATERIALIZED VIEW tiles.buildings_mv IS
  'Polygones 4326 + score précalculé pour MVT zoom 14+. Refresh après recalcul scoring.';
COMMENT ON MATERIALIZED VIEW tiles.buildings_centroids_mv IS
  'Centroïdes 4326 pour MVT zoom 10-13.';
COMMENT ON MATERIALIZED VIEW tiles.commune_passoires_heatmap_mv IS
  'Agrégats communaux 4326 pour heatmap zoom 7-9.';
