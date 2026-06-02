/**
 * Page Marketplace ConX — annuaire structuré des acteurs HDF
 * de la rénovation hors-site biosourcée.
 *
 * Vision pitch deck §08 : « De la fragmentation au réseau structuré ».
 * Les bailleurs et architectes accèdent aux fabricants, BE, entreprises
 * de pose, etc. sur un même environnement — au lieu de chercher un par
 * un. Mutualisation de la demande inter-MOA = ~12 % d'économie unitaire
 * par effet volume (cf. pitch).
 *
 * MVP : annuaire filtrable. Les transactions (devis groupés, appels
 * d'offres collectifs) sont Phase 2.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Search,
  MapPin,
  ExternalLink,
  Store,
  Factory,
  Layers,
  Hammer,
  Building2,
  Award,
  Filter,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CompanyAvatar } from "@/components/CompanyAvatar";
import { cn } from "@/lib/utils";
import companiesData from "@/data/marketplace_companies.json";

export interface Company {
  name: string;
  slug: string;
  category: string;
  ville: string;
  departement: string;
  website: string;
  specialites: string[];
  description: string;
  pacte_bois_biosource: boolean;
  /** URL d'une vraie photo (logo, usine, produit). Si vide, on génère un
   *  avatar SVG catégoriel via `CompanyAvatar`. */
  photo_url?: string | null;
}

interface MarketplaceData {
  metadata?: unknown;
  companies: Company[];
}

const COMPANIES: Company[] = (companiesData as MarketplaceData).companies;

const CATEGORIES: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  "ite-mob": {
    label: "ITE / MOB préfabriqués",
    icon: Layers,
    tone: "bg-emerald-50 text-emerald-900 border-emerald-200",
  },
  "isolation-biosourcee": {
    label: "Isolation biosourcée",
    icon: Layers,
    tone: "bg-amber-50 text-amber-900 border-amber-200",
  },
  "menuiseries": {
    label: "Menuiseries bois",
    icon: Hammer,
    tone: "bg-orange-50 text-orange-900 border-orange-200",
  },
  "be-thermique": {
    label: "Bureau d'études",
    icon: Building2,
    tone: "bg-blue-50 text-blue-900 border-blue-200",
  },
  "architecture": {
    label: "Architecture",
    icon: Building2,
    tone: "bg-purple-50 text-purple-900 border-purple-200",
  },
  "pose-installation": {
    label: "Pose & installation",
    icon: Hammer,
    tone: "bg-stone-100 text-stone-900 border-stone-200",
  },
  "systemes-energetiques": {
    label: "Systèmes énergétiques",
    icon: Factory,
    tone: "bg-cyan-50 text-cyan-900 border-cyan-200",
  },
  "etancheite": {
    label: "Étanchéité",
    icon: Factory,
    tone: "bg-slate-100 text-slate-900 border-slate-200",
  },
  "reseau": {
    label: "Réseaux & coopératives",
    icon: Award,
    tone: "bg-primary/10 text-primary border-primary/20",
  },
};

const DEPT_LABELS: Record<string, string> = {
  "59": "Nord",
  "62": "Pas-de-Calais",
  "80": "Somme",
  "60": "Oise",
  "02": "Aisne",
};

