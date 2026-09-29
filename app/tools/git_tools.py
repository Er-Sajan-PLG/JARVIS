"""
Git tools for JARVIS Documentation Agent (v2.4.0)

All tools are read-only. Zero write risk.
Refs are caller-supplied, so they are validated before they reach git's argv.

These are the eyes of the documentation agent — it reads git history
to understand what JARVIS did and when.
"""

import re
import subprocess

from app.domain import SafetyTier
from app.guardrails.decorator import safety_gate
from app.tools.base import ToolDefinition

# Cap diff output so it doesn't blow the context window
DIFF_MAX_CHARS = 8000

# Conservative revision grammar: an object id (full or abbreviated), or a ref
# name — HEAD, a tag, a local branch, origin/x — optionally followed by
# ancestry operators (~N, ^N). A leading "-" is impossible, so a ref can never
# be read by git as an option.
_SAFE_REF_RE = re.compile(r"(?:[0-9a-fA-F]{4,40}|[A-Za-z0-9][A-Za-z0-9._/-]*)(?:[~^]\d*)*")


def _validate_ref(ref: str, name: str) -> str:
    """Return ``ref`` when it is a plain revision, else raise ValueError.

    A ref is caller-controlled and becomes a git argv element, so it must never
    be readable as an option. Without this, ``git_diff_stat(from_ref=
    "--output=/tmp/x")`` made git write an arbitrary absolute path.
    """
    if not isinstance(ref, str) or not _SAFE_REF_RE.fullmatch(ref):
        raise ValueError(f"Invalid git ref for {name}: {ref!r}")
    if ".." in ref or "@{" in ref or "//" in ref or ref.endswith(("/", ".")):
        raise ValueError(f"Invalid git ref for {name}: {ref!r}")
    return ref


def _run_git(*args: str, cwd: str = ".") -> str:
    """
    Run a git command. Raises RuntimeError on non-zero exit.
    Never prints to stdout — callers decide what to show.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout.strip()


# ─── Raw functions (also useful to call directly from Python) ──────────────────


def git_log(n: int = 15) -> str:
    """Last N commits: hash + date + message."""
    return _run_git("log", "--oneline", f"-{n}", "--format=%h %ad %s", "--date=short")


def git_diff_stat(from_ref: str = "HEAD~1", to_ref: str = "HEAD") -> str:
    """Compact file-level summary: which files changed and by how much."""
    from_ref = _validate_ref(from_ref, "from_ref")
    to_ref = _validate_ref(to_ref, "to_ref")
    return _run_git("diff", "--stat", "--end-of-options", from_ref, to_ref, "--")


def git_diff_full(from_ref: str = "HEAD~1", to_ref: str = "HEAD") -> str:
    """
    Full patch diff — what lines actually changed.
    Capped at DIFF_MAX_CHARS to prevent context explosion.
    """
    from_ref = _validate_ref(from_ref, "from_ref")
    to_ref = _validate_ref(to_ref, "to_ref")
    diff = _run_git("diff", "--end-of-options", from_ref, to_ref, "--")
    if len(diff) > DIFF_MAX_CHARS:
        return (
            diff[:DIFF_MAX_CHARS]
            + f"\n\n... (diff truncated at {DIFF_MAX_CHARS} chars — "
            + f"{len(diff) - DIFF_MAX_CHARS} chars omitted)"
        )
    return diff or "(no changes)"


def git_status() -> str:
    """Current working tree status (staged, unstaged, untracked)."""
    return _run_git("status", "--short") or "(working tree clean)"


def git_show(ref: str = "HEAD") -> str:
    """Show commit message + diff for a single commit."""
    ref = _validate_ref(ref, "ref")
    output = _run_git(
        "show",
        "--stat",
        "--format=%h %ad %s%n%n%b",
        "--date=short",
        "--end-of-options",
        ref,
        "--",
    )
    if len(output) > DIFF_MAX_CHARS:
        return output[:DIFF_MAX_CHARS] + "\n...(truncated)"
    return output


def git_tags() -> str:
    """List all version tags in descending order."""
    try:
        return _run_git("tag", "--sort=-version:refname")
    except RuntimeError:
        return "(no tags found)"


# ─── Tool definitions (registered in the agent's ToolRegistry) ─────────────────

GIT_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="git_log",
        description="Get the last N commits with hash, date, and message",
        parameters={
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of commits to retrieve",
                    "default": 15,
                }
            },
        },
        handler=safety_gate(tier=SafetyTier.SAFE)(git_log),
        risk_level="none",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="git_diff_stat",
        description="Get a compact summary of which files changed between two refs",
        parameters={
            "type": "object",
            "properties": {
                "from_ref": {"type": "string", "default": "HEAD~1"},
                "to_ref": {"type": "string", "default": "HEAD"},
            },
        },
        handler=safety_gate(tier=SafetyTier.SAFE)(git_diff_stat),
        risk_level="none",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="git_diff_full",
        description="Get the full patch diff between two refs (capped at 8000 chars)",
        parameters={
            "type": "object",
            "properties": {
                "from_ref": {"type": "string", "default": "HEAD~1"},
                "to_ref": {"type": "string", "default": "HEAD"},
            },
        },
        handler=safety_gate(tier=SafetyTier.SAFE)(git_diff_full),
        risk_level="none",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="git_show",
        description="Show commit message and changes for a single commit",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "default": "HEAD"},
            },
        },
        handler=safety_gate(tier=SafetyTier.SAFE)(git_show),
        risk_level="none",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="git_tags",
        description="List all version tags in the repo",
        parameters={"type": "object", "properties": {}},
        handler=safety_gate(tier=SafetyTier.SAFE)(git_tags),
        risk_level="none",
        requires_confirmation=False,
    ),
]
