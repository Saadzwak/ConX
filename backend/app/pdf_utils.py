"""ConX — rendu PDF WeasyPrint sécurisé (anti LFI/SSRF). Cf. docs/AUDIT_2026-07-07.md C1.

Contexte du risque : les rapports PDF (pré-cadrage plan, conformité IFC) sont
rendus par WeasyPrint à partir de HTML qui embarque du contenu partiellement
non maîtrisé (texte de plan généré par l'agent, champs issus du fichier IFC
uploadé). Par défaut, le `url_fetcher` de WeasyPrint résout `file:`, `http(s):`
et `data:`. Un HTML contenant `<link rel="attachment" href="file:///app/.env">`
ferait donc lire un fichier local et l'embarquerait dans le PDF retourné
(LFI → exfiltration de secrets), et `href="http://169.254.169.254/…"` permettrait
un SSRF.

Défense : les templates ConX (`plan_rapport.html`, `conformite_rapport.html`)
sont 100 % autosuffisants — CSS inline, aucune ressource externe (vérifié).
On restreint donc le `url_fetcher` aux seules `data:` URIs inline et on refuse
tout `file:` / `http(s):`. WeasyPrint n'exécute par ailleurs aucun JavaScript,
donc cette restriction neutralise l'intégralité du vecteur LFI/SSRF.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("conx.pdf")


def secure_url_fetcher(url: str):
    """`url_fetcher` restreint pour WeasyPrint.

    Autorise uniquement les `data:` URIs inline (auto-suffisantes, ni réseau ni
    disque). Refuse `file:`, `http:`, `https:` et tout autre scheme → bloque
    l'exfiltration de fichiers locaux et le SSRF.
    """
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url)
    logger.warning(
        "Rendu PDF : récupération d'URL externe refusée (anti LFI/SSRF) : %.80s",
        url,
    )
    raise ValueError(f"URL externe interdite dans le rendu PDF ConX : {url[:80]!r}")


def render_html_to_pdf(html_str: str, output_path: Path) -> Path:
    """Rend `html_str` en PDF à `output_path` avec le `url_fetcher` durci.

    Point d'entrée unique pour tous les rendus PDF du backend, afin qu'aucun
    appel `HTML(...).write_pdf(...)` ne contourne la restriction url_fetcher.
    """
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # base_url=None : aucune résolution d'URL relative implicite.
    HTML(string=html_str, url_fetcher=secure_url_fetcher, base_url=None).write_pdf(str(output_path))
    return output_path
