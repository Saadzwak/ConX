/**
 * Dialog modal natif — backdrop + escape close + click outside.
 * Volontairement minimaliste : pas de dépendance Radix-UI (qu'on n'a pas).
 * Couvre les besoins ConX : onboarding score, explications pédagogiques,
 * dialogs d'info contextuels.
 */
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  /** Largeur max du modal. Par défaut max-w-2xl. */
  maxWidth?: string;
  children: React.ReactNode;
}

export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  maxWidth = "max-w-2xl",
  children,
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Escape → close, body scroll lock pendant l'ouverture.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={(e) => {
        // Click backdrop (pas le contenu) → close
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "dialog-title" : undefined}
    >
      <div
        ref={dialogRef}
        className={cn(
          "bg-card border border-border rounded-lg shadow-2xl w-full",
          maxWidth,
          "max-h-[90vh] overflow-hidden flex flex-col",
          "animate-in zoom-in-95 duration-150",
        )}
      >
        {(title || subtitle) && (
          <div className="border-b px-6 py-4 flex items-start justify-between gap-4 shrink-0">
            <div className="min-w-0 flex-1">
              {title && (
                <h2
                  id="dialog-title"
                  className="text-lg font-semibold text-foreground leading-tight"
                >
                  {title}
                </h2>
              )}
              {subtitle && (
                <p className="text-sm text-muted-foreground mt-1 leading-snug">
                  {subtitle}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fermer"
              className="text-muted-foreground hover:text-foreground transition-colors shrink-0 rounded-md p-1 hover:bg-accent"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
