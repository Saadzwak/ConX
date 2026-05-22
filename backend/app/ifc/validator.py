"""ConX — wrapper IFC validator (J13).

Importe la fonction `validate()` depuis `skills/ifc-check/ifc_validator.py`
au runtime. Ce wrapper isole le backend d'éventuels changements de chemin
côté skills bundle.

Pattern : on ajoute `skills/ifc-check/` à `sys.path` au premier appel,
puis on import `ifc_validator`. Pas de copie de code — single source of
truth dans `skills/`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("conx.ifc.validator")

# Le bundle skills est mounté dans le container backend en /app/skills:ro
# (cf. docker-compose.yml). En dev hors-Docker, on remonte aussi jusqu'à la
# racine projet (4 niveaux au-dessus de ce fichier).
_HERE = Path(__file__).resolve().parent
SKILL_DIR_CANDIDATES = [
    _HERE.parent.parent / "skills" / "ifc-check",                       # /app/skills (container)
    _HERE.parent.parent.parent / "skills" / "ifc-check",                # racine projet (dev local)
]
SKILL_DIR = next((p for p in SKILL_DIR_CANDIDATES if p.exists()), SKILL_DIR_CANDIDATES[0])

_validate_fn = None


def _load_validator() -> Any:
    """Lazy-loads `validate` from the skill bundle. Lève ImportError si
    ifcopenshell n'est pas dispo dans le container backend."""
    global _validate_fn
    if _validate_fn is not None:
        return _validate_fn

    if not SKILL_DIR.exists():
        raise ImportError(f"Skill ifc-check introuvable : {SKILL_DIR}")
    if str(SKILL_DIR) not in sys.path:
        sys.path.insert(0, str(SKILL_DIR))
    try:
        from ifc_validator import validate  # type: ignore[import-not-found]
    except ImportError as exc:
        logger.exception("Erreur import ifc_validator")
        raise ImportError(
            f"ifc_validator non importable : {exc}. "
            "Vérifier que ifcopenshell est installé dans le backend."
        ) from exc
    _validate_fn = validate
    return _validate_fn


def validate_ifc(ifc_path: Path) -> dict[str, Any]:
    """Valide un fichier IFC et retourne le JSON de résultat.

    Le JSON contient :
    - `filename`, `ifc_schema`, `valid_syntax`, `n_entities`, `summary`
    - `re2020_checks` : dict des contrôles RE2020
    - `pmr_checks` : dict des contrôles PMR
    - `anomalies` : list[str]
    - `disclaimer` : avertissement obligatoire

    Si parse échoue (fichier corrompu, schéma non supporté), retourne
    `{filename, valid_syntax: False, error: "..."}`.
    """
    validate = _load_validator()
    return validate(ifc_path)
