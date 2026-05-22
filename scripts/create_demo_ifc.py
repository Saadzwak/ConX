"""ConX — Génère un fichier IFC de démo représentatif pour le pitch.

Le fichier produit contient :
- Une structure minimale valide IFC4 (Project, Site, Building, Storey).
- 12 murs (8 externes avec Pset_WallCommon.ThermalResistance OK, 4 internes).
- 4 portes (3 conformes RE2020 + PMR ≥ 0.90 m, **1 avec OverallWidth 0.82 m**
  pour déclencher la 1ère erreur PMR).
- 8 fenêtres (toutes conformes Uw ≤ 1.3 W/m²K).
- 3 spaces (séjour, chambre, salle d'eau).

Sortie : `docs/demo_assets/ifc/test_re2020_pmr_fail.ifc` + un PDF
preview `sample_ifc_report.pdf` (fallback démo si upload plante).
(Committé en repo plutôt que data/storage/ gitignoré pour que la démo
fonctionne sur un checkout frais.)

Usage :
    python scripts/create_demo_ifc.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "demo_assets" / "ifc"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("create_demo_ifc")


def _create_in_container() -> Path:
    """Le module ifcopenshell est lourd à installer côté Windows ; on délègue
    au container backend qui l'a déjà (cf. requirements.txt J13).

    Le container ne peut pas écrire dans `./docs/` (monté read-only), donc on
    génère dans `/app/data/storage/demo_assets/` (writable) puis on copie via
    `docker cp` vers `docs/demo_assets/ifc/` côté hôte.
    """
    import subprocess
    import shutil

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    container_staging_host = ROOT / "data" / "storage" / "demo_assets"
    container_staging_host.mkdir(parents=True, exist_ok=True)
    script_in_container = "/tmp/_create_ifc.py"

    # Script qui tourne DANS le container — utilise ifcopenshell pour générer
    payload = r'''
import ifcopenshell
import ifcopenshell.api
import uuid
import pathlib

OUT = "/app/data/storage/demo_assets/test_re2020_pmr_fail.ifc"
pathlib.Path("/app/data/storage/demo_assets").mkdir(parents=True, exist_ok=True)

f = ifcopenshell.api.run("project.create_file", version="IFC4")
proj = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject",
                            name="ConX Demo IFC")
units = ifcopenshell.api.run("unit.assign_unit", f)
ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
body = ifcopenshell.api.run(
    "context.add_context", f, context_type="Model",
    context_identifier="Body", target_view="MODEL_VIEW", parent=ctx,
)

# Hiérarchie minimale
site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite",
                            name="Wazemmes Site")
ifcopenshell.api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
building = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding",
                                name="Immeuble Wazemmes")
ifcopenshell.api.run("aggregate.assign_object", f, products=[building], relating_object=site)
storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey",
                              name="R+0 — RDC")
ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)

def assign(pset_name, elem, props):
    ifcopenshell.api.run("pset.edit_pset", f,
        pset=ifcopenshell.api.run("pset.add_pset", f, product=elem, name=pset_name),
        properties=props,
    )

# 12 walls
ext_walls = []
for i in range(8):
    w = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name=f"Mur ext {i+1}")
    ifcopenshell.api.run("spatial.assign_container", f, products=[w], relating_structure=storey)
    # Pset RE2020 conforme (R >= 3.7 m².K/W pour murs extérieurs)
    assign("Pset_WallCommon", w, {"IsExternal": True, "ThermalResistance": 4.2 + i*0.1})
    ext_walls.append(w)
for i in range(4):
    w = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name=f"Mur int {i+1}")
    ifcopenshell.api.run("spatial.assign_container", f, products=[w], relating_structure=storey)
    assign("Pset_WallCommon", w, {"IsExternal": False})

# 4 doors — 3 OK, 1 KO (0.82 m < 0.90 m PMR threshold)
door_specs = [
    ("Porte d entree principale", 0.95, 1.2, True),   # OK (RE2020 + PMR)
    ("Porte couloir", 0.92, 1.15, False),               # OK
    ("Porte sejour", 0.95, 1.15, False),                # OK
    ("Porte WC", 0.82, 1.2, False),                     # KO PMR (largeur)
]
for name, width, uw, ext in door_specs:
    d = f.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(),
        Name=name, OverallWidth=width, OverallHeight=2.10)
    ifcopenshell.api.run("spatial.assign_container", f, products=[d], relating_structure=storey)
    assign("Pset_DoorCommon", d, {"IsExternal": ext, "ThermalTransmittance": uw})

# 8 fenetres toutes RE2020 OK (Uw <= 1.3)
for i in range(8):
    w = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow", name=f"Fenetre {i+1}")
    ifcopenshell.api.run("spatial.assign_container", f, products=[w], relating_structure=storey)
    assign("Pset_WindowCommon", w, {"IsExternal": True, "ThermalTransmittance": 1.1 + i*0.02})

# 3 spaces (pour la fiche "summary") — utilise aggregate (IfcSpace est composant spatial)
for nom in ("Sejour", "Chambre 1", "Salle d eau"):
    s = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSpace", name=nom)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[s], relating_object=storey)

f.write(OUT)
print("Wrote " + OUT)
print("Schema: " + f.schema)
print("Walls: " + str(len(f.by_type("IfcWall"))))
print("Doors: " + str(len(f.by_type("IfcDoor"))))
print("Windows: " + str(len(f.by_type("IfcWindow"))))
print("Spaces: " + str(len(f.by_type("IfcSpace"))))
'''

    # Copier le script dans le container et l'exécuter (staging écrivable)
    tmp_script = container_staging_host / "_create_ifc.py"
    tmp_script.write_text(payload, encoding="utf-8")

    # Copier dans le container puis exec
    subprocess.check_call(["docker", "cp", str(tmp_script), "conx_backend:/tmp/_create_ifc.py"])
    out = subprocess.check_output(["docker", "exec", "conx_backend", "python", "/tmp/_create_ifc.py"],
                                  text=True)
    logger.info("%s", out.strip())
    tmp_script.unlink(missing_ok=True)

    # Le container a écrit dans data/storage/demo_assets (mount writable).
    # On copie vers docs/demo_assets/ifc/ (commited) pour la démo.
    staging_ifc = container_staging_host / "test_re2020_pmr_fail.ifc"
    if not staging_ifc.exists():
        raise RuntimeError(f"IFC file not generated at {staging_ifc}")
    final_ifc = OUT_DIR / "test_re2020_pmr_fail.ifc"
    shutil.copy2(staging_ifc, final_ifc)
    return final_ifc


def main() -> int:
    logger.info("Génération du fichier IFC de démo dans %s …", OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        path = _create_in_container()
    except Exception as exc:
        logger.error("Echec génération IFC : %s", exc)
        return 1

    size_kb = path.stat().st_size / 1024
    logger.info("✓ IFC créé : %s (%.1f KB)", path, size_kb)
    logger.info("À utiliser pendant la démo : drag-and-drop dans Mode Conformité IFC.")
    logger.info("Erreurs attendues : 1 porte (Porte WC, 0.82 m) déclenche PMR fail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
