"""`--context` must partition the gate, not silently drop or duplicate a check.

Why this test exists
--------------------
The workflow runs one CI job per context, each calling `ci_gate.py --context X`
so that the split jobs and a whole-gate local run cannot disagree about what
"green" means. That property is only true if the contexts actually PARTITION the
default gate set:

  - a gate reachable from no context is a gate that no CI job ever runs
  - a gate reachable from two contexts runs twice, in two jobs, and a failure in
    it is attributed to whichever job happened to report first
  - a context that selects nothing produces a job that is green while checking
    nothing — the "skip looks like a pass" defect this repository has already
    paid for twice (`--require-tools`, `_missing_tool`)

So the assertions below are about the partition, not about a snapshot of gate
names: they hold for any gate added later, and fail the moment a new gate is
wired without a context.

The gate functions are replaced with stubs that record their own context. That
keeps the test about WIRING (which gates a context selects) rather than about
the behaviour of 29 scanners, and it exercises the real `run_gates` control
flow rather than matching source text.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import ci_gate  # noqa: E402

# Every gate function run_gates calls by default, with the context it declares.
# This mapping is what the test holds run_gates to; it is derived from the
# functions' own Check(...) context, so if a gate's context changes the test
# fails and the mapping must be updated deliberately.
GATE_FUNCTIONS = {
    "gate_ruff_ratchet": "Lint & Typecheck",
    "gate_mypy": "Lint & Typecheck",
    "gate_semgrep": "SAST",
    "gate_pytest": "Tests",
    "gate_contract": "Tests",
    "gate_gitleaks": "Security Scan",
    "gate_trufflehog": "Security Scan",
    "gate_bandit": "Security Scan",
    "gate_pip_audit": "Security Scan",
    "gate_trivy_fs": "Supply Chain",
    "gate_osv": "Supply Chain",
    "gate_licenses": "Supply Chain",
    "gate_sbom": "Supply Chain",
    "gate_provenance": "Supply Chain",
    "gate_action_pinning": "Supply Chain",
    "gate_checkov": "Supply Chain",
    "gate_board": "Virtual Board Governance",
    "gate_docs": "Virtual Board Governance",
    "gate_doc_types": "Virtual Board Governance",
    "gate_doc_coverage": "Virtual Board Governance",
    "gate_docs_layer2": "Virtual Board Governance",
    "gate_doc_facts": "Virtual Board Governance",
    "gate_compileall": "Build",
    "gate_hadolint": "Build",
    "gate_commitlint": "Conventional Commits",
}


@pytest.fixture
def stubbed_gate(monkeypatch, tmp_path):
    """Run the real run_gates control flow with stubbed scanners.

    Returns a callable: contexts -> set of gate function names that ran.
    """
    calls: list[str] = []

    def make_stub(fn_name: str, context: str):
        def stub(*_args, **_kwargs):
            calls.append(fn_name)
            return ci_gate.Check(fn_name, context, True, "pass", "stub")

        return stub

    for fn_name, context in GATE_FUNCTIONS.items():
        monkeypatch.setattr(ci_gate, fn_name, make_stub(fn_name, context))

    # Bypass the worktree: the gates are stubbed, so there is nothing to isolate.
    monkeypatch.setattr(ci_gate, "_prepare_worktree", lambda _sha: (tmp_path, None))
    monkeypatch.setattr(ci_gate, "_resolve_app", lambda _wt: str(tmp_path / "app"))
    monkeypatch.setattr(ci_gate, "_resolve_merge_base", lambda _wt, _base: "base")
    monkeypatch.setattr(ci_gate, "_teardown_worktree", lambda _wt: None)
    monkeypatch.setattr(ci_gate, "_persist_doc_facts", lambda _report: None)

    def run(contexts: set[str] | None) -> set[str]:
        calls.clear()
        ci_gate.run_gates("deadbeef", "origin/main", only=contexts)
        return set(calls)

    return run


def test_every_context_selects_at_least_one_gate(stubbed_gate):
    """A context that selects nothing is a job that is green while checking nothing."""
    for context in ci_gate.GATE_CONTEXTS:
        ran = stubbed_gate({context})
        assert ran, f"context {context!r} selects no gate — its CI job would be vacuous"


def test_contexts_partition_the_default_gate_set(stubbed_gate):
    """Every gate runs under exactly one context: no orphans, no duplicates."""
    all_gates = stubbed_gate(None)
    assert all_gates == set(GATE_FUNCTIONS), (
        "the default run and the declared gate list disagree — a gate was added "
        "or removed without updating the context wiring"
    )

    seen: dict[str, str] = {}
    for context in ci_gate.GATE_CONTEXTS:
        for gate in stubbed_gate({context}):
            assert gate not in seen, (
                f"{gate} is selected by both {seen[gate]!r} and {context!r} — "
                "it would run twice and be attributed to whichever job reported first"
            )
            seen[gate] = context

    assert set(seen) == all_gates, (
        f"gates reachable from no context (so no CI job runs them): "
        f"{sorted(all_gates - set(seen))}"
    )


def test_omitting_context_runs_the_whole_gate(stubbed_gate):
    """A local run must stay a superset of every CI job, not a subset."""
    whole = stubbed_gate(None)
    union = set()
    for context in ci_gate.GATE_CONTEXTS:
        union |= stubbed_gate({context})
    assert whole == union


def test_multiple_contexts_union(stubbed_gate):
    ran = stubbed_gate({"Build", "Conventional Commits"})
    assert ran == {"gate_compileall", "gate_hadolint", "gate_commitlint"}


def test_unknown_context_is_rejected_loudly():
    """A job-name typo must fail, not produce a silently vacuous green job."""
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "ci_gate.py"),
            "--sha",
            "HEAD",
            "--context",
            "Not A Real Context",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "unknown --context" in combined
    assert "Conventional Commits" in combined, "the error must list the valid names"


def test_out_creates_its_parent_directory(tmp_path, monkeypatch):
    """`--out` must not fail when its directory does not exist yet.

    Before the split this never mattered: every run included `gate_sbom`, which
    writes into `artifacts/` and therefore created the directory as a side
    effect. A context without `gate_sbom` -- Build, SAST, Conventional Commits --
    left the directory absent, and `--out` raised FileNotFoundError *after* the
    gates had already run. A green gate reported as a red job.

    Driven in-process rather than through a subprocess, deliberately. The first
    version of this test shelled out, and it passed standalone while failing
    inside the gate's own run: `ci_gate.py` resolves `PYTHON` from its own repo
    root, and when the gate runs pytest in its temporary worktree that path is
    `/tmp/jarvis-ci-gate/HEAD/.venv/bin/python`, which does not exist, so the
    child exited `FATAL` before reaching `--out`. A test that depends on which
    checkout it runs from asserts an environment property, not a code property --
    the exact defect class this repository has paid for repeatedly. Calling
    `main()` directly removes the dependency instead of accommodating it.
    """
    target = tmp_path / "does" / "not" / "exist" / "report.json"
    assert not target.parent.exists()

    # PYTHON must exist: main() refuses to run otherwise. Point it at the
    # interpreter actually running this test.
    monkeypatch.setattr(ci_gate, "PYTHON", Path(sys.executable))
    # Stub the gates so no worktree is needed; this is about main()'s exit path.
    monkeypatch.setattr(
        ci_gate,
        "run_gates",
        lambda *_a, **_k: ci_gate.GateReport(
            sha="deadbeef", base="origin/main", repo="test", started_at="now"
        ),
    )
    monkeypatch.setattr(sys, "argv", ["ci_gate.py", "--sha", "deadbeef", "--out", str(target)])

    ci_gate.main()

    assert target.is_file(), "--out did not create its parent directory"
    assert "conclusion" in target.read_text()
