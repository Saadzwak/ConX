/**
 * Footer légal obligatoire — bandeau sources Etalab 2.0 (cf. CLAUDE.md §4).
 * Présent sur 100 % des pages (vérification J19).
 *
 * Le bandeau positionne ConX comme outil de pré-cadrage professionnel (et
 * non démonstrateur tech) : la mention « Ne remplace pas une étude par
 * maître d'œuvre » est l'écran de sérieux essentiel pour le jury.
 */
export function Footer() {
  return (
    <footer className="border-t bg-muted/40 text-xs text-muted-foreground">
      <div className="container py-3 flex flex-col gap-1.5">
        <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
          <div className="leading-relaxed">
            <strong className="text-foreground">ConX</strong> — outil de
            pré-cadrage pour la rénovation hors-site biosourcée
            <span className="hidden sm:inline">
              {" "}
              · ne remplace pas une étude par maître d'œuvre
            </span>
            .
          </div>
          <span className="text-muted-foreground/60 shrink-0">
            v{import.meta.env.VITE_APP_VERSION ?? "0.14.0-j14"}
          </span>
        </div>
        <div className="leading-relaxed text-[11px]">
          <strong className="text-foreground/80">Données</strong> : IGN (LiDAR
          HD, BD TOPO, BD Ortho), CSTB (BDNB 2025-07.a), ADEME (DPE, Base
          Carbone), INIES (FDES), DGFiP (BAN). Licence Ouverte{" "}
          <a
            href="https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf"
            className="underline hover:text-foreground"
            target="_blank"
            rel="noreferrer noopener"
          >
            Etalab 2.0
          </a>
          .
        </div>
      </div>
    </footer>
  );
}
