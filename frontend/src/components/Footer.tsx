/**
 * Footer légal obligatoire — bandeau sources Etalab 2.0 (cf. CLAUDE.md §4).
 * Présent sur 100 % des pages (vérification J19).
 */
export function Footer() {
  return (
    <footer className="border-t bg-muted/40 text-xs text-muted-foreground">
      <div className="container py-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="leading-relaxed">
          <strong className="text-foreground">Données</strong> : IGN (LiDAR HD, BD TOPO,
          BD Ortho), CSTB (BDNB 2025-07.a), ADEME (DPE, Base Carbone), INIES (FDES
          statique 30 matériaux), DGFiP (BAN). Licence Ouverte{" "}
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
        <div className="flex gap-3">
          {/* TODO J19 — pages À propos / Méthodologie */}
          <span className="text-muted-foreground/60">
            ConX · v{import.meta.env.VITE_APP_VERSION ?? "0.14.0-j14"}
          </span>
        </div>
      </div>
    </footer>
  );
}
