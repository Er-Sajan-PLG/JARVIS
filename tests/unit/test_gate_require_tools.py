"""A blocking gate whose scanner is missing must not report success.

``_missing_tool`` returns ``status="skip"``, and ``Check.failed`` is
``status in ("fail", "error")`` — so a gate declared ``blocking=True`` contributes
nothing to ``blocking_failures`` when its tool is absent. The run concludes
``success`` while the check made no claim at all.

That is survivable locally, where a dev machine may legitimately lack ``syft`` or
``mutmut``. It is not survivable in CI: a workflow that fails to install ``trivy``
turns a *required status check* green while enforcing nothing — the most dangerous
possible failure mode, because it is indistinguishable from a real pass. The whole
point of requiring a check is that green means something.

``--require-tools`` closes it. Under that flag a missing **blocking** tool is a
failure; a missing non-blocking tool is still a skip, since the gate never claimed
it was load-bearing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


@pytest.fixture()
def ci_gate():
    """Fresh import so a flag set by one test cannot leak into another."""
    sys.path.insert(0, str(SCRIPTS))
    if "ci_gate" in sys.modules:
        del sys.modules["ci_gate"]
    mod = importlib.import_module("ci_gate")
    yield mod
    sys.path.remove(str(SCRIPTS))
    sys.modules.pop("ci_gate", None)


def test_a_missing_blocking_tool_is_a_skip_by_default(ci_gate) -> None:
    """Local behaviour is unchanged: absent tooling reports skip, not fail.

    A developer without ``trivy`` installed should see an honest 'skip' rather
    than a red build for something they cannot run.
    """
    ci_gate.REQUIRE_TOOLS = False
    check = ci_gate._missing_tool("trivy", "Supply Chain", True, "not installed")
    assert check.status == "skip"
    assert not check.failed
    assert not (check.blocking and check.failed)


def test_a_missing_blocking_tool_fails_under_require_tools(ci_gate) -> None:
    """Under ``--require-tools`` the same absence is a blocking failure."""
    ci_gate.REQUIRE_TOOLS = True
    check = ci_gate._missing_tool("trivy", "Supply Chain", True, "not installed")
    assert check.status == "fail", (
        "a required blocking scanner was absent and the gate still reported "
        "success — green would mean nothing"
    )
    assert check.failed
    assert check.blocking and check.failed


def test_a_missing_non_blocking_tool_is_still_a_skip_under_require_tools(ci_gate) -> None:
    """The flag hardens only the checks that claim to be load-bearing."""
    ci_gate.REQUIRE_TOOLS = True
    check = ci_gate._missing_tool("osv", "Supply Chain", False, "not installed")
    assert check.status == "skip"
    assert not check.failed


def test_the_failure_message_says_what_to_install(ci_gate) -> None:
    """An unattributable failure is a bad failure."""
    ci_gate.REQUIRE_TOOLS = True
    check = ci_gate._missing_tool("checkov", "Supply Chain", True, "not found on PATH")
    summary = check.summary or ""
    assert "checkov" in summary
    assert (
        "--require-tools" in summary
    ), "the failure should name the flag that caused it, so the fix is obvious"
    assert "not found on PATH" in summary


def test_the_cli_exposes_require_tools(ci_gate) -> None:
    """The flag must be reachable, or the tests above guard dead code."""
    import ast

    tree = ast.parse((SCRIPTS / "ci_gate.py").read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and arg.value == "--require-tools":
                        found = True
    assert found, "ci_gate.py has no --require-tools argument"


def test_require_tools_is_off_unless_asked(ci_gate) -> None:
    """Negative control: the default must not have been flipped by accident.

    If ``REQUIRE_TOOLS`` defaulted to True, every local gate run on a machine
    missing one scanner would fail, and the flag would stop meaning anything.
    """
    source = (SCRIPTS / "ci_gate.py").read_text(encoding="utf-8")
    assert (
        "REQUIRE_TOOLS = False" in source
    ), "REQUIRE_TOOLS no longer defaults to False; the flag's meaning has changed"
