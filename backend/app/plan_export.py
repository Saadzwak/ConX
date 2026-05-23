"""ConX — Export PDF des pré-cadrages rénovation IA (CHANTIER 3, 2026-05-23).

Pipeline : markdown texte (sortie agent) → HTML (markdown library) →
HTML composé avec Jinja2 (cover + TOC + body + sources) → PDF (weasyprint).

Le helper s'appuie sur le template `app/templates/plan_rapport.html` qui
contient toute la mise en page (couverture, en-tête de page, palette ConX).

Idempotent : aucun side-effect autre que la création du PDF de sortie.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger("conx.plan_export")

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "app" / "templates"
TEMPLATE_NAME = "plan_rapport.html"


# Sections-standard attendues dans un pré-cadrage (utilisé pour le sommaire).
# Si l'agent change la structure, le sommaire est généré à partir des h2/h3
# détectés dans le markdown (cf. _extract_toc).
DEFAULT_TOC_FALLBACK = [
    {"num": "1.", "title": "Diagnostic"},
    {"num": "2.", "title": "Stratégie hors-site biosourcée"},
    {"num": "3.", "title": "Bilan carbone 30 ans"},
    {"num": "4.", "title": "Estimation budgétaire"},
    {"num": "5.", "title": "Limites et précautions"},
]


def _extract_toc(markdown_text: str) -> list[dict[str, str]]:
    """Extrait un sommaire depuis les titres H2/H3 numérotés du markdown.

    Reconnaît :
      `### 1. Diagnostic`         → num=1., title=Diagnostic
      `### 2.1 ITE — ouate`       → num=2.1, title=ITE — ouate
      `## Plan rénovation v1`      → skip (titre principal)

    Retourne au maximum les 8 premières sections de niveau 1 (n.X ignorés
    si le résultat dépasse 8 entrées, pour ne pas surcharger la couverture).
    """
    toc: list[dict[str, str]] = []
    pattern = re.compile(
        r"^#{2,3}\s+(\d+(?:\.\d+)?)\.?\s+(.+?)$",
        re.MULTILINE,
    )
    seen_top = set()
    for m in pattern.finditer(markdown_text):
        num = m.group(1)
        title = m.group(2).strip()
        # Garder uniquement les sections top-level (1, 2, 3...)
        if "." in num:
            continue
        if num in seen_top:
            continue
        seen_top.add(num)
        toc.append({"num": f"{num}.", "title": title})
    if len(toc) >= 3:
        return toc
    return DEFAULT_TOC_FALLBACK


def _markdown_to_html(markdown_text: str) -> str:
    """Convertit le markdown en HTML.

    Préfère `markdown` (avec extension `tables`, `fenced_code`) si dispo,
    sinon `markdown-it-py`, sinon fallback minimal (paragraphes + sauts).
    Toutes ces libs sont des wheels purement Python, légères.
    """
    try:
        import markdown  # type: ignore

        return markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        )
    except ImportError:
        pass

    try:
        from markdown_it import MarkdownIt  # type: ignore

        md = MarkdownIt("commonmark", {"breaks": True, "html": False}).enable(
            ["table", "strikethrough"]
        )
        return md.render(markdown_text)
    except ImportError:
        pass

    # Fallback ultra minimal : on tente quand même de rendre quelque chose.
    logger.warning(
        "Ni `markdown` ni `markdown-it-py` disponibles — fallback rendu minimal.",
    )
    paragraphs = markdown_text.split("\n\n")
    html_paragraphs = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("### "):
            html_paragraphs.append(f"<h3>{p[4:]}</h3>")
        elif p.startswith("## "):
            html_paragraphs.append(f"<h2>{p[3:]}</h2>")
        elif p.startswith("# "):
            html_paragraphs.append(f"<h1>{p[2:]}</h1>")
        else:
            html_paragraphs.append(f"<p>{p.replace(chr(10), '<br>')}</p>")
    return "\n".join(html_paragraphs)


def _strip_top_h2(markdown_text: str) -> tuple[str, str]:
    """Enlève le H2 de titre du début du markdown (devient title de la
    couverture). Retourne (title, markdown_sans_h2).
    """
    m = re.match(r"^\s*##\s+(.+?)\s*$", markdown_text, re.MULTILINE)
    if not m:
        return ("Pré-cadrage rénovation", markdown_text)
    title = m.group(1)
    rest = markdown_text[m.end():].lstrip("\n")
    return (title, rest)


def render_plan_pdf(
    *,
    plan_markdown: str,
    building_id: str,
    version: int,
    output_path: Path,
    adresse_postale: str | None = None,
    commune_nom: str | None = None,
    dept: str | None = None,
    rnb_id: str | None = None,
    identifiant_dpe_ademe: str | None = None,
    bdnb_millesime: str | None = None,
) -> Path:
    """Génère le PDF du pré-cadrage.

    Lève HTTPException 503 si jinja2 ou weasyprint absents (mode dégradé).
    Lève HTTPException 422 si le markdown est vide.
    """
    if not plan_markdown or not plan_markdown.strip():
        raise HTTPException(
            status_code=422,
            detail="Plan vide — rien à exporter.",
        )

    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from weasyprint import HTML
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"jinja2/weasyprint indisponibles : {exc}",
        ) from exc

    if not TEMPLATES_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Dossier templates introuvable : {TEMPLATES_DIR}",
        )

    title, body_markdown = _strip_top_h2(plan_markdown)
    toc = _extract_toc(body_markdown)
    plan_html = _markdown_to_html(body_markdown)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    html_str = template.render(
        document_title=title,
        version_label=f"v{version}",
        adresse_postale=adresse_postale,
        commune_nom=commune_nom,
        dept=dept,
        building_id=building_id,
        rnb_id=rnb_id,
        identifiant_dpe_ademe=identifiant_dpe_ademe,
        bdnb_millesime=bdnb_millesime or "2025-07.a",
        plan_html=plan_html,
        toc=toc,
        generated_at=datetime.now(UTC).strftime("%d %B %Y · %H:%M UTC"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str).write_pdf(str(output_path))
    logger.info(
        "PDF plan généré : %s (%d bytes, building=%s, v%d)",
        output_path, output_path.stat().st_size, building_id, version,
    )
    return output_path
