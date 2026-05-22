/**
 * Mode Projet — viewer 3D + fiche bâtiment détaillée + (J16) chat itératif IA.
 *
 * Layout :
 *   ┌──────────────────────────────────┬─────────────────────┐
 *   │ ProjetMap (deck.gl 3D extrusion) │ Sidebar :           │
 *   │                                  │  - Fiche détaillée  │
 *   │                                  │  - (J16) Chat agent │
 *   └──────────────────────────────────┴─────────────────────┘
 */

import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2 } from "lucide-react";

import { ProjetMap } from "@/map/ProjetMap";
import { PlanChat } from "@/components/PlanChat";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { dpeColor } from "@/lib/utils";
import { getBuilding, type BuildingDetail } from "@/lib/api";

export function ProjetPage() {
  const { id } = useParams<{ id?: string }>();
  return id ? <ProjetView id={id} /> : <EmptyProjet />;
}

function EmptyProjet() {
  return (
    <div className="container py-10 max-w-2xl">
      <h1 className="text-2xl font-semibold mb-2">Mode Projet</h1>
      <p className="text-muted-foreground mb-6">
        Sélectionnez un bâtiment depuis la carte Stratégie pour ouvrir sa fiche,
        générer un plan rénovation IA et explorer la 3D.
      </p>
      <Button asChild>
        <Link to="/strategie">
          <Building2 className="h-4 w-4 mr-2" />
          Ouvrir la carte
        </Link>
      </Button>
    </div>
  );
}

function ProjetView({ id }: { id: string }) {
  const {
    data: building,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["building", id],
    queryFn: ({ signal }) => getBuilding(id, signal),
  });

  if (isLoading) {
    return (
      <div className="flex-1 grid place-items-center">
        <div className="text-sm text-muted-foreground">Chargement du bâtiment…</div>
      </div>
    );
  }
  if (error || !building) {
    return (
      <div className="container py-10 max-w-xl">
        <h2 className="text-lg font-semibold mb-2">Bâtiment introuvable</h2>
        <p className="text-sm text-muted-foreground mb-4">
          {error ? (error as Error).message : `ID ${id} non trouvé dans la base.`}
        </p>
        <Button variant="outline" asChild>
          <Link to="/strategie">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Retour à la carte
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex min-h-0">
      <div className="flex-1 min-w-0 relative">
        <ProjetMap building={building} />
        <div className="absolute top-3 left-3 flex gap-2">
          <Button size="sm" variant="outline" asChild>
            <Link to="/strategie">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Carte Stratégie
            </Link>
          </Button>
        </div>
      </div>

      <aside className="w-[460px] shrink-0 border-l bg-card flex flex-col overflow-hidden">
        <FicheHeader building={building} />
        <FicheBody building={building} />
        <PlanChat building={building} />
      </aside>
    </div>
  );
}

