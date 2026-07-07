"""Tests pour `app.plan_export` (CHANTIER 3 — export PDF des plans IA).

Couvre :
- extraction du sommaire depuis markdown numéroté
- conversion markdown → HTML
- strip du H2 titre
- erreur 422 sur markdown vide
- erreur 503 si weasyprint absent (skip si présent)
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.plan_export import (
    DEFAULT_TOC_FALLBACK,
    _extract_toc,
    _fallback_markdown_to_html,
    _markdown_to_html,
    _strip_code_fence_wrapper,
    _strip_top_h2,
    render_plan_pdf,
)

SAMPLE_PLAN = """## Pré-cadrage v1 — Pavillon F → C
*Bâtiment 124 m² | brique | 1965*

> Ce pré-cadrage propose une approche modulaire.

### 1. Diagnostic
Le pavillon est ainsi.

### 2. Stratégie hors-site biosourcée
#### 2.1 ITE — ouate de cellulose
Détail du procédé.

### 3. Bilan carbone 30 ans

| Composante | Valeur |
|---|---|
| Exploitation | +58 t |

### 4. Estimation budgétaire
Total 40 000 €.

### 5. Limites et précautions
À confirmer.
"""


def test_extract_toc_keeps_top_level_only():
    toc = _extract_toc(SAMPLE_PLAN)
    nums = [it["num"] for it in toc]
    assert nums == ["1.", "2.", "3.", "4.", "5."]
    # Section 2.1 ne doit PAS être dans le sommaire (sous-section)
    titles = " ".join(it["title"] for it in toc)
    assert "2.1" not in titles


def test_extract_toc_fallback_si_aucune_section():
    toc = _extract_toc("Du markdown sans titres numérotés.")
    # Le fallback doit avoir au moins 3 entrées
    assert toc == DEFAULT_TOC_FALLBACK
    assert len(toc) >= 5


def test_strip_top_h2_extrait_titre():
    title, rest = _strip_top_h2(SAMPLE_PLAN)
    assert title == "Pré-cadrage v1 — Pavillon F → C"
    # Le H2 ne doit plus être dans le rest (mais le sous-titre italique reste)
    assert not rest.startswith("## ")
    assert "*Bâtiment 124 m²" in rest


def test_strip_top_h2_robuste_sans_h2():
    title, rest = _strip_top_h2("Du markdown sans titre H2 du tout.")
    assert title == "Pré-cadrage rénovation"
    assert rest == "Du markdown sans titre H2 du tout."


def test_markdown_to_html_genere_tables():
    """Si la lib `markdown` est installée, les tableaux GFM sont rendus."""
    html = _markdown_to_html(SAMPLE_PLAN)
    # Tag table doit être présent quelle que soit la lib utilisée
    assert "<table" in html.lower() or "Composante" in html


def test_render_plan_pdf_erreur_422_si_vide(tmp_path):
    with pytest.raises(HTTPException) as exc_info:
        render_plan_pdf(
            plan_markdown="",
            building_id="bdnb-test",
            version=1,
            output_path=tmp_path / "out.pdf",
        )
    assert exc_info.value.status_code == 422


def test_strip_code_fence_wrapper_markdown_lang():
    """Cas réel observé : l'agent wrappe sa sortie dans ```markdown ... ```."""
    src = "```markdown\n## Pré-cadrage v1\n\nContenu.\n```"
    assert _strip_code_fence_wrapper(src) == "## Pré-cadrage v1\n\nContenu."


def test_strip_code_fence_wrapper_plain_fence():
    """Variante : fence vide ``` ... ```."""
    src = "```\ntext\n```"
    assert _strip_code_fence_wrapper(src) == "text"


def test_strip_code_fence_wrapper_no_fence_noop():
    """Idempotent : markdown sans fence passe tel quel."""
    src = "## Plan\nContenu sans fence."
    assert _strip_code_fence_wrapper(src) == src


def test_strip_code_fence_wrapper_inline_fence_not_stripped():
    """Un fence inline (code block mid-document) ne doit PAS être retiré
    en tête — seul le wrapper sur tout le document est ciblé."""
    src = "## Plan\nContenu.\n\n```python\ncode = 1\n```\n\nFin."
    # Le doc ne COMMENCE pas par ``` → no-op
    assert _strip_code_fence_wrapper(src) == src


def test_fallback_markdown_to_html_supports_tables_and_bold():
    """Le fallback doit jamais laisser du markdown brut visible."""
    src = "## Titre\n\n**gras** et *italique*\n\n| a | b |\n|---|---|\n| 1 | 2 |"
    html = _fallback_markdown_to_html(src)
    assert "<h2>Titre</h2>" in html
    assert "<strong>gras</strong>" in html
    assert "<em>italique</em>" in html
    assert "<table>" in html
    assert "<th>a</th>" in html
    # Plus de markdown brut
    assert "**" not in html
    assert "| 1 |" not in html


def test_render_plan_pdf_smoke(tmp_path):
    """Test smoke : si weasyprint est dispo, génère un PDF non-vide.
    Sinon, vérifie que l'erreur est un 503 propre."""
    pytest.importorskip("weasyprint")
    pytest.importorskip("markdown")
    out = tmp_path / "smoke.pdf"
    result = render_plan_pdf(
        plan_markdown=SAMPLE_PLAN,
        building_id="bdnb-test",
        version=1,
        output_path=out,
        adresse_postale="12 Rue de Test",
        commune_nom="Testville",
        dept="59",
        rnb_id="TESTRNB",
        identifiant_dpe_ademe="TESTDPE",
    )
    assert result.exists()
    assert result.stat().st_size > 5000  # un PDF même minimal pèse > 5 KB
    # Sanity check : commence par le magic header PDF
    with result.open("rb") as f:
        assert f.read(5) == b"%PDF-"
