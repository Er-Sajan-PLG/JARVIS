"""Integration tests for the critical CI path: ci_bridge -> ci_gate -> statuses.

Sprint 2 left this as the one genuine testing gap
(`docs/SPRINT_1_2_COMPLETION.md`: "no end-to-end CI-bridge / n8n integration
test verified"). The unit suite already covers token resolution
(`tests/unit/test_ci_bridge_token.py`); what was never pinned is the *contract*
that matters operationally:

  1. A blocking gate failure must produce a ``failure`` status for its context.
  2. A reported-only gate failure must NOT turn its context red -- but it must
     still be visible in the description, so it can never be mistaken for a pass.
  3. Every gate must be mapped onto a published context, so no gate result can
     silently vanish between the gate run and the status payload.
  4. A publish that 403s must be reported as a publish failure rather than being
     announced as success. This is the exact incident
     that motivated the split (`publish_failed`) -- a run once concluded success
     while every status POST had failed.
  5. The JSON report produced by the gate must be consumed without loss.

These tests exercise the real functions in ``scripts/ci_bridge.py`` with a fake
GitHub transport. They do not hit the network and do not touch the repo state.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "ci_bridge.py"


def _load_bridge():
    """Import scripts/ci_bridge.py as a module without invoking main()."""
    spec = importlib.util.spec_from_file_location("ci_bridge_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_bridge_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _check(name: str, status: str, blocking: bool, summary: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "blocking": blocking,
        "summary": summary or f"{name} {status}",
    }


# ── 1. Blocking gate failure turns its context red ──────────────────────────


def test_blocking_gate_failure_marks_its_context_failed():
    bridge = _load_bridge()
    report = {
        "checks": [
            _check("ruff_ratchet", "pass", True),
            _check("pytest", "fail", True, "3 tests failed"),
        ]
    }

    buckets = bridge.aggregate(report)

    assert buckets["Lint & Typecheck"]["state"] == "success"
    assert buckets["Tests"]["state"] == "failure"
    assert buckets["Tests"]["blocking"] is True
    assert any("pytest" in f for f in buckets["Tests"]["blocking_failures"])


# ── 2. Reported-only failure must not go red, but must be visible ───────────


def test_reported_only_failure_is_not_blocking_but_is_visible():
    bridge = _load_bridge()
    report = {"checks": [_check("mypy", "fail", False, "494 errors")]}

    buckets = bridge.aggregate(report)
    bucket = buckets["Lint & Typecheck"]

    # mypy is RISK-005: reported only. It must never fail the context.
    assert bucket["state"] == "success"
    assert bucket["blocking_failures"] == []
    assert any("mypy" in f for f in bucket["reported_failures"])


def test_reported_only_failure_appears_in_published_description():
    bridge = _load_bridge()
    report = {"checks": [_check("coverage", "fail", False, "coverage 36% (floor 80%)")]}

    buckets = bridge.aggregate(report)
    published = bridge.publish_statuses("token", "deadbeef", buckets, dry=True)

    tests_ctx = next(r for r in published if r["context"] == "Tests")
    assert tests_ctx["state"] == "success"
    assert "reported-only" in tests_ctx["description"]


# ── 3. Every gate maps onto a published context (no silent loss) ────────────


def test_every_known_gate_maps_to_a_published_context():
    bridge = _load_bridge()
    known_gates = [
        "ruff_ratchet",
        "mypy",
        "semgrep",
        "pytest",
        "contract",
        "coverage",
        "gitleaks",
        "trufflehog",
        "bandit",
        "pip_audit",
        "trivy",
        "osv",
        "licenses",
        "sbom",
        "provenance",
        "checkov",
        "board",
        "compileall",
        "hadolint",
        "docker_build",
        "worktree",
        "commitlint",
        "mutation",
    ]

    for gate in known_gates:
        assert gate in bridge.CONTEXT_OF, f"gate {gate!r} has no published context"


def test_gate_failure_for_each_blocking_gate_produces_failure_status():
    """Every blocking gate must be able to turn its own context red."""
    bridge = _load_bridge()
    for gate, context in bridge.CONTEXT_OF.items():
        report = {"checks": [_check(gate, "fail", True)]}
        buckets = bridge.aggregate(report)
        assert (
            buckets[context]["state"] == "failure"
        ), f"blocking gate {gate!r} failed but context {context!r} stayed green"


# ── 4. Publish failure must not be reported as success ─────────────────────


def test_publish_403_is_detected_as_publish_failure(monkeypatch):
    bridge = _load_bridge()

    def fake_api(method, path, token, payload=None, timeout=60):
        return 403, {"message": "Resource not accessible by personal access token"}

    monkeypatch.setattr(bridge, "api", fake_api)

    buckets = bridge.aggregate({"checks": [_check("pytest", "pass", True)]})
    published = bridge.publish_statuses("bad-token", "deadbeef", buckets, dry=False)

    assert published, "expected at least one attempted publish"
    assert all(rec["posted"] is False for rec in published)
    assert all(rec["http"] == 403 for rec in published)
    assert all("error" in rec for rec in published)


def test_successful_publish_records_posted_true(monkeypatch):
    bridge = _load_bridge()

    def fake_api(method, path, token, payload=None, timeout=60):
        return 201, {"state": "success"}

    monkeypatch.setattr(bridge, "api", fake_api)

    buckets = bridge.aggregate({"checks": [_check("pytest", "pass", True)]})
    published = bridge.publish_statuses("good-token", "deadbeef", buckets, dry=False)

    assert published
    assert all(rec["posted"] is True for rec in published)
    assert all(rec["http"] == 201 for rec in published)


def test_dry_run_publishes_nothing(monkeypatch):
    bridge = _load_bridge()

    def explode(*args, **kwargs):  # pragma: no cover - must never be called
        raise AssertionError("dry run must not call the GitHub API")

    monkeypatch.setattr(bridge, "api", explode)

    buckets = bridge.aggregate({"checks": [_check("pytest", "pass", True)]})
    published = bridge.publish_statuses("token", "deadbeef", buckets, dry=True)

    assert published
    assert all(rec["posted"] is False for rec in published)


# ── 5. The gate's JSON report is consumed without loss ─────────────────────


def test_gate_json_report_is_parsed_and_annotated(monkeypatch, tmp_path):
    """run_gate must parse ci_gate's JSON and attach the merge-gate note."""
    bridge = _load_bridge()

    payload = {
        "sha": "abc123",
        "conclusion": "success",
        "checks": [_check("pytest", "pass", True)],
    }

    class FakeProc:
        returncode = 0
        stdout = json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(bridge, "merge_gate_ref", lambda pr: ("abc123", "origin/main", "merge ok"))
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **k: FakeProc())

    pr = bridge.PRInfo(number=1, head_sha="abc123", head_ref="feat/x", base_ref="main", title="t")
    report = bridge.run_gate(pr)

    assert report["conclusion"] == "success"
    assert report["checks"][0]["name"] == "pytest"
    assert report["merge_gate_note"] == "merge ok"


