import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Couleur officielle ADEME pour une classe DPE. */
export function dpeColor(classe: string | null | undefined): string {
  const c = (classe ?? "").toUpperCase();
  switch (c) {
    case "A":
      return "#2ECC71";
    case "B":
      return "#82C341";
    case "C":
      return "#FFD11A";
    case "D":
      return "#FFAA1A";
    case "E":
      return "#F37522";
    case "F":
      return "#E84A1A";
    case "G":
      return "#D60000";
    default:
      return "#9CA3AF";
  }
}

/** Couleur scoring (gradient blanc → vert ConX pour score 0 → 1). */
export function scoreColor(score: number): [number, number, number, number] {
  // score 0..1 → couleur RGBA (deck.gl format)
  const s = Math.max(0, Math.min(1, score));
  // Interp blanc (240,240,240) → vert ConX (44, 160, 90)
  const r = Math.round(240 + (44 - 240) * s);
  const g = Math.round(240 + (160 - 240) * s);
  const b = Math.round(240 + (90 - 240) * s);
  return [r, g, b, 200];
}

/** Formate une bbox WGS84 en string pour l'API. */
export function formatBbox(bbox: [number, number, number, number]): string {
  return bbox.map((v) => v.toFixed(6)).join(",");
}
