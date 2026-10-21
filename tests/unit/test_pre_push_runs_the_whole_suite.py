"""The hook that blocks a push must run the suites the gate runs.

``githooks/pre-push`` exits 1 on a test failure, so it is the mechanism that
actually stops a bad commit reaching the remote. Until 2026-09-30 it ran
``pytest tests/unit`` while its own comment called that "the full unit test
suite" -- 2011 of 2128 collected tests.

The 117 it skipped were ``tests/contract`` (50), ``tests/performance`` (48),
``tests/integration`` (12) and ``tests/sprint3`` (7). They run in **13.8 seconds**
and none require a database. So a commit that broke an API contract, a timing
assertion or ``test_legacy_server_import_blocked`` pushed cleanly and was caught
only later, by the CI gate, after the push had already landed.

This file reads the hook as text rather than executing it: running a pre-push
hook from a test would invoke the full suite and recurse.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_PUSH = REPO_ROOT / "githooks" / "pre-push"
CI_GATE = REPO_ROOT / "scripts" / "ci_gate.py"

# Directories the hook must collect from. tests/unit is implicit in tests/.
SUITES = ("tests/unit", "tests/contract", "tests/performance", "tests/integration", "tests/sprint3")


def _pytest_invocations(text: str) -> list[str]:
    """Every line that invokes pytest on a directory."""
    return [
        line.strip()
        for line in text.splitlines()
        if "pytest" in line and "tests/" in line and not line.strip().startswith("#")
    ]


def test_the_hook_exists_and_still_blocks_on_failure() -> None:
    """Negative control: a hook that cannot fail proves nothing below."""
    assert PRE_PUSH.is_file(), "githooks/pre-push is gone"
    text = PRE_PUSH.read_text(encoding="utf-8")
    assert "exit 1" in text, "the pre-push hook no longer refuses a push"


def test_the_suite_invocation_is_not_narrowed_to_a_subdirectory() -> None:
    """The full-suite run passes ``tests/``, not ``tests/<subdir>``.

    This is the regression itself. ``pytest tests/unit`` is a subset; the hook's
    comment claimed otherwise for an unknown period and the difference was 117
    tests that nothing local enforced.
    """
    text = PRE_PUSH.read_text(encoding="utf-8")
    # The bulk run is the invocation with -q and no explicit single test file.
    bulk = [line for line in _pytest_invocations(text) if "test_doc_coverage" not in line]
    assert bulk, "no bulk pytest invocation found in githooks/pre-push"

    narrowed = [
        line
        for line in bulk
        if re.search(r"\btests/[a-z0-9_]+\b", line) and not re.search(r"\btests/(?=\s|$|\")", line)
    ]
    assert not narrowed, (
        f"githooks/pre-push runs a subset of the suite: {narrowed}.\n"
        f"It exits 1 on failure, so anything it does not collect cannot block a "
        f"push. Use the whole tests/ tree, as scripts/ci_gate.py does."
    )


def test_the_hook_and_the_gate_collect_the_same_tree() -> None:
    """Both the hook and the gate must run ``tests/``.

    They are the two enforcement points, and AGENTS.md 4.3 records that
    enforcement here is process rather than platform. Two enforcement points that
    disagree about what to enforce is the gap this file exists to prevent.
    """
    hook = PRE_PUSH.read_text(encoding="utf-8")
    gate = CI_GATE.read_text(encoding="utf-8")
    assert '"tests/"' in gate or "'tests/'" in gate, "the gate no longer runs the whole tests/ tree"
    bulk = [line for line in _pytest_invocations(hook) if "test_doc_coverage" not in line]
    assert any(
        re.search(r"\btests/(?=\s|$|\")", line) for line in bulk
    ), f"the hook collects {bulk}, which is not the whole tests/ tree the gate runs"


def test_every_suite_directory_is_covered_by_the_hook() -> None:
    """Each test directory on disk must be reachable from the hook's run.

    Guards the next narrowing: adding ``tests/something_new`` and having it sit
    outside enforcement because the hook names directories individually.
    """
    on_disk = {
        f"tests/{p.name}"
        for p in (REPO_ROOT / "tests").iterdir()
        if p.is_dir() and not p.name.startswith((".", "__"))
    }
    assert on_disk, "no test directories found under tests/"
    text = PRE_PUSH.read_text(encoding="utf-8")
    bulk = " ".join(_pytest_invocations(text))
    runs_whole_tree = bool(re.search(r"\btests/(?=\s|$|\")", bulk))
    missing = sorted(on_disk - {s for s in SUITES if f" {s} " in f" {bulk} "})
    assert runs_whole_tree or not missing, (
        f"githooks/pre-push does not cover {missing}. Either run tests/ or name "
        f"every directory, but do not leave one unenforced."
    )
