/**
 * Drawer latéral droit : fiche bâtiment résumée + lien Mode Projet.
 * Affiche les indicateurs ConX (score, CO₂ évité, coût, DPE) + sources.
 */

import { X, ExternalLink, BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { dpeColor, cn } from "@/lib/utils";
import { type BuildingListItem } from "@/lib/api";

interface Props {
  building: BuildingListItem | null;
  onClose: () => void;
}

export function BuildingDrawer({ building, onClose }: Props) {
  if (!building) return null;
  const score = building.score_total ?? 0;
  const dpe = building.dpe_classe ?? "?";
  const dpeSource =
    building.dpe_source === "ademe-real"
      ? { label: "DPE réel ADEME", tone: "default" as const }
      : { label: "DPE estimé IA", tone: "secondary" as const };

  return (
    <aside className="w-96 border-l bg-card shrink-0 flex flex-col overflow-hidden">
      <div className="border-b px-4 py-3 flex items-start justify-between">
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">{building.dept ? `Dpt ${building.dept}` : ""}</div>
          <h3 className="font-semibold text-sm break-words leading-snug">{building.building_id}</h3>
          {building.rnb_id && (
            <p className="text-xs text-muted-foreground mt-0.5">RNB {building.rnb_id}</p>
          )}
        </div>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Fermer">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
        {/* Score header */}
        <section className="flex items-center gap-3">
          <div
            className={cn(
              "h-14 w-14 rounded-lg grid place-items-center text-xl font-bold text-white",
            )}
            style={{ backgroundColor: dpeColor(dpe) }}
            title={`DPE ${dpe}`}
          >
            {dpe}
          </div>
          <div className="flex-1">
            <div className="text-2xl font-semibold">
              {(score * 100).toFixed(0)}
              <span className="text-sm text-muted-foreground">/100</span>
            </div>
            <div className="text-xs text-muted-foreground">Score ConX</div>
          </div>
          <Badge variant={dpeSource.tone}>{dpeSource.label}</Badge>
        </section>

        {/* Indicateurs clés */}
        <section className="grid grid-cols-2 gap-2 text-xs">
          <Stat label="Surface" value={fmtNum(building.surface_m2, " m²")} />
          <Stat label="Hauteur" value={fmtNum(building.hauteur_m, " m")} />
          <Stat label="Logements" value={fmtNum(building.nb_logements)} />
          <Stat
            label="Année"
            value={building.annee_constr ? String(building.annee_constr) : "—"}
          />
          <Stat label="Type" value={shortType(building.type_principal)} />
          <Stat label="Propriétaire" value={shortProp(building.type_proprietaire)} />
        </section>

        {/* DPE détaillé */}
        <section className="rounded-md bg-muted/50 p-3 text-xs space-y-1">
          <div className="font-semibold text-sm">Performance énergétique</div>
          <div>
            Consommation :{" "}
            <strong>{fmtNum(building.dpe_kwh_ep_m2_an, " kWh ep/m²/an")}</strong>
          </div>
          <div className="text-muted-foreground">
            Coefficient EP électricité 1.9 (DPE 2026, ConX aligné cadre à venir).
          </div>
        </section>

        {/* Composantes scoring */}
        <section className="space-y-1.5">
          <div className="font-semibold text-sm">Composantes scoring</div>
          <ScoreBar label="CO₂ évité" value={building.s_co2} />
          <ScoreBar label="Faisabilité" value={building.s_faisa} />
          <ScoreBar label="Coût" value={building.s_cout} />
          <ScoreBar label="Social" value={building.s_social} />
          <ScoreBar label="Passoire" value={building.s_passoire} />
        </section>

        {/* Estimations brutes */}
        <section className="rounded-md border p-3 text-xs space-y-1">
          <div>
            <span className="text-muted-foreground">CO₂ évité (30 ans) :</span>{" "}
            <strong>{fmtNum(building.co2_evite_t, " tCO₂")}</strong>
          </div>
          <div>
            <span className="text-muted-foreground">Coût estimé :</span>{" "}
            <strong>{fmtMoney(building.cout_estime_eur)}</strong>
          </div>
          {building.monument_historique && (
            <div className="text-amber-700">⚠ Monument Historique BDNB</div>
          )}
        </section>

        <section className="text-[11px] text-muted-foreground border-t pt-3 leading-relaxed">
          Sources : BDNB CSTB 2025-07.a, DPE ADEME (coefficient EP électricité 1.9
          — DPE 2026), scoring déterministe ConX (méthodologie à venir J19).
        </section>
      </div>

      <div className="border-t p-3 flex gap-2">
        <Button asChild className="flex-1">
          <Link to={`/projet/${encodeURIComponent(building.building_id)}`}>
            <BookOpen className="h-4 w-4 mr-1" />
            Ouvrir Mode Projet
          </Link>
        </Button>
        <Button size="icon" variant="outline" asChild>
          <a
            href={`https://rnb.beta.gouv.fr/buildings/${building.rnb_id ?? ""}`}
            target="_blank"
            rel="noreferrer noopener"
            aria-label="Voir sur RNB"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/30 px-2 py-1.5">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const v = value ?? 0;
  return (
    <div className="text-xs">
      <div className="flex justify-between">
        <span>{label}</span>
        <span className="font-mono text-muted-foreground">{(v * 100).toFixed(0)}</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary"
          style={{ width: `${Math.max(0, Math.min(100, v * 100))}%` }}
        />
      </div>
    </div>
  );
}

function fmtNum(n: number | null | undefined, suffix = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}${suffix}`;
}

function fmtMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(0)} k€`;
  return `${Math.round(n)} €`;
}

function shortType(t: string | null): string {
  if (!t) return "—";
  return t.replace(/_/g, " ").replace("residentiel", "résidentiel");
}

function shortProp(p: string | null): string {
  if (!p) return "—";
  return (
    {
      bailleur_social: "Bailleur social",
      personne_morale_privee: "Copro / foncière",
      particulier: "Particulier",
      public: "Public",
    }[p] ?? p
  );
}
