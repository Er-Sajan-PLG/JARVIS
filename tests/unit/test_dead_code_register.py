"""A register of ``app/`` subsystems with no production call site.

This session removed a defect from ``ModelSwitcher`` that had survived months of a
green suite: it called ``register()`` and ``set_default()`` on a ``ModelRouter``
that has never had either method (ADR-019). The reason it survived is that every
test constructed the class under test *directly*. No test ever walked the path the
application walks, because no application code walks it.

Tracing that led to three more components in the same condition, and to this
file. The pattern is worth naming:

    A component with no production call site cannot fail in production. Its tests
    can only assert what their own fixtures set up, so they will confirm any
    interface the author believed in -- including one that does not exist.

Each entry below is verified to have **zero** construction sites outside its own
module, across ``app/``, ``scripts/`` and ``n8n/``. The test is deliberately a
register that must be *edited* rather than a general scan, because a general scan
of "classes never called" is unusable: enums, dataclasses, ``Protocol``s, ABCs and
settings classes are all correctly never constructed, and they swamp the signal
(196 public classes in ``app/``; only a handful are genuinely orphaned
components).

**When this test fails, it is telling you something good.** It means a registered
component now HAS a production call site. That is the fix, not a regression.
Update the entry and the table in ``docs/architecture/DEAD-CODE-REGISTER.md``,
and if the component was registered because of a specific defect, drop the
"unreachable" caveat from the ADR that recorded it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Production roots. `legacy/` is excluded on purpose: it is retired, `app/` does
# not import it, and a construction there does not make anything reachable.
PRODUCTION_ROOTS = ("app", "scripts", "n8n")
TEST_ROOTS = ("tests",)

# class name -> (module that defines it, what it is)
UNREACHABLE: dict[str, tuple[str, str]] = {
    "DocumentationAgent": (
        "app/agents/doc_agent.py",
        "the `docs` REPL command; main.py has no such command",
    ),
    "MCPClientManager": (
        "app/integrations/mcp/manager.py",
        "MCP client mesh; nothing imports the package from outside it",
    ),
    "MCPServer": (
        "app/mcp/registry.py",
        "MCP server registry; same",
    ),
    "ModelSwitcher": (
        "app/models/switcher.py",
        "runtime model profile switching; only legacy/ constructs it",
    ),
}


def _construction_sites(class_name: str, roots: tuple[str, ...]) -> list[str]:
    """Every ``ClassName(...)`` call site under ``roots``."""
    sites: list[str] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - a broken file is another test's job
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else (func.attr if isinstance(func, ast.Attribute) else None)
                )
                if name == class_name:
                    sites.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}")
    return sites


def test_the_register_is_not_empty() -> None:
    """Negative control. An empty register passes every test below vacuously."""
    assert UNREACHABLE, "the register is empty — the checks below prove nothing"


@pytest.mark.parametrize("class_name", sorted(UNREACHABLE))
def test_the_defining_module_still_exists(class_name: str) -> None:
    """A moved or deleted module must update the register, not silently dodge it."""
    module, why = UNREACHABLE[class_name]
    path = REPO_ROOT / module
    assert path.is_file(), (
        f"{class_name} is registered as unreachable from {module}, which no longer "
        f"exists. It was tracked because: {why}."
    )
    source = path.read_text(encoding="utf-8")
    assert f"class {class_name}" in source, (
        f"{class_name} is registered against {module}, but that module does not "
        f"define it any more."
    )


@pytest.mark.parametrize("class_name", sorted(UNREACHABLE))
def test_the_component_still_has_no_production_call_site(class_name: str) -> None:
    """The registered component is still unreachable from the application.

    If this fails, the component was wired up. Delete it from ``UNREACHABLE`` and
    from the table in ``docs/architecture/DEAD-CODE-REGISTER.md`` — and, if an ADR
    recorded it as unreachable, correct that ADR. This failure is a completed
    task, not a broken build.
    """
    sites = _construction_sites(class_name, PRODUCTION_ROOTS)
    module, why = UNREACHABLE[class_name]
    assert sites == [], (
        f"{class_name} ({module}) now has a production call site at {sites}.\n"
        f"It was registered as unreachable because: {why}.\n"
        f"Good news — remove it from UNREACHABLE and from "
        f"docs/architecture/DEAD-CODE-REGISTER.md."
    )


@pytest.mark.parametrize("class_name", sorted(UNREACHABLE))
def test_the_component_is_still_covered_by_tests(class_name: str) -> None:
    """It is still exercised directly, which is why it looked healthy.

    This is the diagnostic value of the register: these components have tests,
    the tests pass, and that is precisely why nobody noticed they never run. If
    this fails, tests were removed without the component being wired or deleted —
    nothing now covers it at all.
    """
    sites = _construction_sites(class_name, TEST_ROOTS)
    assert sites, (
        f"{class_name} is registered as unreachable AND has no construction site "
        f"in tests/. Either it was deleted (remove it from UNREACHABLE) or it is "
        f"now entirely uncovered."
    )
