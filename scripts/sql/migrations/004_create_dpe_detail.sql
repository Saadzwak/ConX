-- ConX — Migration 004 : table DPE détaillée pour ML J5 et fiche bâtiment Mode Projet.
--
-- public_data.buildings contient les attributs DPE essentiels (classe, conso EP, GES).
-- Cette table garde les attributs riches (matériaux, isolation, chauffage, vitrage, etc.)
-- utiles au ML d'estimation DPE (J5) et à la fiche détaillée du Mode Projet (Section 6 plan).
--
-- Source : batiment_groupe_dpe_representatif_logement (logement) + batiment_groupe_dpe_tertiaire.

CREATE TABLE IF NOT EXISTS public_data.dpe (
    -- Identifiants
    id                      bigserial PRIMARY KEY,
    building_id             text NOT NULL REFERENCES public_data.buildings (building_id) ON DELETE CASCADE,
    rnb_id                  text,
    identifiant_dpe         text,
    dept                    text NOT NULL,

    -- Type DPE
    type_dpe                text,                       -- 'logement' / 'tertiaire'
    type_batiment_dpe       text,
    arrete_2021             boolean,                    -- ConX exige true (coefficient EP élec 1.9)

    -- Surfaces & étages
    surface_habitable_logement   numeric,
    surface_habitable_immeuble   numeric,
    nombre_niveau_logement       int,
    nombre_niveau_immeuble       int,

    -- Énergie (résumé — détail dans raw_json)
    classe_bilan_dpe         text,                      -- A..G (DPE 2021)
    classe_emission_ges      text,                      -- A..G (GES 2021)
    conso_5_usages_ep_m2_an  numeric,                   -- kWh ep/m²/an
    conso_5_usages_ef_m2_an  numeric,                   -- kWh ef/m²/an
    emission_ges_5_usages_m2_an  numeric,               -- kgCO₂/m²/an

    -- Chauffage
    type_installation_chauffage  text,
    type_energie_chauffage   text,
    type_generateur_chauffage    text,
    chauffage_solaire        boolean,

    -- ECS
    type_installation_ecs    text,
    type_energie_ecs         text,
    ecs_solaire              boolean,

    -- Ventilation
    type_ventilation         text,

    -- Vitrages et menuiseries
    type_vitrage             text,                      -- simple / double / triple
    type_materiaux_menuiserie text,                     -- bois / pvc / alu / mixte
    uw                       numeric,                   -- U fenêtre

    -- Parois
    materiaux_structure_mur_exterieur text,
    type_isolation_mur_exterieur      text,
    u_mur_exterieur          numeric,
    type_isolation_plancher_bas       text,
    type_isolation_plancher_haut      text,

    -- Dates
    date_etablissement_dpe   timestamptz,
    date_reception_dpe       timestamptz,

    -- Brut (pour ML feature engineering)
    raw_json                 jsonb,

    -- Méta
    ingested_at              timestamptz NOT NULL DEFAULT now(),

    -- Contrainte d'unicité : un DPE est identifié par son identifiant ADEME + le bâtiment auquel il est rattaché.
    -- (identifiant_dpe peut techniquement être réutilisé via différents bâtiments dans BDNB ; on garde la combo).
    UNIQUE (building_id, identifiant_dpe)
);

CREATE INDEX IF NOT EXISTS idx_dpe_building_id ON public_data.dpe (building_id);
CREATE INDEX IF NOT EXISTS idx_dpe_rnb_id ON public_data.dpe (rnb_id) WHERE rnb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dpe_dept ON public_data.dpe (dept);
CREATE INDEX IF NOT EXISTS idx_dpe_classe ON public_data.dpe (classe_bilan_dpe) WHERE classe_bilan_dpe IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dpe_type ON public_data.dpe (type_dpe);

COMMENT ON TABLE public_data.dpe IS
'DPE détaillé (logement + tertiaire) extrait de BDNB 2025-07-a. Une ligne par DPE,
plusieurs DPE possibles par bâtiment. Utilisé par le ML d''estimation DPE (J5) et la fiche
Mode Projet. Pour le scoring rapide, utiliser public_data.buildings.dpe_* qui agrège.';
