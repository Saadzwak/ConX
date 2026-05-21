"""ConX — Tests d'invariants post-ingestion BDNB.

Ces tests vérifient que public_data.buildings respecte les invariants attendus
après ingestion d'un ou plusieurs départements. Lancés en CI dès que postgres_local
est disponible (variable d'env DATABASE_URL_LOCAL).

Mode dégradé : si postgres_local n'est pas accessible (ex. CI sans Docker), les tests sont skip.
"""

from __future__ import annotations

import os

import pytest

try:
    import psycopg

    HAS_PSYCOPG = True
    _CONN_EXC: type[BaseException] = psycopg.OperationalError
except ImportError:
    HAS_PSYCOPG = False
    _CONN_EXC = Exception

DATABASE_URL = os.environ.get("DATABASE_URL_LOCAL", "").replace("+asyncpg", "")


def _conn():
    if not DATABASE_URL or not HAS_PSYCOPG:
        pytest.skip("postgres_local non disponible (DATABASE_URL_LOCAL non défini)")
    return psycopg.connect(DATABASE_URL, connect_timeout=3)


@pytest.fixture(scope="module")
def db():
    try:
        with _conn() as conn:
            yield conn
    except _CONN_EXC:
        pytest.skip("postgres_local injoignable")


def test_buildings_table_exists(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'public_data' AND table_name = 'buildings';
        """)
        assert cur.fetchone()[0] == 1, "Table public_data.buildings absente"


def test_buildings_has_postgis_geom_2154(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT srid, type FROM geometry_columns
            WHERE f_table_schema = 'public_data' AND f_table_name = 'buildings'
              AND f_geometry_column = 'geom';
        """)
        row = cur.fetchone()
        assert row is not None, "Colonne geom non géométrie PostGIS"
        srid, geom_type = row
        assert srid == 2154, f"SRID attendu 2154, observé {srid}"
        assert "MULTIPOLYGON" in geom_type.upper(), f"Type attendu MULTIPOLYGON, observé {geom_type}"


def test_indexes_present(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public_data' AND tablename = 'buildings';
        """)
        names = {r[0] for r in cur.fetchall()}
        assert "idx_buildings_geom" in names
        assert "idx_buildings_rnb_id" in names
        assert "idx_buildings_dept" in names


def test_no_invalid_geometries(db):
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM public_data.buildings WHERE NOT ST_IsValid(geom);")
        invalid = cur.fetchone()[0]
        assert invalid == 0, f"{invalid} géométries invalides — ST_MakeValid à appliquer"


def test_dept_distribution(db):
    """Si au moins un département est ingéré, vérifier que les codes sont dans HDF."""
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM public_data.buildings;")
        total = cur.fetchone()[0]
        if total == 0:
            pytest.skip("Aucun bâtiment ingéré encore")

        cur.execute("SELECT dept, count(*) FROM public_data.buildings GROUP BY dept ORDER BY dept;")
        rows = cur.fetchall()
        depts = {r[0] for r in rows}
        assert depts.issubset(
            {"02", "59", "60", "62", "80"}
        ), f"Départements inattendus : {depts - {'02', '59', '60', '62', '80'}}"


def test_dpe_classes_valides(db):
    """Toutes les classes DPE non-nulles doivent être A..G."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT dpe_classe FROM public_data.buildings
            WHERE dpe_classe IS NOT NULL;
        """)
        classes = {r[0] for r in cur.fetchall()}
        invalid = classes - {"A", "B", "C", "D", "E", "F", "G"}
        assert not invalid, f"Classes DPE invalides : {invalid}"


def test_type_proprietaire_canonique(db):
    """Toutes les valeurs de type_proprietaire doivent être dans le set canonique.
    Note : 'public' n'est pas dérivable de BDNB open (cf. CLAUDE.md §6.A note)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT type_proprietaire FROM public_data.buildings
            WHERE type_proprietaire IS NOT NULL;
        """)
        vals = {r[0] for r in cur.fetchall()}
        canonical = {"bailleur_social", "personne_morale_privee", "particulier"}
        invalid = vals - canonical
        assert not invalid, f"Valeurs type_proprietaire inattendues : {invalid}"


def test_monument_historique_column_present(db):
    """La colonne monument_historique doit exister (boolean, défaut false)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='public_data' AND table_name='buildings'
              AND column_name='monument_historique';
        """)
        row = cur.fetchone()
        assert row is not None, "Colonne monument_historique absente"
        assert row[0] == "boolean", f"Type attendu boolean, observé {row[0]}"


def test_annee_constr_plausible(db):
    """Les années de construction doivent être dans [1000, 2030].
    Borne basse 1000 pour accepter le patrimoine médiéval (églises, abbayes : ~20 k bâtiments pré-1800 en HDF)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM public_data.buildings
            WHERE annee_constr IS NOT NULL
              AND (annee_constr < 1000 OR annee_constr > 2030);
        """)
        outliers = cur.fetchone()[0]
        assert outliers == 0, f"{outliers} années de construction hors [1000, 2030]"


def test_surface_positive(db):
    """Les surfaces non-nulles doivent être > 0 et < 1 000 000 m² (limite haute sanity)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM public_data.buildings
            WHERE surface_m2 IS NOT NULL AND (surface_m2 <= 0 OR surface_m2 > 1000000);
        """)
        outliers = cur.fetchone()[0]
        assert outliers == 0, f"{outliers} surfaces hors [0, 1M] m²"


def test_dpe_table_exists(db):
    """Table public_data.dpe existe avec ses index."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema='public_data' AND table_name='dpe';
        """)
        assert cur.fetchone()[0] == 1, "Table public_data.dpe absente"

        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname='public_data' AND tablename='dpe';
        """)
        names = {r[0] for r in cur.fetchall()}
        assert "idx_dpe_building_id" in names
        assert "idx_dpe_classe" in names


def test_dpe_types_canoniques(db):
    """type_dpe ∈ {'logement', 'tertiaire'}."""
    with db.cursor() as cur:
        cur.execute("SELECT DISTINCT type_dpe FROM public_data.dpe WHERE type_dpe IS NOT NULL;")
        vals = {r[0] for r in cur.fetchall()}
        if not vals:
            pytest.skip("Aucun DPE ingéré encore")
        invalid = vals - {"logement", "tertiaire"}
        assert not invalid, f"type_dpe inattendus : {invalid}"


def test_dpe_arrete_2021_logements(db):
    """Tous les DPE logement non-nuls doivent être arrete_2021=true (coefficient EP élec 1.9)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FILTER (WHERE arrete_2021 = false) AS bad,
                   count(*) FILTER (WHERE arrete_2021 = true) AS good,
                   count(*) AS total
            FROM public_data.dpe WHERE type_dpe='logement';
        """)
        bad, good, total = cur.fetchone()
        if total == 0:
            pytest.skip("Aucun DPE logement ingéré encore")
        assert bad == 0, (
            f"{bad} DPE logements avec arrete_2021=false trouvés "
            "(BDNB 2025-07.a est censé n'avoir que des DPE arrête 2021)"
        )
        assert good > 0, "Aucun DPE logement avec arrete_2021=true"


def test_dpe_idempotence(db):
    """La contrainte UNIQUE (building_id, identifiant_dpe) empêche les duplicates."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT building_id, identifiant_dpe, count(*) AS dup
            FROM public_data.dpe
            GROUP BY building_id, identifiant_dpe
            HAVING count(*) > 1
            LIMIT 1;
        """)
        row = cur.fetchone()
        assert row is None, f"Duplicate DPE détecté : {row}"
