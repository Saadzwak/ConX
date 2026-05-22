import type { StyleSpecification } from "maplibre-gl";

/**
 * Style MapLibre minimaliste avec :
 * - Fond OSM standard (cartoCDN sans clé) pour fallback rapide.
 * - Overlay BD Ortho IGN (WMTS) en streaming pour zoom élevé.
 * - Routes BD TOPO (martin local) pour le contexte voirie.
 */
export const baseStyle: StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    "osm-raster": {
      type: "raster",
      tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxzoom: 19,
    },
    "ign-ortho": {
      type: "raster",
      tiles: [
        // BD Ortho IGN WMTS — clé "ortho" du Géoportail public Etalab 2.0
        "https://data.geopf.fr/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
      ],
      tileSize: 256,
      attribution: "IGN-F/Géoportail (BD Ortho)",
      // IGN BD Ortho s'arrête à z19 sur la plupart du territoire — déclarer
      // maxzoom=19 oblige MapLibre à overscaler les tuiles z19 pour les zooms
      // 20-22 du layer, au lieu de fetcher des z20+ inexistants (404 storm).
      maxzoom: 19,
      minzoom: 0,
    },
  },
  layers: [
    {
      id: "osm-layer",
      type: "raster",
      source: "osm-raster",
      minzoom: 0,
      maxzoom: 11.5,
      paint: { "raster-opacity": 0.85 },
    },
    {
      id: "ign-ortho-layer",
      type: "raster",
      source: "ign-ortho",
      minzoom: 11.5,
      maxzoom: 22,
      paint: { "raster-opacity": 0.95 },
    },
  ],
};

// Hauts-de-France bbox approx (camera de départ)
export const HDF_BOUNDS: [[number, number], [number, number]] = [
  [1.4, 49.0], // SW
  [4.3, 51.1], // NE
];

// Vieux-Lille (vedette FALLBACK D-023) — copro 1930, R+3, 17 logts G
export const VIEUX_LILLE_VIEW = {
  longitude: 3.066,
  latitude: 50.6446,
  zoom: 16,
};

// Wazemmes (vedette PRINCIPAL D-023) — bailleur social 1978 R+3 48 logts F
export const WAZEMMES_VIEW = {
  longitude: 3.0467,
  latitude: 50.6243,
  zoom: 17,
};

// Bâtiment vedette principal (atterrissage Mode Projet par défaut)
export const VEDETTE_BUILDING_ID = "bdnb-bg-81UB-UTZE-ZP7F";
export const VEDETTE_FALLBACK_BUILDING_ID = "bdnb-bg-JBP7-PFQL-4T69";

export const HDF_VIEW = {
  longitude: 2.85,
  latitude: 50.05,
  zoom: 8,
};
