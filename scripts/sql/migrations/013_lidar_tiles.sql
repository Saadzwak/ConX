-- ConX — J8 : table index des dalles LiDAR HD téléchargées + meshes glTF générés.
--
-- Plan §3.4 : on garde les LAZ sur disque (/data/storage/lidar/), on indexe les emprises
-- en PostGIS pour les requêtes "quels bâtiments couvre cette dalle ?".

CREATE TABLE IF NOT EXISTS public_data.lidar_tiles (
    id           bigserial PRIMARY KEY,
    dalle_name   text NOT NULL UNIQUE,                       -- ex: 'LHD_FXX_0700_7050_PTS_C_LAMB93_IGN69'
    emprise      geometry(Polygon, 2154) NOT NULL,
    millesime    text,                                       -- ex: '2023'
    dept         text,                                       -- ex: '59'
    laz_path_local      text,                                -- chemin local relatif /data/storage/lidar/
    laz_size_bytes      bigint,
    laz_downloaded_at   timestamptz,
    gltf_path_local     text,                                -- mesh glTF généré
    gltf_generated_at   timestamptz,
    ign_url      text,                                       -- URL source IGN (trace)
    notes        text
);

CREATE INDEX IF NOT EXISTS idx_lidar_tiles_emprise ON public_data.lidar_tiles USING GIST (emprise);
CREATE INDEX IF NOT EXISTS idx_lidar_tiles_dept ON public_data.lidar_tiles (dept);

COMMENT ON TABLE public_data.lidar_tiles IS
  'Index des dalles LiDAR HD téléchargées (LAZ sur disque + mesh glTF généré). '
  'Plan §3.4 + D-008. Téléchargement à la demande, ~5-10 dalles pré-générées '
  'pour les bâtiments vedettes de démo.';


-- Table associative bâtiment → dalle (1 bâtiment peut être à cheval sur 2 dalles)
CREATE TABLE IF NOT EXISTS public_data.building_lidar (
    building_id  text NOT NULL REFERENCES public_data.buildings(building_id),
    lidar_tile_id bigint NOT NULL REFERENCES public_data.lidar_tiles(id) ON DELETE CASCADE,
    gltf_path_local text,                                    -- mesh glTF spécifique au bâtiment (cropped)
    gltf_size_bytes bigint,
    gltf_generated_at timestamptz,
    PRIMARY KEY (building_id, lidar_tile_id)
);

CREATE INDEX IF NOT EXISTS idx_building_lidar_building ON public_data.building_lidar (building_id);

COMMENT ON TABLE public_data.building_lidar IS
  'Association building ↔ dalle LiDAR + mesh glTF spécifique cropped sur le bâtiment. '
  'Servi par /api/lidar/mesh/<building_id>.gltf (J15).';
