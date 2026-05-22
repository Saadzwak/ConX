"""ConX — client Supabase Cloud (D-011 + D-012).

Pattern important : le backend crée un nouveau client supabase-py **par
requête** en propageant le JWT utilisateur, afin que PostgREST (et donc la
Row Level Security côté Supabase) voie le bon `auth.uid()`.

Sans propagation du JWT, supabase-py utiliserait la clé `service_role` qui
bypasse la RLS — gros risque de fuite cross-utilisateur.

Module-level cache du `service_role` client est interdit ici : il aurait
auth.uid() = null et la RLS rejetterait les opérations sur `app.*`.

Usage (J12+) :

    @router.post("/api/agents/plan/start")
    async def start_plan(
        user: AuthUser = Depends(get_current_user),
        ...
    ):
        sb = supabase_for_user(user)
        sb.table("agent_sessions").insert({...}).execute()

Implémentation minimale — on évite d'instancier le SDK supabase-py si la
config n'est pas présente (tests offline). Voir B-002 (asyncio supabase-py).
"""

from __future__ import annotations

import logging
import os
from functools import cache
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from supabase import Client

    from .auth import AuthUser

logger = logging.getLogger("conx.supabase")


@cache
def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url or url.startswith("https://YOUR_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Cloud non configuré (SUPABASE_URL manquant).",
        )
    return url


@cache
def _supabase_anon_key() -> str:
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not key or key.startswith("eyJ..."):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Cloud non configuré (SUPABASE_ANON_KEY manquant).",
        )
    return key


def supabase_for_user(user: AuthUser) -> Client:
    """Crée un client supabase-py qui propage le JWT de l'utilisateur.

    PostgREST utilise ce JWT pour évaluer `auth.uid()` dans les policies RLS
    de `app.*`. Sans ça, les inserts/selects échouent avec une violation
    de policy.

    ⚠ Coût : on instancie un nouveau client par requête. Le SDK supabase-py
    n'a pas de mécanisme intégré pour "changer de JWT" sur un client existant,
    donc c'est la voie standard. Si performance critique en prod (B-002),
    envisager un client httpx direct vers PostgREST avec header `Authorization:
    Bearer <jwt>` propagé manuellement.
    """
    try:
        from supabase import create_client
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Module supabase non installé : {exc}",
        ) from exc

    # En mode dev-bypass (CONX_DEV_BYPASS_AUTH), l'AuthUser n'a pas de JWT —
    # on bascule sur le service_role pour permettre l'écriture côté Supabase.
    # ⚠ Bypass la RLS ; à activer uniquement en dev. Cf. auth.py.
    if not user.jwt:
        sr_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if sr_key:
            return create_client(_supabase_url(), sr_key)
    client = create_client(_supabase_url(), _supabase_anon_key())
    # Propager le JWT pour que PostgREST applique la RLS
    client.postgrest.auth(user.jwt)
    return client


def supabase_service_role() -> Client:
    """Client `service_role` — bypass RLS. À utiliser UNIQUEMENT pour les
    opérations admin internes (ex: création d'utilisateur, cleanup), JAMAIS
    sur le chemin chaud des requêtes utilisateur.
    """
    try:
        from supabase import create_client
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Module supabase non installé : {exc}",
        ) from exc

    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key or key.startswith("eyJ..."):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service_role non configuré.",
        )
    return create_client(_supabase_url(), key)


def reset_caches() -> None:
    """Pour les tests : vider les caches LRU `_supabase_url` / `_supabase_anon_key`."""
    _supabase_url.cache_clear()
    _supabase_anon_key.cache_clear()


# ---------------------------------------------------------------------------
# Mode dégradé pour les tests offline
# ---------------------------------------------------------------------------


def is_supabase_configured() -> bool:
    """Retourne True si SUPABASE_URL + SUPABASE_ANON_KEY sont des vraies valeurs."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    return bool(
        url
        and not url.startswith("https://YOUR_")
        and key
        and not key.startswith("eyJ...")
    )


def _empty_response() -> dict[str, Any]:
    """Réponse Supabase factice pour les chemins de test."""
    return {"data": [], "count": 0}
