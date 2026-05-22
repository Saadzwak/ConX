/**
 * Mode Conformité IFC — drag-and-drop + validation.
 * Placeholder J14 — corps construit en J17.
 */

export function IfcPage() {
  return (
    <div className="container py-10 max-w-3xl">
      <h1 className="text-2xl font-semibold mb-2">Conformité IFC</h1>
      <p className="text-muted-foreground mb-6">
        Déposez un fichier IFC pour pré-vérification RE2020 et accessibilité PMR.
      </p>
      <div className="rounded-md border-2 border-dashed p-10 text-center text-muted-foreground">
        <p className="font-medium">Drag-and-drop IFC</p>
        <p className="text-xs mt-1">À construire J17.</p>
      </div>
    </div>
  );
}
