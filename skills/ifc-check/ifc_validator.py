"""Skill ifc-check — validation IFC + pré-vérification RE2020/PMR via IfcOpenShell.

Test critique 2026-05-22 : `pip install ifcopenshell` → 0.8.5 OK dans python:3.12-slim
vanilla. Pas de bascule HTTP backend nécessaire.

Périmètre MVP étroit et assumé (cf. SKILL.md §Limites) — ne remplace pas un BCT.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Seuils RE2020 / PMR (MVP — sous-ensemble)
RE2020_U_DOORS_WINDOWS_MAX = 1.3  # W/m².K
RE2020_R_WALLS_MIN = 3.7  # m².K/W
RE2020_R_TOITURE_MIN = 6.0
PMR_DOOR_WIDTH_MIN_M = 0.90
PMR_RAMP_SLOPE_MAX = 5.0  # %
PMR_CORRIDOR_WIDTH_MIN_M = 1.40


def safe_get_pset_value(elem, pset_name: str, prop_name: str):
    """Récupère une valeur d'un Pset. Retourne None si absent ou inaccessible."""
    try:
        import ifcopenshell.util.element as ifc_util

        psets = ifc_util.get_psets(elem)
        return psets.get(pset_name, {}).get(prop_name)
    except Exception:
        return None


