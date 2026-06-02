/**
 * Système de vues par profil utilisateur.
 *
 * 5 profils calqués sur le pitch deck §07 « Valeur ajoutée par acteur » :
 *   - bailleur     : Bailleurs sociaux & Collectivités (MOA)
 *   - architecte   : Architectes (MOE conception)
 *   - be-moe       : Bureaux d'Études & MOE (ingénierie + conformité)
 *   - fabricant    : Fabricants & Entreprises (filière HDF, marketplace)
 *   - tous         : vue démo (tout visible — défaut)
 *
 * Persistance via `localStorage.conx-user-profile`. Bouton de réinitialisation
 * remet à 'tous'.
 *
 * Le profil ne désactive PAS techniquement les routes (toutes restent
 * accessibles via URL directe), il CACHE les CTA / sections dans la nav
 * et les pages pour proposer un parcours plus focalisé. Réversible 100 %.
 */
import { useEffect, useState } from "react";

export type UserProfile =
  | "tous"
  | "bailleur"
  | "architecte"
  | "be-moe"
  | "fabricant";

export const PROFILE_LABELS: Record<UserProfile, string> = {
  tous: "Vue démo · tout",
  bailleur: "Bailleur / Collectivité",
  architecte: "Architecte",
  "be-moe": "Bureau d'études / MOE",
  fabricant: "Fabricant / Entreprise",
};

export const PROFILE_SUBLABELS: Record<UserProfile, string> = {
  tous: "Toutes les fonctionnalités sont visibles (pour le pitch).",
  bailleur:
    "Priorisation patrimoniale, pré-cadrage rénovation, commandes groupées.",
  architecte:
    "Pré-cadrage modulaire chiffré, conformité IFC, marketplace fournisseurs.",
  "be-moe":
    "Diagnostic technique, conformité IFC, vérification RE2020/PMR.",
  fabricant:
    "Marketplace, commandes groupées, pipeline projets pré-qualifiés.",
};

const STORAGE_KEY = "conx-user-profile";
const DEFAULT_PROFILE: UserProfile = "tous";

/**
 * Hook React qui synchronise le profil utilisateur avec localStorage
 * et notifie les autres composants via un CustomEvent.
 *
 * Le `useState` initial est `DEFAULT_PROFILE` pour éviter un hydration
 * mismatch ; on lit le localStorage dans un useEffect au mount.
 */
export function useUserProfile(): [UserProfile, (p: UserProfile) => void] {
  const [profile, setProfileState] = useState<UserProfile>(DEFAULT_PROFILE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored && stored in PROFILE_LABELS) {
        setProfileState(stored as UserProfile);
      }
    } catch {
      // localStorage indispo (Safari private) — no-op
    }

    // Écoute les changements de profil émis par d'autres instances du hook
    const onProfileChange = (e: Event) => {
      const detail = (e as CustomEvent<UserProfile>).detail;
      if (detail) setProfileState(detail);
    };
    window.addEventListener("conx-profile-changed", onProfileChange);
    return () => {
      window.removeEventListener("conx-profile-changed", onProfileChange);
    };
  }, []);

  const setProfile = (p: UserProfile) => {
    setProfileState(p);
    try {
      window.localStorage.setItem(STORAGE_KEY, p);
    } catch {
      // no-op
    }
    window.dispatchEvent(
      new CustomEvent<UserProfile>("conx-profile-changed", { detail: p }),
    );
  };

  return [profile, setProfile];
}

/**
 * Helper synchrone (hors React) pour les composants qui n'ont pas besoin de
 * réactivité (ex. décisions une fois au load).
 */
export function getCurrentProfile(): UserProfile {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored in PROFILE_LABELS) {
      return stored as UserProfile;
    }
  } catch {
    // no-op
  }
  return DEFAULT_PROFILE;
}

/**
 * Matrice de visibilité — chaque profil voit certaines fonctionnalités.
 * En mode 'tous' tout est visible (vue démo pitch).
 *
 * Les fonctionnalités cachées sont ABSENTES du menu/CTA mais TOUJOURS
 * accessibles via URL directe → garantit qu'aucun test ne casse et
 * que l'utilisateur peut toujours retrouver la fonctionnalité.
 */
const VISIBILITY: Record<UserProfile, Record<string, boolean>> = {
  tous: {
    "nav.strategie": true,
    "nav.projet": true,
    "nav.ifc": true,
    "nav.marketplace": true,
    "nav.commandes-groupees": true,
  },
  bailleur: {
    "nav.strategie": true,
    "nav.projet": true,
    "nav.ifc": false, // pas leur responsabilité directe
    "nav.marketplace": true,
    "nav.commandes-groupees": true, // priorité massification
  },
  architecte: {
    "nav.strategie": true, // utile en phase amont
    "nav.projet": true, // cœur du métier
    "nav.ifc": true, // livrable client
    "nav.marketplace": true, // sourcing
    "nav.commandes-groupees": false, // pas leur primary use case
  },
  "be-moe": {
    "nav.strategie": false, // peu pertinent
    "nav.projet": true,
    "nav.ifc": true, // priorité (vérification réglementaire)
    "nav.marketplace": true,
    "nav.commandes-groupees": false,
  },
  fabricant: {
    "nav.strategie": false,
    "nav.projet": false, // pas leur use case
    "nav.ifc": false,
    "nav.marketplace": true, // priorité
    "nav.commandes-groupees": true, // priorité pipeline projets
  },
};

export function isVisible(profile: UserProfile, feature: string): boolean {
  return VISIBILITY[profile]?.[feature] ?? true;
}
