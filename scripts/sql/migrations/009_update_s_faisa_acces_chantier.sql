-- ConX — Migration 009 : passe de mise à jour S_faisa.acces_chantier post-ingestion BD TOPO.
--
-- À EXÉCUTER UNIQUEMENT après que public_data.topo_roads est peuplée pour les dpts considérés.
--
-- Formule SCORING.md §Composante 2 acces_chantier :
--   1.0 si rue ≥ 4 m de large à moins de 10 m du bâtiment
--   0.5 si rue 2-4 m
--   0.0 si impasse étroite ou bâtiment enclavé (aucune voie à < 10 m)
--
-- Algorithme :
-- 1. Pour chaque bâtiment d'un dpt, on calcule la distance à la voie la plus proche (PostGIS ST_DWithin + largeur la plus large).
-- 2. On en déduit la valeur acces_chantier ∈ {0, 0.5, 1.0}.
-- 3. On RECALCULE S_faisa avec acces_chantier ré-intégré (poids = 0.20 selon scoring_thresholds.yaml).
-- 4. On retire le flag s_faisa_partial.
--
-- Le S_faisa est mis à jour selon la formule pondérée SCORING.md :
--   S_faisa = 0.25*toiture + 0.20*acces + 0.15*hauteur + 0.20*patrimoine + 0.10*geom + 0.10*type
--
-- ATTENTION : cette mise à jour n'utilise QUE acces_chantier mesuré. Les 5 autres sous-indicateurs
-- conservent les valeurs posées au pré-calcul (cf. compute.py _faisa_subindicators). Pour qu'elles
-- soient cohérentes, on déduit `S_faisa - poids_redistribué_initiaux = somme_des_5_autres` puis
-- on ré-applique avec poids original 0.20 sur acces_chantier.
--
-- Approche simple choisie : on FORCE le recalcul de S_faisa à partir de ses inputs depuis
-- building_scores actuel. Mais on n'a pas stocké les sous-indicateurs. Donc deux options :
--   (a) Re-lancer compute_building_scores.py --all après ingestion BD TOPO (recommandé).
--   (b) Calculer ici uniquement la valeur acces_chantier et UPDATE building_scores manuellement.
--
-- DÉCISION : on opte pour (a). Ce script SQL ne fait QUE flaguer/peupler une vue
-- public_data.building_acces_chantier qui sera utilisée par compute_building_scores.py.

-- Table de mapping bâtiment → acces_chantier (calculé via PostGIS).
-- Pré-calculée pour ne pas refaire la requête ST_DWithin à chaque batch.

CREATE TABLE IF NOT EXISTS public_data.building_acces_chantier (
    building_id    text PRIMARY KEY REFERENCES public_data.buildings(building_id) ON DELETE CASCADE,
    acces_chantier numeric NOT NULL CHECK (acces_chantier BETWEEN 0 AND 1),
    nearest_largeur_m numeric,
    nearest_distance_m numeric,
    computed_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bac_acces ON public_data.building_acces_chantier (acces_chantier);

COMMENT ON TABLE public_data.building_acces_chantier IS
'Pré-calcul du sous-indicateur S_faisa.acces_chantier (cf. SCORING.md). Lu par compute.py
pour remplacer le fallback neutre lors du re-batch scoring post-ingestion BD TOPO.';
