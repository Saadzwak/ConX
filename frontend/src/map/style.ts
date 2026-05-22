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
      maxzoom: 20,
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

// Lille / Vieux-Lille atterrissage final pour la démo
export const VIEUX_LILLE_VIEW = {
  longitude: 3.066,
  latitude: 50.6446,
  zoom: 16,
};

export const HDF_VIEW = {
  longitude: 2.85,
  latitude: 50.05,
  zoom: 8,
};
