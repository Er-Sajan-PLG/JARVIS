"""Sub-agent runner: JARVIS spawns OpenCode workers and collects receipts.
v1 (Sprint 8.1, ADR-017): OpenCode only. The worker runs as a subprocess
(``opencode run --format json``), so a rogue worker's blast radius stays
inside its process — never in-process calls.

Worker receipt (untrusted until parsed)::

    {"status": "ok|error|timeout", "session_id": "ses_*", "agent": ...,
     "summary": "<assembled text>", "tokens": {...}, "cost": ...,
     "error": "<message or empty>"}

Policy caps (Sprint 8.2, enforced here from day one):
  - allowlisted agents only (DEFAULT: build, plan, general)
  - per-spawn timeout (DEFAULT 600s), kill on expiry
  - workdir must resolve under the workspace root or system temp
  - output bounded (MAX_OUTPUT_CHARS) so a chatty worker cannot flood context

Tier is SENSITIVE (network/compute side effects, file writes inside the
worker's own project dir), not DESTRUCTIVE: spawning must stay usable
without a phone approval per worker, while the worker's own destructive
acts remain governed by ITS permissions.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.domain import SafetyTier
from app.guardrails import safety_gate

logger = logging.getLogger(__name__)

OPENCODE_BIN = os.environ.get("OPENCODE_BIN") or shutil.which("opencode") or ""
HERMES_BIN = os.environ.get("HERMES_BIN") or shutil.which("hermes") or ""
DSH_BIN = os.environ.get("DSH_BIN") or shutil.which("dsh") or ""
DEFAULT_AGENT = "build"
# Muse Spark 1.3 Free, served by OpenCode Zen (the `opencode/` provider), not
# OpenRouter. Free tier; falls back to any model via the `-m` override.
DEFAULT_MODEL = "opencode/muse-spark-1.3-contributor-free"
DEFAULT_TIMEOUT_S = 600
MAX_OUTPUT_CHARS = 20000

ALLOWED_AGENTS = frozenset(os.environ.get("JARVIS_SUBAGENTS", "build,plan,general").split(","))

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_workdir(workdir: str) -> Path:
    """Fail closed: workers run in the workspace or temp, nowhere else."""
    candidate = Path(workdir) if Path(workdir).is_absolute() else Path.cwd() / workdir
    resolved = candidate.resolve()
    roots = [_REPO_ROOT]
    with contextlib.suppress(OSError):
        roots.append(Path(tempfile.gettempdir()).resolve())
    if not any(
        resolved == r or resolved.is_relative_to(r)
        for r in roots  # noqa: FBT
    ):
        raise PermissionError(f"sub-agent workdir refused: {workdir}")
    return resolved


def _parse_events(raw: str) -> dict:
    """Fold an opencode JSON event stream into a worker receipt."""
    texts: list[str] = []
    tokens: dict = {}
    cost = 0.0
    session_id = ""
    error = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = session_id or event.get("sessionID", "")
        kind = event.get("type", "")
        part = event.get("part", {}) if isinstance(event.get("part"), dict) else {}
        if kind == "text" and part.get("type") == "text":
            texts.append(part.get("text", ""))
        elif kind == "step_finish":
            tokens = part.get("tokens", {}) or {}
            cost = event.get("cost", part.get("cost", 0.0)) or 0.0
        elif kind == "error":
            err = event.get("error", {})
            error = err.get("data", {}).get("message", "") if isinstance(err, dict) else str(err)
    summary = "\n".join(texts).strip()
    suffix = "…[truncated]"
    if len(summary) > MAX_OUTPUT_CHARS:
        summary = summary[: MAX_OUTPUT_CHARS - len(suffix)] + suffix
    return {
        "status": "error" if error and not summary else "ok",
        "session_id": session_id,
        "summary": summary,
        "tokens": tokens,
        "cost": cost,
        "error": error,
    }


@safety_gate(tier=SafetyTier.SENSITIVE, description="Spawn an OpenCode sub-agent worker")
async def spawn_subagent(
    goal: str,
    agent: str = DEFAULT_AGENT,
    model: str = DEFAULT_MODEL,
    workdir: str = ".",
    session_id: str = "",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Spawn one OpenCode worker for a goal. Returns the receipt as JSON."""
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal required")
    if agent not in ALLOWED_AGENTS:
        raise PermissionError(f"agent '{agent}' not allowlisted (JARVIS_SUBAGENTS)")
    if not OPENCODE_BIN:
        raise RuntimeError("opencode binary not found (OPENCODE_BIN)")
    directory = _resolve_workdir(workdir)

    cmd = [
        OPENCODE_BIN,
        "run",
        goal,
        "--format",
        "json",
        "--agent",
        agent,
        "-m",
        model,
        "--dir",
        str(directory),
    ]
    if session_id:
        cmd += ["-s", session_id]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(directory),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return json.dumps(
                {
                    "status": "timeout",
                    "session_id": session_id,
                    "agent": agent,
                    "summary": "",
                    "tokens": {},
                    "cost": 0.0,
                    "error": f"worker exceeded {timeout_s}s and was killed",
                }
            )
    except (OSError, PermissionError) as exc:
        raise RuntimeError(f"worker spawn failed: {exc}") from exc

    receipt = _parse_events(out.decode(errors="replace"))
    receipt["agent"] = agent
    if err:
        logger.warning("worker stderr: %s", err.decode(errors="replace")[:500])
    if proc.returncode not in (0, None) and receipt["status"] == "ok" and not receipt["summary"]:
        receipt["status"] = "error"
        receipt["error"] = receipt["error"] or f"exit {proc.returncode}"
    return json.dumps(receipt)


