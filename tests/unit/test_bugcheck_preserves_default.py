"""The bug-check script must not clobber a default the owner changed.

Regression: ``scripts/check_reported_bugs.py`` snapshotted the default model at
start and wrote that snapshot back at the end, unconditionally. The owner's
NVIDIA default was reverted twice by a script run. The fix is to restore only
when the live value is still what the script itself set.

These tests exercise the decision logic directly, without running the script,
so they cannot themselves mutate the owner's default.
"""

from __future__ import annotations


class FakeDefault:
    """The smallest thing that behaves like the settings default."""

    def __init__(self, provider: str, model: str) -> None:
        self.current = {"provider": provider, "model": model}

    def get(self) -> dict:
        return dict(self.current)

    def set(self, provider: str, model: str) -> None:
        self.current = {"provider": provider, "model": model}


def restore_decision(
    *,
    original: dict | None,
    last_set_by_script: dict | None,
    live: dict | None,
) -> str:
    """Mirror of the restore branch in check_reported_bugs.py.

    Returns one of: "no-original", "left-alone", "restored".
    """
    if not original:
        return "no-original"
    # Someone changed it after we did -> their value wins, leave it.
    if last_set_by_script and live != last_set_by_script:
        return "left-alone"
    # We never touched it -> nothing to undo.
    if not last_set_by_script:
        return "left-alone"
    return "restored"


def test_owner_change_mid_run_is_not_clobbered() -> None:
    """The script set a test default; owner set NVIDIA; NVIDIA must survive."""
    assert (
        restore_decision(
            original={"provider": "openrouter", "model": "x-ai/grok-4.20-multi-agent"},
            last_set_by_script={"provider": "openrouter", "model": "openrouter/auto"},
            live={"provider": "nvidia", "model": "nvidia/nemotron-3-super-120b-a12b"},
        )
        == "left-alone"
    )


def test_script_own_value_is_rolled_back() -> None:
    """Nothing changed since the script wrote -> safe to restore the original."""
    assert (
        restore_decision(
            original={"provider": "openrouter", "model": "x-ai/grok-4.20-multi-agent"},
            last_set_by_script={"provider": "openrouter", "model": "openrouter/auto"},
            live={"provider": "openrouter", "model": "openrouter/auto"},
        )
        == "restored"
    )


def test_untouched_default_is_left_alone() -> None:
    assert (
        restore_decision(
            original={"provider": "nvidia", "model": "nvidia/nemotron-3-super-120b-a12b"},
            last_set_by_script=None,
            live={"provider": "nvidia", "model": "nvidia/nemotron-3-super-120b-a12b"},
        )
        == "left-alone"
    )


def test_no_original_default_does_nothing() -> None:
    assert (
        restore_decision(
            original=None,
            last_set_by_script={"provider": "openrouter", "model": "openrouter/auto"},
            live={"provider": "openrouter", "model": "openrouter/auto"},
        )
        == "no-original"
    )


def test_real_script_has_the_guard() -> None:
    """The production script must actually contain the guard, not just tests."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "check_reported_bugs.py"
    ).read_text()
    assert "DEFAULT_SET_BY_SCRIPT" in src, "script no longer records what it set"
    assert "left untouched" in src, (
        "script appears to restore unconditionally again — it must skip the "
        "restore when the live default is not the one the script set"
    )
    assert 'call("POST", "/api/settings/default"' in src
