/**
 * Mode Projet — viewer 3D + fiche bâtiment dashboard + chat itératif IA.
 *
 * REFONTE J18 :
 * - Fiche compacte par défaut (identité, score, badges, perf, voisins)
 * - Bouton "Voir tout le dashboard" qui déplie 6 sections expert :
 *     A. Diagnostic technique détaillé
 *     B. Conso réelle 7 ans
 *     C. Distribution DPE par logement (RPLS)
 *     D. Coût énergie + classement
 *     E. Aides éligibles
 *     F. Risques + Urbanisme
 *
 * Layout :
 *   ┌──────────────────────────────────┬─────────────────────┐
 *   │ ProjetMap (deck.gl 3D extrusion) │ Sidebar 460px :     │
 *   │                                  │  - Dashboard        │
 *   │                                  │  - PlanChat agent   │
 *   └──────────────────────────────────┴─────────────────────┘
 */

import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  ChevronDown,
  ChevronUp,
  MapPin,
  ShieldCheck,
  Flame,
  Construction,
  Coins,
  Award,
  AlertTriangle,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import { useCountUp } from "@/lib/useCountUp";

import { ProjetMap } from "@/map/ProjetMap";
import { PlanChat } from "@/components/PlanChat";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { dpeColor, cn } from "@/lib/utils";
import {
  getBuilding,
  getBuildingRank,
  type BuildingDetail,
  type BuildingRank,
  type DiagnosticTechnique,
  type RplsData,
  type ConsoAnnuelle,
  type AideEligible,
} from "@/lib/api";

export function ProjetPage() {
  const { id } = useParams<{ id?: string }>();
  return id ? <ProjetView id={id} /> : <EmptyProjet />;
}

function EmptyProjet() {
  return (
    <div className="container py-10 max-w-2xl">
      <h1 className="text-2xl font-semibold mb-2">Mode Projet</h1>
      <p className="text-muted-foreground mb-6">
        Sélectionnez un bâtiment depuis la carte Stratégie pour ouvrir son
        dashboard, générer un plan rénovation IA et explorer la 3D.
      </p>
      <div className="flex gap-2 flex-wrap">
        <Button asChild>
          <Link to="/strategie">
            <Building2 className="h-4 w-4 mr-2" />
            Ouvrir la carte
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/projet/bdnb-bg-81UB-UTZE-ZP7F">Démo Wazemmes (vedette)</Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link to="/projet/bdnb-bg-JBP7-PFQL-4T69">Démo Vieux-Lille (fallback)</Link>
        </Button>
      </div>
    </div>
  );
}

function ProjetView({ id }: { id: string }) {
  const { data: building, isLoading, error } = useQuery({
    queryKey: ["building", id],
    queryFn: ({ signal }) => getBuilding(id, signal),
  });

  if (isLoading) {
    return <ProjetSkeleton />;
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
        <BuildingDashboard building={building} />
        <PlanChat building={building} />
      </aside>
    </div>
  );
}

// =========================================================================
// Skeleton loader (état chargement fiche bâtiment)
// =========================================================================

/**
 * Skeleton mimétique de la mise en page Mode Projet : map + dashboard.
 * Les blocs `animate-pulse bg-muted` occupent les mêmes dimensions que les
 * vrais composants → pas de jump de layout au paint final.
 */
function ProjetSkeleton() {
  return (
    <div className="flex-1 flex min-h-0">
      {/* Map placeholder (3D viewer) */}
      <div className="flex-1 bg-muted/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-muted/20 via-muted/40 to-muted/20 animate-pulse" />
        <div className="absolute top-3 left-3 h-8 w-32 rounded-md bg-muted/60 animate-pulse" />
      </div>
      {/* Dashboard placeholder */}
      <aside className="w-[460px] shrink-0 border-l bg-card flex flex-col p-4 gap-4">
        {/* En-tête : score circle + DPE badge + adresse */}
        <div className="flex items-start gap-3">
          <div className="h-20 w-20 rounded-full bg-muted animate-pulse" />
          <div className="flex-1 space-y-2">
            <div className="h-6 w-20 bg-muted rounded animate-pulse" />
            <div className="h-4 w-3/4 bg-muted/60 rounded animate-pulse" />
            <div className="h-3 w-1/2 bg-muted/40 rounded animate-pulse" />
          </div>
        </div>
        {/* Badges */}
        <div className="flex flex-wrap gap-1.5">
          <div className="h-5 w-20 bg-muted/60 rounded-full animate-pulse" />
          <div className="h-5 w-28 bg-muted/60 rounded-full animate-pulse" />
          <div className="h-5 w-16 bg-muted/60 rounded-full animate-pulse" />
        </div>
        {/* Caractéristiques bâti (grid 2x4) */}
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-2 w-12 bg-muted/40 rounded animate-pulse" />
              <div className="h-3.5 w-20 bg-muted rounded animate-pulse" />
            </div>
          ))}
        </div>
        {/* Performance énergétique placeholder */}
        <div className="rounded-md bg-muted/30 p-3 space-y-2">
          <div className="h-4 w-44 bg-muted rounded animate-pulse" />
          <div className="h-3 w-3/4 bg-muted/60 rounded animate-pulse" />
          <div className="h-3 w-2/3 bg-muted/60 rounded animate-pulse" />
        </div>
        {/* Radar placeholder */}
        <div className="h-32 bg-muted/30 rounded animate-pulse" />
        {/* 3 BigStats horizontal */}
        <div className="grid grid-cols-3 gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-14 bg-muted/40 rounded animate-pulse" />
          ))}
        </div>
        <div className="text-[11px] text-muted-foreground/70 text-center pt-2 animate-pulse">
          Chargement du bâtiment…
        </div>
      </aside>
    </div>
  );
}

