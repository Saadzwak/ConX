/**
 * CompanyAvatar — image illustrative d'une entreprise marketplace.
 *
 * Si `photoUrl` est fourni, charge la vraie photo (avec lazy loading + fallback
 * automatique vers l'avatar SVG en cas d'erreur). Sinon, génère un avatar
 * SVG avec :
 *  - initiales (2 lettres tirées du nom)
 *  - couleur de fond catégorielle (verte ITE-MOB, ambre isolation, etc.)
 *  - pattern subtil (lignes diagonales discrètes)
 *
 * L'avatar SVG reste cohérent visuellement avec le reste de ConX, et
 * professionnel (pas de "placeholder cartoon"). Il sera remplacé par les
 * vraies photos d'usine / produits quand les entreprises les fourniront.
 */
import { useState } from "react";
import { cn } from "@/lib/utils";

interface Props {
  name: string;
  category: string;
  photoUrl?: string | null;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

// Palette catégorielle alignée sur celle de Marketplace.tsx
const CATEGORY_COLORS: Record<string, { bg: string; fg: string }> = {
  "ite-mob": { bg: "#1c7c54", fg: "#ffffff" }, // vert ConX
  "isolation-biosourcee": { bg: "#b45309", fg: "#ffffff" }, // ambre
  "menuiseries": { bg: "#ea580c", fg: "#ffffff" }, // orange
  "be-thermique": { bg: "#1d4ed8", fg: "#ffffff" }, // bleu
  "architecture": { bg: "#7c3aed", fg: "#ffffff" }, // violet
  "pose-installation": { bg: "#57534e", fg: "#ffffff" }, // stone
  "systemes-energetiques": { bg: "#0891b2", fg: "#ffffff" }, // cyan
  "etancheite": { bg: "#475569", fg: "#ffffff" }, // slate
  "reseau": { bg: "#0f766e", fg: "#ffffff" }, // teal
};

const SIZE_CLS: Record<NonNullable<Props["size"]>, { box: string; font: string }> = {
  sm: { box: "h-9 w-9", font: "text-[11px]" },
  md: { box: "h-14 w-14", font: "text-base" },
  lg: { box: "h-20 w-20", font: "text-xl" },
  xl: { box: "h-32 w-full", font: "text-3xl" },
};

function getInitials(name: string): string {
  // Strip parenthèses + slash + numéros, prend les 2 premiers mots significatifs.
  const clean = name
    .replace(/\([^)]*\)/g, "")
    .replace(/[/&-]/g, " ")
    .replace(/[0-9]/g, "")
    .trim();
  const parts = clean.split(/\s+/).filter((p) => p.length > 1 && !/^(et|de|du|la|le|les|des)$/i.test(p));
  if (parts.length === 0) return name.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function CompanyAvatar({
  name,
  category,
  photoUrl,
  size = "md",
  className,
}: Props) {
  const [imgError, setImgError] = useState(false);
  const showPhoto = photoUrl && !imgError;

  const colors = CATEGORY_COLORS[category] ?? CATEGORY_COLORS["reseau"];
  const initials = getInitials(name);
  const sizeCls = SIZE_CLS[size];

  if (showPhoto && photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name}
        loading="lazy"
        onError={() => setImgError(true)}
        className={cn(
          sizeCls.box,
          "object-cover rounded-md bg-muted",
          size === "xl" && "rounded-lg",
          className,
        )}
      />
    );
  }

  // Avatar SVG fallback — pattern diagonal subtil + initiales centrées
  const patternId = `pat-${category}-${initials}`;
  return (
    <svg
      role="img"
      aria-label={name}
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      className={cn(
        sizeCls.box,
        "rounded-md shrink-0",
        size === "xl" && "rounded-lg w-full",
        className,
      )}
    >
      <defs>
        <pattern
          id={patternId}
          patternUnits="userSpaceOnUse"
          width="10"
          height="10"
          patternTransform="rotate(45)"
        >
          <rect width="10" height="10" fill={colors.bg} />
          <line x1="0" y1="0" x2="0" y2="10" stroke="#ffffff" strokeOpacity="0.06" strokeWidth="2" />
        </pattern>
      </defs>
      <rect width="100" height="100" fill={`url(#${patternId})`} />
      <text
        x="50"
        y="50"
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily="Inter, system-ui, sans-serif"
        fontWeight="700"
        fontSize={size === "xl" ? "38" : "42"}
        fill={colors.fg}
        letterSpacing="-1"
      >
        {initials}
      </text>
    </svg>
  );
}
