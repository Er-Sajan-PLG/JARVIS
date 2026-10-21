"""The secret-name denylist may grow but must never shrink.

``tests/unit/test_workspace_secret_protection.py`` builds its cases from
``SECRET_NAMES`` **imported from the module under test**, which makes it
self-validating: remove a name from production and its own test case disappears
with it. Verified — deleting ``id_ed25519`` and ``.netrc`` from ``SECRET_NAMES``
dropped the file from 80 passing tests to 76, with nothing failing. The
protection could be deleted one entry at a time and the suite would stay green
(F-TEST-009).

The fix is a frozen expectation that lives on the test side. Production is free
to add names; this file names the ones that must never leave. Deleting one is
then a red build, not a silently smaller test file.

This file intentionally does NOT import the list it checks against — the literal
below is the whole point. ``test_the_baseline_is_not_built_from_the_module`` is
the negative control that keeps it that way.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.tools.workspace_tools import (
    PROTECTED_FILES,
    PROTECTED_WRITE_PREFIXES,
    SECRET_NAMES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
THIS_FILE = Path(__file__).resolve()

# Frozen 2026-09-30. Every name here was in production at that commit. Add to this
# list when production grows; never remove an entry to make a red build pass,
# unless the file it protects genuinely stopped being a secret.
BASELINE_SECRET_NAMES: frozenset[str] = frozenset(
    {
        ".ci-bridge.env",
        ".env",
        ".env.local",
        ".env.production",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_ed25519",
        "id_rsa",
        "tgcall.session",
        "web_settings.json",
    }
)

# Writing under these prefixes is code execution or a persistent behaviour change:
# prompts/ (injection surviving restart), githooks/ (runs on the next commit),
# .venv/ (patches the running interpreter), data/ (approvals, sessions, keys).
BASELINE_WRITE_PREFIXES: frozenset[str] = frozenset({".venv", "data", "githooks", "prompts"})

# Manifests and container definitions: writing one is arbitrary code on the next
# install or build. Matched as exact workspace-relative paths.
BASELINE_PROTECTED_FILES: frozenset[str] = frozenset(
    {
        "Dockerfile",
        "docker-compose.yml",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
    }
)


def test_no_secret_name_was_removed() -> None:
    """The production denylist is a superset of the frozen baseline.

    A missing name here means the denylist shrank. That is the failure this file
    exists for: it cannot be observed from the tests that iterate the list,
    because those cases are gone by the time it happens.
    """
    missing = BASELINE_SECRET_NAMES - SECRET_NAMES
    assert not missing, (
        f"SECRET_NAMES no longer protects {sorted(missing)}. If these paths are "
        f"genuinely no longer secrets, remove them from BASELINE_SECRET_NAMES in "
        f"this file and say why; otherwise restore them — their test cases were "
        f"derived from the list, so nothing else will fail."
    )


def test_no_protected_write_prefix_was_removed() -> None:
    """Same guard for the write denylist."""
    missing = BASELINE_WRITE_PREFIXES - set(PROTECTED_WRITE_PREFIXES)
    assert not missing, (
        f"PROTECTED_WRITE_PREFIXES no longer covers {sorted(missing)} — writes "
        f"there are code execution or a persistent behaviour change."
    )


def test_no_protected_file_was_removed() -> None:
    """Same guard for the build-manifest denylist."""
    missing = BASELINE_PROTECTED_FILES - PROTECTED_FILES
    assert not missing, (
        f"PROTECTED_FILES no longer covers {sorted(missing)} — writing one is "
        f"arbitrary code on the next install or build."
    )


def test_the_baseline_is_not_built_from_the_module() -> None:
    """Negative control: the literals above must stay literals.

    If the baseline were ever rewritten as ``SECRET_NAMES`` itself, every check
    in this file would pass on any input — the exact defect being fixed here,
    reintroduced inside its own fix. This reads the module AST and requires the
    baseline to be a set/frozenset literal, not a name or a call.
    """
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    baselines = {
        "BASELINE_SECRET_NAMES",
        "BASELINE_WRITE_PREFIXES",
        "BASELINE_PROTECTED_FILES",
    }
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        target = node.target
        if not isinstance(target, ast.Name) or target.id not in baselines:
            continue
        assert isinstance(node.value, ast.Call), f"{target.id} is not a collection literal"
        func = node.value.func
        func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        assert func_name in {"set", "frozenset"}, (
            f"{target.id} is built with {func_name}(); it must be a literal so it "
            f"cannot drift with the module it guards."
        )
        checked += 1
    assert checked == len(baselines), (
        f"expected {len(baselines)} baselines, found {checked} — one was renamed "
        f"or removed and the guard no longer covers it."
    )
