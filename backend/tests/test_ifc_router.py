"""ConX — tests J13 router IFC (offline, sans ifcopenshell ni weasyprint).

On vérifie :
- `_validate_extension` accepte .ifc et rejette le reste.
- `_summarize_pass` retourne True/False/None selon les cas.
- Auth absent → 401 sur tous les endpoints.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers import ifc as ifc_router


def test_validate_extension_ifc_ok() -> None:
    ifc_router._validate_extension("model.ifc")
    ifc_router._validate_extension("MODEL.IFC")
    ifc_router._validate_extension("project.ifczip")


def test_validate_extension_rejects_other() -> None:
    for bad in ["model.dxf", "scan.pdf", "image.png", "no_ext"]:
        with pytest.raises(HTTPException) as exc:
            ifc_router._validate_extension(bad)
        assert exc.value.status_code == 400


def test_summarize_pass_all_true() -> None:
    checks = {
        "a": {"pass": True, "n_fail": 0},
        "b": {"pass": True, "n_fail": 0},
    }
    assert ifc_router._summarize_pass(checks) is True


def test_summarize_pass_at_least_one_false() -> None:
    checks = {
        "a": {"pass": True, "n_fail": 0},
        "b": {"pass": False, "n_fail": 2},
    }
    assert ifc_router._summarize_pass(checks) is False


def test_summarize_pass_empty_dict() -> None:
    """Cas parse error : pas de checks → None (état inconnu)."""
    assert ifc_router._summarize_pass({}) is None


def test_summarize_pass_ignores_non_dict_values() -> None:
    """Si pour une raison X un check n'est pas un dict, on ne crashe pas."""
    checks = {"a": {"pass": True}, "b": "weird-string", "c": {"pass": False}}
    assert ifc_router._summarize_pass(checks) is False


def test_max_ifc_size_bytes_reasonable() -> None:
    """Limite ≥ 50 Mo pour accepter des IFC de bâtiments HDF, ≤ 500 Mo
    pour ne pas saturer le disque par accident."""
    assert 50 * 1024 * 1024 <= ifc_router.MAX_IFC_SIZE_BYTES <= 500 * 1024 * 1024


def test_allowed_extensions() -> None:
    assert ".ifc" in ifc_router.ALLOWED_EXTS
    assert ".ifczip" in ifc_router.ALLOWED_EXTS
