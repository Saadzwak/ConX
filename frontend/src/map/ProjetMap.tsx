/**
 * Mode Projet — vue 3D du bâtiment sélectionné + voisinage.
 *
 * J15 : utilise MapLibre + deck.gl PolygonLayer avec extrusion sur :
 *   - le bâtiment cible (hauteur_m × emprise BDNB depuis /api/buildings/:id)
 *   - les voisins via tiles MVT martin (`buildings_v` schéma `tiles`) servies
 *     déjà par notre stack (fallback extrusion uniforme si pas de hauteur)
 *
 * J15.2 (différé J15.x) : remplacer l'extrusion BDNB par un mesh LiDAR HD
 * glTF chargé via SimpleMeshLayer dès que le partenaire aura téléchargé les
 * 4 dalles VL et que `scripts/lidar_to_gltf.py` aura généré les meshes.
 */

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { PolygonLayer } from "@deck.gl/layers";
import { MVTLayer } from "@deck.gl/geo-layers";

import { baseStyle } from "@/map/style";
import { dpeColor } from "@/lib/utils";
import type { BuildingDetail } from "@/lib/api";

interface Props {
  building: BuildingDetail;
}

export function ProjetMap({ building }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  // Init la map une fois, centrée sur le bâtiment
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle,
      center: [building.centroid.lon, building.centroid.lat],
      zoom: 18,
      pitch: 50,
      bearing: -20,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

    const overlay = new MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay);

    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // (Re)build les layers
  useEffect(() => {
    if (!overlayRef.current) return;
    const targetHeight = building.hauteur_m && building.hauteur_m > 0 ? building.hauteur_m : 9;
    const targetColor = hexToRgb(dpeColor(building.dpe_classe));

    const layers: unknown[] = [];

    // Voisins : MVT depuis martin (mêmes données mais agrégées pour la perf)
    layers.push(
      new MVTLayer({
        id: "neighbors-mvt",
        data: "/tiles/buildings_mv/{z}/{x}/{y}",
        minZoom: 14,
        maxZoom: 22,
        getFillColor: [220, 220, 220, 200],
        getLineColor: [180, 180, 180, 220],
        extruded: true,
        getElevation: (f: { properties?: { hauteur_m?: number } }) =>
          f.properties?.hauteur_m && f.properties.hauteur_m > 0
            ? f.properties.hauteur_m
            : 8,
        material: { ambient: 0.5, diffuse: 0.7, shininess: 8 },
        // On évite de double-dessiner le bâtiment cible
        // (le layer cible sera rendu par-dessus)
        opacity: 0.85,
      }),
    );

    // Bâtiment cible : extrusion colorée par classe DPE
    if (building.geom_geojson?.coordinates?.length) {
      const allRings = building.geom_geojson.coordinates.flatMap((poly) => poly);
      layers.push(
        new PolygonLayer({
          id: "target-building",
          data: allRings.map((ring, i) => ({ ring, idx: i })),
          getPolygon: (d) => d.ring as [number, number][],
          extruded: true,
          getElevation: targetHeight,
          getFillColor: [...targetColor, 240] as [number, number, number, number],
          getLineColor: [20, 20, 20, 255],
          lineWidthMinPixels: 1.5,
          material: { ambient: 0.6, diffuse: 0.85, shininess: 32 },
          pickable: false,
        }),
      );
    }

    // Cast safely: deck.gl typings
    overlayRef.current.setProps({ layers: layers as never });
  }, [building]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />
      {!building.geom_geojson?.coordinates?.length && (
        <div className="absolute top-3 left-3 rounded-md bg-amber-50 border border-amber-200 text-amber-900 text-xs px-3 py-2 max-w-md">
          Géométrie indisponible — extrusion BD TOPO en fallback. Mesh LiDAR HD
          chargé en J15.x (cf. docs/LIDAR_VIEUX_LILLE.md).
        </div>
      )}
    </div>
  );
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}
