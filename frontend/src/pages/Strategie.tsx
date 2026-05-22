/**
 * Page Mode Stratégie — atterrissage par défaut.
 *
 * Composition :
 * - Barre filtres à gauche (FiltersPanel)
 * - Carte au centre (MapLibre + deck.gl)
 * - Drawer fiche bâtiment à droite (BuildingDrawer)
 * - Barre recherche d'adresse en overlay top-center
 * - Boutons d'export en top-right
 */

import { useCallback, useState } from "react";
import { Download, FileSpreadsheet, Target } from "lucide-react";

import { StrategieMap } from "@/map/StrategieMap";
import { FiltersPanel, type Filters } from "@/components/FiltersPanel";
import { BuildingDrawer } from "@/components/BuildingDrawer";
import { SearchBar } from "@/components/SearchBar";
import { Button } from "@/components/ui/button";
import { type BuildingListItem, exportUrl } from "@/lib/api";
import { WAZEMMES_VIEW } from "@/map/style";

export function StrategiePage() {
  const [filters, setFilters] = useState<Filters>({
    dpeClasses: [],
    typoProprietaire: [],
  });
  const [bbox, setBbox] = useState<[number, number, number, number] | null>(null);
  const [zoom, setZoom] = useState<number>(0);
  const [selected, setSelected] = useState<BuildingListItem | null>(null);

  const onMapMove = useCallback(
    (b: [number, number, number, number], z: number) => {
      setBbox(b);
      setZoom(z);
    },
    [],
  );

  const onSearchPick = useCallback((lon: number, lat: number, _label: string) => {
    // Le map listener du composant carte ré-émet la bbox sur "moveend".
    // On peut piloter via un évènement custom, mais ici on déclenche un fly via
    // un evt window — simple et découplé.
    window.dispatchEvent(
      new CustomEvent("conx:flyto", { detail: { lon, lat, zoom: 18 } }),
    );
  }, []);

  const exportParams = {
    bbox: bbox ?? undefined,
    dpe_classes: filters.dpeClasses.length ? filters.dpeClasses : undefined,
    typo_proprietaire: filters.typoProprietaire.length ? filters.typoProprietaire : undefined,
    annee_max: filters.anneeMax,
    limit: 10_000,
  };

  return (
    <div className="flex-1 flex min-h-0">
      <FiltersPanel value={filters} onChange={setFilters} />

      <div className="flex-1 relative min-w-0">
        {/* Map */}
        <StrategieMap
          bbox={bbox}
          filters={filters}
          onBuildingClick={setSelected}
          onMapMove={onMapMove}
        />

        {/* Overlay top : recherche + exports */}
        <div className="absolute top-3 left-3 right-3 flex items-start justify-between gap-3 pointer-events-none">
          <div className="pointer-events-auto">
            <SearchBar onPick={onSearchPick} />
          </div>
          <div className="pointer-events-auto flex gap-2 items-center">
            <span className="text-xs text-muted-foreground bg-card/95 px-2 py-1 rounded border">
              z={zoom.toFixed(1)}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("conx:flyto", {
                    detail: {
                      lon: WAZEMMES_VIEW.longitude,
                      lat: WAZEMMES_VIEW.latitude,
                      zoom: WAZEMMES_VIEW.zoom,
                    },
                  }),
                )
              }
              title="Vol direct vers le bâtiment vedette démo (D-023)"
            >
              <Target className="h-4 w-4 mr-1" />
              Wazemmes
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={exportUrl("csv", exportParams)} download>
                <FileSpreadsheet className="h-4 w-4 mr-1" />
                CSV
              </a>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={exportUrl("geojson", exportParams)} download>
                <Download className="h-4 w-4 mr-1" />
                GeoJSON
              </a>
            </Button>
          </div>
        </div>

        {/* Hint : zoom trop bas */}
        {zoom > 0 && zoom < 11 && (
          <div className="absolute bottom-3 right-3 max-w-md text-xs bg-card/95 backdrop-blur px-3 py-2 rounded-md shadow-md border">
            <strong>Vue régionale Hauts-de-France</strong> — zoomez jusqu'à un
            quartier (zoom ≥ 11) pour afficher les bâtiments individuels et
            leur scoring.
          </div>
        )}
      </div>

      <BuildingDrawer building={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
