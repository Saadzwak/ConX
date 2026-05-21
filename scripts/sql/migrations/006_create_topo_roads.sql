-- ConX — Migration 006 : table BD TOPO routes (TRONCON_DE_ROUTE) pour scoring `acces_chantier`.
--
-- Sert au sous-indicateur S_faisa.acces_chantier (cf. SCORING.md) : on calcule pour chaque
-- bâtiment la distance à la voie carrossable la plus proche + sa largeur. Voies < 4 m d'accès
-- difficile → score réduit.

CREATE TABLE IF NOT EXISTS public_data.topo_roads (
    id              bigserial PRIMARY KEY,
    cleabs          text,                       -- identifiant stable IGN (cleabs)
    dept            text NOT NULL,
    nature          text,                       -- 'Route à 1 chaussée', 'Sentier', 'Type autoroutier', etc.
    importance      text,                       -- 'Locale' / 'Régionale' / 'Nationale' / 'Autoroute'
    largeur_m       numeric,                    -- largeur en mètres
    nombre_de_voies int,
    sens            text,                       -- 'Double sens' / 'Sens direct' / etc.
    nom             text,
    geom            geometry(LineString, 2154) NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    bdtopo_millesime text
);

CREATE INDEX IF NOT EXISTS idx_topo_roads_geom ON public_data.topo_roads USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_topo_roads_dept ON public_data.topo_roads (dept);
CREATE INDEX IF NOT EXISTS idx_topo_roads_largeur ON public_data.topo_roads (largeur_m) WHERE largeur_m IS NOT NULL;

COMMENT ON TABLE public_data.topo_roads IS
'Couche TRONCON_DE_ROUTE de la BD TOPO IGN par département HDF.
Ingéré par scripts/ingest_bdtopo_roads.py depuis les GPKG IGN (data.geopf.fr).
Utilisé par le scoring S_faisa.acces_chantier.';
