/**
 * Page Commandes Groupées Marketplace — `/marketplace/commandes-groupees`.
 *
 * Implémente le narratif pitch §08 « De la fragmentation au réseau structuré ».
 *
 * Mécanisme :
 *  - Plusieurs MOA (bailleurs sociaux, collectivités, copropriétés) publient
 *    leur besoin sur un même lot technique (ITE ouate, menuiseries bois,
 *    PAC collective…).
 *  - ConX agrège les volumes pour atteindre la masse critique.
 *  - Un appel d'offres groupé est lancé auprès des fabricants HDF.
 *  - Effet volume → ~12 % d'économie sur le prix unitaire (médiane CD2E /
 *    retours filière 2025).
 *
 * Phase 1 (actuelle) : annuaire des commandes ouvertes (collecte /
 * consultation / attribution).
 * Phase 2 : workflow complet de souscription + appariement fabricants +
 * suivi exécution.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Users,
  ArrowLeft,
  Clock,
  CheckCircle2,
  Hourglass,
  TrendingDown,
  Layers,
  Hammer,
  Building2,
  Factory,
  Mail,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import groupOrdersData from "@/data/group_orders.json";
import companiesData from "@/data/marketplace_companies.json";
import type { Company } from "@/pages/Marketplace";

interface GroupOrder {
  slug: string;
  title: string;
  category: string;
  status: "collecte" | "consultation" | "attribution";
  volume_cumule_m2: number;
  volume_alt?: string;
  n_moa: number;
  moa_types: string[];
  deadline_collecte: string;
  deadline_consultation: string;
  economie_estimee_pct: number;
  fabricants_pressentis_slugs: string[];
  description: string;
  ratio_unite: string;
  ratio_marche: string;
  ratio_groupe_cible: string;
}

const ORDERS = (groupOrdersData as { orders: GroupOrder[] }).orders;
const COMPANIES = (
  companiesData as { companies: Company[] }
).companies;

const STATUS_META: Record<
  GroupOrder["status"],
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  collecte: {
    label: "Collecte en cours",
    icon: Hourglass,
    tone: "bg-amber-50 text-amber-900 border-amber-200",
  },
  consultation: {
    label: "Consultation lancée",
    icon: Clock,
    tone: "bg-blue-50 text-blue-900 border-blue-200",
  },
  attribution: {
    label: "Lauréat retenu",
    icon: CheckCircle2,
    tone: "bg-emerald-50 text-emerald-900 border-emerald-200",
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  "ite-mob": "ITE / MOB",
  "isolation-biosourcee": "Isolation biosourcée",
  "menuiseries": "Menuiseries bois",
  "be-thermique": "Bureau d'études / AMO",
  "systemes-energetiques": "Systèmes énergétiques",
  "etancheite": "Étanchéité",
  "architecture": "Architecture",
  "pose-installation": "Pose & installation",
  "reseau": "Réseaux & coopératives",
};

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  "ite-mob": Layers,
  "isolation-biosourcee": Layers,
  "menuiseries": Hammer,
  "be-thermique": Building2,
  "systemes-energetiques": Factory,
  "etancheite": Factory,
  "architecture": Building2,
  "pose-installation": Hammer,
  "reseau": Users,
};

export function MarketplaceGroupOrdersPage() {
  const [statusFilter, setStatusFilter] = useState<GroupOrder["status"] | null>(null);

  const filtered = useMemo(() => {
    if (!statusFilter) return ORDERS;
    return ORDERS.filter((o) => o.status === statusFilter);
  }, [statusFilter]);

  const stats = useMemo(() => {
    const totalMOA = ORDERS.reduce((sum, o) => sum + o.n_moa, 0);
    const avgEconomie = ORDERS.reduce((s, o) => s + o.economie_estimee_pct, 0) / ORDERS.length;
    const byStatus: Record<string, number> = {};
    for (const o of ORDERS) byStatus[o.status] = (byStatus[o.status] || 0) + 1;
    return {
      n_orders: ORDERS.length,
      totalMOA,
      avgEconomie: Math.round(avgEconomie),
      byStatus,
    };
  }, []);

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
      {/* HEADER */}
      <section className="border-b bg-gradient-to-br from-primary/5 via-background to-amber-50/30">
        <div className="container py-8 max-w-5xl">
          <Link
            to="/marketplace"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mb-3"
          >
            <ArrowLeft className="h-3 w-3" />
            Retour à la Marketplace
          </Link>

          <div className="flex items-center gap-2 text-xs text-primary font-semibold tracking-wide uppercase mb-2">
            <Users className="h-3.5 w-3.5" />
            Marketplace ConX · Commandes groupées
          </div>
          <h1 className="text-3xl md:text-4xl font-bold leading-tight tracking-tight">
            Mutualiser la demande
            <br />
            <span className="text-primary">pour structurer la filière</span>.
          </h1>
          <p className="mt-3 text-base text-muted-foreground max-w-3xl leading-relaxed">
            Plusieurs maîtres d'ouvrage rejoignent un même appel d'offres lot
            par lot — ITE ouate cellulose, menuiseries bois, PAC collective,
            isolation chanvre. L'effet volume permet jusqu'à{" "}
            <strong className="text-primary">~12 % d'économie</strong> sur le
            prix unitaire, tout en sécurisant les volumes pour les fabricants
            HDF.
          </p>

          {/* Stats globales */}
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl">
            <BigStat
              icon={<Layers className="h-4 w-4" />}
              value={stats.n_orders}
              label="Commandes actives"
            />
            <BigStat
              icon={<Users className="h-4 w-4" />}
              value={stats.totalMOA}
              label="MOA participants"
            />
            <BigStat
              icon={<TrendingDown className="h-4 w-4" />}
              value={`${stats.avgEconomie} %`}
              label="Économie moyenne estimée"
              tone="primary"
            />
            <BigStat
              icon={<CheckCircle2 className="h-4 w-4" />}
              value={stats.byStatus.attribution || 0}
              label="Lauréats attribués"
            />
          </div>
        </div>
      </section>

      {/* COMMENT ÇA MARCHE */}
      <section className="border-b bg-card">
        <div className="container py-6 max-w-5xl">
          <h2 className="text-sm font-semibold mb-3 inline-flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Comment fonctionne une commande groupée
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Step
              n={1}
              title="Publier un besoin"
              text="Un MOA publie son besoin (lot technique, volume, calendrier) sur ConX."
            />
            <Step
              n={2}
              title="Agréger les volumes"
              text="ConX agrège les besoins similaires de plusieurs MOA HDF. Masse critique atteinte → consultation."
            />
            <Step
              n={3}
              title="Consultation groupée"
              text="Appel d'offres unique lancé auprès des fabricants HDF référencés."
            />
            <Step
              n={4}
              title="Attribution"
              text="Lauréat sélectionné, contrats individuels par MOA mais conditions unitaires harmonisées."
            />
          </div>
        </div>
      </section>

      {/* FILTRES STATUT */}
      <section className="border-b bg-card sticky top-14 z-10">
        <div className="container py-2.5 max-w-5xl flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Statut :
          </span>
          <FilterChip
            label="Toutes"
            active={!statusFilter}
            onClick={() => setStatusFilter(null)}
            count={ORDERS.length}
          />
          {(["collecte", "consultation", "attribution"] as const).map((s) => (
            <FilterChip
              key={s}
              label={STATUS_META[s].label}
              active={statusFilter === s}
              onClick={() =>
                setStatusFilter(statusFilter === s ? null : s)
              }
              count={stats.byStatus[s] || 0}
            />
          ))}
        </div>
      </section>

      {/* LISTE COMMANDES */}
      <section className="container py-6 max-w-5xl">
        <div className="space-y-3">
          {filtered.map((o) => (
            <OrderCard key={o.slug} order={o} />
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t bg-muted/30">
        <div className="container py-8 max-w-3xl text-center">
          <h3 className="text-lg font-semibold mb-2">
            Maître d'ouvrage ? Publiez votre besoin.
          </h3>
          <p className="text-sm text-muted-foreground max-w-2xl mx-auto leading-relaxed mb-4">
            Bailleurs sociaux, collectivités, copropriétés : ajoutez votre lot
            de rénovation à une commande groupée existante ou publiez un
            nouveau besoin. L'équipe ConX vous accompagne dans la
            qualification du périmètre.
          </p>
          <Button asChild size="sm">
            <a href="mailto:saadbabidi.com@gmail.com?subject=Publier%20une%20commande%20group%C3%A9e%20Marketplace%20ConX">
              <Mail className="h-3.5 w-3.5 mr-1.5" />
              Publier un besoin
            </a>
          </Button>
        </div>
      </section>
    </div>
  );
}

// =========================================================================
// Sous-composants
// =========================================================================

function BigStat({
  icon,
  value,
  label,
  tone,
}: {
  icon: React.ReactNode;
  value: number | string;
  label: string;
  tone?: "primary";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-3",
        tone === "primary" && "bg-primary/5 border-primary/20",
      )}
    >
      <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
        {icon}
        <span className="text-[10px] uppercase tracking-wide leading-none">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold leading-none tabular-nums">{value}</div>
    </div>
  );
}

