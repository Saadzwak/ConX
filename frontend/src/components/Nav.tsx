import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Building2, Map, FileCheck2 } from "lucide-react";

const NAV_LINKS = [
  { to: "/strategie", label: "Stratégie", icon: Map },
  { to: "/projet", label: "Projet", icon: Building2 },
  { to: "/ifc", label: "Conformité IFC", icon: FileCheck2 },
];

export function Nav() {
  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/70 sticky top-0 z-30">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              aria-hidden
              className="h-8 w-8 rounded-md bg-primary text-primary-foreground grid place-items-center font-bold"
            >
              C
            </div>
            <span className="font-semibold tracking-tight">ConX</span>
            <span className="text-xs text-muted-foreground hidden md:inline">
              · Rénovation hors-site décarbonée · Hauts-de-France
            </span>
          </div>
        </div>

        <nav className="flex items-center gap-1">
          {NAV_LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )
              }
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
