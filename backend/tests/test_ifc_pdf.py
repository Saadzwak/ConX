"""ConX — tests J13 module ifc/pdf (offline, sans WeasyPrint runtime).

Tests qui ne nécessitent PAS WeasyPrint installé : on vérifie la logique de
préparation du context, la liste des labels, la gestion des champs manquants.

Les tests qui appellent `render_pdf` réellement sont skippés en CI Windows
(WeasyPrint nécessite gtk3 + cairo + pango, lourd sur Win). En Linux Docker
backend, ils tournent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ifc import pdf as ifc_pdf


def test_check_labels_complete() -> None:
    """Tous les codes RE2020 + PMR doivent avoir un label lisible."""
    expected = {
        "uw_doors_below_1_3",
        "uw_windows_below_1_3",
        "r_walls_above_3_7",
        "door_width_min_900mm",
        "ramp_slope_max_5pct",
    }
    for key in expected:
        assert key in ifc_pdf.CHECK_LABELS, f"Label manquant pour {key}"
        assert ifc_pdf.CHECK_LABELS[key], f"Label vide pour {key}"


def test_templates_dir_exists() -> None:
    assert ifc_pdf.TEMPLATES_DIR.exists(), f"Dossier templates introuvable : {ifc_pdf.TEMPLATES_DIR}"
    assert (ifc_pdf.TEMPLATES_DIR / ifc_pdf.TEMPLATE_NAME).exists()


def test_template_contains_required_blocks() -> None:
    """Le template doit avoir les sections clés (disclaimer, re2020, pmr, anomalies)."""
    content = (ifc_pdf.TEMPLATES_DIR / ifc_pdf.TEMPLATE_NAME).read_text(encoding="utf-8")
    for keyword in [
        "disclaimer",  # avertissement obligatoire
        "re2020_checks",
        "pmr_checks",
        "anomalies",
        "Pré-vérification",  # marketing ConX
    ]:
        assert keyword in content, f"Mot-clé {keyword!r} absent du template"


try:
    import weasyprint as _wp  # noqa: F401

    _HAS_WEASYPRINT = True
except ImportError:
    _HAS_WEASYPRINT = False


@pytest.mark.skipif(
    not _HAS_WEASYPRINT,
    reason="WeasyPrint non installé (CI Windows) — testé dans le container Docker backend.",
)
def test_render_pdf_smoke(tmp_path: Path) -> None:
    """Smoke test : rendu d'un JSON minimal en PDF non vide. Skip si pas dispo."""
    fake_validation = {
        "filename": "test.ifc",
        "valid_syntax": True,
        "ifc_schema": "IFC4",
        "n_entities": 100,
        "summary": {"n_walls": 10, "n_doors": 4, "n_windows": 6, "n_stairs": 1, "n_ramps": 0, "n_spaces": 5},
        "re2020_checks": {
            "uw_doors_below_1_3": {"pass": True, "n_checked": 4, "n_fail": 0, "details": []},
        },
        "pmr_checks": {
            "door_width_min_900mm": {"pass": True, "n_checked": 4, "n_fail": 0, "details": []},
        },
        "anomalies": [],
        "disclaimer": "Pré-vérification ConX — ne remplace pas un BCT.",
    }
    out = tmp_path / "out.pdf"
    ifc_pdf.render_pdf(fake_validation, out)
    assert out.exists()
    assert out.stat().st_size > 1000  # PDF non vide
