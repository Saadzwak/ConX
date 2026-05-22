/**
 * Mode Projet — viewer 3D + chat itératif IA.
 * Placeholder J14 — corps construit en J15 (Three.js) + J16 (chat SSE).
 */

import { useParams, Link } from "react-router-dom";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ProjetPage() {
  const { id } = useParams<{ id?: string }>();

  if (!id) {
    return (
      <div className="container py-10 max-w-2xl">
        <h1 className="text-2xl font-semibold mb-2">Mode Projet</h1>
        <p className="text-muted-foreground mb-6">
          Sélectionnez un bâtiment depuis la carte Stratégie pour ouvrir sa fiche,
          générer un plan rénovation IA et explorer la 3D LiDAR.
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

  return (
    <div className="container py-10">
      <h1 className="text-2xl font-semibold mb-1">Mode Projet</h1>
      <p className="text-sm text-muted-foreground mb-6 font-mono">{id}</p>
      <div className="rounded-md border-2 border-dashed p-10 text-center text-muted-foreground">
        <p className="font-medium">Viewer 3D + chat itératif IA</p>
        <p className="text-xs mt-1">À construire J15 (Three.js LiDAR) + J16 (chat SSE Agent Plan).</p>
      </div>
    </div>
  );
}
