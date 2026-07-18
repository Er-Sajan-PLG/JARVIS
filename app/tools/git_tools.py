"""
Git tools for JARVIS Documentation Agent (v2.4.0)

All tools are read-only. Zero write risk.
These are the eyes of the documentation agent — it reads git history
to understand what JARVIS did and when.
"""

import subprocess
from pathlib import Path

from app.tools.base import ToolDefinition, ToolResult

# Cap diff output so it doesn't blow the context window
DIFF_MAX_CHARS = 8000


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
    return _run_git("log", f"--oneline", f"-{n}", "--format=%h %ad %s", "--date=short")


def git_diff_stat(from_ref: str = "HEAD~1", to_ref: str = "HEAD") -> str:
    """Compact file-level summary: which files changed and by how much."""
    return _run_git("diff", from_ref, to_ref, "--stat")


def git_diff_full(from_ref: str = "HEAD~1", to_ref: str = "HEAD") -> str:
    """
    Full patch diff — what lines actually changed.
    Capped at DIFF_MAX_CHARS to prevent context explosion.
    """
    diff = _run_git("diff", from_ref, to_ref)
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
    output = _run_git("show", ref, "--stat", "--format=%h %ad %s%n%n%b", "--date=short")
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
        handler=git_log,
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
                "to_ref":   {"type": "string", "default": "HEAD"},
            },
        },
        handler=git_diff_stat,
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
                "to_ref":   {"type": "string", "default": "HEAD"},
            },
        },
        handler=git_diff_full,
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
        handler=git_show,
        risk_level="none",
        requires_confirmation=False,
    ),
    ToolDefinition(
        name="git_tags",
        description="List all version tags in the repo",
        parameters={"type": "object", "properties": {}},
        handler=git_tags,
        risk_level="none",
        requires_confirmation=False,
    ),
]