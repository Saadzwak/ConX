/**
 * Logo ConX — typo travaillée, sobre, professionnelle.
 *
 * Design : sans-serif géométrique moderne (Inter / system stack) ;
 * "Con" en regular gris foreground, "X" en bold accent vert primary.
 * Le X est légèrement surdimensionné (110 %) pour donner du caractère sans
 * pictogramme ajouté. Petit point coloré sous le X, repère visuel discret.
 *
 * Variantes :
 *   <Logo />          → 32 px (header, défaut)
 *   <Logo size={48} /> → couverture PDF / écrans À propos
 *   <Logo mono />     → noir uniquement (pour PDF noir et blanc si requis)
 *
 * SVG inline pour qu'il s'imprime net en PDF (weasyprint inline le SVG).
 */
interface LogoProps {
  size?: number;
  mono?: boolean;
  className?: string;
  /** Couleur principale du texte (sans accent). Par défaut : currentColor. */
  textColor?: string;
  /** Couleur de l'accent (X + point). Par défaut : var(--primary) ConX. */
  accentColor?: string;
}

export function Logo({
  size = 32,
  mono = false,
  className,
  textColor,
  accentColor,
}: LogoProps) {
  const accent = mono ? "#111" : (accentColor ?? "hsl(142 71% 35%)");
  const txt = mono ? "#111" : (textColor ?? "hsl(220 13% 18%)");
  // ViewBox 120×40 → ratio ~3:1. Hauteur paramétrable via `size`.
  const width = (size * 120) / 40;
  return (
    <svg
      width={width}
      height={size}
      viewBox="0 0 120 40"
      role="img"
      aria-label="ConX"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <style>
          {`
            .conx-base {
              font-family: 'Inter', 'Manrope', system-ui, -apple-system,
                'Segoe UI', Roboto, sans-serif;
              font-size: 30px;
              letter-spacing: -0.5px;
              font-weight: 600;
            }
            .conx-x {
              font-weight: 800;
              font-size: 32px;
            }
          `}
        </style>
      </defs>
      {/* "Con" en regular */}
      <text
        x="2"
        y="30"
        className="conx-base"
        fill={txt}
        style={{ fontVariantLigatures: "none" }}
      >
        Con
      </text>
      {/* "X" en bold accent */}
      <text x="60" y="31" className="conx-base conx-x" fill={accent}>
        X
      </text>
      {/* Point coloré sous le X (repère discret) */}
      <circle cx="79" cy="36" r="1.6" fill={accent} />
    </svg>
  );
}
