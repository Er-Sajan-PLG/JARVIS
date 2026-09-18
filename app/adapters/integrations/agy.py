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

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash-medium"
MAX_FILE_CHARS = 60000


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
    """
    # For now, read file and include in prompt (capped).
    # TODO: Use agy's native file upload when available
    try:
        with open(file_path, "rb") as f:
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
