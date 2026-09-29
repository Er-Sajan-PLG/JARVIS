#!/usr/bin/env python3
"""AGY (Antigravity CLI) integration for JARVIS.

Provides access to Google AI Pro / Antigravity models via the local `agy` CLI.
No API key needed - uses the locally signed-in Google session.

Usage:
    provider: agy
    model: gemini-3.8-flash-medium  # or any model from `agy models`

Sprint 8.3: stateful conversations (--conversation/--continue), --effort,
--agent, --mode, --add-dir passthrough, real token usage from CLI JSON.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash-medium"
MAX_FILE_CHARS = 60000

# Repo root = .../app/adapters/integrations/agy.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Basenames whose contents must never be inlined into a prompt. Whatever is
# inlined leaves the machine, so this is an *egress* control, and it is
# maintained here rather than imported from ``app.tools.workspace_tools``:
# ``app.adapters`` is not allowed to import ``app.tools``
# (scripts/board/review.py, check_import_layering -- a function-local import does
# not exempt it either). Drift is caught by a test instead of by the type system:
# tests/unit/test_agy_analyze_file_sandbox.py asserts this set is a superset of
# workspace_tools.SECRET_NAMES, so adding a secret name there fails the build
# until it is added here.
EGRESS_SECRET_NAMES: frozenset[str] = frozenset(
    {
        ".ci-bridge.env",
        ".env",
        ".env.development",
        ".env.local",
        ".env.production",
        ".env.staging",
        ".env.test",
        ".git-credentials",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "tgcall.session",
        "web_settings.json",
    }
)

# Suffixes that are credentials whatever they are called. ``.env`` covers both
# ``.ci-bridge.env`` and, via the ``.env`` prefix rule below, ``.env.local``.
_EGRESS_SECRET_SUFFIXES: tuple[str, ...] = (".env", ".key", ".p12", ".pem", ".pfx")

# JARVIS's own state directory: the memory store, conversation transcripts, the
# SQLite databases and the web settings key store. None of it is a document.
# ``data/uploads`` is excluded -- that is the console's document area, and it is
# what file analysis is legitimately pointed at.
_PRIVATE_STATE_DIR = "data"
_UPLOAD_SUBDIR = "uploads"


def _agy_which() -> str | None:
    """Find the agy CLI executable."""
    # Check PATH first
    found = shutil.which("agy")
    if found:
        return found
    # Check common install locations
    for p in [
        Path.home() / ".local" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def is_available() -> bool:
    """Check if agy CLI is available."""
    return _agy_which() is not None


def get_models() -> list[dict[str, Any]]:
    """Get available models from agy CLI."""
    exe = _agy_which()
    if not exe:
        return []

    try:
        result = subprocess.run(
            [exe, "models"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("agy models failed: %s", result.stderr[:200])
            return []

        models = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith(("Name", "Model", "──", "Usage", "Featured")):
                continue
            # Parse tab-separated format: "slug\tDisplay Name"
            parts = line.split("\t")
            if len(parts) >= 2:
                slug = parts[0].strip()
                display_name = parts[1].strip()
                if slug:
                    models.append(
                        {
                            "id": slug,
                            "name": display_name,
                            "description": f"AGY model: {display_name}",
                            "context_length": 1000000,
                            "pricing": {},
                        }
                    )
        return models
    except Exception as e:
        logger.error("Failed to get agy models: %s", e)
        return []


def chat(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    effort: str | None = None,
    timeout: int = 300,
    conversation_id: str = "",
    agent: str | None = None,
    mode: str | None = None,
    add_dirs: list[str] | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """
    Send a chat request via agy CLI.

    Args:
        messages: OpenAI-style messages list (history preserved in the prompt;
            pass conversation_id as well for server-side threading).
        model: Model ID from `agy models`.
        effort: Reasoning effort (low/medium/high).
        timeout: Timeout in seconds (rounded UP to whole minutes for the CLI).
        conversation_id: Resume this CLI conversation (threaded workers).
        agent: `--agent` worker profile (see `agy agent`).
        mode: `plan` (propose only) or `accept-edits`.
        add_dirs: Extra `--add-dir` scopes (repeatable).
        project: `--project` scope for the run.

    Returns:
        Dict with content, model, tokens_used, finish_reason, conversation_id.
    """
    exe = _agy_which()
    if not exe:
        raise RuntimeError("AGY CLI not found. Install from https://antigravity.google/")

    # Build prompt from messages
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt_parts.append(f"[System]\n{content}")
        elif role == "assistant":
            prompt_parts.append(f"[Assistant]\n{content}")
        else:
            prompt_parts.append(f"[User]\n{content}")

    prompt = "\n\n".join(prompt_parts)

    # Build command - prompt must be attached to --print with =
    # Minutes round UP: 90s needs "2m", never "1m" (truncation starved the CLI).
    minutes = max(1, -(-timeout // 60))
    cmd = [
        exe,
        f"--print={prompt}",
        "--output-format",
        "json",
        "--print-timeout",
        f"{minutes}m",
        "--model",
        model,
    ]

    if effort:
        cmd += ["--effort", effort]
    if conversation_id:
        cmd += ["--conversation", conversation_id]
    if agent:
        cmd += ["--agent", agent]
    if mode:
        cmd += ["--mode", mode]
    for extra_dir in add_dirs or []:
        cmd += ["--add-dir", extra_dir]
    if project:
        cmd += ["--project", project]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"AGY CLI timed out after {timeout}s") from exc
    except OSError as e:
        raise RuntimeError(f"AGY CLI failed to start: {e}") from e

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:]
        raise RuntimeError(f"AGY CLI returned {result.returncode}: {tail}")

    out = (result.stdout or "").strip()
    if not out:
        raise RuntimeError("AGY CLI returned no response")

    # Parse JSON response
    content = out
    conversation_out = conversation_id
    tokens_used = None
    finish_reason = "stop"
    try:
        parsed = json.loads(out)
        # Extract text from various response formats
        if isinstance(parsed, str):
            content = parsed
        elif isinstance(parsed, dict):
            content = (
                parsed.get("response")
                or parsed.get("text")
                or parsed.get("output")
                or parsed.get("content")
                or str(parsed)
            )
            conversation_out = (
                parsed.get("conversation_id")
                or parsed.get("conversationId")
                or parsed.get("session_id")
                or conversation_out
            )
            usage = parsed.get("usage") or {}
            if isinstance(usage, dict):
                tokens_used = usage.get("total_tokens", usage.get("total"))
            if parsed.get("status") and str(parsed["status"]).lower() not in (
                "success",
                "ok",
            ):
                finish_reason = str(parsed["status"])
        else:
            content = str(parsed)
    except json.JSONDecodeError:
        content = out

    return {
        "content": content,
        "model": model,
        "tokens_used": tokens_used,
        "finish_reason": finish_reason,
        "conversation_id": conversation_out,
    }


def _analysis_roots() -> list[Path]:
    """Roots a file may be analysed from: the workspace root and the temp dir.

    Mirrors the tool sandbox's roots without importing it -- see
    ``EGRESS_SECRET_NAMES`` for why that import is unavailable here.
    """
    env = os.environ.get("JARVIS_WORKSPACE_ROOT")
    roots = [Path(env).resolve() if env else _REPO_ROOT]
    with contextlib.suppress(OSError, ValueError):
        roots.append(Path(tempfile.gettempdir()).resolve())
    extra = os.environ.get("JARVIS_EXTRA_ALLOWED_ROOTS", "")
    for chunk in extra.split(os.pathsep):
        if chunk.strip():
            roots.append(Path(chunk.strip()).resolve())
    return roots


def _is_private_state(resolved: Path, workspace_root: Path) -> bool:
    """True for JARVIS's own state tree, which is not a document and never leaves."""
    state_dir = workspace_root / _PRIVATE_STATE_DIR
    if not resolved.is_relative_to(state_dir):
        return False
    return not resolved.is_relative_to(state_dir / _UPLOAD_SUBDIR)


