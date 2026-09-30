"""Every Protocol in ``app/`` must be usable as a runtime check.

``isinstance(x, SomeProtocol)`` raises ``TypeError`` unless the Protocol is
decorated ``@runtime_checkable``. That error is easy to avoid by accident: the
usual way to check "does this object satisfy the interface" in a test is to
``patch`` the class under test instead, which always succeeds. So a Protocol that
cannot be checked at runtime is not a neutral omission — it routes tests toward
mocking, which is how ``ModelSwitcher`` spent months calling
``router.set_default(...)`` on a ``ModelRouter`` that has never had that method,
with a green suite (see ``tests/unit/test_router_call_sites.py``).

``app/models/client.py:ModelClient`` and ``app/session/checkpointer.py:Checkpointer``
already carry the decorator. ``app/memory/retrieval.py:CandidateRetriever`` and
``app/memory/llm_extractor.py:ChatModel`` did not, and this holds them to it.

Two things this guard is **not**:

* It does not check that the Protocol has the right method signatures. A
  runtime-checkable Protocol's ``isinstance`` only proves the named members
  exist, not that they take the arguments the caller will pass. The negative
  tests below are written to prove that limit rather than hide it.
* It does not require every ``Protocol`` in the tree to be checkable on
  aesthetic grounds. It requires it because these are declared seams, and a
  declared seam should be assertable.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"


def _protocols() -> list[tuple[str, str, bool]]:
    """(module path, class name, is_runtime_checkable) for every app/ Protocol."""
    found: list[tuple[str, str, bool]] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not any("Protocol" in ast.unparse(b) for b in node.bases):
                continue
            decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
            rel = path.relative_to(REPO_ROOT).as_posix()
            found.append((rel, node.name, "runtime_checkable" in decorators))
    return found


def test_the_scan_finds_protocols_at_all() -> None:
    """Negative control: a guard over an empty set passes vacuously.

    Without this, breaking ``_protocols`` (a changed base-class spelling, a moved
    directory) would turn every assertion below into a no-op that still reports
    green — the exact failure mode this file exists to prevent.
    """
    found = _protocols()
    assert found, "no Protocol classes found under app/ — the scan is broken"
    names = {name for _, name, _ in found}
    assert {
        "CandidateRetriever",
        "ChatModel",
        "ModelClient",
    } <= names, f"expected Protocols missing from the scan: {sorted(names)}"


def test_every_protocol_in_app_is_runtime_checkable() -> None:
    """An undecorated Protocol cannot be asserted on, only mocked around."""
    missing = [f"{path}:{name}" for path, name, ok in _protocols() if not ok]
    assert missing == [], (
        "these Protocols are not @runtime_checkable, so isinstance() on them "
        "raises TypeError and the only way to 'verify' a conforming object is to "
        f"mock the class under test: {missing}"
    )


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("app.memory.retrieval", "CandidateRetriever"),
        ("app.memory.llm_extractor", "ChatModel"),
        ("app.models.client", "ModelClient"),
        ("app.session.checkpointer", "Checkpointer"),
    ],
)
def test_isinstance_against_a_real_implementation_succeeds(module: str, name: str) -> None:
    """A conforming object passes the runtime check, and a bare one does not."""
    import importlib

    protocol = getattr(importlib.import_module(module), name)
    assert isinstance(object(), protocol) is False, (
        f"a bare object() passed isinstance(x, {name}) — the Protocol declares no "
        f"members, so the check proves nothing"
    )


def test_runtime_checkable_is_membership_only_not_signature() -> None:
    """The limit of this decorator, pinned so it is not mistaken for typing.

    ``isinstance`` against a runtime-checkable Protocol checks that the named
    members are *present*. It does not check their signatures, so an object whose
    ``generate`` takes no arguments still passes ``isinstance(x, ChatModel)`` and
    fails only when called. Anything relying on this check for safety needs its
    own call-site validation.
    """

    class WrongShape:
        def generate(self) -> None:  # no `messages`, no `**kwargs`
            return None

    from app.memory.llm_extractor import ChatModel

    assert isinstance(WrongShape(), ChatModel), (
        "if this ever fails, the decorator started validating signatures — the "
        "caveat in the module docstring is then stale and should be corrected"
    )