export function MarketplacePage() {
  const [searchParams] = useSearchParams();
  const refSlug = searchParams.get("ref");
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeDept, setActiveDept] = useState<string | null>(null);
  const [pacteOnly, setPacteOnly] = useState(false);
  // Si la page est ouverte via un lien `marketplace:slug` depuis un plan
  // (ex. "[Goudalle Charpente](marketplace:goudalle-charpente)"), on
  // pré-remplit la recherche avec le nom de l'entreprise pour la mettre
  // en haut + on scroll vers sa carte une fois rendue.
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});
  useEffect(() => {
    if (!refSlug) return;
    const match = COMPANIES.find((c) => c.slug === refSlug);
    if (match) setQuery(match.name);
  }, [refSlug]);
  useEffect(() => {
    if (!refSlug) return;
    const node = cardRefs.current[refSlug];
    if (node) {
      // petit délai pour laisser le filter rendre la carte
      setTimeout(() => {
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        node.classList.add(
          "ring-2",
          "ring-primary",
          "ring-offset-2",
          "ring-offset-background",
        );
        setTimeout(() => {
          node.classList.remove(
            "ring-2",
            "ring-primary",
            "ring-offset-2",
            "ring-offset-background",
          );
        }, 2500);
      }, 150);
    }
  }, [refSlug, query]);

  // Stats globales (calculées une fois)
  const stats = useMemo(() => {
    const byCat: Record<string, number> = {};
    const byDept: Record<string, number> = {};
    let pacte = 0;
    for (const c of COMPANIES) {
      byCat[c.category] = (byCat[c.category] || 0) + 1;
      byDept[c.departement] = (byDept[c.departement] || 0) + 1;
      if (c.pacte_bois_biosource) pacte++;
    }
    return { total: COMPANIES.length, byCat, byDept, pacte };
  }, []);

  // Filtre composé
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return COMPANIES.filter((c) => {
      if (activeCategory && c.category !== activeCategory) return false;
      if (activeDept && c.departement !== activeDept) return false;
      if (pacteOnly && !c.pacte_bois_biosource) return false;
      if (q) {
        const hay = (
          c.name +
          " " +
          c.description +
          " " +
          c.ville +
          " " +
          c.specialites.join(" ")
        ).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [query, activeCategory, activeDept, pacteOnly]);

  const hasFilters = activeCategory || activeDept || pacteOnly || query.trim();

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
      {/* HERO */}
      <section className="border-b bg-gradient-to-br from-primary/5 via-background to-amber-50/40">
        <div className="container py-10 max-w-6xl">
          <div className="flex items-center gap-2 text-xs text-primary font-semibold tracking-wide uppercase mb-2">
            <Store className="h-3.5 w-3.5" />
            Marketplace ConX · Phase 1
          </div>
          <h1 className="text-3xl md:text-4xl font-bold leading-tight tracking-tight">
            La filière rénovation hors-site biosourcée
            <br />
            <span className="text-primary">Hauts-de-France</span>, sur un seul
            écran.
          </h1>
          <p className="mt-3 text-base text-muted-foreground max-w-3xl leading-relaxed">
            {stats.total} acteurs vérifiés — fabricants MOB, isolation
            biosourcée, menuiseries bois, bureaux d'études, architectes,
            coopératives filière. Tous implantés en HDF. Trouvez les bons
            partenaires pour chaque lot de votre pré-cadrage.
          </p>

          {/* CTA Commandes groupées */}
          <div className="mt-4">
            <Link
              to="/marketplace/commandes-groupees"
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <span className="font-medium">Commandes groupées ouvertes</span>
              <span className="text-xs opacity-90">— mutualiser pour économiser ~12 %</span>
              <span aria-hidden>→</span>
            </Link>
          </div>

          {/* Quick stats */}
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl">
            <StatCard
              icon={<Factory className="h-4 w-4" />}
              value={stats.total}
              label="Acteurs HDF référencés"
            />
            <StatCard
              icon={<Layers className="h-4 w-4" />}
              value={stats.byCat["ite-mob"] || 0}
              label="Fabricants ITE / MOB"
            />
            <StatCard
              icon={<Award className="h-4 w-4" />}
              value={stats.pacte}
              label="Partenaires Pacte Bois-Biosourcés"
              tone="primary"
            />
            <StatCard
              icon={<MapPin className="h-4 w-4" />}
              value={Object.keys(stats.byDept).length}
              label="Départements HDF"
            />
          </div>
        </div>
      </section>

      {/* FILTRES + SEARCH */}
      <section className="border-b bg-card sticky top-14 z-10">
        <div className="container py-3 max-w-6xl">
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Chercher par nom, spécialité, ville…"
                className="w-full h-9 pl-9 pr-3 text-sm rounded-md border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            {/* Reset filters */}
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setActiveCategory(null);
                  setActiveDept(null);
                  setPacteOnly(false);
                  setQuery("");
                }}
              >
                <X className="h-3.5 w-3.5 mr-1" />
                Réinitialiser
              </Button>
            )}
          </div>

          {/* Chip filters */}
          <div className="mt-3 flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-1 flex items-center gap-1">
              <Filter className="h-3 w-3" />
              Catégorie :
            </span>
            {Object.entries(CATEGORIES).map(([slug, meta]) => {
              const n = stats.byCat[slug] || 0;
              if (n === 0) return null;
              const active = activeCategory === slug;
              return (
                <button
                  key={slug}
                  onClick={() => setActiveCategory(active ? null : slug)}
                  className={cn(
                    "px-2 py-0.5 text-[11px] rounded-full border transition",
                    active
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background hover:bg-accent",
                  )}
                >
                  {meta.label}
                  <span className="ml-1 opacity-70">({n})</span>
                </button>
              );
            })}
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground ml-2 mr-1">
              · Dpt :
            </span>
            {Object.entries(DEPT_LABELS).map(([code, label]) => {
              const n = stats.byDept[code] || 0;
              if (n === 0) return null;
              const active = activeDept === code;
              return (
                <button
                  key={code}
                  onClick={() => setActiveDept(active ? null : code)}
                  className={cn(
                    "px-2 py-0.5 text-[11px] rounded-full border transition",
                    active
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background hover:bg-accent",
                  )}
                  title={label}
                >
                  {code} {label}
                  <span className="ml-1 opacity-70">({n})</span>
                </button>
              );
            })}
            <button
              onClick={() => setPacteOnly((v) => !v)}
              className={cn(
                "ml-2 px-2 py-0.5 text-[11px] rounded-full border transition inline-flex items-center gap-1",
                pacteOnly
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background hover:bg-accent",
              )}
              title="Partenaire officiel du Pacte Bois-Biosourcés HDF (Fibois/CD2E)"
            >
              <Award className="h-3 w-3" />
              Pacte Bois-Biosourcés
            </button>
          </div>
        </div>
      </section>

      {/* RÉSULTATS */}
      <section className="container py-6 max-w-6xl">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="text-sm font-semibold text-foreground">
            {filtered.length} acteur{filtered.length > 1 ? "s" : ""}
            {hasFilters ? " trouvé" + (filtered.length > 1 ? "s" : "") : " référencé" + (filtered.length > 1 ? "s" : "")}
          </h2>
          <p className="text-[11px] text-muted-foreground">
            Données vérifiées Mai 2026 — sources publiques CD2E, Fibois HDF, sites
            officiels entreprises.
          </p>
        </div>

        {filtered.length === 0 ? (
          <EmptyResult />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((c) => (
              <CompanyCard
                key={c.slug}
                c={c}
                cardRef={(node) => {
                  cardRefs.current[c.slug] = node;
                }}
              />
            ))}
          </div>
        )}
      </section>

      {/* Méthodologie + sources */}
      <section className="border-t bg-muted/30 mt-8">
        <div className="container py-8 max-w-4xl">
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Award className="h-4 w-4 text-primary" />
                Comment l'annuaire est construit
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Chaque entreprise est vérifiée sur trois critères :
                implantation effective en Hauts-de-France, présence d'un site
                officiel actif, alignement avec la filière hors-site
                biosourcée. Les partenaires officiels du{" "}
                <strong className="text-foreground">
                  Pacte Bois-Biosourcés HDF
                </strong>{" "}
                (Fibois HDF / CD2E) sont marqués d'un badge dédié.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Store className="h-4 w-4 text-primary" />
                Votre entreprise n'est pas listée ?
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed mb-3">
                Pour rejoindre l'annuaire et accéder aux pipelines de projets
                pré-qualifiés via la mutualisation inter-MOA, contactez
                l'équipe ConX.
              </p>
              <Button asChild variant="outline" size="sm">
                <a
                  href="mailto:saadbabidi.com@gmail.com?subject=Demande%20de%20r%C3%A9f%C3%A9rencement%20Marketplace%20ConX"
                >
                  Demander un référencement
                </a>
              </Button>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-border/50 flex flex-wrap justify-between items-center gap-3 text-[11px] text-muted-foreground">
            <div>
              <strong className="text-foreground/80">Sources de vérification</strong> :
              Fibois Hauts-de-France · CD2E · INSEE/Industrie Explorer · sites
              officiels des entreprises.
            </div>
            <div className="flex gap-3">
              <Link to="/strategie" className="hover:text-foreground underline-offset-2 hover:underline">
                ← Retour à la carte
              </Link>
              <span className="text-muted-foreground/40">·</span>
              <Link to="/projet" className="hover:text-foreground underline-offset-2 hover:underline">
                Ouvrir Mode Projet
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// =========================================================================
// Sous-composants
// =========================================================================

