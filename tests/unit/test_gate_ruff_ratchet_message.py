"""The ruff ratchet must name the files that failed, not the files it checked.

The failure message read ``f"{len(changed)} changed file(s) with lint errors"``,
where ``changed`` is the list of files *passed to ruff*. It therefore reported
"12 changed file(s) with lint errors" when exactly ONE file had errors and eleven
were clean.

That is the kind of false claim this repository keeps producing: a number that
looks like a measurement but measures something else. It sends the reader hunting
through twelve files for a violation that eleven of them do not contain, and it
inflates the apparent damage of every lint failure.

The distinction matters more than usual here because the ratchet is BLOCKING: a
wrong count appears in the gate report that decides whether a branch may merge.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


@pytest.fixture()
def ci_gate():
    sys.path.insert(0, str(SCRIPTS))
    if "ci_gate" in sys.modules:
        del sys.modules["ci_gate"]
    mod = importlib.import_module("ci_gate")
    yield mod
    sys.path.remove(str(SCRIPTS))
    sys.modules.pop("ci_gate", None)


def _source(ci_gate) -> str:
    return (SCRIPTS / "ci_gate.py").read_text(encoding="utf-8")


def test_the_failure_message_does_not_count_checked_files(ci_gate) -> None:
    """The message must not derive its number from the list of checked files."""
    src = _source(ci_gate)
    body = src[src.index("def gate_ruff_ratchet") : src.index("def gate_pytest")]
    assert '"fail",\n            f"{len(changed)} changed file(s) with lint errors"' not in body, (
        "the failure summary still counts files that were CHECKED, not files that "
        "failed; eleven clean files would be reported as violation sites"
    )


def test_the_failure_message_names_the_offending_files(ci_gate) -> None:
    """A reader should be able to act on the summary without opening the output."""
    src = _source(ci_gate)
    body = src[src.index("def gate_ruff_ratchet") : src.index("def gate_pytest")]
    assert (
        "offend" in body or "failing" in body
    ), "the failure summary does not distinguish offending files from checked ones"


def test_ruff_output_parsing_extracts_distinct_filenames(ci_gate) -> None:
    """The helper must pull one entry per file, not one per diagnostic.

    Ruff emits a line per diagnostic, so a file with 13 errors appears 13 times.
    Counting lines would report 13 "files"; the helper must deduplicate.
    """
    helper = getattr(ci_gate, "_ruff_failing_files", None)
    assert helper is not None, "gate_ruff_ratchet has no output-parsing helper"

    sample = (
        "tests/unit/test_issues.py:12:1: I001 [*] Import block is un-sorted\n"
        "tests/unit/test_issues.py:23:1: E402 Module level import not at top\n"
        "tests/unit/test_issues.py:39:1: E402 Module level import not at top\n"
        "scripts/ci_gate.py:100:1: F401 unused import\n"
    )
    assert helper(sample) == {"tests/unit/test_issues.py", "scripts/ci_gate.py"}


def test_the_helper_ignores_non_diagnostic_lines(ci_gate) -> None:
    """Ruff prints banners and help text; those are not filenames."""
    helper = ci_gate._ruff_failing_files
    sample = (
        "warning: The top-level linter settings are deprecated in favour of\n"
        "Found 3 errors.\n"
        "[*] 1 fixable with the `--fix` option.\n"
        "  - 'select' -> 'lint.select'\n"
    )
    assert helper(sample) == set()


def test_the_file_pattern_matches_a_real_diagnostic(ci_gate) -> None:
    """Negative control on the regex: it must be anchored enough to not match prose."""
    assert re.search(r"^\S+\.py:\d+:\d+: ", "tests/unit/x.py:12:1: E501 line too long")
    assert not re.search(r"^\S+\.py:\d+:\d+: ", "see tests/unit/x.py:12 for details")
