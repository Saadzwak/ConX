/**
 * J17 — Mode Conformité IFC : drag-and-drop + validation + PDF.
 *
 * UX :
 *  - Zone drop centrée
 *  - Upload → POST /api/ifc/upload (multipart)
 *  - Affichage : badges RE2020 / PMR + summary entités + détail checks
 *  - Bouton download PDF rapport
 *
 * Le backend gère parsing (IfcOpenShell), règles RE2020, règles PMR, et
 * génère un PDF weasyprint. Pour démo : un IFC de 50 Mo prend < 10 s.
 */

import { useCallback, useRef, useState } from "react";
import {
  Upload,
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileDown,
  Loader2,
  FileText,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { uploadIfc, type IfcUploadResponse, type IfcCheck } from "@/lib/api";

const ACCEPTED_EXTS = [".ifc"];
const MAX_SIZE_MB = 50;

export function IfcPage() {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IfcUploadResponse | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    if (!ACCEPTED_EXTS.some((e) => file.name.toLowerCase().endsWith(e))) {
      setError(`Extension non supportée. Attendu : ${ACCEPTED_EXTS.join(", ")}`);
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Fichier > ${MAX_SIZE_MB} Mo (taille reçue : ${(file.size / 1024 / 1024).toFixed(1)} Mo).`);
      return;
    }
    setFilename(file.name);
    setBusy(true);
    try {
      const resp = await uploadIfc(file);
      setResult(resp);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDrag(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  const reset = () => {
    setResult(null);
    setFilename(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="container py-8 max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold mb-1">Conformité IFC</h1>
        <p className="text-sm text-muted-foreground">
          Déposez un fichier IFC (.ifc, max {MAX_SIZE_MB} Mo) pour pré-vérification
          RE2020 (thermique) et accessibilité PMR (largeur portes, pente rampes).
          Génère un rapport PDF téléchargeable.
        </p>
      </header>

      {/* Zone drop */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          "rounded-lg border-2 border-dashed p-12 text-center cursor-pointer transition-colors",
          drag ? "border-primary bg-primary/5" : "border-border bg-muted/30 hover:bg-muted/50",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".ifc"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
          }}
        />
        {busy ? (
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <div>
              Validation en cours…
              {filename && (
                <div className="text-xs mt-1 font-mono">{filename}</div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Upload className="h-10 w-10 text-muted-foreground" />
            <div>
              <strong>Déposez votre fichier IFC ici</strong>
              <div className="text-xs text-muted-foreground mt-1">
                ou cliquez pour parcourir · {ACCEPTED_EXTS.join(", ")} · max {MAX_SIZE_MB} Mo
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Erreur */}
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1">{error}</div>
          <Button size="icon" variant="ghost" onClick={reset} aria-label="Fermer">
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Résultat */}
      {result && (
        <section className="rounded-lg border bg-card p-5 space-y-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                Rapport de conformité
              </h2>
              <p className="text-xs text-muted-foreground font-mono mt-0.5">
                {result.ifc_filename} · {result.validation_id}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" asChild>
                <a href={result.pdf_url} target="_blank" rel="noreferrer noopener" download>
                  <FileDown className="h-4 w-4 mr-1" />
                  PDF
                </a>
              </Button>
              <Button variant="ghost" size="sm" onClick={reset}>
                Nouveau fichier
              </Button>
            </div>
          </div>

          {/* Badges RE2020 / PMR */}
          <div className="flex gap-2 flex-wrap">
            <VerdictBadge label="RE2020" pass={result.re2020_pass} />
            <VerdictBadge label="PMR" pass={result.pmr_pass} />
            {result.rapport_json.schema && (
              <Badge variant="outline">Schéma {result.rapport_json.schema}</Badge>
            )}
          </div>

          {/* Summary entités */}
          {result.rapport_json.summary && (
            <div className="grid grid-cols-4 gap-2 text-sm">
              {Object.entries(result.rapport_json.summary).map(([k, v]) => (
                <div key={k} className="rounded-md bg-muted/40 p-2 text-center">
                  <div className="text-xl font-semibold">{v ?? 0}</div>
                  <div className="text-xs text-muted-foreground capitalize">{k}</div>
                </div>
              ))}
            </div>
          )}

          {/* Détail checks RE2020 */}
          <ChecksTable
            title="RE2020 — performance thermique"
            checks={result.rapport_json.re2020_checks ?? {}}
          />

          {/* Détail checks PMR */}
          <ChecksTable
            title="PMR — accessibilité"
            checks={result.rapport_json.pmr_checks ?? {}}
          />

          {/* Warnings */}
          {result.rapport_json.warnings && result.rapport_json.warnings.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5" />
                Avertissements
              </div>
              <ul className="list-disc pl-5">
                {result.rapport_json.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-[11px] text-muted-foreground border-t pt-3 leading-relaxed">
            Pré-vérification automatisée — ne remplace pas un Bureau de Contrôle
            Technique agréé. Sources : IfcOpenShell (parsing), règles RE2020 +
            PMR codées par ConX (cf. <code>skills/ifc-check</code>).
          </p>
        </section>
      )}
    </div>
  );
}

function VerdictBadge({ label, pass }: { label: string; pass: boolean | null }) {
  if (pass === true) {
    return (
      <Badge className="bg-green-600 hover:bg-green-700 text-white">
        <CheckCircle2 className="h-3 w-3 mr-1" />
        {label} OK
      </Badge>
    );
  }
  if (pass === false) {
    return (
      <Badge variant="destructive">
        <XCircle className="h-3 w-3 mr-1" />
        {label} à corriger
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">
      <AlertCircle className="h-3 w-3 mr-1" />
      {label} indéterminé
    </Badge>
  );
}

function ChecksTable({
  title,
  checks,
}: {
  title: string;
  checks: Record<string, IfcCheck>;
}) {
  const entries = Object.entries(checks);
  if (entries.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      <div className="rounded-md border divide-y text-sm">
        {entries.map(([key, c]) => (
          <div key={key} className="px-3 py-2 flex items-start gap-2">
            <CheckIcon pass={c.pass} />
            <div className="flex-1 min-w-0">
              <div className="font-medium">{c.name || key}</div>
              {c.message && (
                <div className="text-xs text-muted-foreground mt-0.5">{c.message}</div>
              )}
              {(c.value !== undefined || c.threshold !== undefined) && (
                <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                  {c.value !== undefined && <>val={String(c.value)} </>}
                  {c.threshold !== undefined && <>seuil={String(c.threshold)}</>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckIcon({ pass }: { pass: boolean | null | undefined }) {
  if (pass === true) return <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />;
  if (pass === false) return <XCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />;
  return <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />;
}
