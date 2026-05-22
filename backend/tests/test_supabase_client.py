"""ConX — tests J12 module supabase_client (offline)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import supabase_client


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    supabase_client.reset_caches()
    yield
    supabase_client.reset_caches()


def test_is_supabase_configured_avec_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://YOUR_PROJECT_REF.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "eyJ...")
    assert supabase_client.is_supabase_configured() is False


def test_is_supabase_configured_vide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert supabase_client.is_supabase_configured() is False


def test_is_supabase_configured_vrai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://realproject.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "eyJrealkeycontent")
    assert supabase_client.is_supabase_configured() is True


def test_supabase_url_placeholder_raise_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://YOUR_PROJECT_REF.supabase.co")
    with pytest.raises(HTTPException) as exc:
        supabase_client._supabase_url()
    assert exc.value.status_code == 503


def test_supabase_url_absent_raise_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(HTTPException) as exc:
        supabase_client._supabase_url()
    assert exc.value.status_code == 503


def test_supabase_url_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://realproject.supabase.co")
    assert supabase_client._supabase_url() == "https://realproject.supabase.co"


def test_supabase_anon_key_placeholder_raise_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_ANON_KEY", "eyJ...")
    with pytest.raises(HTTPException) as exc:
        supabase_client._supabase_anon_key()
    assert exc.value.status_code == 503


def test_supabase_anon_key_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_ANON_KEY", "eyJrealkeycontent_long_enough")
    assert supabase_client._supabase_anon_key() == "eyJrealkeycontent_long_enough"
