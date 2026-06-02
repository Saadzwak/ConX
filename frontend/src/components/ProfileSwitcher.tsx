/**
 * Sélecteur de profil utilisateur — bouton dans la nav qui ouvre un
 * dropdown des 5 profils. Le choix est persistant (localStorage) et
 * affecte la visibilité des sections (cf. `lib/userProfile.ts`).
 *
 * Toujours réversible : un bouton « Vue démo · tout » remet l'utilisateur
 * dans la vue exhaustive sans aucune fonctionnalité cachée.
 */
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Check, Eye } from "lucide-react";
import {
  useUserProfile,
  PROFILE_LABELS,
  PROFILE_SUBLABELS,
  type UserProfile,
} from "@/lib/userProfile";
import { cn } from "@/lib/utils";

const PROFILE_ORDER: UserProfile[] = [
  "tous",
  "bailleur",
  "architecte",
  "be-moe",
  "fabricant",
];

export function ProfileSwitcher() {
  const [profile, setProfile] = useUserProfile();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Click outside → close
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // Escape → close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const isDefaultView = profile === "tous";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-md border transition-colors",
          isDefaultView
            ? "border-input bg-background text-muted-foreground hover:bg-accent"
            : "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20",
        )}
        title="Choisir la vue selon votre profil"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Eye className="h-3.5 w-3.5" />
        <span className="hidden md:inline">{PROFILE_LABELS[profile]}</span>
        <span className="md:hidden">Vue</span>
        <ChevronDown
          className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1.5 z-50 w-72 rounded-lg border bg-card shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150"
        >
          <div className="px-3 py-2 border-b bg-muted/30">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">
              Voir la plateforme selon
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">
              Les sections non pertinentes sont masquées du menu. Tout reste
              accessible via URL directe. Réversible à tout moment.
            </p>
          </div>
          <ul className="py-1">
            {PROFILE_ORDER.map((p) => {
              const active = profile === p;
              return (
                <li key={p}>
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    onClick={() => {
                      setProfile(p);
                      setOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 text-xs hover:bg-accent transition-colors flex items-start gap-2",
                      active && "bg-primary/5",
                    )}
                  >
                    <Check
                      className={cn(
                        "h-3.5 w-3.5 mt-0.5 shrink-0",
                        active ? "text-primary" : "text-transparent",
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className={cn("font-semibold leading-tight", active && "text-primary")}>
                        {PROFILE_LABELS[p]}
                      </div>
                      <div className="text-[10.5px] text-muted-foreground mt-0.5 leading-snug">
                        {PROFILE_SUBLABELS[p]}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
          {!isDefaultView && (
            <div className="border-t bg-muted/30 px-3 py-2">
              <button
                type="button"
                onClick={() => {
                  setProfile("tous");
                  setOpen(false);
                }}
                className="text-[11px] text-primary hover:underline inline-flex items-center gap-1"
              >
                ← Revenir à la vue démo complète
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
