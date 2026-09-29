"""Sandbox regression tests for the workspace file tools (S0 / S1 findings).

What this pins
--------------
* **S0 -- the write denylist was six prefixes.** ``_check_sandbox`` refused writes
  only under ``app``, ``tests``, ``scripts``, ``.git``, ``.github`` and ``legacy``.
  Everything else inside the workspace root was writable, including primitives
  that are code execution or a persistent behaviour change:

  - ``prompts/system.md`` -- prompt injection that survives a restart,
  - ``githooks/pre-commit`` -- runs on the next commit,
  - ``.venv/bin/activate`` -- patches the interpreter that runs JARVIS,
  - ``requirements.txt``, ``pyproject.toml``, ``package.json``, ``Dockerfile``,
    ``docker-compose.yml`` -- arbitrary code on the next install/build,
  - anything under ``data/`` -- runtime state (approvals, sessions, DBs, keys).

* **S1 -- ``data/`` was neither a secret nor a protected prefix.**
  ``data/tgcall.session`` is a full Telegram userbot credential and
  ``data/web_settings.json`` holds plaintext provider API keys, so a plain
  ``read_file`` handed out live credentials.

Two rules this module follows so that it is safe *before* the fix as well as
after it
--------------------------------------------------------------------------
1. **No test writes inside the repository.** Writes that the fixed sandbox must
   refuse are aimed at a fake workspace root (``tmp_path`` plus
   ``JARVIS_WORKSPACE_ROOT``), so the pre-fix run mutates only the temp tree.
   The real repository layout is probed through ``_check_sandbox``, which decides
   without touching the disk.
2. **No test opens a secret file.** Every assertion about a real credential path
   goes through a refusal, so no failure report can print a credential value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.tools.workspace_tools import (
    SECRET_NAMES,
    _check_sandbox,
    workspace_append_file as append_file,
    workspace_create_directory as create_directory,
    workspace_list_dir as list_dir,
    workspace_read_file as read_file,
    workspace_write_file as write_file,
)

# Derived from this file, not from the module under test: the repo root must not
# move because a test monkeypatched the workspace root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Paths inside the workspace root that a write must be refused for.
WRITE_REFUSED = [
    "prompts/system.md",
    "prompts/identity.md",
    "githooks/pre-commit",
    ".venv/bin/activate",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    "docker-compose.yml",
    "data/web_settings.json",
    "data/tgcall.session",
    "data/approvals.json",
    "data/attachments/files/upload.bin",
    "data/nested/deeper/new.json",
]

# Paths that are none of the sandbox's business: refusing them is over-blocking.
WRITE_ALLOWED = [
    "README.md",
    "DEVLOG.md",
    "docs/CHANGELOG.md",
    "docs/new-document.md",
    "docs/architecture/nested.md",
    "docs/prompts/not-a-prompt.md",
    "docs/data/not-runtime-state.md",
    "docs/tests/not-a-test.md",
    "artifacts/report.md",
    "tmp/scratch.txt",
    "evals/notes.md",
    "config-notes.md",
    "appendix/notes.md",
    "tests-not-really.md",
]

# Every secret name, wherever it lives, plus the two reported data/ credentials.
SECRET_PATHS = sorted(
    {".env", ".env.local", "data/web_settings.json", "data/tgcall.session"} | SECRET_NAMES
)


@pytest.fixture(autouse=True)
def _pin_workspace_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's JARVIS_WORKSPACE_ROOT must not redefine "protected"."""
    monkeypatch.delenv("JARVIS_WORKSPACE_ROOT", raising=False)


