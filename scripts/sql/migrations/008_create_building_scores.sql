-- ConX — Migration 008 : table public_data.building_scores.
--
-- Cf. docs/SCORING.md "Pré-calcul des composantes (batch)" — schéma exact + check constraints.
-- Le score total N'EST PAS stocké : calculé à la volée en SQL pur (cf. SCORING.md §"Calcul à la volée").
--
-- D-006 : formule scoring (5 composantes, poids 0.35/0.25/0.20/0.10/0.10) gravée dans SCORING.md.
-- D-016 : invariants sanity dérivés de la donnée.
--
-- Champs `incomplete_data` et `s_faisa_partial` ajoutés vs schéma SCORING.md pour gérer les bâtiments
-- où certaines sources sont temporairement absentes (DPE manquant J5, BD TOPO pas encore ingérée).
-- Ne modifient PAS la formule — flag de qualité uniquement.

CREATE TABLE IF NOT EXISTS public_data.building_scores (
    building_id            text PRIMARY KEY REFERENCES public_data.buildings(building_id) ON DELETE CASCADE,

    -- Composantes [0,1] — formule SCORING.md
    s_co2                  numeric NOT NULL CHECK (s_co2 BETWEEN 0 AND 1),
    s_faisa                numeric NOT NULL CHECK (s_faisa BETWEEN 0 AND 1),
    s_cout                 numeric NOT NULL CHECK (s_cout BETWEEN 0 AND 1),
    s_social               numeric NOT NULL CHECK (s_social BETWEEN 0 AND 1),
    s_passoire             numeric NOT NULL CHECK (s_passoire BETWEEN 0 AND 1),

    -- Valeurs brutes pour affichage UI + debug
    co2_evite_t            numeric NOT NULL,
    cout_estime_eur        numeric NOT NULL,
    cout_eur_par_t_co2     numeric,                              -- NULL si co2_evite_t <= 0

    -- Métadonnées
    confidence             numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    -- dpe_source : valeurs canoniques SCORING.md (D-006). 'ml-predicted' couvre tous les fallbacks
    -- pré-J5 (point milieu de classe DPE par typologie) en attendant la vraie estimation ML.
    dpe_source             text NOT NULL CHECK (dpe_source IN ('ademe-real', 'ml-predicted')),
    thresholds_version     text NOT NULL,                        -- hash sha256-short du scoring_thresholds.yaml utilisé

    -- Flags qualité (cf. SCORING.md, ne touchent pas la formule)
    incomplete_data        boolean NOT NULL DEFAULT false,       -- true si plusieurs sources manquent
    s_faisa_partial        boolean NOT NULL DEFAULT false,       -- true si acces_chantier non calculé (BD TOPO pas encore ingérée)
    missing_fields         text[],                               -- liste des champs manquants pour debug

    computed_at            timestamptz NOT NULL DEFAULT now()
);

-- Indexes pour requêtes courantes : filtrage par dpe_source (confiance) + flags qualité.
-- Pas d'index sur score_total (calculé à la volée — SCORING.md).
CREATE INDEX IF NOT EXISTS idx_building_scores_dpe_source ON public_data.building_scores (dpe_source);
CREATE INDEX IF NOT EXISTS idx_building_scores_incomplete ON public_data.building_scores (incomplete_data) WHERE incomplete_data;
CREATE INDEX IF NOT EXISTS idx_building_scores_s_faisa_partial ON public_data.building_scores (s_faisa_partial) WHERE s_faisa_partial;

COMMENT ON TABLE public_data.building_scores IS
'Pré-calcul des 5 composantes scoring (SCORING.md). Score total calculé à la volée en SQL pur.
D-006 : formule gravée. D-016 : invariants sanity. thresholds_version pinne le YAML utilisé.';
