/**
 * Carte Mode Stratégie : MapLibre base map + deck.gl overlay des bâtiments.
 *
 * - Zoom < 11 : pas d'overlay (vue régionale, OSM seul).
 * - Zoom 11-14 : centroïdes ScatterplotLayer colorés par score ConX (à activer
 *   à mesure que martin sert des tuiles d'agrégat — fallback ici sur fetch
 *   `/api/buildings?bbox=...&limit=2000`).
 * - Zoom ≥ 14 : ScatterplotLayer + click pour ouvrir la fiche.
 *
 * Pour J14 init : on consomme `/api/buildings` (scoring server-side) et on
 * affiche un Scatterplot. Les tuiles vectorielles MVT MVTLayer arriveront en
 * J14.5+ si nécessaire pour la perf 1.5 M bâtiments.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer } from "@deck.gl/layers";
import maplibregl from "maplibre-gl";

import { baseStyle, HDF_VIEW } from "@/map/style";
import { type BuildingListItem, listBuildings } from "@/lib/api";
import { dpeColor } from "@/lib/utils";

interface Props {
  bbox: [number, number, number, number] | null;
  filters: {
    dpeClasses: string[];
    typoProprietaire: string[];
    anneeMax?: number;
  };
  onBuildingClick: (b: BuildingListItem) => void;
  onMapMove: (bbox: [number, number, number, number], zoom: number) => void;
}

export function StrategieMap({ bbox, filters, onBuildingClick, onMapMove }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [data, setData] = useState<BuildingListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Init MapLibre une seule fois
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle,
      center: [HDF_VIEW.longitude, HDF_VIEW.latitude],
      zoom: HDF_VIEW.zoom,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
    });
    map.addControl(overlay);

    mapRef.current = map;
    overlayRef.current = overlay;

    const emitMove = () => {
      const b = map.getBounds();
      onMapMove(
        [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
        map.getZoom(),
      );
    };
    map.on("moveend", emitMove);
    map.once("load", emitMove);

    const onFlyto = (ev: Event) => {
      const e = ev as CustomEvent<{ lon: number; lat: number; zoom?: number }>;
      if (!e.detail) return;
      map.flyTo({
        center: [e.detail.lon, e.detail.lat],
        zoom: e.detail.zoom ?? 17,
        duration: 1500,
      });
    };
    window.addEventListener("conx:flyto", onFlyto);

    return () => {
      window.removeEventListener("conx:flyto", onFlyto);
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch buildings quand bbox/filtres changent
  useEffect(() => {
    if (!bbox) {
      setData([]);
      return;
    }
    // Pas de fetch en dehors d'un zoom utile
    const zoom = mapRef.current?.getZoom() ?? 0;
    if (zoom < 11) {
      setData([]);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    listBuildings(
      {
        bbox,
        dpe_classes: filters.dpeClasses.length ? filters.dpeClasses : undefined,
        typo_proprietaire: filters.typoProprietaire.length
          ? filters.typoProprietaire
          : undefined,
        annee_max: filters.anneeMax,
        limit: 2000,
      },
      ctrl.signal,
    )
      .then((resp) => setData(resp.items))
      .catch((e) => {
        if ((e as Error).name === "AbortError") return;
        setError((e as Error).message);
      })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [bbox, filters]);

  // Rebuild deck.gl layers when data changes
  useEffect(() => {
    if (!overlayRef.current) return;
    const layer = new ScatterplotLayer<BuildingListItem>({
      id: "buildings-scatter",
      data,
      getPosition: (d) => [d.centroid.lon, d.centroid.lat],
      getFillColor: (d) => {
        // Couleur DPE pour repère instantané du jury
        const [r, g, b] = hexToRgb(dpeColor(d.dpe_classe));
        return [r, g, b, 220];
      },
      getRadius: (d) => {
        // Taille proportionnelle au score (plus prioritaire → plus gros)
        const s = d.score_total ?? 0;
        return 4 + s * 16;
      },
      radiusUnits: "pixels",
      pickable: true,
      stroked: true,
      lineWidthMinPixels: 0.5,
      getLineColor: [40, 40, 40, 200],
      onClick: (info) => {
        if (info.object) onBuildingClick(info.object as BuildingListItem);
      },
    });
    overlayRef.current.setProps({ layers: [layer] });
  }, [data, onBuildingClick]);

  const statusMsg = useMemo(() => {
    if (error) return `Erreur : ${error}`;
    if (loading) return "Chargement…";
    if (!bbox) return null;
    return `${data.length.toLocaleString("fr-FR")} bâtiments`;
  }, [data, loading, error, bbox]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />
      {statusMsg && (
        <div className="absolute bottom-3 left-3 rounded-md bg-card/95 backdrop-blur px-3 py-1.5 text-xs shadow-md border border-border">
          {statusMsg}
        </div>
      )}
    </div>
  );
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return [r, g, b];
}