function StatCard({
  icon,
  value,
  label,
  tone,
}: {
  icon: React.ReactNode;
  value: number;
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
        <span className="text-[10px] uppercase tracking-wide leading-none">{label}</span>
      </div>
      <div className="text-2xl font-bold leading-none tabular-nums">{value}</div>
    </div>
  );
}

function CompanyCard({
  c,
  cardRef,
}: {
  c: Company;
  cardRef?: (node: HTMLElement | null) => void;
}) {
  const meta = CATEGORIES[c.category] ?? {
    label: c.category,
    icon: Factory,
    tone: "bg-muted text-foreground border-border",
  };
  return (
    <article
      ref={cardRef}
      className="rounded-lg border bg-card hover:shadow-md hover:border-primary/30 transition-shadow flex flex-col h-full overflow-hidden group"
    >
      {/* Bandeau photo / avatar — clic vers page dédiée */}
      <Link
        to={`/marketplace/${c.slug}`}
        className="block aspect-[16/9] overflow-hidden bg-muted relative"
      >
        <CompanyAvatar
          name={c.name}
          category={c.category}
          photoUrl={c.photo_url}
          size="xl"
          className="!h-full !w-full !rounded-none"
        />
        {c.pacte_bois_biosource && (
          <span className="absolute top-1.5 right-1.5 inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] rounded-full border font-medium bg-white/95 text-primary border-primary/20 shadow-sm">
            <Award className="h-2.5 w-2.5" />
            Pacte BB
          </span>
        )}
      </Link>

      <div className="p-4 flex flex-col flex-1">
        <header className="mb-2">
          <Link to={`/marketplace/${c.slug}`}>
            <h3 className="font-semibold text-sm leading-tight group-hover:text-primary transition-colors">
              {c.name}
            </h3>
          </Link>
          <div className="text-[11px] text-muted-foreground mt-0.5 inline-flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {c.ville} · Dpt {c.departement}
          </div>
        </header>

        <div className="flex flex-wrap gap-1 mb-2">
          <span
            className={cn(
              "inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full border font-medium",
              meta.tone,
            )}
          >
            {meta.label}
          </span>
        </div>

        <p className="text-xs text-foreground/80 leading-snug flex-1 mb-3 line-clamp-3">
          {c.description}
        </p>

        {c.specialites && c.specialites.length > 0 && (
          <div className="text-[11px] text-muted-foreground mb-3 leading-snug">
            <strong className="text-foreground/70">Spécialités :</strong>{" "}
            {c.specialites.slice(0, 3).join(" · ")}
            {c.specialites.length > 3 && " · …"}
          </div>
        )}

        <div className="flex items-center justify-between text-xs mt-auto">
          <Link
            to={`/marketplace/${c.slug}`}
            className="text-primary font-medium inline-flex items-center gap-1 hover:underline"
          >
            Voir la fiche
            <span aria-hidden>→</span>
          </Link>
          {c.website && (
            <a
              href={c.website}
              target="_blank"
              rel="noreferrer noopener"
              className="text-muted-foreground inline-flex items-center gap-1 hover:text-foreground"
              onClick={(e) => e.stopPropagation()}
            >
              Site
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

function EmptyResult() {
  return (
    <div className="text-center py-12 text-muted-foreground">
      <Search className="h-8 w-8 mx-auto mb-3 opacity-30" />
      <p className="text-sm">Aucun acteur ne correspond à ces filtres.</p>
      <p className="text-xs mt-1">Essayez d'élargir votre recherche.</p>
    </div>
  );
}