def test_gate_with_unparseable_output_becomes_error_not_success(monkeypatch):
    """A gate that prints garbage must never be read as a passing gate."""
    bridge = _load_bridge()

    class FakeProc:
        returncode = 1
        stdout = "not json at all"
        stderr = "boom"

    monkeypatch.setattr(bridge, "merge_gate_ref", lambda pr: ("abc123", "origin/main", "n"))
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **k: FakeProc())

    pr = bridge.PRInfo(number=1, head_sha="abc123", head_ref="feat/x", base_ref="main", title="t")
    report = bridge.run_gate(pr)

    assert report["conclusion"] == "error"
    assert report["checks"] == []
    assert "error" in report


# ── 6. Idempotency: state persists so a SHA is not re-gated ────────────────


def test_gate_state_round_trips(monkeypatch, tmp_path):
    bridge = _load_bridge()
    state_file = tmp_path / "ci_bridge_state.json"
    monkeypatch.setattr(bridge, "STATE_FILE", state_file)

    assert bridge.load_state() == {"gated": {}}

    bridge.save_state({"gated": {"abc123": {"conclusion": "success"}}})
    assert state_file.is_file()
    assert bridge.load_state()["gated"]["abc123"]["conclusion"] == "success"


def test_corrupt_gate_state_does_not_crash(monkeypatch, tmp_path):
    """A truncated state file must degrade to empty state, not raise."""
    bridge = _load_bridge()
    state_file = tmp_path / "ci_bridge_state.json"
    state_file.write_text("{ this is not json")
    monkeypatch.setattr(bridge, "STATE_FILE", state_file)

    assert bridge.load_state() == {"gated": {}}
