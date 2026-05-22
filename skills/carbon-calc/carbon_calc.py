"""Skill carbon-calc — wrapper CLI léger autour de backend.app.carbon.

Réutilise EXACTEMENT le module `backend/app/carbon/` (D-006 : un seul calcul
déterministe, la skill et le backend partagent le code). Pas de duplication.

Pour le bundle Anthropic : on copie/lie le module carbon en chemin relatif.
Utilisation depuis l'agent :
    python carbon_calc.py --surface 100 --avant G --apres B --energie gaz \\
        --material bois-clt=80 --material ouate-cellulose-insufflee=200
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Quand cette skill est uploadée sur Anthropic, le sandbox aura backend/ en sibling
# (cf. SKILL.md upload structure). En local on suppose être lancé depuis ROOT.
SKILL_DIR = Path(__file__).resolve().parent
ROOT_GUESS = SKILL_DIR.parent.parent  # skills/carbon-calc → repo root
sys.path.insert(0, str(ROOT_GUESS / "backend"))

from app.carbon import (  # noqa: E402
    MaterialQuantity,
    compute_total,
    list_materials,
    report_to_json,
)


def parse_material(spec: str) -> MaterialQuantity:
    """Parse 'material_id=quantity' (ex: bois-clt=80)."""
    if "=" not in spec:
        raise SystemExit(f"--material attendu 'id=quantity', reçu {spec!r}")
    mid, qty_str = spec.split("=", 1)
    return MaterialQuantity(material_id=mid.strip(), quantity=float(qty_str))


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcul bilan carbone ConX (J6)")
    parser.add_argument("--surface", type=float, required=True, help="Surface m² (>0)")
    parser.add_argument(
        "--avant", default=None, help="Classe DPE actuelle A-G (None autorisé)"
    )
    parser.add_argument("--apres", required=True, help="Classe DPE cible A-G")
    parser.add_argument(
        "--energie",
        default=None,
        help="Type d'énergie (gaz, électricité, fioul, bois, PAC…)",
    )
    parser.add_argument(
        "--material",
        action="append",
        default=[],
        help="Matériau au format 'material_id=quantity'. Répéter pour plusieurs.",
    )
    parser.add_argument(
        "--kwh-avant",
        type=float,
        default=None,
        help="DPE réel kWh ep/m²/an (override midpoint classe)",
    )
    parser.add_argument("--horizon-years", type=int, default=30)
    parser.add_argument(
        "--horssite-fraction",
        type=float,
        default=0.25,
        help="Fraction émissions évitées par hors-site (défaut 0.25 médiane CSTB)",
    )
    parser.add_argument(
        "--list-materials",
        action="store_true",
        help="Affiche la liste des material_id disponibles et quitte",
    )
    args = parser.parse_args()

    if args.list_materials:
        for m in list_materials():
            print(f"{m['id']:<40}  {m['name']}  [{m['category']}]")
        return 0

    materials = [parse_material(s) for s in args.material]
    report = compute_total(
        surface_m2=args.surface,
        classe_avant=args.avant,
        classe_apres=args.apres,
        materials=materials,
        kwh_avant_per_m2_an=args.kwh_avant,
        type_energie_chauffage=args.energie,
        horizon_years=args.horizon_years,
        horssite_fraction=args.horssite_fraction,
    )
    # ensure_ascii=True pour compat Windows cp1252 (les agents Anthropic ont UTF-8 par défaut)
    sys.stdout.write(json.dumps(report_to_json(report), indent=2, ensure_ascii=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
