#!/usr/bin/env python3
"""AGY (Antigravity CLI) integration for JARVIS.

Provides access to Google AI Pro / Antigravity models via the local `agy` CLI.
No API key needed - uses the locally signed-in Google session.

Usage:
    provider: agy
    model: gemini-3.1-pro-high  # or any model from `agy models`
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
            # Parse tab-separated format: "display name\tslug"
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[0].strip()
                slug = parts[1].strip()
                if slug:
                    models.append({
                        "id": slug,
                        "name": slug,
                        "description": f"AGY model: {name}",
                        "context_length": 1000000,
                        "pricing": {},
                    })
        return models
    except Exception as e:
        logger.error("Failed to get agy models: %s", e)
        return []


def chat(
    messages: list[dict[str, Any]],
    model: str = "gemini-3.1-pro-high",
    effort: str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Send a chat request via agy CLI.
    
    Args:
        messages: OpenAI-style messages list
        model: Model ID from `agy models`
        effort: Reasoning effort (low/medium/high)
        timeout: Timeout in seconds
    
    Returns:
        Dict with content, model, tokens_used, finish_reason
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
    
    # Build command
    cmd = [
        exe,
        "--print",
        "--output-format", "json",
        "--print-timeout", f"{timeout // 60}m",
        "--model", model,
    ]
    
    if effort:
        cmd += ["--effort", effort]
    
    cmd += [prompt]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"AGY CLI timed out after {timeout}s")
    except OSError as e:
        raise RuntimeError(f"AGY CLI failed to start: {e}")
    
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:]
        raise RuntimeError(f"AGY CLI returned {result.returncode}: {tail}")
    
    out = (result.stdout or "").strip()
    if not out:
        raise RuntimeError("AGY CLI returned no response")
    
    # Parse JSON response
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
        else:
            content = str(parsed)
    except json.JSONDecodeError:
        content = out
    
    return {
        "content": content,
        "model": model,
        "tokens_used": None,
        "finish_reason": "stop",
    }


def analyze_file(
    file_path: str,
    query: str,
    model: str = "gemini-3.1-pro-high",
    mime_type: str | None = None,
) -> str:
    """
    Ask agy to analyze a file.
    
    Args:
        file_path: Path to the file
        query: What to ask about the file
        model: Model ID
        mime_type: Optional MIME type hint
    
    Returns:
        Response text
    """
    # For now, read file and include in prompt
    # TODO: Use agy's native file upload when available
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        
        # Try to decode as text
        try:
            text_content = content.decode("utf-8", errors="replace")
        except Exception:
            text_content = f"[Binary file: {file_path}]"
        
        messages = [
            {"role": "system", "content": "You are analyzing a file. Be thorough and accurate."},
            {"role": "user", "content": f"{query}\n\n[File: {os.path.basename(file_path)}]\n{text_content}"},
        ]
        
        result = chat(messages, model=model)
        return result["content"]
    except Exception as e:
        raise RuntimeError(f"File analysis failed: {e}")
