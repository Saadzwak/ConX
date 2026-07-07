"""ConX — tests J12 du module agents_client (offline, sans appel API).

On vérifie :
- `_load_agent_ids` lit correctement agents.lock.yaml.
- `get_agent_id` retourne l'ID ou lève 503.
- `serialize_event_for_sse` produit le format attendu.
- `keepalive_event` est un commentaire SSE valide.

Tests qui appelleraient `client.beta.agents.*` sont SKIP — ils nécessitent
ANTHROPIC_API_KEY + un agent réellement créé (B-001/B-009).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from app import agents_client


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    agents_client.reset_cache()
    yield
    agents_client.reset_cache()


def _write_lock(tmp_path: Path, content: dict) -> Path:
    lock = tmp_path / "agents.lock.yaml"
    lock.write_text(yaml.dump(content), encoding="utf-8")
    return lock


def test_load_agent_ids_absent_raise_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agents_client, "LOCK_YAML", tmp_path / "absent.yaml")
    with pytest.raises(HTTPException) as exc:
        agents_client._load_agent_ids()
    assert exc.value.status_code == 503


def test_load_agent_ids_vide_raise_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = _write_lock(tmp_path, {})
    monkeypatch.setattr(agents_client, "LOCK_YAML", lock)
    with pytest.raises(HTTPException) as exc:
        agents_client._load_agent_ids()
    assert exc.value.status_code == 503


def test_load_agent_ids_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = _write_lock(
        tmp_path,
        {"agents": {"conx-selection": "agt_aaa", "conx-plan": "agt_bbb", "conx-conformite": "agt_ccc"}},
    )
    monkeypatch.setattr(agents_client, "LOCK_YAML", lock)
    ids = agents_client._load_agent_ids()
    assert ids["conx-plan"] == "agt_bbb"
    assert ids["conx-selection"] == "agt_aaa"


def test_get_agent_id_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = _write_lock(tmp_path, {"agents": {"conx-plan": "agt_42"}})
    monkeypatch.setattr(agents_client, "LOCK_YAML", lock)
    assert agents_client.get_agent_id("conx-plan") == "agt_42"


def test_get_agent_id_inconnu_raise_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = _write_lock(tmp_path, {"agents": {"conx-plan": "agt_42"}})
    monkeypatch.setattr(agents_client, "LOCK_YAML", lock)
    with pytest.raises(HTTPException) as exc:
        agents_client.get_agent_id("conx-inconnu")
    assert exc.value.status_code == 503


def test_serialize_event_for_sse_format() -> None:
    raw = agents_client.serialize_event_for_sse({"type": "agent_message", "id": "evt_1"})
    text = raw.decode("utf-8")
    assert text.startswith("data: ")
    assert text.endswith("\n\n")
    payload = json.loads(text[len("data: ") : -2])
    assert payload["type"] == "agent_message"
    assert payload["id"] == "evt_1"


def test_serialize_event_for_sse_unicode_french() -> None:
    """Vérifie que les caractères accentués ne sont pas \\uXXXX-encodés
    (ensure_ascii=False)."""
    raw = agents_client.serialize_event_for_sse({"content": "Bâtiment résidentiel"})
    text = raw.decode("utf-8")
    assert "Bâtiment résidentiel" in text


def test_keepalive_event_format() -> None:
    raw = agents_client.keepalive_event()
    text = raw.decode("utf-8")
    # SSE comment lines start with ':'
    assert text.startswith(": ")
    assert text.endswith("\n\n")


def test_beta_header_contains_managed_agents() -> None:
    assert "managed-agents-2026-04-01" in agents_client.BETA_HEADER
    assert "skills-2025-10-02" in agents_client.BETA_HEADER
    assert "files-api-2025-04-14" in agents_client.BETA_HEADER


def test_event_to_dict_minimal_object() -> None:
    """Convertit un event-like object minimal en dict."""

    class FakeEvent:
        id = "evt_1"
        type = "agent_message"
        role = "agent"
        content = "Voici le plan."
        created_at = None

    d = agents_client._event_to_dict(FakeEvent())
    assert d["id"] == "evt_1"
    assert d["type"] == "agent_message"
    assert d["role"] == "agent"
    assert d["content"] == "Voici le plan."
    assert d["created_at"] is None
