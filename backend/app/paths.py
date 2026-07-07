"""ConX — résolution robuste des répertoires `config/` et `data/`.

Le layout diffère entre Docker et dev local :
  - Docker : le code est monté sur `/app` → `/app/config`, `/app/data`.
  - Dev    : `<repo>/backend/app/...` avec `config/` et `data/` à la racine du repo.

Un `parents[N]` fixe donne donc un chemin différent (et faux) selon le contexte —
c'est la cause des 8 tests carbone en échec + 2 erreurs de collection en conteneur
(cf. docs/AUDIT_2026-07-07.md). On résout ici par recherche de candidats + override
d'environnement (`CONX_CONFIG_DIR` / `CONX_DATA_DIR`), utilisable par le code
applicatif ET les tests.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve()  # <root>/app/paths.py


def _resolve_dir(env_var: str, dirname: str) -> Path:
    """Retourne le répertoire `dirname`, via override d'env sinon recherche.

    Candidats (premier existant gagné) :
      1. `<code_root>/<dir>`  → `/app/<dir>` en Docker
      2. `<repo>/<dir>`       → `<repo>/<dir>` en dev local
      3. `/app/<dir>`         → secours Docker absolu
    """
    override = os.environ.get(env_var, "").strip()
    if override:
        return Path(override)
    candidates = [
        _HERE.parent.parent / dirname,  # /app/<dir> (Docker)
        _HERE.parent.parent.parent / dirname,  # <repo>/<dir> (dev local)
        Path("/app") / dirname,  # secours Docker
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]  # défaut → message d'erreur clair en aval


CONFIG_DIR = _resolve_dir("CONX_CONFIG_DIR", "config")
DATA_DIR = _resolve_dir("CONX_DATA_DIR", "data")
