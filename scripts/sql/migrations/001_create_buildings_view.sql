-- ConX — Migration 001 : table consolidée public_data.buildings
-- Cf. CLAUDE.md §6.A, D-002 (HDF), D-007 (RNB ID prioritaire), D-008 (LiDAR à la demande).
--
-- À exécuter APRÈS restore des pgdumps BDNB par département (ingest_bdnb.py).
-- L'ingestion BDNB crée des tables sources nommées avec leur schéma natif (ex. bdnb_<dept>.batiment_groupe_complet).
-- Cette migration consolide les 5 départements HDF dans public_data.buildings.

-- IMPORTANT : Le schéma exact des tables BDNB est confirmé après restore du premier pgdump.
-- Ce script utilise des noms de colonnes BDNB documentés publiquement (mode d'emploi bdnb.io).
-- Si une colonne diffère dans le millésime 2025-07.a, on adapte ici puis on commit.

CREATE TABLE IF NOT EXISTS public_data.buildings (
    -- Identifiants
    building_id           text PRIMARY KEY,            -- batiment_groupe_id BDNB
    rnb_id                text,                        -- Référentiel National Bâtiment (D-007)
    dept                  text NOT NULL,               -- 02 / 59 / 60 / 62 / 80

    -- Géométrie (EPSG:2154 — Lambert-93)
    geom                  geometry(MultiPolygon, 2154) NOT NULL,
    centroid              geometry(Point, 2154) GENERATED ALWAYS AS (ST_PointOnSurface(geom)) STORED,

    -- Attributs morphologiques
    surface_m2            numeric,                     -- surface au sol (footprint), BDNB s_geom_groupe
    hauteur_m             numeric,                     -- hauteur moyenne BD TOPO (bdtopo_bat.hauteur_mean)
    nb_logements          int,                         -- ffo.nb_log / rpls.nb_log / rnc.nb_log

    -- Construction
    annee_constr          int,                         -- ffo.annee_construction
    periode_construction  text,                        -- "<1948" / "1948-1974" / "1975-1981" / etc.

    -- Typologie
    type_principal        text,                        -- résidentiel / tertiaire / industriel / autre
    materiau_mur          text,                        -- pierre / brique / béton / bois / ... (ffo.mat_mur_txt)

    -- Propriété (D-002 : typologie, jamais d'identité)
    type_proprietaire     text,                        -- bailleur_social / personne_morale_privee / particulier
                                                       -- Note: 'public' non-distinguable en BDNB open.

    -- Patrimoine / contraintes
    -- BDNB open ne distingue pas Monument Historique inscrit vs classé.
    -- Single boolean. À enrichir si une source plus fine devient dispo.
    monument_historique   boolean DEFAULT false,       -- batiment_groupe_urbanisme.monument_historique
    spr                   boolean DEFAULT false,       -- batiment_groupe_urbanisme.zone_plu_bati_patrimonial

    -- DPE rattaché (depuis batiment_groupe_dpe_representatif_logement)
    -- Validation empirique dpt 02 : 100% des DPE non-nuls sont arrete_2021=true (coefficient 1.9).
    dpe_classe            text,                        -- 'A'..'G' (NULL si pas de DPE rattaché)
    dpe_kwh_ep_m2_an      numeric,
    dpe_kg_co2_m2_an      numeric,
    dpe_coefficient_ep_electricite  numeric DEFAULT 1.9,  -- ConX impose 1.9 (cf. CLAUDE.md §4)

    -- Méta
    ingested_at           timestamptz NOT NULL DEFAULT now(),
    bdnb_millesime        text NOT NULL DEFAULT '2025-07-a'
);

-- Index spatial principal
CREATE INDEX IF NOT EXISTS idx_buildings_geom ON public_data.buildings USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_buildings_centroid ON public_data.buildings USING GIST (centroid);

-- Index attributs fréquents
CREATE INDEX IF NOT EXISTS idx_buildings_rnb_id ON public_data.buildings (rnb_id) WHERE rnb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_buildings_dept ON public_data.buildings (dept);
CREATE INDEX IF NOT EXISTS idx_buildings_dpe_classe ON public_data.buildings (dpe_classe) WHERE dpe_classe IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_buildings_type_proprietaire ON public_data.buildings (type_proprietaire);
CREATE INDEX IF NOT EXISTS idx_buildings_annee_constr ON public_data.buildings (annee_constr);
CREATE INDEX IF NOT EXISTS idx_buildings_mh ON public_data.buildings (monument_historique) WHERE monument_historique = true;

COMMENT ON TABLE public_data.buildings IS
'Table consolidée des bâtiments BDNB Hauts-de-France (5 dpts), projetée EPSG:2154.
Construite par ingest_bdnb.py à partir des pgdumps BDNB millésime 2025-07-a.
Cf. CLAUDE.md §6.A et docs/DATA_SOURCES.md.';

COMMENT ON COLUMN public_data.buildings.dpe_coefficient_ep_electricite IS
'Coefficient EP électricité utilisé pour le calcul DPE. ConX impose 1.9 (cadre réglementaire 2026-01-01).
Validation empirique dpt 02 : 100% des DPE non-nuls dans batiment_groupe_dpe_representatif_logement
ont arrete_2021=true. Cf. SCORING.md composante S_passoire.';

COMMENT ON COLUMN public_data.buildings.monument_historique IS
'Bâtiment Monument Historique (inscrit ou classé indifférencié — BDNB open n''expose pas la distinction).
Issu de batiment_groupe_urbanisme.monument_historique. La table batiment_groupe_merimee donne seulement
distance/nom du MH le plus proche, sans qualification.';

COMMENT ON COLUMN public_data.buildings.type_proprietaire IS
'Typologie propriétaire dérivée : bailleur_social (présence batiment_groupe_rpls),
personne_morale_privee (présence batiment_groupe_rnc = copropriété), particulier (défaut).
BDNB open ne permet pas de distinguer public/particulier de manière fiable.';
