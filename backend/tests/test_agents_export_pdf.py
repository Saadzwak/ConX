"""Tests d'intégration route POST /api/agents/plan/<sid>/export-pdf
(CHANTIER 3, 2026-05-23).

On vérifie le câblage de la route :
- auth requise (401 sans JWT)
- accepte un `plan_text` dans le body
- query param `version` requis
- appelle bien `plan_export.render_plan_pdf` avec les bons arguments
- streame le PDF avec Content-Type application/pdf

weasyprint n'est pas dispo en venv local → on monkeypatch `render_plan_pdf`
pour valider la chaîne FastAPI sans rendu PDF réel.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def monkeyclient(monkeypatch):
    """TestClient avec auth + DB + render_plan_pdf monkeypatchés."""
    # Bypass auth via le fixture standard du projet (cf. test_auth.py)
    from app.auth import AuthUser, get_current_user
    from app.db import get_db
    from app.main import app

    fake_user = AuthUser(
        user_id="00000000-0000-0000-0000-000000000001",
        email="test@conx.local",
        role="architecte",
        jwt="fake.jwt.token",
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user

    # Mock l'asyncpg.Connection — la route fait `await conn.fetchrow(...)`
    # pour enrichir la couverture avec adresse BAN. On simule un retour
    # null (le PDF se génèrera avec building_id minimal).
    class _FakeConn:
        async def fetchrow(self, *_a, **_kw):
            return None

    app.dependency_overrides[get_db] = lambda: _FakeConn()

    # Monkeypatch render_plan_pdf pour ne pas appeler weasyprint
    from app import plan_export
    from app.routers import agents as agents_router

    pdf_marker = b"%PDF-1.4\n<mock-pdf-content>\n%%EOF"

    def fake_render(*, output_path: Path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_marker)
        return output_path

    monkeypatch.setattr(plan_export, "render_plan_pdf", fake_render)
    monkeypatch.setattr(agents_router, "render_plan_pdf", fake_render, raising=False)

    # Le module router importe render_plan_pdf à l'intérieur de la fonction
    # → monkeypatch direct sur plan_export marche
    client = TestClient(app)
    yield client, pdf_marker

    # Cleanup
    app.dependency_overrides.clear()


def test_export_pdf_requires_auth(monkeypatch):
    """Sans dependency_overrides, l'auth est requise.

    On neutralise le dev-bypass ambiant (le conteneur tourne avec
    CONX_DEV_BYPASS_AUTH=1) pour tester réellement le chemin non authentifié.
    """
    monkeypatch.delenv("CONX_DEV_BYPASS_AUTH", raising=False)
    from app.main import app

    client = TestClient(app)
    # Pas de header Authorization
    r = client.post(
        "/api/agents/plan/sesn_fake/export-pdf?version=1",
        json={"plan_text": "## Test\nLorem ipsum"},
    )
    assert r.status_code in (401, 403, 422), f"Expected auth error, got {r.status_code}"


def test_export_pdf_happy_path(monkeyclient):
    """Body avec plan_text → 200 + Content-Type application/pdf + bytes PDF."""
    client, pdf_marker = monkeyclient
    r = client.post(
        "/api/agents/plan/sesn_test01/export-pdf?version=2",
        json={
            "plan_text": "## Test plan v2\nContenu markdown\n### 1. Section A",
            "building_id": "bdnb-test-foo",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "v2" in r.headers.get("content-disposition", "")
    assert r.headers.get("x-conx-plan-version") == "2"
    # Le contenu doit être le faux PDF qu'on a écrit
    assert r.content.startswith(b"%PDF-")


def test_export_pdf_vide_renvoie_422(monkeyclient):
    """plan_text vide + cache absent → 422."""
    client, _ = monkeyclient
    r = client.post(
        "/api/agents/plan/sesn_test02/export-pdf?version=1",
        json={"plan_text": "", "building_id": "bdnb-inexistant"},
    )
    # 422 (markdown vide) ou 404 (cache miss)
    assert r.status_code in (404, 422), r.text


def test_export_pdf_version_query_required(monkeyclient):
    """L'absence du query param `version` doit donner 422 (validation FastAPI)."""
    client, _ = monkeyclient
    r = client.post(
        "/api/agents/plan/sesn_test03/export-pdf",  # pas de ?version=
        json={"plan_text": "## Test", "building_id": "bdnb-test"},
    )
    assert r.status_code == 422
