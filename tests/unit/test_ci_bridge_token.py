"""Tests for scripts/ci_bridge.py token resolution (RISK-015 / ADR-012 residual).

The bug this guards against: ``load_token()`` scanned the ambient process env
BEFORE any file, and ``.ci-bridge.env`` (the systemd EnvironmentFile that holds
the dedicated, correctly-scoped ``JARVIS_CI_TOKEN``) was not in ``TOKEN_FILES``
at all. In any interactive shell that exports a dev PAT (``GITHUB_MCP_PAT`` —
lists PRs fine, 403s on POST /statuses), the dev token shadowed the publishing
token and every gate ran ``published=0/8`` while concluding success.

The fix: ``.ci-bridge.env`` is first in ``TOKEN_FILES``, and file-based tokens
are resolved BEFORE the ambient env. The App token still wins over both.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "ci_bridge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("ci_bridge_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["ci_bridge_under_test"] = module
    spec.loader.exec_module(module)
    return module


FAKE_CI_TOKEN = "github_pat_ci_publisher_0123456789abcdef0123456789abcdef"
FAKE_DEV_TOKEN = "github_pat_dev_only_0123456789abcdef0123456789abcdef"


def test_ci_bridge_env_token_beats_ambient_dev_pat(monkeypatch, tmp_path):
    """The dedicated CI token in .ci-bridge.env must beat an ambient dev PAT."""
    module = _load_module()

    bridge_env = tmp_path / ".ci-bridge.env"
    bridge_env.write_text(f"JARVIS_CI_TOKEN={FAKE_CI_TOKEN}\n")

    # Poison the ambient env with the dev PAT (the token that 403s on publish).
    monkeypatch.setenv("GITHUB_MCP_PAT", FAKE_DEV_TOKEN)
    monkeypatch.delenv("JARVIS_CI_TOKEN", raising=False)

    # Point TOKEN_FILES at only our tmp .ci-bridge.env so the test is hermetic.
    monkeypatch.setattr(module, "TOKEN_FILES", (bridge_env,))

    token, source = module.load_token()

    assert token == FAKE_CI_TOKEN
    assert str(bridge_env).endswith(".ci-bridge.env")
    assert "JARVIS_CI_TOKEN" in source


def test_ci_bridge_env_is_first_token_file():
    """``.ci-bridge.env`` must be the FIRST entry in TOKEN_FILES."""
    module = _load_module()
    assert module.TOKEN_FILES[0].name == ".ci-bridge.env"


def test_ambient_env_is_still_a_fallback(monkeypatch, tmp_path):
    """When no file has a token, the ambient env still resolves."""
    module = _load_module()
    monkeypatch.setattr(module, "TOKEN_FILES", (tmp_path / "nonexistent.env",))
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_DEV_TOKEN)
    monkeypatch.delenv("JARVIS_CI_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_PAT", raising=False)

    token, source = module.load_token()
    assert token == FAKE_DEV_TOKEN
    assert source == "env:GITHUB_TOKEN"


def test_placeholder_is_skipped_even_in_ci_bridge_env(monkeypatch, tmp_path):
    """A placeholder value in .ci-bridge.env is skipped, not returned."""
    module = _load_module()
    bridge_env = tmp_path / ".ci-bridge.env"
    bridge_env.write_text("JARVIS_CI_TOKEN=PLACEHOLDER_REPLACE_ME_0123456789\n")
    monkeypatch.setattr(module, "TOKEN_FILES", (bridge_env,))
    for var in module.TOKEN_VARS:
        monkeypatch.delenv(var, raising=False)
    # Neutralise the gh-CLI fallback so the only resolutions are the file and env.
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: module.subprocess.CompletedProcess([], 1, "", ""),
    )

    token, _ = module.load_token()
    assert token == ""
