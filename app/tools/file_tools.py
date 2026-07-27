"""
File tools for JARVIS Documentation Agent

Intentionally scoped:
- read_file: documentation files + README only
- write_file: CHANGELOG and DEVLOG only, requires confirmation

Blast radius is defined here, not enforced by the caller.
The allowlist is the security model.
In v3.0, this becomes a proper permission system with user-configurable rules.
"""

from pathlib import Path
from app.tools.base import ToolDefinition

# ─── Allowlists ───────────────────────────────────────────────────────────────

# Files the agent can read (documentation + context)
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

# Files the agent can write (documentation only)
ALLOWED_WRITE: set[str] = {
    "docs/CHANGELOG.md",
    "docs/DEVLOG.md",
    "CHANGELOG.md",
    "DEVLOG.md",
}

ALLOWED_CREATE_DIR: set[str] = set()


# ─── Raw functions ─────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """
    Read a documentation file.
    Raises PermissionError if path is not in the allowlist.
    Returns a placeholder string if the file doesn't exist yet
    (useful when CHANGELOG doesn't exist on a fresh project).
    """
    if path not in ALLOWED_READ:
        raise PermissionError(
            f"'{path}' is not in the allowed read list.\n"
            f"Allowed: {sorted(ALLOWED_READ)}"
        )
    p = Path(path)
    if not p.exists():
        return f"(file not found: {path} — this may be a new file)"
    return p.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    """
    Write content to a documentation file.
    Raises PermissionError if path is not in the write allowlist.
    Creates parent directories if needed.
    """
    if path not in ALLOWED_WRITE:
        raise PermissionError(
            f"'{path}' is not in the allowed write list.\n"
            f"Allowed: {sorted(ALLOWED_WRITE)}"
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"

def append_file(path: str, content: str) -> str:
    """Append content to an existing file without overwriting."""
    if path not in ALLOWED_WRITE:
        raise PermissionError(f"'{path}' not in allowed write list")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content)} chars to {path}"

def create_directory(path: str) -> str:
    """
    Create a new directory, including any necessary parent directories.
    Raises PermissionError if path is not in the allowed create directory list.
    """
    # Check if the requested path is in the allowed list or a subpath of an allowed path
    if not any(Path(path).is_relative_to(allowed_path) or Path(path) == Path(allowed_path) for allowed_path in ALLOWED_CREATE_DIR):
        raise PermissionError(
            f"'{path}' is not in the allowed directory creation list or a subpath of an allowed directory.\n"
            f"Allowed base paths: {sorted(ALLOWED_CREATE_DIR)}"
        )

    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


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
            "Use this ONLY after you have gathered all information and generated the complete entry. "
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
                    "description": "Complete file content to write (the ENTIRE file, not just the new section)",
                },
            },
            "required": ["path", "content"],
        },
        handler=write_file,
        risk_level="medium",
        requires_confirmation=True,   # always confirm before writing
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
        requires_confirmation=True,   # always confirm before appending
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
                    "description": "Path of the directory to create (must be an allowed path or a subpath of an allowed path)",
                }
            },
            "required": ["path"],
        },
        handler=create_directory,
        risk_level="medium",
        requires_confirmation=True, # always confirm before creating a directory
    ),
]

