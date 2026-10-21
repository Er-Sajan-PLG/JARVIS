"""Tests for the coverage gate's measurement, not for coverage itself.

``gate_coverage`` is the only gate that reports a *number* rather than a
pass/fail over a fixed property. That makes it the easiest one to let drift: an
unverified percentage in a docstring reads exactly like a verified one, and it is
never re-derived by anything.

It had drifted. The docstring claimed ``TOTAL 98%``; the gate's own command
reported **87%** statement-only (86% once branch measurement was added) when this
file was written. RISK-004 already carried the correct figure, so the register and
the code disagreed, and only the register was right.

It was also blind to branches. ``pytest --cov=app`` measures statements only, so
an ``if`` that is entered but never taken in the other direction is
indistinguishable from one that is fully exercised. Branch measurement is
opt-in via ``--cov-branch``.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_GATE = REPO_ROOT / "scripts" / "ci_gate.py"


def _gate_coverage_source() -> str:
    """The full source of ``gate_coverage``, extracted via AST.

    Sliced by node rather than matched with a regex so a comment elsewhere in the
    file cannot satisfy these tests, and so the checks survive reformatting.
    """
    tree = ast.parse(CI_GATE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "gate_coverage":
            return ast.get_source_segment(CI_GATE.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("gate_coverage is gone from scripts/ci_gate.py")


def test_the_gate_measures_branch_coverage() -> None:
    """``--cov-branch`` is present, so an untaken branch is visible.

    Without it, ``if flag:`` with only the true path exercised reports the same
    coverage as a fully exercised one. The audit raised this as F-TEST-001.
    """
    src = _gate_coverage_source()
    assert "--cov-branch" in src, (
        "gate_coverage does not pass --cov-branch, so it measures statements "
        "only and an untaken branch is invisible (F-TEST-001)."
    )


def test_the_gate_still_measures_line_coverage() -> None:
    """Adding branch mode must not remove the statement measurement."""
    assert "--cov=app" in _gate_coverage_source()


def test_the_docstring_does_not_claim_an_unverified_percentage() -> None:
    """Any percentage in the docstring must be attributable to a gate run.

    This does not check the number is *right* — it cannot, without running the
    suite, which this unit test must not do. It checks that the docstring states
    when and how it was measured, so a bare drifting figure fails. The stale claim
    this guards against read "measured 98% on 2026-09-13" while the live gate
    reported 87%.
    """
    src = _gate_coverage_source()
    docstring = ast.get_docstring(
        next(
            n
            for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name == "gate_coverage"
        )
    )
    assert docstring is not None
    if "%" not in docstring:
        return
    has_provenance = any(
        marker in docstring for marker in ("gate reports", "gate reported", "measured by")
    )
    assert has_provenance, (
        "gate_coverage's docstring quotes a percentage but does not say it was "
        "measured by running the gate. Add how the figure was obtained, or remove "
        "the number — an unverified percentage is indistinguishable from a "
        "verified one."
    )


def test_the_floor_is_still_enforced_against_the_measured_value() -> None:
    """The pass/fail verdict reads the parsed percentage, not a literal.

    A gate whose verdict is independent of its measurement always passes.
    """
    src = _gate_coverage_source()
    assert "pct >= 80" in src, "the 80% floor is no longer compared to the parsed figure"