// =========================================================================
// Dashboard (fiche compacte + sections dépliables)
// =========================================================================

function BuildingDashboard({ building }: { building: BuildingDetail }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="flex-1 min-h-[260px] overflow-y-auto">
      <CompactCard building={building} />
      <div className="px-4 py-2 border-t border-b bg-muted/30">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center text-xs font-medium"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-4 w-4 mr-1" />
              Replier le dashboard
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4 mr-1" />
              Voir tout le dashboard
            </>
          )}
        </Button>
      </div>
      {expanded && <ExpertSections building={building} />}
      <Footer building={building} />
    </div>
  );
}

// -------------------------------------------------------------------------
// FICHE COMPACTE
// -------------------------------------------------------------------------

function CompactCard({ building }: { building: BuildingDetail }) {
  const score = building.score_total ?? 0;
  const dpe = building.dpe_classe ?? "?";
  const dpeIsReal = building.dpe_source === "ademe-real";
  const adresse = building.adresse_postale ?? building.building_id;

  return (
    <div className="p-4 space-y-4 text-sm">
      {/* Identité + score */}
      <section className="flex items-start gap-3">
        <ScoreCircle score={score} />
        <div className="flex-1 min-w-0">
          <DpeBadge classe={dpe} source={building.dpe_source ?? "—"} large />
          <div className="mt-2 flex items-start gap-1.5">
            <MapPin className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
            <div className="min-w-0">
              <h2 className="text-sm font-semibold leading-snug break-words">{adresse}</h2>
              {building.commune_nom && (
                <p className="text-[11px] text-muted-foreground">
                  {building.commune_nom}
                  {building.code_iris && ` · IRIS ${building.code_iris}`}
                  {` · Dpt ${building.dept}`}
                </p>
              )}
              {building.identifiant_dpe_ademe && (
                <p
                  className="inline-flex items-center gap-1 text-[11px] text-muted-foreground mt-0.5"
                  title="Identifiant DPE officiel ADEME — consultable sur observatoire-dpe-audit.ademe.fr"
                >
                  DPE ADEME :{" "}
                  <code className="font-mono text-[10.5px] text-foreground/80">
                    {building.identifiant_dpe_ademe}
                  </code>
                </p>
              )}
              <p className="text-[10px] text-muted-foreground/70 mt-1 font-mono break-all">
                {building.building_id}
                {building.rnb_id && ` · RNB ${building.rnb_id}`}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Badges contextuels */}
      <ContextBadges building={building} dpeIsReal={dpeIsReal} />

      {/* Caractéristiques bâti */}
      <section>
        <SectionTitle>Caractéristiques bâti</SectionTitle>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <DL label="Surface au sol" value={fmt(building.surface_m2, " m²")} />
          <DL label="SHAB immeuble" value={fmt(building.shab_immeuble_m2, " m²")} />
          <DL
            label="Niveaux"
            value={
              building.nb_niveaux_ffo
                ? `R+${building.nb_niveaux_ffo - 1} (${building.nb_niveaux_ffo} niveaux)`
                : fmt(building.hauteur_m, " m hauteur")
            }
          />
          <DL label="Logements" value={fmt(building.nb_logements)} />
          <DL
            label="Année"
            value={building.annee_constr ? String(building.annee_constr) : "—"}
            sub={building.periode_thermique_reglementaire ?? undefined}
          />
          <DL label="Propriétaire" value={shortProp(building.type_proprietaire)} />
          <DL label="Murs" value={building.materiau_mur ?? "—"} />
          <DL label="Toiture" value={building.materiau_toiture ?? "—"} />
        </dl>
      </section>

      {/* Performance énergétique */}
      <section className="rounded-md bg-muted/50 p-3 text-xs space-y-1">
        <div className="font-semibold text-sm">Performance énergétique</div>
        <div>
          Consommation :{" "}
          <strong>{fmt(building.dpe_kwh_ep_m2_an, " kWh ep/m²/an")}</strong>
        </div>
        <div>
          Émissions :{" "}
          <strong>{fmt(building.dpe_kg_co2_m2_an, " kg CO₂/m²/an")}</strong>
          {building.classe_emission_ges && (
            <span className="text-muted-foreground"> · classe GES {building.classe_emission_ges}</span>
          )}
        </div>
        <div className="text-muted-foreground">
          Coefficient EP électricité{" "}
          <strong>{building.dpe_coefficient_ep_electricite?.toFixed(1) ?? "1.9"}</strong>{" "}
          (DPE 2026 anticipé).
        </div>
      </section>

      {/* Composantes scoring — radar visuel + barres détaillées */}
      <section className="space-y-1.5">
        <SectionTitle>Composantes du score</SectionTitle>
        <ScoreRadar
          s_co2={building.s_co2}
          s_faisa={building.s_faisa}
          s_cout={building.s_cout}
          s_social={building.s_social}
          s_passoire={building.s_passoire}
        />
        <details className="text-[10.5px] text-muted-foreground">
          <summary className="cursor-pointer hover:text-foreground select-none">
            Voir le détail des 5 composantes
          </summary>
          <div className="mt-1.5 space-y-1.5">
            <ScoreBar label="CO₂ évité" value={building.s_co2} />
            <ScoreBar label="Faisabilité" value={building.s_faisa} />
            <ScoreBar label="Coût" value={building.s_cout} />
            <ScoreBar label="Social" value={building.s_social} />
            <ScoreBar label="Passoire" value={building.s_passoire} />
          </div>
        </details>
      </section>

      {/* Impacts 30 ans — chiffres animés au paint pour l'effet pitch */}
      <section className="rounded-md border p-3 space-y-1.5 text-xs bg-primary/5">
        <div className="font-semibold text-sm flex items-center gap-1.5">
          <Award className="h-4 w-4 text-primary" /> Impacts 30 ans
        </div>
        <div className="grid grid-cols-3 gap-2 mt-1">
          <BigStat
            label="CO₂ évité"
            value={fmtT(building.co2_evite_t)}
            unit="tCO₂"
            animateNumber={building.co2_evite_t ?? null}
          />
          <BigStat
            label="Coût op."
            value={fmtMoneyShort(building.cout_estime_eur)}
            animateNumber={
              building.cout_estime_eur != null
                ? building.cout_estime_eur / 1000
                : null
            }
            unit={building.cout_estime_eur != null && building.cout_estime_eur >= 1000 ? "k€" : "€"}
          />
          <BigStat
            label="€/tCO₂"
            value={fmtMoneyShort(building.cout_eur_par_t_co2)}
            animateNumber={building.cout_eur_par_t_co2 ?? null}
            unit="€"
          />
        </div>
      </section>

      {/* Voisins */}
      {building.neighbors && building.neighbors.length > 0 && (
        <section className="space-y-1.5">
          <SectionTitle>Voisins proches (KNN 200m)</SectionTitle>
          <div className="space-y-1">
            {building.neighbors.slice(0, 5).map((n) => (
              <div key={n.building_id} className="flex items-center gap-2 text-[11px]">
                <DpeBadge classe={n.dpe_classe ?? "?"} small />
                <span className="font-mono truncate text-muted-foreground flex-1">
                  {n.building_id}
                </span>
                <span className="text-muted-foreground">{n.distance_m.toFixed(0)} m</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ContextBadges({
  building,
  dpeIsReal,
}: {
  building: BuildingDetail;
  dpeIsReal: boolean;
}) {
  // Chaque badge porte un `tooltip` pour expliquer le sigle technique en hover.
  // Cible : un juré ou un utilisateur non-spécialiste qui survole un badge
  // « AC1 » doit immédiatement savoir ce que c'est.
  const items: { label: string; tone: BadgeTone; tooltip?: string }[] = [];
  if (building.dans_qpv) {
    items.push({
      label: `QPV${building.qpv_nom ? " · " + building.qpv_nom : ""}`,
      tone: "info",
      tooltip:
        "Quartier Prioritaire de la Politique de la Ville — bonus de financement rénovation (CEE majorés, ANRU si éligible).",
    });
  }
  if (building.reseau_chaleur_id) {
    items.push({
      label: building.reseau_chaleur_prioritaire
        ? `Réseau chaleur ${building.reseau_chaleur_id} · prioritaire`
        : `Réseau chaleur ${building.reseau_chaleur_id}`,
      tone: "success",
      tooltip:
        "Réseau de Chaleur Urbain (RCU) à proximité. Statut « prioritaire » = obligation de raccordement réglementaire pour les bâtiments tertiaires neufs.",
    });
  }
  if (building.urbanisme?.zone_ac1) {
    items.push({
      label: "Zone AC1 · servitude",
      tone: "warn",
      tooltip:
        "Servitude AC1 : Abords de Monument Historique. Tout travaux visibles doivent obtenir l'avis conforme de l'Architecte des Bâtiments de France (ABF).",
    });
  }
  if (building.monument_historique) {
    items.push({
      label: "Monument historique",
      tone: "warn",
      tooltip:
        "Bâtiment inscrit ou classé Monument Historique — autorisations renforcées + accès aux aides spécifiques (DRAC).",
    });
  }
  if (building.spr) {
    items.push({
      label: "SPR",
      tone: "warn",
      tooltip:
        "Site Patrimonial Remarquable — protection urbanistique d'ensemble, règles ABF.",
    });
  }
  if (building.rpls?.accessible_pmr === false) {
    items.push({
      label: "Non accessible PMR",
      tone: "danger",
      tooltip:
        "PMR = Personnes à Mobilité Réduite. Bâtiment déclaré non accessible dans le Répertoire des Logements Locatifs des bailleurs Sociaux (RPLS).",
    });
  }
  items.push({
    label: dpeIsReal ? "DPE réel ADEME" : "DPE estimé IA",
    tone: dpeIsReal ? "default" : "muted",
    tooltip: dpeIsReal
      ? "Diagnostic de Performance Énergétique officiel issu de la base ADEME (observatoire-dpe-audit.ademe.fr)."
      : "Diagnostic estimé par modèle Random Forest entraîné sur les DPE ADEME existants — à confirmer par diagnostic réel avant travaux.",
  });
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((it, i) => (
        <ChipBadge key={i} tone={it.tone} tooltip={it.tooltip}>
          {it.label}
        </ChipBadge>
      ))}
    </div>
  );
}

// -------------------------------------------------------------------------
// SECTIONS EXPERT (dashboard déplié)
// -------------------------------------------------------------------------

function ExpertSections({ building }: { building: BuildingDetail }) {
  return (
    <div className="border-t bg-background">
      <SectionAccordion title="A. Diagnostic technique" icon={<Construction className="h-3.5 w-3.5" />}>
        {building.diagnostic_technique ? (
          <DiagnosticPanel diag={building.diagnostic_technique} />
        ) : (
          <EmptyPanel msg="Diagnostic technique non disponible pour ce bâtiment (DPE estimé IA ou DPE pré-2021)." />
        )}
      </SectionAccordion>

      <SectionAccordion title="B. Consommation réelle (DLE 7 ans)" icon={<Flame className="h-3.5 w-3.5" />}>
        {building.conso_reelle_annuelle && building.conso_reelle_annuelle.length > 0 ? (
          <ConsoChart data={building.conso_reelle_annuelle} />
        ) : (
          <EmptyPanel msg="Pas de données DLE Enedis/GRDF pour ce bâtiment." />
        )}
      </SectionAccordion>

      <SectionAccordion title="C. Distribution DPE par logement (RPLS)" icon={<Building2 className="h-3.5 w-3.5" />}>
        {building.rpls?.rpls_open ? (
          <RplsPanel rpls={building.rpls} />
        ) : (
          <EmptyPanel msg="Pas de données RPLS (bâtiment non répertorié bailleur social)." />
        )}
      </SectionAccordion>

      <SectionAccordion title="D. Coût énergie + classement" icon={<Coins className="h-3.5 w-3.5" />}>
        <CoutEtClassementPanel building={building} />
      </SectionAccordion>

      <SectionAccordion title="E. Aides éligibles" icon={<Award className="h-3.5 w-3.5" />}>
        <AidesPanel aides={building.aides_eligibles ?? []} />
      </SectionAccordion>

      <SectionAccordion title="F. Risques + Urbanisme" icon={<ShieldCheck className="h-3.5 w-3.5" />}>
        <RisquesUrbaPanel building={building} />
      </SectionAccordion>
    </div>
  );
}

function SectionAccordion({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <details className="group border-b last:border-b-0">
      <summary className="px-4 py-2.5 cursor-pointer flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-foreground/80 hover:bg-muted/50 transition select-none">
        <span className="flex items-center gap-2">
          {icon}
          {title}
        </span>
        <ChevronDown className="h-4 w-4 group-open:rotate-180 transition" />
      </summary>
      <div className="px-4 pb-3 pt-1 text-xs">{children}</div>
    </details>
  );
}

// --- A. Diagnostic ------------------------------------------------------

function DiagnosticPanel({ diag }: { diag: DiagnosticTechnique }) {
  const ventBad = diag.type_ventilation?.includes("ouverture des fenêtres");
  const totalDeperdition =
    (diag.deperdition_mur ?? 0) +
    (diag.deperdition_plancher_haut ?? 0) +
    (diag.deperdition_plancher_bas ?? 0) +
    (diag.deperdition_baie_vitree ?? 0) +
    (diag.deperdition_porte ?? 0);

  return (
    <div className="space-y-3">
      {/* Enveloppe */}
      <div>
        <SubTitle>Enveloppe</SubTitle>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
          <DL label="Murs" value={fmtU(diag.u_mur_exterieur, "W/m²K")} sub={diag.type_isolation_mur_exterieur ?? undefined} />
          <DL
            label="Structure"
            value={
              diag.materiaux_structure_mur_exterieur
                ? diag.materiaux_structure_mur_exterieur +
                  (diag.epaisseur_structure_mur_exterieur ? ` (${diag.epaisseur_structure_mur_exterieur} cm)` : "")
                : "—"
            }
          />
          <DL label="Plancher haut" value={fmtU(diag.u_plancher_haut_deperditif, "W/m²K")} sub={diag.type_isolation_plancher_haut ?? undefined} />
          <DL label="Plancher bas" value={fmtU(diag.u_plancher_bas_final_deperditif, "W/m²K")} sub={diag.type_isolation_plancher_bas ?? undefined} />
          <DL label="Menuiseries" value={fmtU(diag.uw, "Uw")} sub={diag.type_vitrage ?? undefined} />
          <DL label="Porte" value={fmtU(diag.u_porte, "W/m²K")} sub={diag.surface_porte ? `${diag.surface_porte.toFixed(1)} m²` : undefined} />
        </dl>
        {diag.vitrage_vir && (
          <div className="text-[10px] text-muted-foreground mt-1">
            ✓ Vitrage isolant renforcé (VIR) · {diag.type_materiaux_menuiserie?.toUpperCase()}
          </div>
        )}
      </div>

      {/* Systèmes */}
      <div>
        <SubTitle>Systèmes</SubTitle>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
          <DL
            label="Chauffage"
            value={joinNonNull([diag.type_installation_chauffage, diag.type_energie_chauffage]) || "—"}
            sub={joinNonNull([diag.type_generateur_chauffage, diag.type_generateur_chauffage_anciennete])}
          />
          <DL
            label="ECS"
            value={joinNonNull([diag.type_installation_ecs, diag.type_energie_ecs]) || "—"}
            sub={joinNonNull([diag.type_generateur_ecs, diag.type_generateur_ecs_anciennete])}
          />
        </dl>
        {diag.type_ventilation && (
          <div
            className={cn(
              "mt-2 text-[11px] px-2 py-1.5 rounded-md",
              ventBad ? "bg-red-50 text-red-900 border border-red-200" : "bg-muted/40",
            )}
          >
            <strong>Ventilation :</strong> {diag.type_ventilation}
            {ventBad && " — aucune VMC, cible de rénovation prioritaire."}
          </div>
        )}
      </div>

      {/* Déperditions */}
      {totalDeperdition > 0 && (
        <div>
          <SubTitle>Déperditions thermiques (W/K)</SubTitle>
          <div className="space-y-1">
            <DeperBar label="Murs" value={diag.deperdition_mur} total={totalDeperdition} />
            <DeperBar label="Plancher haut" value={diag.deperdition_plancher_haut} total={totalDeperdition} />
            <DeperBar label="Plancher bas" value={diag.deperdition_plancher_bas} total={totalDeperdition} />
            <DeperBar label="Baies vitrées" value={diag.deperdition_baie_vitree} total={totalDeperdition} />
            <DeperBar label="Portes" value={diag.deperdition_porte} total={totalDeperdition} />
          </div>
          <div className="text-[10px] text-muted-foreground mt-1">
            Total {totalDeperdition.toFixed(1)} W/K — l'ITE traite typiquement le poste mur + ponts thermiques.
          </div>
        </div>
      )}
    </div>
  );
}

function DeperBar({ label, value, total }: { label: string; value: number | null | undefined; total: number }) {
  const v = value ?? 0;
  const pct = total > 0 ? (v / total) * 100 : 0;
  return (
    <div className="text-[11px]">
      <div className="flex justify-between">
        <span>{label}</span>
        <span className="font-mono text-muted-foreground">{v.toFixed(1)} ({pct.toFixed(0)}%)</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full bg-orange-500/80" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// --- B. Conso 7 ans -----------------------------------------------------

function ConsoChart({ data }: { data: ConsoAnnuelle[] }) {
  const chartData = data.map((d) => ({
    annee: d.annee,
    elec: d.kwh_elec_residentiel ? Math.round(d.kwh_elec_residentiel / 1000) : null,
    gaz: d.kwh_gaz_residentiel ? Math.round(d.kwh_gaz_residentiel / 1000) : null,
  }));
  return (
    <div className="space-y-2">
      <div className="text-[11px] text-muted-foreground">
        Conso résidentielle (MWh/an, source Enedis + GRDF — facturé, ≠ DPE théorique)
      </div>
      <div style={{ width: "100%", height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="#e5e7eb" />
            <XAxis dataKey="annee" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} width={42} />
            <RTooltip
              contentStyle={{ fontSize: 11, padding: 6 }}
              formatter={(v, n) => [`${v ?? "—"} MWh`, n === "elec" ? "Élec" : "Gaz"]}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
            <Line type="monotone" dataKey="elec" stroke="#2563eb" strokeWidth={1.6} dot={{ r: 2 }} name="Élec" />
            <Line type="monotone" dataKey="gaz" stroke="#f59e0b" strokeWidth={1.6} dot={{ r: 2 }} name="Gaz" />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <table className="w-full text-[10px] mt-1">
        <thead>
          <tr className="text-muted-foreground">
            <th className="text-left">Année</th>
            <th className="text-right">Élec PDL</th>
            <th className="text-right">Élec MWh</th>
            <th className="text-right">Gaz PDL</th>
            <th className="text-right">Gaz MWh</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.annee} className="border-t border-border/40">
              <td>{d.annee}</td>
              <td className="text-right font-mono">{d.pdl_elec_residentiel?.toFixed(0) ?? "—"}</td>
              <td className="text-right font-mono">
                {d.kwh_elec_residentiel ? (d.kwh_elec_residentiel / 1000).toFixed(1) : "—"}
              </td>
              <td className="text-right font-mono">{d.pdl_gaz_residentiel?.toFixed(0) ?? "—"}</td>
              <td className="text-right font-mono">
                {d.kwh_gaz_residentiel ? (d.kwh_gaz_residentiel / 1000).toFixed(1) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- C. RPLS distribution ----------------------------------------------

function RplsPanel({ rpls }: { rpls: RplsData }) {
  const total = Object.values(rpls.distribution_dpe).reduce((a, b) => a + b, 0);
  const classes = ["A", "B", "C", "D", "E", "F", "G"] as const;
  return (
    <div className="space-y-2">
      <div className="text-[11px]">
        Bailleur social RPLS officiel · {total} logements · SHAB {rpls.shab_total_m2?.toFixed(0) ?? "—"} m²
      </div>
      {/* Barre stacked */}
      <div className="flex h-8 rounded-md overflow-hidden text-[10px] font-mono border">
        {classes.map((c) => {
          const n = rpls.distribution_dpe[c] || 0;
          if (n === 0) return null;
          const pct = (n / total) * 100;
          return (
            <div
              key={c}
              className="grid place-items-center text-white"
              style={{ width: `${pct}%`, backgroundColor: dpeColor(c) }}
              title={`${n} logt(s) en classe ${c}`}
            >
              {pct > 10 ? `${c} (${n})` : c}
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
        <DL label="DPE déclaré RPLS" value={rpls.classe_ener_principale ?? "—"} />
        <DL label="GES principal" value={rpls.classe_ges_principale ?? "—"} />
        <DL label="Accessible PMR" value={rpls.accessible_pmr ? "Oui" : "Non"} />
        <DL label="En QPV (RPLS)" value={rpls.dans_qpv ? "Oui" : "Non"} />
      </div>
      <div className="text-[10px] text-muted-foreground leading-relaxed border-t pt-1.5 mt-1">
        Note : la classe DPE déclarative RPLS du bailleur ({rpls.classe_ener_principale}) peut
        différer de la classe officielle ADEME du logement représentatif. La distribution
        ci-dessus est l'auto-déclaration du bailleur logt par logt.
      </div>
    </div>
  );
}

// --- D. Coût énergie + classement --------------------------------------

function CoutEtClassementPanel({ building }: { building: BuildingDetail }) {
  const [rank, setRank] = useState<BuildingRank | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRankLoading(true);
    setRankError(null);
    const ctrl = new AbortController();
    getBuildingRank(building.building_id, ctrl.signal)
      .then((r) => {
        if (!cancelled) setRank(r);
      })
      .catch((e) => {
        if (!cancelled && (e as Error).name !== "AbortError")
          setRankError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setRankLoading(false);
      });
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [building.building_id]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <BigStat label="€/an actuel" value={fmtMoneyShort(building.cout_energie_annuel_eur)} />
        <BigStat label="€ 30 ans" value={fmtMoneyShort(building.cout_energie_30_ans_eur)} />
        <BigStat label="tCO₂ 30 ans" value={fmt(building.emissions_totales_30_ans_t)} />
      </div>
      <div className="text-[10px] text-muted-foreground">
        Coût énergie : DPE × SHAB × tarif moyen 0.15 €/kWh EP. Émissions : DPE × SHAB × 30 ans.
        Estimations indicatives, à raffiner selon mix énergétique réel.
      </div>
      <hr className="border-border" />
      <SubTitle>Classement ConX</SubTitle>
      {rankLoading && <div className="text-[11px] text-muted-foreground">Calcul du classement…</div>}
      {rankError && <div className="text-[11px] text-destructive">Classement indisponible : {rankError}</div>}
      {rank && (
        <div className="space-y-2">
          <RankBar
            label="Dans son IRIS"
            rank={rank.rank_iris}
            total={rank.total_iris}
            percentile={rank.percentile_iris}
          />
          <RankBar label="Dans la commune" rank={rank.rank_commune} total={rank.total_commune} />
        </div>
      )}
    </div>
  );
}

function RankBar({
  label,
  rank,
  total,
  percentile,
}: {
  label: string;
  rank: number | null;
  total: number | null;
  percentile?: number | null;
}) {
  if (!rank || !total) return null;
  const pct = (rank / total) * 100;
  return (
    <div className="text-[11px]">
      <div className="flex justify-between mb-0.5">
        <span>{label}</span>
        <span className="font-mono text-foreground">
          #{rank.toLocaleString("fr-FR")} sur {total.toLocaleString("fr-FR")}
          {percentile !== undefined && percentile !== null && ` · top ${(percentile * 100).toFixed(1)}%`}
        </span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full bg-primary" style={{ width: `${Math.min(100, Math.max(2, 100 - pct))}%` }} />
      </div>
    </div>
  );
}

// --- E. Aides éligibles -------------------------------------------------

function AidesPanel({ aides }: { aides: AideEligible[] }) {
  if (aides.length === 0) {
    return <EmptyPanel msg="Aucune aide standardisée détectée par les règles. Voir conseiller France Rénov'." />;
  }
  return (
    <div className="space-y-1.5">
      {aides.map((a) => (
        <div key={a.code} className="rounded-md border border-border bg-card p-2">
          <div className="flex items-start gap-2">
            <Badge variant="default" className="shrink-0 text-[10px]">
              {a.code}
            </Badge>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-[11px]">{a.nom}</div>
              <div className="text-[10px] text-muted-foreground">{a.condition}</div>
              {a.montant_estimatif_eur !== null && (
                <div className="text-[11px] mt-0.5">
                  Estim. <strong>{fmtMoneyShort(a.montant_estimatif_eur)}</strong>
                </div>
              )}
              <div className="text-[9px] text-muted-foreground/70 mt-0.5">Source : {a.source}</div>
            </div>
          </div>
        </div>
      ))}
      <div className="text-[10px] text-muted-foreground leading-relaxed border-t pt-1.5">
        Estimations indicatives basées sur les barèmes publics 2024-2025. À confirmer par
        simulation Action Logement + DDT pour chaque opération.
      </div>
    </div>
  );
}

// --- F. Risques + urbanisme --------------------------------------------

function RisquesUrbaPanel({ building }: { building: BuildingDetail }) {
  return (
    <div className="space-y-3">
      <div>
        <SubTitle>Risques naturels</SubTitle>
        <div className="grid grid-cols-3 gap-2">
          <RisqueBadge label="Radon" niveau={building.risques?.radon ?? null} />
          <RisqueBadge label="Argile" niveau={building.risques?.argile ?? null} />
          <RisqueBadge label="Sismique" niveau={building.risques?.sismique ?? null} />
        </div>
      </div>
      <div>
        <SubTitle>Urbanisme</SubTitle>
        <div className="text-[11px] space-y-1">
          {building.urbanisme?.zone_ac1 && (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-2 py-1.5 text-amber-900">
              <strong>Zone AC1</strong> — Servitude d'utilité publique liée au patrimoine.
              Toute intervention en façade nécessite avis du Service urbanisme.
            </div>
          )}
          {building.urbanisme?.zone_plu_bati_patrimonial && (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-2 py-1.5 text-amber-900">
              <strong>Zone PLU bâti patrimonial</strong>
            </div>
          )}
          {building.urbanisme?.distance_monument_historique !== null &&
            building.urbanisme?.distance_monument_historique !== undefined && (
              <div className="text-muted-foreground">
                MH le plus proche :{" "}
                <strong>{building.urbanisme.denomination_monument_historique ?? "—"}</strong>
                {` à ${building.urbanisme.distance_monument_historique} m`}
                {building.urbanisme.distance_monument_historique <= 500
                  ? " — dans le périmètre 500 m ABF"
                  : " — hors périmètre ABF"}
              </div>
            )}
        </div>
      </div>
      {building.dpe_expire_le && (
        <div className="rounded-md border border-border p-2 text-[11px]">
          <strong>DPE valable jusqu'au :</strong> {building.dpe_expire_le}
          <div className="text-[10px] text-muted-foreground">
            DPE arrêté 2021 — validité 10 ans à compter de l'établissement{" "}
            {building.date_etablissement_dpe?.slice(0, 10)}.
          </div>
        </div>
      )}
      {building.acces_chantier && (
        <div>
          <SubTitle>Accès chantier</SubTitle>
          <div className="text-[11px]">
            Voirie la plus proche : <strong>{building.acces_chantier.nearest_largeur_m?.toFixed(1) ?? "—"} m de large</strong>
            {building.acces_chantier.nearest_distance_m !== null &&
              ` à ${building.acces_chantier.nearest_distance_m?.toFixed(1)} m du bâtiment`}
            .
          </div>
        </div>
      )}
    </div>
  );
}

function RisqueBadge({ label, niveau }: { label: string; niveau: string | null }) {
  const tone =
    niveau === "Faible"
      ? "bg-green-100 text-green-900 border-green-200"
      : niveau === "Moyen"
        ? "bg-amber-100 text-amber-900 border-amber-200"
        : niveau === "Fort" || niveau === "Élevé"
          ? "bg-red-100 text-red-900 border-red-200"
          : "bg-muted text-muted-foreground border-border";
  return (
    <div className={cn("rounded-md border px-2 py-1.5 text-center", tone)}>
      <div className="text-[10px] uppercase">{label}</div>
      <div className="text-[12px] font-semibold">{niveau ?? "—"}</div>
    </div>
  );
}

// -------------------------------------------------------------------------
// Footer méthodologie
// -------------------------------------------------------------------------

function Footer({ building }: { building: BuildingDetail }) {
  const fiab = building.fiabilite;
  const fiabSummary = fiab
    ? [
        fiab.emprise_sol ? `Emprise ${fiab.emprise_sol}` : null,
        fiab.hauteur ? `Hauteur ${fiab.hauteur}` : null,
        fiab.adresse !== null ? `Adresse ${fiab.adresse ? "fiable" : "incertaine"}` : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : null;
  return (
    <div className="px-4 py-3 border-t text-[10px] text-muted-foreground leading-relaxed">
      Sources : BDNB CSTB {building.bdnb_millesime ?? "2025-07.a"} · DPE ADEME (coef EP élec
      1.9, réforme 2026) · DLE Enedis/GRDF · RPLS · BD TOPO IGN · scoring déterministe ConX{" "}
      {building.thresholds_version ? `(v${building.thresholds_version.slice(0, 8)})` : ""}
      {fiabSummary && (
        <div className="mt-1">
          <span className="font-medium text-foreground/80">Fiabilité BDNB :</span> {fiabSummary}
        </div>
      )}
      {building.incomplete_data && (
        <div className="mt-1 text-amber-700">
          <AlertTriangle className="h-3 w-3 inline mr-1" />
          Scoring partiel — certaines données manquaient au calcul.
        </div>
      )}
    </div>
  );
}

// =========================================================================
// Atomes UI
// =========================================================================

function ScoreCircle({ score }: { score: number }) {
  const targetPct = Math.max(0, Math.min(1, score)) * 100;
  const animated = useCountUp(targetPct, { duration: 900 });
  return (
    <div
      className="relative h-20 w-20 rounded-full shrink-0 grid place-items-center transition-all"
      style={{
        background: `conic-gradient(hsl(var(--primary)) ${animated}%, hsl(var(--muted)) ${animated}% 100%)`,
      }}
      title={`Score ConX de priorisation : ${targetPct.toFixed(0)}/100`}
    >
      <div className="absolute inset-1.5 rounded-full bg-card grid place-items-center text-center">
        <div className="font-bold text-xl leading-none tabular-nums">
          {animated.toFixed(0)}
        </div>
        <div className="text-[9px] text-muted-foreground -mt-0.5">/100</div>
      </div>
    </div>
  );
}

/**
 * Radar pentagone des 5 composantes du score ConX.
 * Affiche les 5 axes (CO₂, Faisabilité, Coût, Social, Passoire) sur 0-1.
 * Petit (taille fiche compacte), lisible, narratif pour le pitch.
 */
function ScoreRadar({
  s_co2,
  s_faisa,
  s_cout,
  s_social,
  s_passoire,
}: {
  s_co2: number | null;
  s_faisa: number | null;
  s_cout: number | null;
  s_social: number | null;
  s_passoire: number | null;
}) {
  const data = [
    { axis: "CO₂", value: (s_co2 ?? 0) * 100 },
    { axis: "Faisa", value: (s_faisa ?? 0) * 100 },
    { axis: "Coût", value: (s_cout ?? 0) * 100 },
    { axis: "Social", value: (s_social ?? 0) * 100 },
    { axis: "Passoire", value: (s_passoire ?? 0) * 100 },
  ];
  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <PolarGrid stroke="hsl(var(--border))" strokeOpacity={0.6} />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={false}
            stroke="transparent"
          />
          <Radar
            name="Composantes"
            dataKey="value"
            stroke="hsl(var(--primary))"
            fill="hsl(var(--primary))"
            fillOpacity={0.35}
            isAnimationActive
            animationDuration={900}
          />
          <RTooltip
            formatter={(v) => [`${Math.round(Number(v))}/100`, "Score"]}
            contentStyle={{ fontSize: 11 }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DpeBadge({
  classe,
  source,
  small,
  large,
}: {
  classe: string;
  source?: string;
  small?: boolean;
  large?: boolean;
}) {
  const sz = small ? "h-5 w-5 text-[10px]" : large ? "h-8 w-8 text-sm" : "h-6 w-6 text-xs";
  return (
    <div className="inline-flex items-center gap-1.5">
      <div
        className={cn("rounded grid place-items-center font-bold text-white", sz)}
        style={{ backgroundColor: dpeColor(classe) }}
        title={`DPE ${classe}${source ? ` · ${source}` : ""}`}
      >
        {classe}
      </div>
    </div>
  );
}

type BadgeTone = "default" | "info" | "success" | "warn" | "danger" | "muted";

function ChipBadge({
  tone,
  children,
  tooltip,
}: {
  tone: BadgeTone;
  children: React.ReactNode;
  /** Si fourni, l'attribut `title` natif déclenche un tooltip au hover.
   * Volontairement basique (native), évite d'ajouter une lib tooltip. */
  tooltip?: string;
}) {
  const cls = {
    default: "bg-primary/10 text-primary border-primary/20",
    info: "bg-blue-50 text-blue-900 border-blue-200",
    success: "bg-emerald-50 text-emerald-900 border-emerald-200",
    warn: "bg-amber-50 text-amber-900 border-amber-200",
    danger: "bg-red-50 text-red-900 border-red-200",
    muted: "bg-muted text-muted-foreground border-border",
  }[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border font-medium",
        tooltip && "cursor-help",
        cls,
      )}
      title={tooltip}
    >
      {children}
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
      {children}
    </h3>
  );
}

function SubTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
      {children}
    </div>
  );
}

function DL({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <dt className="text-muted-foreground text-[10px] uppercase">{label}</dt>
      <dd className="font-medium" title={value}>
        {value}
      </dd>
      {sub && <div className="text-[10px] text-muted-foreground/80">{sub}</div>}
    </div>
  );
}

function BigStat({
  label,
  value,
  unit,
  animateNumber,
}: {
  label: string;
  value: string;
  unit?: string;
  /** Si fourni, anime la valeur numérique en count-up. Le rendu est formaté
   * via Intl.NumberFormat fr-FR. La prop `value` est ignorée si présente. */
  animateNumber?: number | null;
}) {
  return (
    <div className="rounded-md bg-card border border-border px-2 py-1.5 text-center">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm font-bold tabular-nums">
        {animateNumber !== undefined && animateNumber !== null ? (
          <AnimatedNumber target={animateNumber} />
        ) : (
          value
        )}
        {unit && <span className="text-[10px] text-muted-foreground ml-0.5">{unit}</span>}
      </div>
    </div>
  );
}

function AnimatedNumber({ target }: { target: number }) {
  const v = useCountUp(target, { duration: 750 });
  const fmt = (n: number): string => {
    if (Math.abs(n) >= 1000) {
      return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(
        Math.round(n),
      );
    }
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(n);
  };
  return <>{fmt(v)}</>;
}

function ScoreBar({ label, value }: { label: string; value: number | null | undefined }) {
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

function EmptyPanel({ msg }: { msg: string }) {
  return <div className="text-[11px] text-muted-foreground italic py-1">{msg}</div>;
}

// =========================================================================
// Formatters
// =========================================================================

function fmt(n: number | null | undefined, suffix = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}${suffix}`;
}

function fmtT(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(2)} k`;
  return n.toFixed(0);
}

function fmtMoneyShort(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} M€`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} k€`;
  return `${Math.round(n)} €`;
}

function fmtU(n: number | null | undefined, suffix = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toFixed(2)} ${suffix}`;
}

function joinNonNull(xs: (string | null | undefined)[]): string {
  return xs.filter(Boolean).join(" · ");
}

function shortProp(p: string | null | undefined): string {
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
