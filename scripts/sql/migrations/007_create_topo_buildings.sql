-- ConX — Migration 007 : table BD TOPO BATIMENT (fallback 3D + cross-validation BDNB).
--
-- D-008 : BD TOPO partout pour vue Stratégie (extrusion hauteur + emprise), LiDAR HD à la demande
-- pour 5-10 bâtiments démo. BD TOPO `BATIMENT` est notre source UNIVERSELLE pour les emprises 3D.
--
-- Différent de public_data.buildings (BDNB) : la BDNB est la référence ConX (rnb_id, dpe, propriétaire),
-- BD TOPO BATIMENT sert pour (1) cross-validation hauteur, (2) tuiles MVT 3D régionales, (3) fallback
-- si BDNB n'a pas d'emprise pour un bâtiment.

CREATE TABLE IF NOT EXISTS public_data.topo_buildings (
    id              bigserial PRIMARY KEY,
    cleabs          text,                         -- identifiant stable IGN (cleabs)
    dept            text NOT NULL,
    nature          text,                         -- 'Indifférenciée', 'Industriel', 'Commercial', etc.
    usage_1         text,                         -- usage principal (Résidentiel / Annexe / etc.)
    usage_2         text,                         -- usage secondaire
    nombre_de_logements int,
    nombre_d_etages int,
    materiaux_des_murs text,
    materiaux_de_la_toiture text,
    hauteur         numeric,                      -- mètres
    altitude_minimale_sol numeric,
    altitude_maximale_sol numeric,
    altitude_minimale_toit numeric,
    altitude_maximale_toit numeric,
    geom            geometry(MultiPolygon, 2154) NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    bdtopo_millesime text
);

CREATE INDEX IF NOT EXISTS idx_topo_buildings_geom ON public_data.topo_buildings USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_topo_buildings_dept ON public_data.topo_buildings (dept);
CREATE INDEX IF NOT EXISTS idx_topo_buildings_hauteur ON public_data.topo_buildings (hauteur) WHERE hauteur IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_topo_buildings_cleabs ON public_data.topo_buildings (cleabs) WHERE cleabs IS NOT NULL;

COMMENT ON TABLE public_data.topo_buildings IS
'Couche BATIMENT de la BD TOPO IGN par département HDF. Ingérée par scripts/ingest_bdtopo.py.
Sources : data.geopf.fr, millésime BDTOPO_MILLESIME (cf. variable env). Licence Etalab 2.0.
Usage : (1) cross-val hauteur BDNB, (2) tuiles MVT 3D régionales, (3) fallback emprise/hauteur si BDNB incomplet.';
