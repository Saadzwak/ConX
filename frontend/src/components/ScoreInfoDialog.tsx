/**
 * Onboarding pédagogique du Score ConX.
 *
 * S'ouvre :
 *  - automatiquement au premier landing Mode Projet (cookie `conx-score-seen=1`)
 *  - sur clic du score circle de la fiche compacte
 *  - depuis le bouton « ? » du header dashboard
 *
 * Explique en 5 sections :
 *   1. C'est quoi le score (priorisation 0-100)
 *   2. Composé de 5 axes
 *   3. D'où viennent les données (BDNB, DPE, BD TOPO, IGN, ADEME)
 *   4. Ce que le score impacte (priorisation patrimoine)
 *   5. Limites (à valider par MOE)
 */
import { Award, Database, Layers, MapPin, ShieldAlert } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ScoreInfoDialog({ open, onClose }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Le score ConX, en bref"
      subtitle="Comprendre ce chiffre 0-100, ses 5 composantes et ses sources."
      maxWidth="max-w-2xl"
    >
      <div className="space-y-5 text-sm leading-relaxed">
        {/* 1. C'est quoi le score */}
        <Section
          icon={<Award className="h-4 w-4" />}
          title="1. Une priorisation patrimoniale, pas une note"
        >
          Le <strong>score ConX</strong> (0 à 100) classe les bâtiments d'un
          patrimoine par <strong>priorité de rénovation hors-site biosourcée</strong>.
          Un score 96 ne dit pas « ce bâtiment est bon » — il dit « ce bâtiment
          est <em>prioritaire</em> : fort gain CO₂, faisabilité technique,
          ratio coût/CO₂ favorable, enjeu social, statut passoire ».
        </Section>

        {/* 2. 5 axes */}
        <Section
          icon={<Layers className="h-4 w-4" />}
          title="2. Cinq composantes, normalisées de 0 à 1"
        >
          <ul className="space-y-1.5 ml-1">
            <Bullet label="CO₂ évité">
              Tonnes de CO₂ évitées sur 30 ans après rénovation. Calcul
              déterministe : surface × ΔkWh × facteur émission ADEME × 30.
            </Bullet>
            <Bullet label="Faisabilité">
              Compatibilité technique hors-site (matériau mur, structure,
              accessibilité chantier).
            </Bullet>
            <Bullet label="Coût">
              € investis par tonne CO₂ évitée. Plus c'est bas, plus le score
              monte (efficience climatique).
            </Bullet>
            <Bullet label="Social">
              Présence en QPV, type de propriétaire bailleur social, densité
              de logements.
            </Bullet>
            <Bullet label="Passoire">
              Classes DPE F ou G — bâtiments interdits à la location dès 2028
              (loi Climat & Résilience).
            </Bullet>
          </ul>
          <p className="text-xs text-muted-foreground mt-2.5 italic">
            Le score total combine ces 5 axes par pondération configurable.
            Calcul 100&nbsp;% déterministe — aucun chiffre n'est inventé.
          </p>
        </Section>

        {/* 3. Sources */}
        <Section
          icon={<Database className="h-4 w-4" />}
          title="3. D'où viennent les chiffres"
        >
          <div className="space-y-1.5 text-[12.5px]">
            <DataRow source="BDNB CSTB" what="géométrie, hauteur, surface, matériau mur, type propriétaire, année construction (millésime 2025-07.a)" />
            <DataRow source="DPE ADEME" what="classe énergétique réelle quand disponible, consommation kWh/m²/an, identifiant officiel" />
            <DataRow source="BD TOPO / LiDAR HD IGN" what="emprise au sol, hauteur précise pour extrusion 3D" />
            <DataRow source="Base Carbone ADEME" what="facteurs d'émission CO₂ par vecteur énergétique (électricité, gaz, fioul…)" />
            <DataRow source="INIES" what="base FDES publique (Fiches de Déclaration Environnementale) pour le bilan carbone matériaux" />
            <DataRow source="BAN DGFiP" what="adresse postale géocodée, lien parcelle cadastre" />
          </div>
          <p className="text-xs text-muted-foreground mt-2.5">
            Toutes les sources sont <strong>publiques</strong>, sous{" "}
            <em>Licence Ouverte Etalab 2.0</em>.
          </p>
        </Section>

        {/* 4. Quand DPE manquant */}
        <Section
          icon={<MapPin className="h-4 w-4" />}
          title="4. Que se passe-t-il quand le DPE est absent ?"
        >
          <strong>~60 % des bâtiments HDF</strong> n'ont pas de DPE officiel.
          On estime alors la classe énergétique par modèle statistique sur les
          DPE ADEME voisins partageant les caractéristiques (typologie,
          période thermique, matériau, géographie). Une étiquette
          <span className="inline-flex items-center gap-1 mx-1 px-1.5 py-0.5 rounded bg-muted text-[11px]">
            DPE estimé statistique
          </span>
          remplace la mention « DPE réel ADEME ». À confirmer par diagnostic
          officiel avant engagement de travaux.
        </Section>

        {/* 5. Limites */}
        <Section
          icon={<ShieldAlert className="h-4 w-4" />}
          title="5. Ce que ConX n'est PAS"
        >
          <ul className="space-y-1 list-disc pl-4 text-[12.5px]">
            <li>
              Pas un audit énergétique réglementaire — il ne remplace pas un
              diagnostic d'un bureau d'études thermique qualifié.
            </li>
            <li>
              Pas un projet d'exécution — les coûts et délais sont des
              fourchettes indicatives filière HDF 2025, à valider par devis.
            </li>
            <li>
              Pas un bureau de contrôle agréé — la pré-vérification IFC est
              une orientation, pas un avis technique réglementaire.
            </li>
          </ul>
        </Section>
      </div>
    </Dialog>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-1.5">
        <span className="text-primary">{icon}</span>
        {title}
      </h3>
      <div className="text-foreground/85">{children}</div>
    </section>
  );
}

function Bullet({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <li className="text-[12.5px] leading-snug pl-3 relative">
      <span className="absolute left-0 top-1.5 h-1.5 w-1.5 rounded-full bg-primary" />
      <strong className="text-foreground">{label}</strong> —{" "}
      <span className="text-foreground/75">{children}</span>
    </li>
  );
}

function DataRow({ source, what }: { source: string; what: string }) {
  return (
    <div className="flex gap-2 text-[12.5px]">
      <span className="font-semibold text-foreground/90 shrink-0 min-w-[140px]">
        {source}
      </span>
      <span className="text-foreground/70">{what}</span>
    </div>
  );
}
