import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { dpeColor, cn } from "@/lib/utils";

const DPE_CLASSES = ["A", "B", "C", "D", "E", "F", "G"] as const;

const PROPRIETAIRES = [
  { id: "bailleur_social", label: "Bailleur social" },
  { id: "personne_morale_privee", label: "Copro / foncière" },
  { id: "particulier", label: "Particulier" },
  { id: "public", label: "Public" },
];

export interface Filters {
  dpeClasses: string[];
  typoProprietaire: string[];
  anneeMax?: number;
}

interface Props {
  value: Filters;
  onChange: (next: Filters) => void;
  totalCount?: number;
}

export function FiltersPanel({ value, onChange, totalCount }: Props) {
  const [anneeMax, setAnneeMax] = useState<string>(
    value.anneeMax !== undefined ? String(value.anneeMax) : "",
  );

  const toggleDpe = (c: string) => {
    const next = value.dpeClasses.includes(c)
      ? value.dpeClasses.filter((x) => x !== c)
      : [...value.dpeClasses, c];
    onChange({ ...value, dpeClasses: next });
  };
  const toggleProp = (id: string) => {
    const next = value.typoProprietaire.includes(id)
      ? value.typoProprietaire.filter((x) => x !== id)
      : [...value.typoProprietaire, id];
    onChange({ ...value, typoProprietaire: next });
  };
  const applyAnnee = () => {
    const n = parseInt(anneeMax, 10);
    onChange({
      ...value,
      anneeMax: Number.isFinite(n) && n > 1000 ? n : undefined,
    });
  };

  const presetPassoires = () => {
    onChange({ ...value, dpeClasses: ["F", "G"] });
  };
  const reset = () => {
    onChange({ dpeClasses: [], typoProprietaire: [], anneeMax: undefined });
    setAnneeMax("");
  };

  return (
    <aside className="w-80 shrink-0 border-r bg-card flex flex-col h-full overflow-hidden">
      <div className="border-b px-4 py-3">
        <h2 className="font-semibold text-sm">Filtres</h2>
        {totalCount !== undefined && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {totalCount.toLocaleString("fr-FR")} bâtiments dans la vue
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
        {/* Presets */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            Préréglages
          </h3>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={presetPassoires}>
              Passoires F-G
            </Button>
            <Button size="sm" variant="ghost" onClick={reset}>
              Réinitialiser
            </Button>
          </div>
        </section>

        {/* DPE */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            Classe DPE
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {DPE_CLASSES.map((c) => {
              const active = value.dpeClasses.includes(c);
              return (
                <button
                  key={c}
                  onClick={() => toggleDpe(c)}
                  aria-pressed={active}
                  className={cn(
                    "h-8 w-8 rounded-md text-xs font-bold border transition-all",
                    active
                      ? "ring-2 ring-offset-1 ring-primary scale-105"
                      : "opacity-70 hover:opacity-100",
                  )}
                  style={{
                    backgroundColor: dpeColor(c),
                    color: c === "C" || c === "D" ? "#000" : "#fff",
                    borderColor: "rgba(0,0,0,0.15)",
                  }}
                >
                  {c}
                </button>
              );
            })}
          </div>
        </section>

        {/* Propriétaire */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            Type propriétaire
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {PROPRIETAIRES.map((p) => {
              const active = value.typoProprietaire.includes(p.id);
              return (
                <Badge
                  key={p.id}
                  variant={active ? "default" : "outline"}
                  className="cursor-pointer select-none"
                  onClick={() => toggleProp(p.id)}
                >
                  {p.label}
                </Badge>
              );
            })}
          </div>
        </section>

        {/* Année max */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            Construit avant
          </h3>
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="ex 1948"
              value={anneeMax}
              onChange={(e) => setAnneeMax(e.target.value)}
              onBlur={applyAnnee}
              onKeyDown={(e) => {
                if (e.key === "Enter") applyAnnee();
              }}
              className="flex-1 h-9 px-2 text-sm rounded-md border border-input bg-background"
            />
            <Button size="sm" variant="outline" onClick={applyAnnee}>
              OK
            </Button>
          </div>
        </section>

        <section className="text-[11px] text-muted-foreground border-t pt-3 leading-relaxed">
          <p>
            Scoring ConX déterministe (5 composantes : CO₂ évité, faisabilité, coût,
            social, passoire). Couleurs = classe DPE officielle ADEME. Taille =
            score (plus grand = plus prioritaire).
          </p>
        </section>
      </div>
    </aside>
  );
}