def validate(ifc_path: Path) -> dict:
    """Charge l'IFC et exécute les contrôles."""
    try:
        import ifcopenshell
    except ImportError:
        return {
            "filename": ifc_path.name,
            "valid_syntax": False,
            "error": "ifcopenshell non installé dans l'environment.",
        }

    try:
        ifc = ifcopenshell.open(str(ifc_path))
    except Exception as e:
        return {
            "filename": ifc_path.name,
            "valid_syntax": False,
            "error": f"Parse IFC échoué : {type(e).__name__} : {str(e)[:200]}",
        }

    schema = ifc.schema  # "IFC2X3", "IFC4", "IFC4X3", …

    walls = ifc.by_type("IfcWall")
    doors = ifc.by_type("IfcDoor")
    windows = ifc.by_type("IfcWindow")
    stairs = ifc.by_type("IfcStair")
    ramps = ifc.by_type("IfcRamp")
    spaces = ifc.by_type("IfcSpace")

    # RE2020 checks
    re2020 = {}

    # U fenêtres/portes
    u_fails_doors = []
    for d in doors:
        u = safe_get_pset_value(d, "Pset_DoorCommon", "ThermalTransmittance")
        if u is not None and u > RE2020_U_DOORS_WINDOWS_MAX:
            u_fails_doors.append({"id": str(d.id()), "GlobalId": d.GlobalId, "Uw": u})
    re2020["uw_doors_below_1_3"] = {
        "pass": len(u_fails_doors) == 0,
        "threshold_max": RE2020_U_DOORS_WINDOWS_MAX,
        "n_checked": len(doors),
        "n_fail": len(u_fails_doors),
        "details": u_fails_doors[:10],
    }

    u_fails_windows = []
    for w in windows:
        u = safe_get_pset_value(w, "Pset_WindowCommon", "ThermalTransmittance")
        if u is not None and u > RE2020_U_DOORS_WINDOWS_MAX:
            u_fails_windows.append({"id": str(w.id()), "GlobalId": w.GlobalId, "Uw": u})
    re2020["uw_windows_below_1_3"] = {
        "pass": len(u_fails_windows) == 0,
        "threshold_max": RE2020_U_DOORS_WINDOWS_MAX,
        "n_checked": len(windows),
        "n_fail": len(u_fails_windows),
        "details": u_fails_windows[:10],
    }

    # R murs extérieurs
    r_fails_walls = []
    for wall in walls:
        is_external = safe_get_pset_value(wall, "Pset_WallCommon", "IsExternal")
        if not is_external:
            continue
        r = safe_get_pset_value(wall, "Pset_WallCommon", "ThermalResistance")
        if r is not None and r < RE2020_R_WALLS_MIN:
            r_fails_walls.append(
                {"id": str(wall.id()), "GlobalId": wall.GlobalId, "R": r}
            )
    re2020["r_walls_above_3_7"] = {
        "pass": len(r_fails_walls) == 0,
        "threshold_min": RE2020_R_WALLS_MIN,
        "n_checked_external": sum(
            1 for w in walls if safe_get_pset_value(w, "Pset_WallCommon", "IsExternal")
        ),
        "n_fail": len(r_fails_walls),
        "details": r_fails_walls[:10],
    }

    # PMR checks
    pmr = {}

    door_width_fails = []
    for d in doors:
        is_accessible = safe_get_pset_value(d, "Pset_DoorCommon", "IsExternal")
        # On vérifie sur toutes les portes (l'agent décidera lesquelles sont accessibles)
        width = (
            d.OverallWidth if hasattr(d, "OverallWidth") and d.OverallWidth else None
        )
        if width is None:
            continue
        if width < PMR_DOOR_WIDTH_MIN_M:
            door_width_fails.append(
                {
                    "id": str(d.id()),
                    "GlobalId": d.GlobalId,
                    "OverallWidth_m": float(width),
                    "is_external": bool(is_accessible),
                }
            )
    pmr["door_width_min_900mm"] = {
        "pass": len(door_width_fails) == 0,
        "threshold_min_m": PMR_DOOR_WIDTH_MIN_M,
        "n_checked": len(doors),
        "n_fail": len(door_width_fails),
        "details": door_width_fails[:10],
    }

    # Pente rampes — heuristique basique via Pset_RampCommon.RampSlope
    ramp_slope_fails = []
    for r in ramps:
        slope = safe_get_pset_value(r, "Pset_RampCommon", "Slope")
        if slope is None:
            continue
        # Convertir en % si en radians (heuristique : valeur < 1 = radians → tangente)
        if abs(slope) < 1.0:
            import math

            slope_pct = math.tan(slope) * 100
        else:
            slope_pct = float(slope)
        if slope_pct > PMR_RAMP_SLOPE_MAX:
            ramp_slope_fails.append(
                {
                    "id": str(r.id()),
                    "GlobalId": r.GlobalId,
                    "slope_pct": round(slope_pct, 2),
                }
            )
    pmr["ramp_slope_max_5pct"] = {
        "pass": len(ramp_slope_fails) == 0,
        "threshold_max_pct": PMR_RAMP_SLOPE_MAX,
        "n_checked": len(ramps),
        "n_fail": len(ramp_slope_fails),
        "details": ramp_slope_fails,
    }

    # Anomalies générales
    anomalies = []
    if len(spaces) == 0:
        anomalies.append("Aucune IfcSpace définie — impossible de calculer SHAB/SHON.")
    if len(walls) == 0:
        anomalies.append("Aucun IfcWall détecté.")
    if len(doors) == 0:
        anomalies.append("Aucune IfcDoor détectée.")

    return {
        "filename": ifc_path.name,
        "ifc_schema": schema,
        "valid_syntax": True,
        "n_entities": len(ifc.by_type("IfcRoot")),
        "summary": {
            "n_walls": len(walls),
            "n_doors": len(doors),
            "n_windows": len(windows),
            "n_stairs": len(stairs),
            "n_ramps": len(ramps),
            "n_spaces": len(spaces),
        },
        "re2020_checks": re2020,
        "pmr_checks": pmr,
        "anomalies": anomalies,
        "disclaimer": (
            "Pré-vérification ConX — ne remplace pas un bureau de contrôle agréé. "
            "Périmètre MVP étroit (10-15 contrôles sur ~200 que ferait un BCT)."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validation IFC + RE2020/PMR (skill ifc-check)"
    )
    parser.add_argument("ifc_path", help="Chemin vers le fichier .ifc")
    parser.add_argument("--output", help="Chemin JSON de sortie (sinon stdout)")
    args = parser.parse_args()

    p = Path(args.ifc_path)
    if not p.exists():
        print(f"Fichier introuvable : {p}", file=sys.stderr)
        return 1

    report = validate(p)
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    else:
        # ensure_ascii=True pour compat stdout cp1252 Windows
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0 if report.get("valid_syntax") else 2


if __name__ == "__main__":
    sys.exit(main())
