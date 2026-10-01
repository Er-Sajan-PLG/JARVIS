"""Every third-party Action must be pinned to a commit SHA, and the gate must say so.

`uses: actions/checkout@v7` names a **mutable tag**. Whoever can move that tag runs
arbitrary code in this repository's CI — and since `ci-gate.yml` requests
`id-token: write` for keyless provenance, that code can mint OIDC identities too.
OpenSSF Scorecard calls this Pinned-Dependencies; the repo's own audit reported it
as SUP-010 against 18 occurrences, then recommended a script that had never been
written.

`scripts/pin-actions.mjs` now pins them, but a one-time pin decays: the next
workflow added with `@v7` reopens the hole silently. This gate is the ratchet. It
is pure Python rather than a call into node, so it still runs if node is absent —
a check that disappears with its toolchain is not a check.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


@pytest.fixture()
def ci_gate():
    sys.path.insert(0, str(SCRIPTS))
    if "ci_gate" in sys.modules:
        del sys.modules["ci_gate"]
    mod = importlib.import_module("ci_gate")
    yield mod
    sys.path.remove(str(SCRIPTS))
    sys.modules.pop("ci_gate", None)


def _worktree(tmp_path: Path, workflow_body: str) -> Path:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "test.yml").write_text(workflow_body)
    return tmp_path


def test_an_unpinned_action_is_a_blocking_failure(ci_gate, tmp_path) -> None:
    tree = _worktree(tmp_path, "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v7\n")
    check = ci_gate.gate_action_pinning(tree)
    assert check.status == "fail"
    assert check.blocking
    assert "checkout@v7" in (check.summary + check.output)


def test_a_pinned_action_passes(ci_gate, tmp_path) -> None:
    tree = _worktree(
        tmp_path,
        f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{SHA} # v7\n",
    )
    check = ci_gate.gate_action_pinning(tree)
    assert check.status == "pass", check.summary


def test_a_local_action_is_not_pinnable(ci_gate, tmp_path) -> None:
    """`./.github/actions/x` is this repo's own code, pinned by the commit."""
    body = "jobs:\n  a:\n    steps:\n      - uses: ./.github/actions/setup-env\n"
    tree = _worktree(tmp_path, body)
    check = ci_gate.gate_action_pinning(tree)
    assert check.status == "pass", check.summary


def test_a_short_sha_is_not_enough(ci_gate, tmp_path) -> None:
    """A 7-char SHA is still ambiguous; only a full 40-hex digest pins anything."""
    tree = _worktree(tmp_path, "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@3d3c42e\n")
    check = ci_gate.gate_action_pinning(tree)
    assert check.status == "fail"


def test_every_violation_is_listed_not_just_the_first(ci_gate, tmp_path) -> None:
    """One report should let the author fix all of them in one pass."""
    body = (
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - uses: actions/checkout@v7\n"
        "      - uses: actions/setup-python@v7\n"
    )
    check = ci_gate.gate_action_pinning(_worktree(tmp_path, body))
    assert check.status == "fail"
    assert "checkout@v7" in check.output
    assert "setup-python@v7" in check.output


def test_the_real_repository_is_fully_pinned(ci_gate) -> None:
    """The gate's own tree must satisfy it, or the repo is red at HEAD."""
    check = ci_gate.gate_action_pinning(REPO_ROOT)
    assert check.status == "pass", f"{check.summary}\n{check.output}"


def test_the_gate_is_wired_into_the_run(ci_gate) -> None:
    """A gate nobody calls is dead code pretending to be enforcement."""
    source = (SCRIPTS / "ci_gate.py").read_text(encoding="utf-8")
    assert "gate_action_pinning(" in source.replace(
        "def gate_action_pinning", ""
    ), "gate_action_pinning is defined but never appended to report.checks"
