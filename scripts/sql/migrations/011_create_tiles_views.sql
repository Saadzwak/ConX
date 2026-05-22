-- ConX — J7 : vues 4326 pour martin (tuiles vectorielles MVT).
--
-- Martin v1.10+ auto-publie les tables/vues avec une colonne geometry(_, 4326).
-- On crée un schéma 'tiles' dédié pour ne pas exposer toutes les tables public_data
-- en MVT (sécurité + clarté du catalogue).

CREATE SCHEMA IF NOT EXISTS tiles;

-- =============================================================================
-- tiles.buildings_v — vue 4326 des bâtiments avec score + classe pour zoom 14+
-- =============================================================================
-- Utilisée pour les zooms 14+ : polygones extrudés avec couleur scoring et hauteur.
-- Champs minimaux (taille tuile) : id, geom 4326, dept, classe, score précalc, hauteur, type.

DROP VIEW IF EXISTS tiles.buildings_v CASCADE;
CREATE VIEW tiles.buildings_v AS
SELECT
    b.building_id,
    ST_Transform(b.geom, 4326)::geometry(MultiPolygon, 4326) AS geom,
    b.dept,
    b.dpe_classe AS classe,
    b.dpe_source,
    COALESCE(b.hauteur_m, 6.0)::float AS hauteur_m,  -- défaut 6m (pavillon)
    b.type_principal,
    b.type_proprietaire,
    -- Score total recalculé à la volée (poids défaut SCORING.md : 35/25/20/10/10)
    ROUND(
      (0.35 * bs.s_co2 + 0.25 * bs.s_faisa + 0.20 * bs.s_cout
       + 0.10 * bs.s_social + 0.10 * bs.s_passoire) * 100
    )::int AS score_total,
    bs.s_passoire::float AS s_passoire,  -- pour heatmap passoires
    bs.incomplete_data,
    (b.dpe_classe IN ('F', 'G')) AS is_passoire
FROM public_data.buildings b
LEFT JOIN public_data.building_scores bs ON bs.building_id = b.building_id
WHERE b.geom IS NOT NULL;


-- =============================================================================
-- tiles.buildings_centroids_v — centroïdes 4326 pour zooms 10-13
-- =============================================================================
-- Utilisée pour les zooms 10-13 : un point par bâtiment, allégeant la taille de tuile.

DROP VIEW IF EXISTS tiles.buildings_centroids_v CASCADE;
CREATE VIEW tiles.buildings_centroids_v AS
SELECT
    b.building_id,
    ST_Transform(b.centroid, 4326)::geometry(Point, 4326) AS geom,
    b.dept,
    b.dpe_classe AS classe,
    b.dpe_source,
    (b.dpe_classe IN ('F', 'G')) AS is_passoire,
    ROUND(
      (0.35 * COALESCE(bs.s_co2, 0) + 0.25 * COALESCE(bs.s_faisa, 0)
       + 0.20 * COALESCE(bs.s_cout, 0) + 0.10 * COALESCE(bs.s_social, 0)
       + 0.10 * COALESCE(bs.s_passoire, 0)) * 100
    )::int AS score_total
FROM public_data.buildings b
LEFT JOIN public_data.building_scores bs ON bs.building_id = b.building_id
WHERE b.centroid IS NOT NULL;


-- =============================================================================
-- tiles.epci_passoires_heatmap_v — agrégat communal 4326 pour zooms 7-9
-- =============================================================================
-- Utilisée pour la vue régionale : 1 point par commune avec densité de passoires F/G.
-- En attendant l'ingestion EPCI (à faire en J7+), on agrège par commune INSEE.

DROP VIEW IF EXISTS tiles.commune_passoires_heatmap_v CASCADE;
CREATE VIEW tiles.commune_passoires_heatmap_v AS
SELECT
    code_commune_insee,
    dept,
    ST_Transform(ST_Centroid(ST_Collect(geom)), 4326)::geometry(Point, 4326) AS geom,
    count(*)::int AS n_buildings,
    count(*) FILTER (WHERE dpe_classe IN ('F', 'G'))::int AS n_passoires,
    ROUND(
      100.0 * count(*) FILTER (WHERE dpe_classe IN ('F', 'G'))::numeric
      / NULLIF(count(*), 0), 2
    )::float AS pct_passoires
FROM public_data.buildings
WHERE geom IS NOT NULL AND code_commune_insee IS NOT NULL
GROUP BY code_commune_insee, dept;


COMMENT ON SCHEMA tiles IS
  'Vues 4326 publiées par martin pour tuiles MVT (J7). '
  'buildings_v: polygones zoom 14+. buildings_centroids_v: points zoom 10-13. '
  'commune_passoires_heatmap_v: agrégats communaux zoom 7-9.';
