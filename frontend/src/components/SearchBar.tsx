/**
 * Barre de recherche d'adresse globale.
 * Utilise l'API BAN (data.gouv.fr) en autocomplete.
 * Sur sélection, fly-to MapLibre vers le point + zoom 18.
 */

import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { geocodeAddress, type BanFeature } from "@/lib/api";

interface Props {
  onPick: (lon: number, lat: number, label: string) => void;
}

export function SearchBar({ onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<BanFeature[]>([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    if (!q.trim() || q.trim().length < 3) {
      setResults([]);
      return;
    }
    // AbortController : annule la requête en vol au changement de saisie, sinon
    // une réponse lente (« lil ») peut arriver après une plus récente (« lille »)
    // et écraser les bons résultats (race). Le .catch avale l'AbortError + les
    // erreurs réseau (fetch qui throw). Cf. AUDIT M9.
    const ctrl = new AbortController();
    timerRef.current = window.setTimeout(() => {
      geocodeAddress(q, 6, ctrl.signal)
        .then((feats) => {
          if (ctrl.signal.aborted) return;
          setResults(feats);
          setOpen(true);
          setHi(0);
        })
        .catch(() => {
          if (!ctrl.signal.aborted) setResults([]);
        });
    }, 250);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      ctrl.abort();
    };
  }, [q]);

  const pick = (f: BanFeature) => {
    onPick(f.geometry.coordinates[0], f.geometry.coordinates[1], f.properties.label);
    setQ(f.properties.label);
    setOpen(false);
  };

  return (
    <div className="relative w-80">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Adresse, commune, IRIS… (BAN)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setOpen(results.length > 0)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (!open || results.length === 0) return;
            if (e.key === "ArrowDown") {
              setHi((h) => Math.min(h + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              setHi((h) => Math.max(h - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              pick(results[hi]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="w-full h-9 pl-9 pr-3 text-sm rounded-md border border-input bg-card shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      {open && results.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full max-h-80 overflow-auto rounded-md border bg-popover shadow-lg">
          {results.map((f, i) => (
            <li
              key={`${f.properties.label}-${i}`}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(f);
              }}
              onMouseEnter={() => setHi(i)}
              className={`px-3 py-1.5 text-sm cursor-pointer ${
                i === hi ? "bg-accent" : "hover:bg-accent/60"
              }`}
            >
              <div className="font-medium">{f.properties.label}</div>
              <div className="text-xs text-muted-foreground">{f.properties.context}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
