"""
File tools for JARVIS Documentation Agent (v2.4.0)

Intentionally scoped:
- read_file: documentation files + README only
- write_file: CHANGELOG and DEVLOG only, requires confirmation

Blast radius is defined here, not enforced by the caller.
The allowlist is the security model for v2.4.
In v3.0, this becomes a proper permission system with user-configurable rules.
"""

from pathlib import Path
from app.tools.base import ToolDefinition

# ─── Allowlists ───────────────────────────────────────────────────────────────

# Files the agent can read (documentation + context)
ALLOWED_READ: set[str] = {
    "docs/CHANGELOG.md",
    "docs/DEVLOG.md",
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
]