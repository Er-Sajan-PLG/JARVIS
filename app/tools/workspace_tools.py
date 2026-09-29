"""Workspace-scoped file tools for the ExecutionRunner.

These are the *generic* file primitives the runner executes for ordinary tasks
(workspace inspection, temp-dir work, create_directory). They are deliberately
NOT the same objects as ``app.tools.file_tools.FILE_TOOLS``.

Why two sets exist (see ADR note in docs):
  ``file_tools`` is the DocumentationAgent's narrow, docs-only policy. The
  adversarial suite asserts that a model driving the doc agent cannot overwrite
  source code (``app/agents/doc_agent.py``) or read secrets (``.env``). That is a
  real security property and must stay.

  The ExecutionRunner, by contrast, must be able to work in temp/workspace paths
  (e.g. an approved DESTRUCTIVE step creating a directory under a temp dir). Those
  two trust levels cannot share one exact-match allowlist — enforcing it on the
  shared objects dead-coded the runner path (ALLOWED_CREATE_DIR was empty) while
  loosening it would delete the doc-agent protection.

Sandbox model (fail closed):
  * Path is resolved (symlinks and ``..`` collapse before any decision).
  * The resolved path must live under an allowed root: the workspace root
    (repo root by default, override with ``JARVIS_WORKSPACE_ROOT``) or the system
    temp dir. Anything else -> PermissionError.
  * Inside the workspace root, protected prefixes (``app/``, ``tests/``,
    ``scripts/``, ``.git/``, ...) are refused for reads and writes.
  * Inside the workspace root, write-only protected prefixes (``prompts/``,
    ``githooks/``, ``.venv/``, ``data/``) and protected build manifests
    (``requirements.txt``, ``pyproject.toml``, ``package.json``, ``Dockerfile``,
    ``docker-compose.yml``) are refused for writes only: a write to any of them is
    code execution or a persistent behaviour change, while reading a data
    attachment or a prompt file is an ordinary workspace read.
  * Secret-shaped files are refused for reads and writes.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from app.domain import SafetyTier
from app.guardrails import safety_gate
from app.tools.base import ToolDefinition

# Repo root = .../app/tools/workspace_tools.py -> parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _workspace_root() -> Path:
    """Resolve the sandbox root, honouring JARVIS_WORKSPACE_ROOT."""
    env = os.environ.get("JARVIS_WORKSPACE_ROOT")
    root = Path(env).resolve() if env else _REPO_ROOT
    return root


def _allowed_roots() -> list[Path]:
    """Roots a path may resolve under. Workspace root + system temp dir."""
    roots = [_workspace_root()]
    with contextlib.suppress(OSError, ValueError):
        roots.append(Path(tempfile.gettempdir()).resolve())
    extra = os.environ.get("JARVIS_EXTRA_ALLOWED_ROOTS", "")
    for chunk in extra.split(os.pathsep):
        if chunk.strip():
            roots.append(Path(chunk.strip()).resolve())
    return roots


# Write-protected inside the workspace root: source, tests, CI and VCS metadata.
# Refused for reads as well as writes.
PROTECTED_PREFIXES: tuple[str, ...] = ("app", "tests", "scripts", ".git", ".github", "legacy")

# Write-protected inside the workspace root, but still readable. Each entry is a
# path where a *write* is code execution or a persistent behaviour change:
#   prompts/  -> system/identity prompts; a write is prompt injection that
#                survives a restart.
#   githooks/ -> hooks execute on the next commit/push.
#   .venv/    -> the interpreter and site-packages that run JARVIS.
#   data/     -> runtime state (approvals, sessions, DBs, provider API keys).
# Reads stay allowed because data attachments and prompt files are ordinary read
# targets for a task; only rewriting them is out of bounds.
PROTECTED_WRITE_PREFIXES: tuple[str, ...] = ("prompts", "githooks", ".venv", "data")

# Build/dependency manifests and container definitions at the workspace root.
# Writing one is arbitrary code execution on the next install/build, and none of
# them is secret-shaped, so SECRET_NAMES cannot cover them. Matched as exact
# workspace-relative paths (a nested docs/pyproject.toml is not this file).
PROTECTED_FILES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "Dockerfile",
        "docker-compose.yml",
    }
)

# Never readable/writable regardless of location.
SECRET_NAMES: frozenset[str] = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".ci-bridge.env",
        "credentials.json",
        "id_rsa",
        "id_ed25519",
        ".netrc",
        ".npmrc",
        ".pypirc",
        # data/web_settings.json persists provider API keys in plaintext (it is
        # the on-disk twin of .env:GOOGLE_API_KEY).
        "web_settings.json",
        # data/tgcall.session is a Telegram userbot StringSession: a full account
        # credential, written by tgcall/login.js at mode 600.
        "tgcall.session",
    }
)


def _resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    # strict=False: the target may not exist yet (create/write).
    return p.resolve()


def _check_sandbox(path: str, operation: str, *, for_write: bool) -> Path:
    """Fail closed. Raise PermissionError unless path is inside the sandbox."""
    resolved = _resolve(path)

    if resolved.name in SECRET_NAMES:
        raise PermissionError(f"Path not allowed for {operation}: {path} (protected secret file)")

    roots = _allowed_roots()
    within = next((r for r in roots if resolved.is_relative_to(r)), None)
    if within is None:
        raise PermissionError(f"Path not allowed for {operation}: {path} (outside workspace root)")

    # Protected prefixes only apply inside the workspace root, not the temp dir.
    if within == _workspace_root():
        rel = resolved.relative_to(within)
        if rel.parts and rel.parts[0] in PROTECTED_PREFIXES:
            raise PermissionError(
                f"Path not allowed for {operation}: {path} (protected path '{rel.parts[0]}/')"
            )

        if for_write:
            if rel.parts and rel.parts[0] in PROTECTED_WRITE_PREFIXES:
                raise PermissionError(
                    f"Path not allowed for {operation}: {path} "
                    f"(protected write path '{rel.parts[0]}/')"
                )
            if rel.as_posix() in PROTECTED_FILES:
                raise PermissionError(
                    f"Path not allowed for {operation}: {path} (protected build/config file)"
                )

    if for_write and resolved.is_dir():
        raise PermissionError(f"Path not allowed for {operation}: {path} (is a directory)")

    return resolved


@safety_gate(tier=SafetyTier.SAFE, description="Read workspace file")
def workspace_read_file(path: str) -> str:
    """Read a file from inside the sandbox."""
    p = _check_sandbox(path, "read", for_write=False)
    if not p.exists():
        return f"(file not found: {path} — this may be a new file)"
    return p.read_text(encoding="utf-8")


@safety_gate(tier=SafetyTier.SENSITIVE, description="Write workspace file")
def workspace_write_file(path: str, content: str) -> str:
    """Write content to a file inside the sandbox."""
    p = _check_sandbox(path, "write", for_write=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"


@safety_gate(tier=SafetyTier.SENSITIVE, description="Append workspace file")
def workspace_append_file(path: str, content: str) -> str:
    """Append to a file inside the sandbox."""
    p = _check_sandbox(path, "append", for_write=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content)} chars to {path}"


@safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Create workspace directory")
def workspace_create_directory(path: str) -> str:
    """Create a directory inside the sandbox (DESTRUCTIVE -> HITL gated)."""
    p = _check_sandbox(path, "create_directory", for_write=True)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


@safety_gate(tier=SafetyTier.SAFE, description="List workspace directory entries")
def workspace_list_dir(path: str = ".") -> str:
    """List entries of a directory inside the sandbox (bounded to 200)."""
    p = _check_sandbox(path, "list_dir", for_write=False)
    if not p.exists() or not p.is_dir():
        return f"(directory not found: {path})"
    entries = sorted(entry.name + ("/" if entry.is_dir() else "") for entry in p.iterdir())
    return "\n".join(entries[:200])


WORKSPACE_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="read_file",
        description=(
            "Read a file from the workspace. Paths outside the workspace root and "
            "protected source/secret paths are refused."
        ),
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path to read"}},
            "required": ["path"],
        },
        handler=workspace_read_file,
        risk_level="low",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="write_file",
        description=("Write content to a workspace file. Refused for source/test/secret paths."),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Complete file content"},
            },
            "required": ["path", "content"],
        },
        handler=workspace_write_file,
        risk_level="medium",
        requires_confirmation=True,
    ),
    ToolDefinition(
        name="append_file",
        description="Append content to a workspace file without overwriting it.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to append to"},
                "content": {"type": "string", "description": "Content to append"},
            },
            "required": ["path", "content"],
        },
        handler=workspace_append_file,
        risk_level="medium",
        requires_confirmation=True,
    ),
    ToolDefinition(
        name="create_directory",
        description="Create a directory inside the workspace (requires approval).",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        },
        handler=workspace_create_directory,
        risk_level="medium",
        requires_confirmation=True,
    ),
]
