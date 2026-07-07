"""ConX — génération PDF du rapport Conformité (J13).

Pipeline : Jinja2 (HTML template) → WeasyPrint (HTML → PDF).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger("conx.ifc.pdf")

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = ROOT / "app" / "templates"
TEMPLATE_NAME = "conformite_rapport.html"

# Labels lisibles pour les clés techniques de check (RE2020/PMR)
CHECK_LABELS: dict[str, str] = {
    # RE2020
    "uw_doors_below_1_3": "U portes ≤ 1.3 W/m².K",
    "uw_windows_below_1_3": "U fenêtres ≤ 1.3 W/m².K",
    "r_walls_above_3_7": "R murs extérieurs ≥ 3.7 m².K/W",
    "r_toiture_above_6": "R toiture ≥ 6.0 m².K/W",
    # PMR
    "door_width_min_900mm": "Largeur portes ≥ 0.90 m",
    "ramp_slope_max_5pct": "Pente rampes ≤ 5 %",
    "corridor_width_min_1400mm": "Largeur couloirs ≥ 1.40 m",
}


def render_pdf(validation_json: dict[str, Any], output_path: Path) -> Path:
    """Génère le PDF du rapport conformité.

    `validation_json` : sortie de `ifc/validator.py validate_ifc()`.
    `output_path` : chemin absolu où écrire le PDF.

    Lève HTTPException 503 si jinja2 ou weasyprint ne sont pas dispos.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        from ..pdf_utils import render_html_to_pdf
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Jinja2 ou WeasyPrint non installé : {exc}",
        ) from exc

    if not TEMPLATES_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Dossier templates introuvable : {TEMPLATES_DIR}",
        )

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_NAME)

    context = {
        **validation_json,
        "check_labels": CHECK_LABELS,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        # Sécurise les sous-dicts attendus par le template :
        "summary": validation_json.get("summary") or {},
        "re2020_checks": validation_json.get("re2020_checks") or {},
        "pmr_checks": validation_json.get("pmr_checks") or {},
        "anomalies": validation_json.get("anomalies") or [],
    }
    html_str = template.render(**context)

    # Rendu via le helper durci (url_fetcher restreint — anti LFI/SSRF, C1).
    render_html_to_pdf(html_str, output_path)
    logger.info("PDF généré : %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path
