import { NavLink, Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Building2, Map, FileCheck2, Store } from "lucide-react";
import { Logo } from "@/components/Logo";
import { ProfileSwitcher } from "@/components/ProfileSwitcher";
import { useUserProfile, isVisible } from "@/lib/userProfile";

const NAV_LINKS = [
  { to: "/strategie", label: "Stratégie", icon: Map, feature: "nav.strategie" },
  { to: "/projet", label: "Projet", icon: Building2, feature: "nav.projet" },
  { to: "/ifc", label: "Conformité IFC", icon: FileCheck2, feature: "nav.ifc" },
  { to: "/marketplace", label: "Marketplace", icon: Store, feature: "nav.marketplace" },
];

export function Nav() {
  const [profile] = useUserProfile();
  const visibleLinks = NAV_LINKS.filter((l) => isVisible(profile, l.feature));

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/70 sticky top-0 z-30">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/" className="flex items-center gap-3 min-w-0" aria-label="ConX accueil">
            <Logo size={28} />
            <span className="text-[11px] leading-tight text-muted-foreground hidden lg:block border-l pl-3">
              Pré-cadrage rénovation
              <br />
              hors-site biosourcée · HDF
            </span>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          <nav className="flex items-center gap-1">
            {visibleLinks.map(({ to, label, icon: Icon }) => (
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
          <ProfileSwitcher />
        </div>
      </div>
    </header>
  );
}
