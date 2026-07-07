"""ConX — calcul carbone incorporé via la base statique FDES (J6).

Lit `data/fdes_static.json` (30 matériaux clés, D-014) et calcule le total kgCO2eq incorporé
d'une liste d'éléments matériaux.

UF (unité fonctionnelle) du JSON : voir `uf_description` dans chaque matériau. Le caller doit
fournir une quantité dans la même UF que la FDES (ex: m² pour les parois, m³ pour les structures).

Carbone biogénique stocké : remonté en sortie pour l'UI ("XX kg de CO₂ piégés dans les biosourcés").
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.carbon.factors import SOURCE_REFERENCES
from app.paths import DATA_DIR

# Résolution robuste Docker/dev (cf. app/paths.py) — remplace un parents[3] qui
# pointait sur `/data` en conteneur au lieu de `/app/data`.
FDES_PATH_DEFAULT = DATA_DIR / "fdes_static.json"


@dataclass(frozen=True)
class MaterialQuantity:
    """Une ligne d'élément matériau dans un plan de rénovation."""

    material_id: str  # ex: 'bois-clt'
    quantity: float  # en UF du matériau (m² ou m³ selon la FDES)
    label: str | None = None  # description libre pour l'UI


@dataclass(frozen=True)
class IncorporeResult:
    """Résultat carbone incorporé."""

    total_kg_co2_eq: float  # somme algébrique (peut être négative si biosourcés dominent)
    total_biogenic_co2_stored_kg: float  # carbone piégé via biosourcés
    breakdown: list[dict]  # 1 entrée par matériau, pour l'UI détaillée
    hypotheses: dict[str, str]


@lru_cache(maxsize=1)
def _load_fdes(path: str | None = None) -> dict:
    """Charge le JSON FDES (cache mono-instance)."""
    p = Path(path) if path else FDES_PATH_DEFAULT
    if not p.exists():
        raise FileNotFoundError(f"FDES statique introuvable : {p}")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def list_materials(path: str | None = None) -> list[dict]:
    """Liste tous les matériaux disponibles (id, name, kgCO2eq_per_uf, category, …)."""
    return list(_load_fdes(path)["materials"])


def get_material(material_id: str, path: str | None = None) -> dict:
    """Récupère un matériau par id. KeyError si introuvable."""
    for m in _load_fdes(path)["materials"]:
        if m["id"] == material_id:
            return m
    raise KeyError(f"Matériau FDES introuvable : {material_id!r}")


def compute_incorpore(
    items: list[MaterialQuantity],
    fdes_path: str | None = None,
) -> IncorporeResult:
    """Bilan carbone incorporé d'une liste de matériaux+quantités.

    Args:
        items : liste de (material_id, quantity, label).
        fdes_path : chemin alternatif du JSON FDES (tests).

    Returns:
        IncorporeResult avec total kg CO2eq + carbone biogénique stocké + breakdown.
    """
    fdes = _load_fdes(fdes_path)
    materials_by_id = {m["id"]: m for m in fdes["materials"]}

    total_kg_co2 = 0.0
    total_biogenic = 0.0
    breakdown: list[dict] = []

    for item in items:
        if item.quantity < 0:
            raise ValueError(f"Quantité doit être >= 0, reçu {item.quantity} pour {item.material_id}")
        mat = materials_by_id.get(item.material_id)
        if mat is None:
            raise KeyError(f"Matériau FDES inconnu : {item.material_id!r}")
        co2_kg = float(mat["kgCO2eq_per_uf"]) * item.quantity
        biogenic_kg = float(mat.get("biogenic_co2_stored_kg") or 0.0) * item.quantity
        total_kg_co2 += co2_kg
        total_biogenic += biogenic_kg
        breakdown.append(
            {
                "material_id": item.material_id,
                "material_name": mat["name"],
                "label": item.label,
                "category": mat["category"],
                "quantity": item.quantity,
                "uf_description": mat["uf_description"],
                "kg_co2_eq_per_uf": float(mat["kgCO2eq_per_uf"]),
                "kg_co2_eq_total": round(co2_kg, 2),
                "biogenic_co2_stored_kg": round(biogenic_kg, 2),
                "fdes_declaration_id": mat["fdes_declaration_id"],
            }
        )

    hypotheses = {
        "n_materials": str(len(items)),
        "source_fdes": SOURCE_REFERENCES["inies_fdes"],
        "version_fdes_static": str(fdes.get("version", "1.0")),
        "consulted_at": str(fdes.get("consulted_at", "2026-05-21")),
        "convention_uf": (
            "kgCO2eq exprimé pour 1 m² (parois) ou 1 m³ (structures) selon FDES "
            "(cf. uf_description par matériau). Pour les isolants : R=5 m².K/W sauf mention."
        ),
        "biogenic_co2_meaning": (
            "Carbone biogénique stocké = CO₂ atmosphérique séquestré dans la biomasse "
            "du matériau (bois, paille, chanvre, …). Affiché séparément du kgCO2eq."
        ),
    }

    return IncorporeResult(
        total_kg_co2_eq=round(total_kg_co2, 2),
        total_biogenic_co2_stored_kg=round(total_biogenic, 2),
        breakdown=breakdown,
        hypotheses=hypotheses,
    )
