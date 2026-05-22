"""ConX — vérification JWT Supabase (D-012).

Le backend FastAPI vérifie les JWT Supabase **localement** en HS256 avec le
secret partagé `SUPABASE_JWT_SECRET`. Pas de round-trip réseau dans le chemin
auth — performance + simplicité (cf. DECISIONS.md D-012).

Workflow :
  1. Frontend obtient un JWT via Supabase Auth (login email/password ou OAuth).
  2. Frontend envoie `Authorization: Bearer <jwt>` au backend.
  3. `get_current_user` décode + vérifie signature + exp + aud.
  4. La route reçoit un `AuthUser` avec `user_id`, `role`, `email`, `jwt`.
  5. Si la route doit appeler Supabase Cloud, elle crée un `supabase-py` client
     PER REQUEST en propageant `jwt` afin que la RLS s'applique correctement.

Rôles (D-004) : `collectivite`, `bailleur`, `architecte`, `entreprise`.
Le rôle est lu depuis le claim `app_metadata.role` (défaut Supabase).

Bypass interne : le secret `INTERNAL_SHARED_TOKEN` permet aux Managed Agents
d'appeler `/api/internal/*` sans JWT utilisateur (cf. D-013 — ngrok + agent
Sélection). Le token n'est jamais exposé au frontend.
"""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

logger = logging.getLogger("conx.auth")

ALLOWED_ROLES = {"collectivite", "bailleur", "architecte", "entreprise"}
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class AuthUser:
    user_id: str  # sub (UUID Supabase auth.users.id)
    email: str | None
    role: str  # un des ALLOWED_ROLES, ou "anonymous" si non défini
    jwt: str  # token brut, à propager à supabase-py pour la RLS


def _get_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth non configurée : SUPABASE_JWT_SECRET manquant.",
        )
    return secret


def decode_token(token: str) -> AuthUser:
    """Décode + valide un JWT Supabase. Lève 401 si invalide.

    Vérifie : signature HS256, exp, iss (optionnel), aud='authenticated'
    (par défaut Supabase).
    """
    secret = _get_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            audience="authenticated",
            # Supabase n'impose pas de 'iss' strict — on laisse défaut.
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT audience invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        # PyInvalidSignatureError, DecodeError, etc.
        logger.warning("JWT rejeté : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT sans claim sub.",
        )

    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        email = None

    app_meta = payload.get("app_metadata") or {}
    role = app_meta.get("role") if isinstance(app_meta, dict) else None
    if role not in ALLOWED_ROLES:
        # Pas de rôle valide → on laisse "anonymous", les endpoints peuvent
        # filtrer via require_role().
        role = "anonymous"

    return AuthUser(user_id=sub, email=email, role=role, jwt=token)


# Constantes pour le bypass dev (cf. get_current_user)
_DEV_BYPASS_USER_ID = "00000000-0000-0000-0000-0000000000de"
_DEV_BYPASS_EMAIL = "dev@conx.local"


def _dev_bypass_enabled() -> bool:
    """Vrai si on doit accepter un fake user en dev.

    Activé via `CONX_DEV_BYPASS_AUTH=1`. À ne JAMAIS activer en prod.
    Utilité : permettre au frontend de fonctionner sans Supabase Auth (utile
    tant que la migration `app` schema n'est pas appliquée). Cf. BLOCKERS SUP.
    """
    return os.environ.get("CONX_DEV_BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes"}


def _dev_bypass_user(role: str = "architecte") -> AuthUser:
    """Construit un AuthUser fictif pour le mode dev bypass."""
    return AuthUser(
        user_id=_DEV_BYPASS_USER_ID,
        email=_DEV_BYPASS_EMAIL,
        role=role if role in ALLOWED_ROLES else "architecte",
        jwt="",  # pas de vrai JWT — les routes qui font supabase-py avec jwt
        # devront tolérer cet état (chemin dev uniquement, RLS désactivée
        # côté Supabase tant que migration pas appliquée).
    )


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    """Dépendance FastAPI : extrait + valide le JWT depuis le header.

    Retourne un `AuthUser`. Lève 401 si absent ou invalide.

    Mode dev bypass : si `CONX_DEV_BYPASS_AUTH=1`, accepte les requêtes sans
    JWT et retourne un user fictif (UUID `00000000-0000-0000-0000-0000000000de`).
    À ne JAMAIS activer en prod.
    """
    if not authorization:
        if _dev_bypass_enabled():
            logger.debug("Dev bypass auth actif — user fictif retourné.")
            return _dev_bypass_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        if _dev_bypass_enabled():
            return _dev_bypass_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization mal formé (attendu : 'Bearer <jwt>').",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(parts[1])


async def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser | None:
    """Variante : retourne None si pas d'auth (endpoints publics avec niveau enrichi)."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization=authorization)
    except HTTPException:
        return None


def require_role(*allowed: str):
    """Factory de dépendance : check que le rôle est dans `allowed`.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("collectivite"))])
    """
    allowed_set = set(allowed)
    if not allowed_set.issubset(ALLOWED_ROLES):
        raise ValueError(
            f"Rôles inconnus passés à require_role: {allowed_set - ALLOWED_ROLES}"
        )

    async def _check(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {sorted(allowed_set)}. Rôle actuel : {user.role}.",
            )
        return user

    return _check


# ----------------------------------------------------------------------------
# Bypass interne pour Managed Agents (D-013)
# ----------------------------------------------------------------------------


async def verify_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """Vérifie le header X-Internal-Token contre INTERNAL_SHARED_TOKEN.

    Utilisé sur `/api/internal/*` appelés par les agents Anthropic via ngrok.
    Pas d'utilisateur associé — c'est un token de service.
    """
    expected = os.environ.get("INTERNAL_SHARED_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Endpoint interne non configuré (INTERNAL_SHARED_TOKEN manquant).",
        )
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Internal-Token invalide.",
        )
