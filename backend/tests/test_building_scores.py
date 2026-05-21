"""ConX — Tests d'invariants post-pré-calcul scoring (public_data.building_scores).

Vérifie sur la BD réelle : (1) bornes [0,1] respectées sur les 5 composantes,
(2) cohérence DPE-source vs flag incomplete, (3) référentiel building_id intact,
(4) thresholds_version stable.

Mode dégradé : skip si DATABASE_URL_LOCAL non défini ou DB injoignable.
D-016 : invariants sanity dérivés de la donnée, pas inventés.
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


def test_building_scores_table_exists(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema='public_data' AND table_name='building_scores';
        """)
        assert cur.fetchone()[0] == 1, "Table public_data.building_scores absente"


def test_components_in_bounds(db):
    """Les 5 composantes sont strictement dans [0,1] grâce aux CHECK constraints, mais
    on vérifie qu'aucune ligne n'est en dehors (au cas où les contraintes auraient été dropées)."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM public_data.building_scores
            WHERE s_co2 < 0 OR s_co2 > 1
               OR s_faisa < 0 OR s_faisa > 1
               OR s_cout < 0 OR s_cout > 1
               OR s_social < 0 OR s_social > 1
               OR s_passoire < 0 OR s_passoire > 1;
        """)
        bad = cur.fetchone()[0]
        if not _has_any_rows(cur):
            pytest.skip("Aucune ligne dans building_scores — lancer compute_building_scores.py")
        assert bad == 0, f"{bad} lignes avec composante hors [0,1]"


def test_confidence_in_bounds(db):
    """confidence ∈ [0,1]."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("""
            SELECT count(*) FROM public_data.building_scores
            WHERE confidence < 0 OR confidence > 1;
        """)
        assert cur.fetchone()[0] == 0


def test_dpe_source_canonique(db):
    """dpe_source ∈ {ademe-real, ml-predicted} (SCORING.md §Implémentation, D-006)."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("SELECT DISTINCT dpe_source FROM public_data.building_scores;")
        vals = {r[0] for r in cur.fetchall()}
        canonical = {"ademe-real", "ml-predicted"}
        assert vals.issubset(canonical), f"dpe_source inattendus : {vals - canonical}"


def test_real_dpe_source_implies_dpe_classe(db):
    """Si dpe_source='ademe-real', le bâtiment doit avoir dpe_classe non null."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("""
            SELECT count(*) FROM public_data.building_scores bs
            JOIN public_data.buildings b USING (building_id)
            WHERE bs.dpe_source = 'ademe-real' AND b.dpe_classe IS NULL;
        """)
        n_bad = cur.fetchone()[0]
        assert n_bad == 0, f"{n_bad} lignes 'ademe-real' avec dpe_classe NULL"


def test_thresholds_version_uniforme(db):
    """Toutes les lignes doivent avoir le même thresholds_version (sinon, batch incohérent)."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("SELECT DISTINCT thresholds_version FROM public_data.building_scores;")
        versions = {r[0] for r in cur.fetchall()}
        assert len(versions) <= 1, (
            f"Plusieurs thresholds_version coexistent : {versions} — "
            "relancer compute_building_scores.py pour homogénéiser."
        )


def test_referentiel_building_id(db):
    """Chaque building_id de building_scores doit exister dans buildings (FK active)."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("""
            SELECT count(*) FROM public_data.building_scores bs
            LEFT JOIN public_data.buildings b ON b.building_id = bs.building_id
            WHERE b.building_id IS NULL;
        """)
        orphans = cur.fetchone()[0]
        assert orphans == 0, f"{orphans} building_scores orphelins"


def test_co2_evite_negatif_implique_s_co2_nul(db):
    """Pas de co2_evite_t < 0 (les buildings A avec kwh < cible donnent co2_evite_t = 0 par clip)."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("SELECT count(*) FROM public_data.building_scores WHERE co2_evite_t < 0;")
        bad = cur.fetchone()[0]
        assert bad == 0, f"{bad} co2_evite_t négatifs"


def test_passoire_correlation_dpe_classe(db):
    """s_passoire doit refléter la classe DPE selon SCORING.md (A-D=0, E=0.5, F-G=1)."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("""
            SELECT b.dpe_classe, MIN(bs.s_passoire), MAX(bs.s_passoire), count(*)
            FROM public_data.building_scores bs
            JOIN public_data.buildings b USING (building_id)
            WHERE b.dpe_classe IS NOT NULL
            GROUP BY b.dpe_classe ORDER BY b.dpe_classe;
        """)
        rows = cur.fetchall()
        if not rows:
            pytest.skip("Aucun bâtiment avec dpe_classe")
        expected = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0, "E": 0.5, "F": 1.0, "G": 1.0}
        for classe, min_s, max_s, _n in rows:
            assert float(min_s) == expected[classe], f"{classe}: min={min_s}"
            assert float(max_s) == expected[classe], f"{classe}: max={max_s}"


def test_social_correlation_type_proprietaire(db):
    """s_social doit refléter type_proprietaire."""
    with db.cursor() as cur:
        _skip_if_empty(cur)
        cur.execute("""
            SELECT b.type_proprietaire, MIN(bs.s_social), MAX(bs.s_social), count(*)
            FROM public_data.building_scores bs
            JOIN public_data.buildings b USING (building_id)
            WHERE b.type_proprietaire IS NOT NULL
            GROUP BY b.type_proprietaire;
        """)
        rows = cur.fetchall()
        if not rows:
            pytest.skip("Aucun type_proprietaire")
        expected = {"bailleur_social": 1.0, "personne_morale_privee": 0.5, "particulier": 0.3}
        for tp, min_s, max_s, _n in rows:
            if tp in expected:
                assert float(min_s) == expected[tp], f"{tp}: min={min_s}"
                assert float(max_s) == expected[tp], f"{tp}: max={max_s}"


def _has_any_rows(cur) -> bool:
    cur.execute("SELECT count(*) FROM public_data.building_scores LIMIT 1;")
    return cur.fetchone()[0] > 0


def _skip_if_empty(cur):
    if not _has_any_rows(cur):
        pytest.skip("Aucune ligne dans building_scores — lancer compute_building_scores.py")
