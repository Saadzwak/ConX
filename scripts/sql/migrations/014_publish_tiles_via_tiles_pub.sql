-- ConX — 014 : publie les vues matérialisées via un schéma dédié `tiles_pub`.
--
-- Problème (docs/AUDIT_2026-07-07.md C5) : martin auto-publiait TOUT le schéma
-- `tiles`, donc aussi les vues NON matérialisées `*_v` (ST_Transform à la volée
-- sur 3,1 M lignes → jusqu'à 21 s/tuile). Le frontend ne consomme que les `*_mv`.
--
-- Solution : on déplace les 3 matviews (rapides, indexées) dans `tiles_pub` et on
-- pointe martin sur `tiles_pub` uniquement (cf. martin.yaml). Les vues sources
-- `*_v` restent dans `tiles` (non publiées). Déplacement METADATA-ONLY (pas de
-- rebuild des 3,1 M lignes), les index et la dépendance vers `tiles.*_v`
-- (utilisée par REFRESH) sont conservés. source_id martin = nom de table →
-- URLs frontend `/tiles/buildings_mv` inchangées.
--
-- Idempotent : les ALTER ne s'exécutent que si la matview est encore dans `tiles`.

CREATE SCHEMA IF NOT EXISTS tiles_pub;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname='tiles' AND matviewname='buildings_mv') THEN
    ALTER MATERIALIZED VIEW tiles.buildings_mv SET SCHEMA tiles_pub;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname='tiles' AND matviewname='buildings_centroids_mv') THEN
    ALTER MATERIALIZED VIEW tiles.buildings_centroids_mv SET SCHEMA tiles_pub;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname='tiles' AND matviewname='commune_passoires_heatmap_mv') THEN
    ALTER MATERIALIZED VIEW tiles.commune_passoires_heatmap_mv SET SCHEMA tiles_pub;
  END IF;
END $$;
