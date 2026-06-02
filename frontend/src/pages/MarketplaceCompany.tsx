/**
 * Page dédiée par entreprise marketplace — `/marketplace/<slug>`.
 *
 * Cible UX : un architecte ou bailleur qui clique sur un lien dans le
 * pré-cadrage rénovation (« [Goudalle Charpente](marketplace:goudalle-charpente) »)
 * arrive sur une page complète qui :
 *  - présente l'entreprise (photo / avatar, localisation, badges Pacte BB)
 *  - liste les spécialités et produits
 *  - donne accès au site officiel
 *  - propose de la contacter ou de rejoindre une commande groupée
 *
 * Phase 2 marketplace : enrichir avec photos d'usine/produits, gallery
 * réalisations, contacts directs, formulaire devis.
 */
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  MapPin,
  ExternalLink,
  Award,
  Mail,
  Users,
  CheckCircle2,
  Factory,
  Layers,
  Hammer,
  Building2,
  Store,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CompanyAvatar } from "@/components/CompanyAvatar";
import { cn } from "@/lib/utils";
import companiesData from "@/data/marketplace_companies.json";
import type { Company } from "@/pages/Marketplace";

interface MarketplaceData {
  metadata?: unknown;
  companies: Company[];
}
const COMPANIES: Company[] = (companiesData as MarketplaceData).companies;

const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  "ite-mob": { label: "ITE / MOB préfabriqués", icon: Layers, tone: "bg-emerald-50 text-emerald-900 border-emerald-200" },
  "isolation-biosourcee": { label: "Isolation biosourcée", icon: Layers, tone: "bg-amber-50 text-amber-900 border-amber-200" },
  "menuiseries": { label: "Menuiseries bois", icon: Hammer, tone: "bg-orange-50 text-orange-900 border-orange-200" },
  "be-thermique": { label: "Bureau d'études", icon: Building2, tone: "bg-blue-50 text-blue-900 border-blue-200" },
  "architecture": { label: "Architecture", icon: Building2, tone: "bg-purple-50 text-purple-900 border-purple-200" },
  "pose-installation": { label: "Pose & installation", icon: Hammer, tone: "bg-stone-100 text-stone-900 border-stone-200" },
  "systemes-energetiques": { label: "Systèmes énergétiques", icon: Factory, tone: "bg-cyan-50 text-cyan-900 border-cyan-200" },
  "etancheite": { label: "Étanchéité", icon: Factory, tone: "bg-slate-100 text-slate-900 border-slate-200" },
  "reseau": { label: "Réseaux & coopératives", icon: Award, tone: "bg-primary/10 text-primary border-primary/20" },
};

const DEPT_LABELS: Record<string, string> = {
  "59": "Nord",
  "62": "Pas-de-Calais",
  "80": "Somme",
  "60": "Oise",
  "02": "Aisne",
};

