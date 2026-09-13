"""
File tools for JARVIS Documentation Agent.

Intentionally scoped:
- read_file: documentation files + README only
- write_file: CHANGELOG and DEVLOG only, requires confirmation

The allowlist IS the security model, and it is ENFORCED here: each handler calls
_require_allowed(), which fails closed with PermissionError. ToolDefinition.execute
converts that into ToolResult(success=False), so a refused path is an error the
caller cannot mistake for a success.

Approval (_hitl_approved, injected by @safety_gate) gates whether an already-allowed
operation runs. It never widens the allowlist.

These are the DocumentationAgent's narrow tools. The ExecutionRunner uses the
generic, workspace-sandboxed primitives in app/tools/workspace_tools.py instead;
the two trust levels are deliberately separate.

In v3.0, this becomes a proper permission system with user-configurable rules.
"""

from pathlib import Path

from app.domain import SafetyTier
from app.guardrails import safety_gate
from app.tools.base import ToolDefinition

ALLOWED_READ: set[str] = {
    "docs/CHANGELOG.md",
    "docs/DEVLOG.md",
    "docs/CHANGELOG_recovered.md",
    "docs/DEVLOG_recovered.md",
    "docs/V3_ROADMAP.md",
    "CHANGELOG.md",
    "DEVLOG.md",
    "README.md",
    "config.yaml",
}

ALLOWED_WRITE: set[str] = {
    "docs/CHANGELOG.md",
    "docs/DEVLOG.md",
    "CHANGELOG.md",
    "DEVLOG.md",
}

ALLOWED_CREATE_DIR: set[str] = set()


# ─── Raw functions ─────────────────────────────────────────────────────────────


def _require_allowed(path: str, allowed: set[str], operation: str) -> None:
    """Fail closed: raise PermissionError if path is outside the allowlist.

    Raising (rather than returning a message) is what makes the allowlist a real
    control: ToolDefinition.execute converts the exception into
    ToolResult(success=False), so a refused path is an *error* the caller cannot
    mistake for a successful read/write. Approval (_hitl_approved) gates whether an
    allowed operation runs; it must never widen the allowlist itself.
    """
    if path not in allowed:
        raise PermissionError(f"Path not allowed for {operation}: {path} (not in allowlist)")
    if path.startswith("/") or ".." in path:
        raise PermissionError(f"Path not allowed for {operation}: {path} (absolute or traversal)")


@safety_gate(tier=SafetyTier.SAFE, description="Read file content")
def read_file(path: str) -> str:
    """Read a documentation file."""
    _require_allowed(path, ALLOWED_READ, "read")
    p = Path(path)
    if not p.exists():
        return f"(file not found: {path} — this may be a new file)"
    return p.read_text(encoding="utf-8")


@safety_gate(tier=SafetyTier.SENSITIVE, description="Write file content")
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    _require_allowed(path, ALLOWED_WRITE, "write")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"


@safety_gate(tier=SafetyTier.SENSITIVE, description="Append file content")
def append_file(path: str, content: str) -> str:
    """Append content to an existing file without overwriting."""
    _require_allowed(path, ALLOWED_WRITE, "append")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content)} chars to {path}"


@safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Create directory")
def create_directory(path: str) -> str:
    """Create a new directory."""
    _require_allowed(path, ALLOWED_CREATE_DIR, "create_directory")
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


@safety_gate(tier=SafetyTier.SAFE, description="List directory entries")
def list_dir(path: str = ".") -> str:
    """List directory entries (bounded to 200 so model context stays small).

    Registered as a SAFE tool so the planner's workspace-inspection step actually
    executes (ADR-011); the runner invokes tools by name with keyword arguments.
    """
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return f"(directory not found: {path})"
    entries = sorted(entry.name + ("/" if entry.is_dir() else "") for entry in p.iterdir())
    return "\n".join(entries[:200])


# ─── Tool definitions ──────────────────────────────────────────────────────────

FILE_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="read_file",
        description=(
            "Read an existing documentation file to understand its current content and format. "
            f"Allowed paths: {sorted(ALLOWED_READ)}"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read (must be in allowed list)",
                }
            },
            "required": ["path"],
        },
        handler=read_file,
        risk_level="low",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="write_file",
        description=(
            "Write generated content to a documentation file. "
            "Use this ONLY after you have gathered all information and generated "
            "the complete entry. "
            f"Allowed paths: {sorted(ALLOWED_WRITE)}"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write",
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Complete file content to write (the ENTIRE file, "
                        "not just the new section)"
                    ),
                },
            },
            "required": ["path", "content"],
        },
        handler=write_file,
        risk_level="medium",
        requires_confirmation=True,  # always confirm before writing
    ),
    ToolDefinition(
        name="append_file",
        description=(
            "Append new content to an existing documentation file without overwriting it. "
            "Use this for adding new entries to CHANGELOG.md and DEVLOG.md. "
            f"Allowed paths: {sorted(ALLOWED_WRITE)}"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to append to (must be in allowed list)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to append to the file",
                },
            },
            "required": ["path", "content"],
        },
        handler=append_file,
        risk_level="medium",
        requires_confirmation=True,  # always confirm before appending
    ),
    ToolDefinition(
        name="create_directory",
        description=(
            "Create a new directory, including any necessary parent directories. "
            f"Allowed base paths: {sorted(ALLOWED_CREATE_DIR)}"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path of the directory to create "
                        "(must be an allowed path or a subpath of an allowed path)"
                    ),
                }
            },
            "required": ["path"],
        },
        handler=create_directory,
        risk_level="medium",
        requires_confirmation=True,  # always confirm before creating a directory
    ),
]
