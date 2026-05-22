"""ConX — tests Auth Supabase JWT (D-012).

Tests offline : pas de Supabase Cloud requis. On génère des JWT localement
avec le même secret que le backend.
"""

from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi import HTTPException

from app.auth import (
    decode_token,
    get_current_user,
    get_current_user_optional,
    require_role,
    verify_internal_token,
)

JWT_SECRET = "test-secret-conx-only-do-not-reuse-anywhere-prod"  # nosec — test only (≥32 bytes)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("INTERNAL_SHARED_TOKEN", "internal-token-xyz")


def _make_jwt(*, sub: str = "user-uuid-1", role: str | None = "architecte",
              email: str = "a@b.fr", expired: bool = False,
              aud: str = "authenticated") -> str:
    now = int(time.time())
    payload: dict = {
        "sub": sub,
        "email": email,
        "aud": aud,
        "iat": now - 10,
        "exp": now - 100 if expired else now + 3600,
    }
    if role is not None:
        payload["app_metadata"] = {"role": role}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------


def test_decode_token_valid() -> None:
    token = _make_jwt(role="architecte")
    user = decode_token(token)
    assert user.user_id == "user-uuid-1"
    assert user.email == "a@b.fr"
    assert user.role == "architecte"
    assert user.jwt == token


def test_decode_token_role_inconnu_devient_anonymous() -> None:
    token = _make_jwt(role="hacker")
    user = decode_token(token)
    assert user.role == "anonymous"


def test_decode_token_sans_role_devient_anonymous() -> None:
    token = _make_jwt(role=None)
    user = decode_token(token)
    assert user.role == "anonymous"


def test_decode_token_expire_raise_401() -> None:
    token = _make_jwt(expired=True)
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_token_audience_invalide_raise_401() -> None:
    token = _make_jwt(aud="wrong-aud")
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_token_signature_invalide_raise_401() -> None:
    token = jwt.encode({"sub": "u", "aud": "authenticated"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_token_sans_secret_raise_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        decode_token("anything")
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# get_current_user dépendance FastAPI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_sans_header_raise_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_header_malforme_raise_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Token xyz")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_bearer_valide() -> None:
    token = _make_jwt(role="bailleur")
    user = await get_current_user(authorization=f"Bearer {token}")
    assert user.role == "bailleur"


@pytest.mark.asyncio
async def test_get_current_user_optional_retourne_none_si_pas_de_header() -> None:
    assert await get_current_user_optional(authorization=None) is None


@pytest.mark.asyncio
async def test_get_current_user_optional_retourne_none_si_jwt_invalide() -> None:
    assert await get_current_user_optional(authorization="Bearer not-a-jwt") is None


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_role_ok() -> None:
    dep = require_role("collectivite", "bailleur")
    token = _make_jwt(role="bailleur")
    user = await get_current_user(authorization=f"Bearer {token}")
    result = await dep(user=user)
    assert result.role == "bailleur"


@pytest.mark.asyncio
async def test_require_role_refuse_role_different() -> None:
    dep = require_role("collectivite")
    token = _make_jwt(role="architecte")
    user = await get_current_user(authorization=f"Bearer {token}")
    with pytest.raises(HTTPException) as exc:
        await dep(user=user)
    assert exc.value.status_code == 403


def test_require_role_avec_role_inconnu_raise_value_error() -> None:
    with pytest.raises(ValueError):
        require_role("admin")  # 'admin' n'est pas un rôle ConX (D-004)


# ---------------------------------------------------------------------------
# verify_internal_token (Managed Agents bypass)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_internal_token_ok() -> None:
    await verify_internal_token(x_internal_token="internal-token-xyz")  # ne raise pas


@pytest.mark.asyncio
async def test_verify_internal_token_mauvais_token_raise_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_internal_token(x_internal_token="wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_internal_token_absent_raise_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_internal_token(x_internal_token=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_internal_token_sans_env_raise_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_SHARED_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        await verify_internal_token(x_internal_token="anything")
    assert exc.value.status_code == 503