export function MarketplaceCompanyPage() {
  const { slug } = useParams<{ slug: string }>();

  const company = useMemo(
    () => COMPANIES.find((c) => c.slug === slug),
    [slug],
  );

  // Entreprises similaires (même catégorie, hors current).
  const related = useMemo(() => {
    if (!company) return [];
    return COMPANIES.filter(
      (c) => c.category === company.category && c.slug !== company.slug,
    ).slice(0, 4);
  }, [company]);

  if (!company) {
    return (
      <div className="container py-12 max-w-2xl text-center">
        <h1 className="text-xl font-semibold mb-2">Entreprise introuvable</h1>
        <p className="text-sm text-muted-foreground mb-4">
          Le slug <code className="bg-muted px-1 rounded">{slug}</code> ne
          correspond à aucune entreprise référencée dans la Marketplace ConX.
        </p>
        <Button asChild variant="outline">
          <Link to="/marketplace">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Retour à la Marketplace
          </Link>
        </Button>
      </div>
    );
  }

  const meta = CATEGORY_META[company.category] ?? {
    label: company.category,
    icon: Factory,
    tone: "bg-muted border-border",
  };
  const Icon = meta.icon;

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
      {/* Fil d'Ariane */}
      <div className="border-b bg-background">
        <div className="container py-2.5 max-w-5xl">
          <Link
            to="/marketplace"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <ArrowLeft className="h-3 w-3" />
            Marketplace
          </Link>
          <span className="text-xs text-muted-foreground mx-2">/</span>
          <span className="text-xs font-medium text-foreground">{company.name}</span>
        </div>
      </div>

      {/* HERO entreprise */}
      <section className="border-b bg-gradient-to-br from-primary/5 via-background to-amber-50/30">
        <div className="container py-8 max-w-5xl">
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {/* Avatar / photo */}
            <div className="md:col-span-1">
              <div className="aspect-[4/3] rounded-lg overflow-hidden border bg-card">
                <CompanyAvatar
                  name={company.name}
                  category={company.category}
                  photoUrl={company.photo_url}
                  size="xl"
                  className="!h-full"
                />
              </div>
              {!company.photo_url && (
                <p className="text-[10px] text-muted-foreground/70 mt-1.5 text-center italic">
                  Photo à venir — vue catégorielle générée
                </p>
              )}
            </div>

            {/* Identité + actions */}
            <div className="md:col-span-2 space-y-3">
              <div className="flex items-center flex-wrap gap-1.5">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-medium",
                    meta.tone,
                  )}
                >
                  <Icon className="h-3 w-3" />
                  {meta.label}
                </span>
                {company.pacte_bois_biosource && (
                  <span
                    className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-medium bg-primary/10 text-primary border-primary/20"
                    title="Partenaire officiel du Pacte Bois-Biosourcés HDF (Fibois HDF / CD2E)"
                  >
                    <Award className="h-3 w-3" />
                    Partenaire Pacte Bois-Biosourcés
                  </span>
                )}
              </div>

              <h1 className="text-2xl md:text-3xl font-bold tracking-tight leading-tight">
                {company.name}
              </h1>

              <div className="text-sm text-muted-foreground inline-flex items-center gap-1.5">
                <MapPin className="h-4 w-4" />
                <span>
                  {company.ville}, {DEPT_LABELS[company.departement] || company.departement} (dpt {company.departement})
                </span>
              </div>

              <p className="text-sm text-foreground/85 leading-relaxed">
                {company.description}
              </p>

              {/* CTAs */}
              <div className="flex flex-wrap gap-2 pt-1">
                {company.website && (
                  <Button asChild size="sm">
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      Visiter le site officiel
                      <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
                    </a>
                  </Button>
                )}
                <Button asChild variant="outline" size="sm">
                  <a
                    href={`mailto:saadbabidi.com@gmail.com?subject=Mise%20en%20relation%20Marketplace%20ConX%20%E2%80%94%20${encodeURIComponent(company.name)}`}
                  >
                    <Mail className="h-3.5 w-3.5 mr-1.5" />
                    Demander une mise en relation
                  </a>
                </Button>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/marketplace/commandes-groupees">
                    <Users className="h-3.5 w-3.5 mr-1.5" />
                    Voir les commandes groupées
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Spécialités + Massification */}
      <section className="container py-8 max-w-5xl">
        <div className="grid md:grid-cols-3 gap-6">
          {/* Spécialités */}
          <div className="md:col-span-2">
            <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
              <Icon className="h-4 w-4 text-primary" />
              Spécialités &amp; savoir-faire
            </h2>
            {company.specialites && company.specialites.length > 0 ? (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {company.specialites.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-foreground/85 leading-snug bg-card border rounded-md px-3 py-2"
                  >
                    <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                Spécialités à compléter.
              </p>
            )}

            {/* Note transparence — placeholder pour future galerie produits */}
            <div className="mt-6 p-4 rounded-md bg-muted/40 border text-xs text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Phase 2 Marketplace</strong> —
              cette fiche sera enrichie d'une galerie de produits ou de
              réalisations dès qu'{company.name.replace(/^L'|^Le |^La |^Les /, "")} aura
              référencé son catalogue auprès de ConX. Données actuelles vérifiées
              sur le site officiel + base CD2E / Fibois HDF.
            </div>
          </div>

          {/* Side panel : commande groupée hint */}
          <aside className="md:col-span-1">
            <div className="rounded-lg border bg-primary/5 border-primary/20 p-4">
              <div className="flex items-center gap-2 text-primary mb-2">
                <Users className="h-4 w-4" />
                <h3 className="text-sm font-semibold">Effet volume</h3>
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed mb-3">
                Les commandes groupées inter-MOA permettent jusqu'à{" "}
                <strong className="text-primary">12&nbsp;% d'économie</strong> sur
                le prix unitaire par effet de mutualisation. {company.name} peut
                répondre à des appels d'offres groupés via la Marketplace.
              </p>
              <Button asChild size="sm" variant="outline" className="w-full">
                <Link to="/marketplace/commandes-groupees">
                  <Users className="h-3.5 w-3.5 mr-1.5" />
                  Commandes ouvertes
                </Link>
              </Button>
            </div>

            <div className="mt-3 rounded-lg border bg-card p-4">
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                Informations
              </h3>
              <dl className="space-y-1.5 text-xs">
                <div>
                  <dt className="text-muted-foreground">Catégorie</dt>
                  <dd className="font-medium">{meta.label}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Localisation</dt>
                  <dd className="font-medium">
                    {company.ville} ({company.departement})
                  </dd>
                </div>
                {company.website && (
                  <div>
                    <dt className="text-muted-foreground">Site web</dt>
                    <dd className="truncate">
                      <a
                        href={company.website}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-primary hover:underline"
                      >
                        {company.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                      </a>
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-muted-foreground">Pacte Bois-Biosourcés</dt>
                  <dd className="font-medium">
                    {company.pacte_bois_biosource ? "Partenaire officiel" : "Non recensé"}
                  </dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      </section>

      {/* Entreprises similaires */}
      {related.length > 0 && (
        <section className="border-t bg-muted/30">
          <div className="container py-8 max-w-5xl">
            <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
              <Store className="h-4 w-4 text-primary" />
              Autres acteurs HDF — {meta.label}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {related.map((c) => (
                <Link
                  key={c.slug}
                  to={`/marketplace/${c.slug}`}
                  className="rounded-lg border bg-card p-3 hover:shadow-md hover:border-primary/30 transition-shadow group"
                >
                  <div className="flex items-start gap-2.5">
                    <CompanyAvatar
                      name={c.name}
                      category={c.category}
                      photoUrl={c.photo_url}
                      size="sm"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold truncate group-hover:text-primary">
                        {c.name}
                      </div>
                      <div className="text-[10px] text-muted-foreground inline-flex items-center gap-1 mt-0.5">
                        <MapPin className="h-2.5 w-2.5" />
                        {c.ville}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