function Step({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="h-6 w-6 rounded-full bg-primary text-primary-foreground text-xs font-bold grid place-items-center">
          {n}
        </span>
        <h3 className="text-xs font-semibold">{title}</h3>
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">{text}</p>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
  count,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 text-xs rounded-full border transition",
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-background hover:bg-accent border-input",
      )}
    >
      {label}
      {count !== undefined && (
        <span className="ml-1 opacity-70">({count})</span>
      )}
    </button>
  );
}

function OrderCard({ order: o }: { order: GroupOrder }) {
  const status = STATUS_META[o.status];
  const StatusIcon = status.icon;
  const CategoryIcon = CATEGORY_ICONS[o.category] ?? Factory;

  const fabricants = o.fabricants_pressentis_slugs
    .map((slug) => COMPANIES.find((c) => c.slug === slug))
    .filter((c): c is Company => c !== undefined);

  return (
    <article className="rounded-lg border bg-card overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-5">
        <div className="flex flex-wrap items-start gap-2 mb-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-medium",
              status.tone,
            )}
          >
            <StatusIcon className="h-3 w-3" />
            {status.label}
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-medium bg-muted/60 border-border">
            <CategoryIcon className="h-3 w-3" />
            {CATEGORY_LABELS[o.category] || o.category}
          </span>
          <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-medium bg-primary/10 text-primary border-primary/20">
            <TrendingDown className="h-3 w-3" />~{o.economie_estimee_pct} % d'économie
          </span>
        </div>

        <h3 className="text-base font-semibold leading-snug mb-1.5">
          {o.title}
        </h3>
        <p className="text-xs text-foreground/80 leading-relaxed mb-3">
          {o.description}
        </p>

        {/* Métriques clés */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-3">
          <Metric
            label="Volume cumulé"
            value={
              o.volume_cumule_m2 > 0
                ? `${o.volume_cumule_m2.toLocaleString("fr-FR")} m²`
                : o.volume_alt || "—"
            }
          />
          <Metric label="MOA participants" value={`${o.n_moa}`} />
          <Metric
            label="Cible groupée"
            value={o.ratio_groupe_cible}
            sub={`marché : ${o.ratio_marche}`}
          />
          <Metric label="Unité" value={o.ratio_unite} small />
        </div>

        {/* MOA types */}
        <div className="text-[10.5px] text-muted-foreground mb-3 leading-snug">
          <strong className="text-foreground/70">MOA participants :</strong>{" "}
          {o.moa_types.join(" · ")}
        </div>

        {/* Fabricants pressentis */}
        {fabricants.length > 0 && (
          <div className="border-t pt-3 mt-3">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
              {o.status === "attribution"
                ? "Lauréats retenus"
                : "Fabricants HDF pressentis"}{" "}
              ({fabricants.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {fabricants.map((f) => (
                <Link
                  key={f.slug}
                  to={`/marketplace/${f.slug}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-md border bg-card hover:border-primary/40 hover:text-primary transition-colors"
                >
                  {f.name}
                  <span className="text-[10px] text-muted-foreground">
                    · {f.ville}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Footer dates + CTA */}
        <div className="border-t mt-3 pt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
          <div>
            Collecte jusqu'au{" "}
            <strong className="text-foreground">{o.deadline_collecte}</strong> ·
            Consultation lancée{" "}
            <strong className="text-foreground">{o.deadline_consultation}</strong>
          </div>
          {o.status !== "attribution" && (
            <Button asChild size="sm" variant="outline">
              <a
                href={`mailto:saadbabidi.com@gmail.com?subject=Rejoindre%20la%20commande%20group%C3%A9e%20%E2%80%94%20${encodeURIComponent(o.title)}`}
              >
                <Users className="h-3 w-3 mr-1" />
                Rejoindre
              </a>
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}

function Metric({
  label,
  value,
  sub,
  small,
}: {
  label: string;
  value: string;
  sub?: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-md bg-muted/40 px-2 py-1.5">
      <div className="text-[9.5px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={cn("font-semibold tabular-nums leading-snug", small ? "text-[10.5px]" : "text-xs")}>
        {value}
      </div>
      {sub && (
        <div className="text-[9.5px] text-muted-foreground/70 mt-0.5 truncate" title={sub}>
          {sub}
        </div>
      )}
    </div>
  );
}
