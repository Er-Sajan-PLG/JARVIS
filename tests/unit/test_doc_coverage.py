"""Tests for the doc coverage gate.

A single missing doc must fail the suite — that failure is what blocks the
pipeline (pre-push hook + CI). These tests pin the gate's collectors so the
gate itself cannot silently rot.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "check_doc_coverage", REPO_ROOT / "scripts" / "check_doc_coverage.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_coverage"] = mod
    spec.loader.exec_module(mod)
    return mod


gate = _load_gate()


class TestModuleCoverage:
    def test_sources_collected(self):
        sources = gate.collect_sources()
        assert len(sources) > 10

    def test_known_binding_passes(self):
        # app/main.py is bound by MOBILE_ACCESS.md; must not be flagged.
        assert "app/main.py" not in gate.check_module_coverage({"app/main.py"})

    def test_missing_binding_flagged(self):
        findings = gate.check_module_coverage(set())
        assert any("app/adapters/web/notify_routes.py" in f for f in findings)

    def test_full_tree_currently_covered(self):
        """The live tree must satisfy its own gate — no grandfathering."""
        assert gate.check_module_coverage(gate.collect_sources()) == []


class TestRouteCensus:
    def test_routes_collected_with_prefixes(self):
        routes = gate.collect_routes()
        assert "/api/chat" in routes
        assert "/api/v1/notify" in routes
        assert "/api/v1/voice/stt" in routes
        assert "/api/v1/push/vapid-public-key" in routes
        # Bare environ.get() must never appear as a route.
        assert not any(r.isupper() for r in routes)

    def test_full_tree_currently_covered(self):
        assert gate.check_route_census() == []


class TestEnvCensus:
    def test_env_vars_collected(self):
        names = gate.collect_env_vars()
        assert "JARVIS_API_KEY" in names
        assert "TELEGRAM_BOT_TOKEN" in names
        assert "PATH" not in names  # allowlisted internals

    def test_full_tree_currently_covered(self):
        assert gate.check_env_census() == []


class TestGateEntry:
    def test_run_all_clean(self):
        assert gate.run_all() == []
