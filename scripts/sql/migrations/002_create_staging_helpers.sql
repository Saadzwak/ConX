-- ConX — Migration 002 : fonctions et vues d'aide à l'ingestion staging.
-- Crée des helpers pour parser et normaliser les attributs BDNB lors de l'ingestion.

-- Fonction de normalisation des classes DPE (A..G + 'N' = non classé)
CREATE OR REPLACE FUNCTION public_data.normalize_dpe_classe(raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN raw IS NULL OR length(trim(raw)) = 0 THEN NULL
        WHEN upper(trim(raw)) IN ('A','B','C','D','E','F','G') THEN upper(trim(raw))
        ELSE NULL
    END
$$;

-- Fonction de mapping période de construction → texte canonique
CREATE OR REPLACE FUNCTION public_data.periode_from_annee(annee int)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN annee IS NULL                THEN NULL
        WHEN annee < 1948                 THEN '<1948'
        WHEN annee BETWEEN 1948 AND 1974  THEN '1948-1974'
        WHEN annee BETWEEN 1975 AND 1981  THEN '1975-1981'
        WHEN annee BETWEEN 1982 AND 1988  THEN '1982-1988'
        WHEN annee BETWEEN 1989 AND 2000  THEN '1989-2000'
        WHEN annee BETWEEN 2001 AND 2011  THEN '2001-2011'
        WHEN annee BETWEEN 2012 AND 2020  THEN '2012-2020'
        ELSE '>2020'
    END
$$;

-- Fonction de mapping type de propriétaire BDNB → catégorie ConX
-- Mapping conservateur : si la valeur BDNB n'est pas reconnue, on retourne 'inconnu'.
CREATE OR REPLACE FUNCTION public_data.map_type_proprietaire(raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN raw IS NULL                                                THEN 'inconnu'
        WHEN lower(raw) ~ 'bailleur|hlm|social|opac|sa[_ ]hlm'           THEN 'bailleur_social'
        WHEN lower(raw) ~ 'collectivite|commune|departement|region|etat|public' THEN 'public'
        WHEN lower(raw) ~ 'sci|sas|sarl|sa |societe|copropriete|foncier' THEN 'personne_morale_privee'
        WHEN lower(raw) ~ 'particulier|personne[_ ]physique|individuel'  THEN 'particulier'
        ELSE 'inconnu'
    END
$$;
