"""Skill fdes-lookup — recherche dans la base FDES statique D-014."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
DEFAULT_FDES = SKILL_DIR / "references" / "fdes_static.json"


def load_fdes(path: Path = DEFAULT_FDES) -> dict:
    if not path.exists():
        # Fallback : repo root
        alt = SKILL_DIR.parent.parent / "data" / "fdes_static.json"
        if alt.exists():
            path = alt
        else:
            raise SystemExit(f"FDES non trouvée : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="FDES lookup ConX (D-014)")
    parser.add_argument("--by-id", help="Récupère par material_id")
    parser.add_argument(
        "--by-category",
        choices=[
            "biosource",
            "mineral",
            "metal",
            "verre",
            "synthetique",
            "menuiserie",
            "vitrage",
        ],
    )
    parser.add_argument("--search", help="Recherche libre dans name + notes")
    parser.add_argument(
        "--list", action="store_true", help="Liste tous les material_id"
    )
    args = parser.parse_args()

    fdes = load_fdes()
    materials = fdes["materials"]

    if args.list:
        for m in materials:
            print(f"{m['id']:<40}  {m['name']}")
        return 0

    if args.by_id:
        for m in materials:
            if m["id"] == args.by_id:
                sys.stdout.write(json.dumps(m, indent=2, ensure_ascii=True) + "\n")
                return 0
        print(f"Materiau introuvable : {args.by_id}", file=sys.stderr)
        return 1

    results = materials
    if args.by_category:
        results = [m for m in results if m["category"] == args.by_category]
    if args.search:
        q = args.search.lower()
        results = [
            m
            for m in results
            if q in m["name"].lower() or q in (m.get("notes") or "").lower()
        ]

    sys.stdout.write(
        json.dumps(
            {"count": len(results), "materials": results}, indent=2, ensure_ascii=True
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