def resolve_analysis_path(file_path: str) -> Path:
    """Resolve ``file_path`` and refuse it unless its contents may leave the machine.

    The file is read locally and inlined into a prompt sent to a third party, so
    this is an egress boundary as much as a read boundary: a refusal here is the
    only thing between an arbitrary path and an outbound request.

    Resolution happens *before* the decision, and the resolved path is returned so
    the caller opens exactly what was checked -- checking one form of a path and
    opening another is how ``..`` and symlinks slip past a sandbox.

    Args:
        file_path: Path as supplied by the caller.

    Returns:
        The resolved path. The caller must open *this*, not the original string.

    Raises:
        PermissionError: The path must not be read into an outgoing prompt.
    """
    if not file_path or not file_path.strip():
        raise PermissionError("File analysis refused: no path given")

    candidate = Path(file_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    # strict=False: the target need not exist for the decision to be made.
    resolved = candidate.resolve()

    name = resolved.name
    lowered = name.lower()
    if (
        name in EGRESS_SECRET_NAMES
        or lowered.startswith(".env")
        or lowered.endswith(_EGRESS_SECRET_SUFFIXES)
    ):
        raise PermissionError(
            f"File analysis refused: '{name}' is a secret file and its contents "
            "would be sent to a third party"
        )

    roots = _analysis_roots()
    if not any(resolved.is_relative_to(root) for root in roots):
        raise PermissionError(
            f"File analysis refused: {file_path} resolves outside the workspace root "
            "and the temp dir, so it may not be analysed"
        )

    if _is_private_state(resolved, roots[0]):
        raise PermissionError(
            f"File analysis refused: {file_path} is JARVIS state, not a document "
            f"(only {_PRIVATE_STATE_DIR}/{_UPLOAD_SUBDIR}/ is analysable)"
        )

    return resolved


def analyze_file(
    file_path: str,
    query: str,
    model: str = DEFAULT_MODEL,
    mime_type: str | None = None,
) -> str:
    """
    Ask agy to analyze a file.

    Reads the file locally (capped at MAX_FILE_CHARS) and inlines it; native
    CLI upload is still on the roadmap. The mime hint is passed along so the
    model knows binary vs text handling.

    The path is checked before the file is opened and before any prompt exists
    (``resolve_analysis_path``). A refusal is a ``PermissionError`` -- never an
    empty result -- and it is raised outside the ``try`` below so that it is not
    reported as an "analysis failure".
    """
    resolved = resolve_analysis_path(file_path)

    # For now, read file and include in prompt (capped).
    # TODO: Use agy's native file upload when available
    try:
        with open(resolved, "rb") as f:
            content = f.read()

        # Try to decode as text
        try:
            text_content = content.decode("utf-8", errors="replace")
        except Exception:
            text_content = f"[Binary file: {file_path}]"

        if len(text_content) > MAX_FILE_CHARS:
            text_content = (
                text_content[:MAX_FILE_CHARS]
                + f"\n…[truncated {len(text_content) - MAX_FILE_CHARS} chars]"
            )
        mime_hint = f" (MIME: {mime_type})" if mime_type else ""

        messages = [
            {"role": "system", "content": "You are analyzing a file. Be thorough and accurate."},
            {
                "role": "user",
                "content": (
                    f"{query}\n\n[File: {os.path.basename(file_path)}"
                    f"{mime_hint}]\n{text_content}"
                ),
            },
        ]

        result = chat(messages, model=model)
        return result["content"]
    except Exception as e:
        raise RuntimeError(f"File analysis failed: {e}") from e