async def _run_plain(
    binary: str,
    args: list[str],
    workdir: str,
    timeout_s: int,
) -> dict:
    """Run a single-shot CLI worker (Hermes -z, dsh headless) to completion."""
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "timeout",
                "summary": "",
                "tokens": {},
                "cost": 0.0,
                "error": f"worker exceeded {timeout_s}s and was killed",
            }
    except (OSError, PermissionError) as exc:
        raise RuntimeError(f"worker spawn failed: {exc}") from exc
    text = out.decode(errors="replace").strip()
    suffix = "…[truncated]"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[: MAX_OUTPUT_CHARS - len(suffix)] + suffix
    return {
        "status": "ok" if text and proc.returncode in (0, None) else "error",
        "summary": text,
        "tokens": {},
        "cost": 0.0,
        "error": ""
        if text
        else (err.decode(errors="replace").strip()[:300] or f"exit {proc.returncode}"),
    }


@safety_gate(tier=SafetyTier.SENSITIVE, description="Spawn a sub-agent worker on any backend")
async def spawn_worker(
    goal: str,
    backend: str = "opencode",
    agent: str = DEFAULT_AGENT,
    model: str = DEFAULT_MODEL,
    workdir: str = ".",
    session_id: str = "",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Spawn a worker on a bridged backend (opencode | hermes | deepseek).

    Returns a worker receipt identical in shape to :func:`spawn_subagent`, so
    callers and the MCP mesh treat every backend uniformly. ``model`` only
    applies to opencode; hermes/dsh use their own configured models.
    """
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal required")
    if backend not in {"opencode", "hermes", "deepseek"}:
        raise ValueError(f"unknown backend '{backend}' (opencode|hermes|deepseek)")
    directory = _resolve_workdir(workdir)

    if backend == "opencode":
        return await spawn_subagent(
            goal=goal,
            agent=agent,
            model=model,
            workdir=str(directory),
            session_id=session_id,
            timeout_s=timeout_s,
        )

    if backend == "hermes":
        if not HERMES_BIN:
            raise RuntimeError("hermes binary not found (HERMES_BIN)")
        receipt = await _run_plain(HERMES_BIN, ["-z", goal], str(directory), timeout_s)
        receipt["agent"] = agent
        return json.dumps(receipt)

    # deepseek harness
    if not DSH_BIN:
        raise RuntimeError(
            "dsh binary not found (DSH_BIN). Build the DeepSeek harness first "
            "or run `pnpm build` in deepseek-harness/"
        )
    receipt = await _run_plain(DSH_BIN, ["--profile", "headless", goal], str(directory), timeout_s)
    receipt["agent"] = agent
    return json.dumps(receipt)


SUBAGENT_TOOLS = {
    "spawn_subagent": spawn_subagent,
    "spawn_worker": spawn_worker,
}
