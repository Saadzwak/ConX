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

    Priorité :
      1. `markdown` (Python-Markdown, extensions tables + fenced_code + nl2br
         + sane_lists + attr_list) — rendu complet GFM-compatible.
      2. `markdown-it-py` (CommonMark + tables + breaks).
      3. Fallback minimal — TOUJOURS gère gras/italique/listes/tableaux/
         blockquotes (sinon le PDF affiche du markdown brut, cf. CHANTIER 2
         brief Saad 2026-05-23).

    Si on tombe dans le fallback, on log un WARNING explicite — l'env du
    container Docker est probablement cassé (markdown pas installé).
    """
    try:
        import markdown  # type: ignore

        return markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "sane_lists", "nl2br", "attr_list"],
        )
    except ImportError:
        pass

    try:
        from markdown_it import MarkdownIt  # type: ignore

        md = MarkdownIt("commonmark", {"breaks": True, "html": False}).enable(["table", "strikethrough"])
        return md.render(markdown_text)
    except ImportError:
        pass

    # Fallback robuste — supporte tableaux pipe, blockquotes, listes, gras,
    # italique. Ne couvre pas les fenced code blocks. À utiliser en dernier
    # recours si la prod tourne sans `markdown` dans le venv.
    logger.error(
        "Ni `markdown` ni `markdown-it-py` disponibles dans l'env Python. "
        "Le PDF sera rendu via fallback dégradé. Installer `markdown==3.7` "
        "dans le container (backend/requirements.txt + rebuild).",
    )
    return _fallback_markdown_to_html(markdown_text)


def _fallback_markdown_to_html(text: str) -> str:
    """Rendu markdown minimaliste sans lib externe — supporte :
       - h1/h2/h3/h4
       - gras **x**, italique *x*
       - listes - et 1.
       - blockquotes >
       - tableaux pipe (| col | col |)
       - séparateurs ---

    L'objectif est de ne JAMAIS produire de markdown brut visible dans le
    PDF, même en environnement dégradé.
    """
    import html as html_mod
    import re

    out: list[str] = []
    lines = text.split("\n")
    i = 0
    n = len(lines)
    in_ul = in_ol = False

    def _inline(s: str) -> str:
        """Convertit gras + italique + code inline. Échappe le HTML d'abord."""
        s = html_mod.escape(s)
        # Code inline `xx`
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        # Gras **x**
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        # Italique *x* (mais pas si entouré d'autres *)
        s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
        return s

    def _close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < n:
        line = lines[i].rstrip()
        stripped = line.strip()

        # Lignes vides
        if not stripped:
            _close_lists()
            i += 1
            continue

        # Séparateur horizontal
        if re.match(r"^---+$", stripped):
            _close_lists()
            out.append("<hr/>")
            i += 1
            continue

        # Titres h1-h4
        m = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m:
            _close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote (peut s'étendre sur plusieurs lignes)
        if stripped.startswith(">"):
            _close_lists()
            quote_lines: list[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote_lines.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            out.append("<blockquote>" + _inline("<br/>".join(quote_lines)) + "</blockquote>")
            continue

        # Tableau pipe (détection : ligne avec >=2 pipes ET ligne suivante de
        # séparateurs --- pipe)
        if "|" in stripped and i + 1 < n:
            next_line = lines[i + 1].strip()
            if re.match(r"^\|?\s*:?-{2,}.*\|.*$", next_line):
                _close_lists()
                # Header
                header_cells = [c.strip() for c in stripped.strip("|").split("|")]
                rows: list[list[str]] = []
                j = i + 2
                while j < n and "|" in lines[j].strip():
                    rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                    j += 1
                # Render
                tbl = ["<table><thead><tr>"]
                for c in header_cells:
                    tbl.append(f"<th>{_inline(c)}</th>")
                tbl.append("</tr></thead><tbody>")
                for r in rows:
                    tbl.append("<tr>")
                    for c in r:
                        tbl.append(f"<td>{_inline(c)}</td>")
                    tbl.append("</tr>")
                tbl.append("</tbody></table>")
                out.append("".join(tbl))
                i = j
                continue

        # Liste à puces
        if re.match(r"^[-*+]\s+", stripped):
            if not in_ul:
                _close_lists()
                out.append("<ul>")
                in_ul = True
            item = re.sub(r"^[-*+]\s+", "", stripped)
            out.append(f"<li>{_inline(item)}</li>")
            i += 1
            continue

        # Liste numérotée
        if re.match(r"^\d+\.\s+", stripped):
            if not in_ol:
                _close_lists()
                out.append("<ol>")
                in_ol = True
            item = re.sub(r"^\d+\.\s+", "", stripped)
            out.append(f"<li>{_inline(item)}</li>")
            i += 1
            continue

        # Paragraphe normal
        _close_lists()
        out.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    _close_lists()
    return "\n".join(out)


def _strip_code_fence_wrapper(text: str) -> str:
    """Enlève les fences ```markdown ... ``` que les LLMs ajoutent parfois
    autour de leur sortie complète. Idempotent (no-op si pas de fence).

    Cas réel observé : l'agent conx-plan répond parfois avec
        ```markdown
        ## Pré-cadrage…
        …
        ```
    Si on garde le fence, markdown.markdown() rend la totalité comme un
    bloc de code monospace dans le PDF — catastrophique.
    """
    s = text.strip()
    if s.startswith("```"):
        # Format ```markdown\n...content...\n```
        first_nl = s.find("\n")
        if first_nl >= 0:
            first_line = s[:first_nl].strip()
            # Accepte ```, ```markdown, ```md
            if first_line in ("```", "```markdown", "```md", "```text"):
                s = s[first_nl + 1 :]
                if s.rstrip().endswith("```"):
                    s = s.rstrip()[:-3].rstrip()
    return s


def _strip_top_h2(markdown_text: str) -> tuple[str, str]:
    """Enlève le H2 de titre du début du markdown (devient title de la
    couverture). Retourne (title, markdown_sans_h2).

    Nettoie d'abord les fences ```markdown ... ``` que les LLMs ajoutent
    parfois.
    """
    markdown_text = _strip_code_fence_wrapper(markdown_text)
    m = re.match(r"^\s*##\s+(.+?)\s*$", markdown_text, re.MULTILINE)
    if not m:
        return ("Pré-cadrage rénovation", markdown_text)
    title = m.group(1)
    rest = markdown_text[m.end() :].lstrip("\n")
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

        from .pdf_utils import render_html_to_pdf
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

    # Rendu via le helper durci (url_fetcher restreint — anti LFI/SSRF, C1).
    render_html_to_pdf(html_str, output_path)
    logger.info(
        "PDF plan généré : %s (%d bytes, building=%s, v%d)",
        output_path,
        output_path.stat().st_size,
        building_id,
        version,
    )
    return output_path