@pytest.fixture()
def fake_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway workspace root that has the real repo's shape.

    Real tool calls are made against this root so the pre-fix run can only ever
    mutate ``tmp_path``.
    """
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("JARVIS_WORKSPACE_ROOT", str(root))
    return root


# --- writes that must be refused ------------------------------------------------


@pytest.mark.parametrize("rel", WRITE_REFUSED)
def test_write_tools_refuse_protected_paths(fake_workspace: Path, rel: str) -> None:
    """write_file / append_file / create_directory must all refuse the path."""
    target = fake_workspace / rel

    with pytest.raises(PermissionError, match="not allowed"):
        write_file(str(target), "x")

    with pytest.raises(PermissionError, match="not allowed"):
        append_file(str(target), "x")

    with pytest.raises(PermissionError, match="not allowed"):
        create_directory(str(target), _hitl_approved=True)

    assert not target.exists(), f"{rel} was created despite being protected"


@pytest.mark.parametrize("rel", WRITE_REFUSED)
def test_repo_layout_refuses_the_same_paths_without_touching_disk(rel: str) -> None:
    """Same decision for the real repo layout, made without writing anything."""
    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(REPO_ROOT / rel), "write", for_write=True)

    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(REPO_ROOT / rel), "append", for_write=True)


@pytest.mark.parametrize(
    "rel",
    [
        "data/attachments/files/upload.bin",
        "data/projects/index.json",
        "prompts/identity.md",
        "githooks/pre-commit",
        ".venv/bin/activate",
    ],
)
def test_the_new_protection_is_write_only(rel: str) -> None:
    """Reads that worked before this change must still work.

    ``prompts/``, ``githooks/``, ``.venv/`` and ``data/`` join the denylist for
    *writes* only. Reads of a data attachment or a prompt file are ordinary
    workspace reads, and turning them into errors would be over-blocking.
    """
    assert _check_sandbox(str(REPO_ROOT / rel), "read", for_write=False)
    assert _check_sandbox(str(REPO_ROOT / rel), "list_dir", for_write=False)

    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(REPO_ROOT / rel), "write", for_write=True)


# --- reads that must be refused -------------------------------------------------


@pytest.mark.parametrize("rel", SECRET_PATHS)
def test_read_refuses_secret_paths(fake_workspace: Path, rel: str) -> None:
    """A secret-shaped file is refused for reads even when it exists."""
    target = fake_workspace / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("placeholder-not-a-real-credential", encoding="utf-8")

    with pytest.raises(PermissionError, match="not allowed"):
        read_file(str(target))

    with pytest.raises(PermissionError, match="not allowed"):
        write_file(str(target), "x")


@pytest.mark.parametrize("rel", SECRET_PATHS)
def test_repo_secret_paths_are_refused_without_being_opened(rel: str) -> None:
    """The real repo's secret names are refused; no content is ever read."""
    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(REPO_ROOT / rel), "read", for_write=False)


def test_secret_refusal_follows_the_name_not_the_directory(tmp_path: Path) -> None:
    """Secret names are refused wherever they resolve, not only under data/."""
    nested = tmp_path / "elsewhere" / "deeply" / "nested" / "web_settings.json"
    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(nested), "write", for_write=True)

    with pytest.raises(PermissionError, match="not allowed"):
        _check_sandbox(str(tmp_path / "tgcall.session"), "read", for_write=False)


# --- paths that must keep working -----------------------------------------------


@pytest.mark.parametrize("rel", WRITE_ALLOWED)
def test_ordinary_workspace_paths_are_not_blocked(rel: str) -> None:
    """Documentation, artifacts and temp output must stay writable."""
    assert _check_sandbox(str(REPO_ROOT / rel), "write", for_write=True)


def test_ordinary_workspace_paths_are_writable_for_real(fake_workspace: Path) -> None:
    """A real write/append/create_directory round trip outside protected paths."""
    doc = fake_workspace / "docs" / "notes.md"
    assert "Written" in write_file(str(doc), "# Notes\n")
    assert "Appended" in append_file(str(doc), "more\n")
    assert read_file(str(doc)) == "# Notes\nmore\n"

    directory = fake_workspace / "artifacts" / "run-1"
    assert "Created directory" in create_directory(str(directory), _hitl_approved=True)
    assert directory.is_dir()


def test_scratch_workspace_under_tmp_path_still_works(tmp_path: Path) -> None:
    """The ExecutionRunner's temp-dir work must be untouched by this change."""
    scratch = tmp_path / "scratch" / "plan.md"
    assert "Written" in write_file(str(scratch), "step 1\n")
    assert scratch.read_text(encoding="utf-8") == "step 1\n"
    assert read_file(str(scratch)) == "step 1\n"


def test_ordinary_repo_reads_still_work() -> None:
    """The sandbox must not have turned into a read denylist for the repo."""
    readme = read_file(str(REPO_ROOT / "README.md"))
    assert isinstance(readme, str)
    assert "file not found" not in readme
    assert readme.strip()


def test_listing_the_data_directory_still_works() -> None:
    """``data/`` is write-protected, not read-protected: attachments live there.

    A refused path raises instead of returning, so reaching the string return is
    the assertion.
    """
    listing = list_dir(str(REPO_ROOT / "data"))
    assert isinstance(listing, str)
