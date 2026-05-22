"""ConX — tests fallback replay-previous-plan (B-001).

Vérifie que `_send_with_replay_fallback` :
- envoie directement quand status = idle/working,
- crée une nouvelle session + injecte le plan précédent quand status = terminated.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.auth import AuthUser
from app.routers.agents import (
    _build_replay_prompt,
    _send_with_replay_fallback,
)


@pytest.fixture
def fake_user() -> AuthUser:
    return AuthUser(
        user_id="00000000-0000-0000-0000-0000000000de",
        email="dev@conx.local",
        role="architecte",
        jwt="",
    )


@pytest.mark.asyncio
async def test_replay_nominal_idle_envoie_direct(fake_user: AuthUser) -> None:
    """Status idle → on n'engage pas le fallback, on envoie directement."""
    with (
        patch("app.routers.agents.retrieve_session", return_value={"status": "idle"}),
        patch("app.routers.agents.send_user_message") as mock_send,
        patch("app.routers.agents.create_session") as mock_create,
        patch("app.routers.agents.is_supabase_configured", return_value=False),
    ):
        sid, replayed, prev = await _send_with_replay_fallback(
            fake_user, "sesn_original_42", "Et plutôt en chanvre ?"
        )
    assert sid == "sesn_original_42"
    assert replayed is False
    assert prev is None
    mock_send.assert_called_once_with("sesn_original_42", "Et plutôt en chanvre ?")
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_replay_session_terminated_recreates_with_context(
    fake_user: AuthUser,
) -> None:
    """Status terminated → nouvelle session + injection plan précédent."""
    fake_plan = {
        "version": 1,
        "strategie": "ITE chanvre 200 mm",
        "materiaux": [{"nom": "Béton de chanvre Tradical", "fdes": "INIES-12345"}],
        "carbon_t_total": -517,
    }

    # Stub supabase pour fetch_last_plan + insert
    class _FakeQuery:
        def __init__(self, data: list[dict[str, Any]]):
            self.data = data
            self._inserted: list[dict[str, Any]] = []

        def select(self, *_a, **_k):
            return self
        def eq(self, *_a, **_k):
            return self
        def order(self, *_a, **_k):
            return self
        def limit(self, *_a, **_k):
            return self
        def insert(self, row):
            self._inserted.append(row)
            return self
        def execute(self):
            return self

    fake_qb = _FakeQuery([{"building_id": "bdnb-bg-TEST", "plan_json": fake_plan, "version": 1}])

    class _FakeSb:
        def schema(self, _name):
            return self
        def table(self, _name):
            return fake_qb

    with (
        patch(
            "app.routers.agents.retrieve_session",
            return_value={"status": "terminated"},
        ),
        patch(
            "app.routers.agents.create_session",
            return_value={"session_id": "sesn_new_99", "status": "idle"},
        ) as mock_create,
        patch("app.routers.agents.send_user_message") as mock_send,
        patch("app.routers.agents.is_supabase_configured", return_value=True),
        patch("app.routers.agents.supabase_for_user", return_value=_FakeSb()),
    ):
        sid, replayed, prev = await _send_with_replay_fallback(
            fake_user, "sesn_expired_42", "Et plutôt en bois CLT ?"
        )

    assert replayed is True
    assert sid == "sesn_new_99"  # nouvelle session
    assert prev == "sesn_expired_42"
    mock_create.assert_called_once_with("conx-plan")
    # Vérifie qu'on a bien envoyé un user_message sur la NOUVELLE session avec
    # le prompt contenant le plan précédent et la nouvelle demande.
    mock_send.assert_called_once()
    args, _kwargs = mock_send.call_args
    assert args[0] == "sesn_new_99"
    payload = args[1]
    assert "Et plutôt en bois CLT ?" in payload
    assert "ITE chanvre 200 mm" in payload
    assert "INIES-12345" in payload
    # Et qu'on a inséré la nouvelle session_id dans Supabase
    inserted_rows = fake_qb._inserted
    assert any(r.get("session_id") == "sesn_new_99" for r in inserted_rows)


@pytest.mark.asyncio
async def test_replay_session_terminated_sans_plan_stocke(fake_user: AuthUser) -> None:
    """Status terminated MAIS pas de plan stocké → on relance from-scratch
    (le prompt contient une note explicite)."""

    class _FakeQuery:
        def select(self, *_a, **_k): return self
        def eq(self, *_a, **_k): return self
        def order(self, *_a, **_k): return self
        def limit(self, *_a, **_k): return self
        def insert(self, row): return self
        def execute(self):
            class R:
                data = []
            return R()

    class _FakeSb:
        def schema(self, _name): return self
        def table(self, _name): return _FakeQuery()

    with (
        patch("app.routers.agents.retrieve_session", return_value={"status": "terminated"}),
        patch(
            "app.routers.agents.create_session",
            return_value={"session_id": "sesn_recovered", "status": "idle"},
        ),
        patch("app.routers.agents.send_user_message") as mock_send,
        patch("app.routers.agents.is_supabase_configured", return_value=True),
        patch("app.routers.agents.supabase_for_user", return_value=_FakeSb()),
    ):
        sid, replayed, prev = await _send_with_replay_fallback(
            fake_user, "sesn_orphan", "Ajoute une isolation toiture"
        )

    assert sid == "sesn_recovered"
    assert replayed is True
    assert prev == "sesn_orphan"
    # Le prompt contient la note from-scratch
    payload = mock_send.call_args.args[1]
    assert "Pas de plan v1 stocké" in payload
    assert "Ajoute une isolation toiture" in payload


@pytest.mark.asyncio
async def test_replay_retrieve_session_exception_assumed_terminated(
    fake_user: AuthUser,
) -> None:
    """Si retrieve_session lève (ex: 404), on assume terminated → fallback."""

    class _FakeQuery:
        def select(self, *_a, **_k): return self
        def eq(self, *_a, **_k): return self
        def order(self, *_a, **_k): return self
        def limit(self, *_a, **_k): return self
        def insert(self, row): return self
        def execute(self):
            class R:
                data = []
            return R()

    class _FakeSb:
        def schema(self, _name): return self
        def table(self, _name): return _FakeQuery()

    with (
        patch(
            "app.routers.agents.retrieve_session",
            side_effect=RuntimeError("404 Session not found"),
        ),
        patch(
            "app.routers.agents.create_session",
            return_value={"session_id": "sesn_after_404", "status": "idle"},
        ),
        patch("app.routers.agents.send_user_message"),
        patch("app.routers.agents.is_supabase_configured", return_value=True),
        patch("app.routers.agents.supabase_for_user", return_value=_FakeSb()),
    ):
        sid, replayed, _ = await _send_with_replay_fallback(
            fake_user, "sesn_unknown", "Continue"
        )
    assert replayed is True
    assert sid == "sesn_after_404"


def test_build_replay_prompt_format() -> None:
    plan = {"strategie": "ITE chanvre"}
    out = _build_replay_prompt(plan, "Continue plus loin")
    assert "Contexte — plan précédent" in out
    assert "ITE chanvre" in out
    assert "Continue plus loin" in out
    assert "Régénère un plan COMPLET" in out
