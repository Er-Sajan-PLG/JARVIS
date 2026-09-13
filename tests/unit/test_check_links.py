"""Unit tests for scripts/check_links.py — external link probing.

These pin the design invariants that keep the link checker trustworthy:

1. **Placeholders are skipped** without a request — `example.com`, `localhost`,
   `127.0.0.1` are illustrative, not links a reader clicks.
2. **The host is probed, always.** A host allowlist (`ALLOW_HOSTS`) must never
   mean "do not check this URL". The old code returned `unverified` for any
   allowlisted host without sending a request at all, which let a 404 on
   github.com pass silently — the exact failure a link checker exists to catch.
3. **DNS failure is hard-dead for every URL**, including an API base. A hostname
   that does not resolve is dead whatever path follows it, so the API-base
   special case must not swallow it.
4. **A definite status (e.g. 404) on an allowlisted host is NOT downgraded.**
   Only a status plausibly consistent with bot-blocking (401/403/405/406/429)
   earns the `unverified` benefit of the doubt.

Only `check_links.py` is allowed to use the network, and these tests probe real
endpoints that are stable by design (`example.com` is skipped; a nonexistent
host always fails DNS; a real broken GitHub path returns 404).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_links.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_links"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cl():
    return _load()


# ── placeholders are illustrative, not links ─────────────────────────────────


def test_example_com_is_skipped(cl):
    v, _ = cl.probe("https://example.com/")
    assert v == "skipped"


def test_localhost_is_skipped(cl):
    v, _ = cl.probe("https://localhost:8000/docs")
    assert v == "skipped"


def test_ipv4_localhost_is_skipped(cl):
    v, _ = cl.probe("https://127.0.0.1:8000/docs")
    assert v == "skipped"


# ── the host is always probed ────────────────────────────────────────────────


def test_dead_path_on_allowed_host_is_probed_and_is_dead(cl):
    """D3 regression: github.com is allowlisted, but a dead path under it must
    still be probed and must come back 'dead' (a 404), not 'unverified'."""
    v, detail = cl.probe("https://github.com/some/dead-repo-name-xyz123")
    assert v == "dead", f"expected dead, got {v}: {detail}"


def test_real_github_url_is_ok(cl):
    """A known-good allowlisted host must reach 'ok'."""
    v, detail = cl.probe("https://github.com/")
    assert v == "ok", f"expected ok, got {v}: {detail}"


# ── DNS failure is hard-dead for all URLs ───────────────────────────────────


def test_nonexistent_hostname_is_dead(cl):
    v, detail = cl.probe("https://this-host-does-not-exist-xyz-abc-123.com/")
    assert v == "dead"
    assert "DNS" in detail


def test_nonexistent_hostname_with_api_base_is_dead(cl):
    """D3 regression: a dead hostname with an API-path suffix must NOT be masked
    by the API-base special case. The old code returned 'unverified' here."""
    v, detail = cl.probe("https://no-such-host-999999-xyz.com/api/v1beta")
    assert v == "dead", f"expected dead, got {v}: {detail}"


# ── API base on a LIVE host is unverified, not dead ──────────────────────────


def test_live_api_base_is_unverified_not_dead(cl):
    """A live host whose /v1 root 404s is 'unverified' (non-browsable), never
    'dead' — the host answered, so it is not dead."""
    v, detail = cl.probe("https://generativelanguage.googleapis.com/v1beta")
    assert v == "unverified"
    assert "API base" in detail


# ── a definite status on an allowlisted host is not downgraded ──────────────


def test_404_on_allowed_host_is_dead_not_unverified(cl):
    """A 404 is a definite answer (this URL does not exist), not a plausible bot
    block. It must not be downgraded merely because the host is familiar."""
    v, detail = cl.probe("https://github.com/this-org-does-not-exist-xyz/repo")
    assert v == "dead", f"expected dead, got {v}: {detail}"