function FicheHeader({ building }: { building: BuildingDetail }) {
  const dpe = building.dpe_classe ?? "?";
  const score = building.score_total ?? 0;
  return (
    <div className="border-b p-4 space-y-2">
      <div className="text-xs text-muted-foreground">
        Dpt {building.dept} · IRIS {building.code_iris ?? "—"}
      </div>
      <div className="flex items-start gap-3">
        <div
          className="h-14 w-14 rounded-lg grid place-items-center text-xl font-bold text-white shrink-0"
          style={{ backgroundColor: dpeColor(dpe) }}
        >
          {dpe}
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-sm break-all">{building.building_id}</h2>
          <p className="text-xs text-muted-foreground">RNB {building.rnb_id ?? "—"}</p>
          <div className="mt-1.5 flex items-center gap-2 text-xs">
            <span className="font-mono text-base font-semibold text-foreground">
              {(score * 100).toFixed(0)}
              <span className="text-muted-foreground text-sm">/100</span>
            </span>
            <Badge
              variant={building.dpe_source === "ademe-real" ? "default" : "secondary"}
            >
              {building.dpe_source === "ademe-real" ? "DPE réel" : "DPE estimé IA"}
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}

function FicheBody({ building }: { building: BuildingDetail }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
      {/* Caractéristiques bâti */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Caractéristiques bâti
        </h3>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <DL label="Surface" value={fmt(building.surface_m2, " m²")} />
          <DL label="Hauteur" value={fmt(building.hauteur_m, " m")} />
          <DL label="Logements" value={fmt(building.nb_logements)} />
          <DL label="Année" value={building.annee_constr ? String(building.annee_constr) : "—"} />
          <DL label="Type" value={building.type_principal ?? "—"} />
          <DL label="Période" value={building.periode_construction ?? "—"} />
          <DL label="Matériau mur" value={building.materiau_mur ?? "—"} />
          <DL label="Propriétaire" value={shortProp(building.type_proprietaire)} />
        </dl>
      </section>

      {/* DPE */}
      <section className="rounded-md bg-muted/50 p-3 text-xs space-y-1">
        <div className="font-semibold text-sm">Performance énergétique</div>
        <div>
          Consommation :{" "}
          <strong>{fmt(building.dpe_kwh_ep_m2_an, " kWh ep/m²/an")}</strong>
        </div>
        <div>
          Émissions :{" "}
          <strong>{fmt(building.dpe_kg_co2_m2_an, " kg CO₂/m²/an")}</strong>
        </div>
        <div className="text-muted-foreground">
          Coefficient EP électricité{" "}
          <strong>
            {building.dpe_coefficient_ep_electricite?.toFixed(1) ?? "1.9"}
          </strong>{" "}
          (DPE 2026, ConX aligné cadre à venir).
        </div>
      </section>

      {/* Scoring */}
      <section className="space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Composantes scoring ConX
        </h3>
        <ScoreBar label="CO₂ évité" value={building.s_co2} />
        <ScoreBar label="Faisabilité" value={building.s_faisa} />
        <ScoreBar label="Coût" value={building.s_cout} />
        <ScoreBar label="Social" value={building.s_social} />
        <ScoreBar label="Passoire" value={building.s_passoire} />
      </section>

      {/* Estimations bilan */}
      <section className="rounded-md border p-3 text-xs space-y-1">
        <div className="font-semibold text-sm mb-1">Bilan rénovation estimé</div>
        <div>
          <span className="text-muted-foreground">CO₂ évité (30 ans) :</span>{" "}
          <strong>{fmt(building.co2_evite_t, " tCO₂")}</strong>
        </div>
        <div>
          <span className="text-muted-foreground">Coût estimé :</span>{" "}
          <strong>{fmtMoney(building.cout_estime_eur)}</strong>
        </div>
        <div className="text-[11px] text-muted-foreground mt-1.5 leading-relaxed">
          Estimations indicatives (cf. SCORING.md). Le plan IA détaillé ci-contre
          affine la composition matériaux et le bilan carbone par sous-composante.
        </div>
      </section>

      {/* Drapeaux */}
      {(building.monument_historique || building.spr) && (
        <section className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs space-y-1">
          {building.monument_historique && <div>⚠ Monument Historique BDNB</div>}
          {building.spr && <div>⚠ Site Patrimonial Remarquable</div>}
          <div className="text-amber-900/80 mt-1">
            Toute intervention en façade nécessite l'aval ABF (Architecte des
            Bâtiments de France).
          </div>
        </section>
      )}

      <section className="text-[11px] text-muted-foreground border-t pt-3 leading-relaxed">
        Sources : BDNB CSTB {building.bdnb_millesime ?? "2025-07.a"}, DPE ADEME,
        scoring déterministe ConX (méthodologie à venir J19).
      </section>
    </div>
  );
}

function DL({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium truncate" title={value}>
        {value}
      </dd>
    </>
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

function fmt(n: number | null | undefined, suffix = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}${suffix}`;
}

function fmtMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(0)} k€`;
  return `${Math.round(n)} €`;
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

