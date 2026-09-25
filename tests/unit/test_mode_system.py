"""Tests for the mode system facade (Migration Plan Step 3)."""

from __future__ import annotations

import pytest

from app.context.builder import ContextBuilder
from app.core import ModeManager
from app.domain import SessionState
from app.modes.production_mode import ProductionMode


def test_mode_manager_defaults_to_production() -> None:
    manager = ModeManager()

    assert manager.mode_name == "production"
    assert isinstance(manager.active_mode, ProductionMode)
    assert manager.active_mode.emoji == "⚡"


def test_set_mode_updates_state_and_logs_transition() -> None:
    manager = ModeManager()

    manager.set_mode("teacher")
    assert manager.mode_name == "teacher"
    manager.set_mode("maintenance")
    assert manager.mode_name == "maintenance"

    history = manager.history
    assert [entry["to"] for entry in history] == ["teacher", "maintenance"]
    assert history[0]["from"] == "production"
    assert all("at" in entry for entry in history)

    with pytest.raises(ValueError, match="Unknown mode"):
        manager.set_mode("nope")


def test_get_system_prompt_matches_todays_default() -> None:
    manager = ModeManager()
    expected = ContextBuilder().build_system_prompt(SessionState(session_id="default_session"))

    assert manager.get_system_prompt() == expected
    for mode_name in ("teacher", "maintenance", "evolution", "production"):
        manager.set_mode(mode_name)
        assert manager.get_system_prompt() == expected


def test_format_response_delegates_to_active_mode() -> None:
    manager = ModeManager()

    assert manager.format_response("hello") == "hello"
    manager.set_mode("teacher")
    assert manager.format_response("hello") == "hello"
