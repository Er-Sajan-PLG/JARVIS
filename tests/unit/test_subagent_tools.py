"""Tests for the sub-agent runner (OpenCode workers, mocked subprocess)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools import DEFAULT_TOOLSET
from app.tools.subagent_tools import (
    _parse_events,
    _resolve_workdir,
    spawn_subagent,
    spawn_worker,
)


def _event(kind, **extra):
    base = {"type": kind, "timestamp": 1, "sessionID": "ses_test123"}
    base.update(extra)
    return json.dumps(base)


SAMPLE_STREAM = "\n".join([
    _event("step_start"),
    _event("text", part={"type": "text", "text": "done thing"}),
    _event(
        "step_finish",
        part={"tokens": {"total": 10}, "cost": 0.01},
    ),
])


class TestParseEvents:
    def test_ok_receipt(self):
        receipt = _parse_events(SAMPLE_STREAM)
        assert receipt["status"] == "ok"
        assert receipt["session_id"] == "ses_test123"
        assert receipt["summary"] == "done thing"
        assert receipt["tokens"] == {"total": 10}

    def test_error_event(self):
        raw = _event("error", error={"data": {"message": "boom"}})
        receipt = _parse_events(raw)
        assert receipt["status"] == "error"
        assert receipt["error"] == "boom"

    def test_garbage_lines_ignored(self):
        receipt = _parse_events("not json\n" + SAMPLE_STREAM)
        assert receipt["status"] == "ok"

    def test_output_bounded(self):
        big = _event("text", part={"type": "text", "text": "x" * 30000})
        receipt = _parse_events(big)
        assert len(receipt["summary"]) <= 20001


class TestWorkdirPolicy:
    def test_tmp_allowed(self):
        assert _resolve_workdir("/tmp/x").is_absolute()

    def test_home_refused(self):
        with pytest.raises(PermissionError):
            _resolve_workdir("/home/testuser/secret")

    def test_etc_refused(self):
        with pytest.raises(PermissionError):
            _resolve_workdir("/etc")


class TestSpawn:
    def _proc(self, out, returncode=0):
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(out.encode(), b""))
        proc.returncode = returncode
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        return proc

    @pytest.mark.asyncio
    async def test_agent_allowlist(self):
        with pytest.raises(PermissionError):
            await spawn_subagent("hi", agent="evil-agent")

    @pytest.mark.asyncio
    async def test_empty_goal(self):
        with pytest.raises(ValueError):
            await spawn_subagent("  ")

    @pytest.mark.asyncio
    async def test_ok_run(self):
        proc = self._proc(SAMPLE_STREAM)
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            out = await spawn_subagent("do thing", workdir="/tmp")
        receipt = json.loads(out)
        assert receipt["status"] == "ok"
        assert receipt["agent"] == "build"
        assert receipt["summary"] == "done thing"

    @pytest.mark.asyncio
    async def test_session_threading(self):
        proc = self._proc(SAMPLE_STREAM)
        seen = {}

        async def fake_exec(*cmd, **kwargs):
            seen["cmd"] = cmd
            return proc

        with patch("asyncio.create_subprocess_exec", new=fake_exec):
            await spawn_subagent("again", session_id="ses_abc", workdir="/tmp")
        assert "-s" in seen["cmd"] and "ses_abc" in seen["cmd"]

    @pytest.mark.asyncio
    async def test_timeout_kills(self):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=TimeoutError())
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            out = await spawn_subagent("hang", timeout_s=1, workdir="/tmp")
        receipt = json.loads(out)
        assert receipt["status"] == "timeout"
        proc.kill.assert_called_once()

    def test_registered(self):
        assert DEFAULT_TOOLSET["spawn_subagent"] is spawn_subagent


class TestSpawnWorkerBridge:
    def _proc(self, text, returncode=0):
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(text.encode(), b""))
        proc.returncode = returncode
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        return proc

    @pytest.mark.asyncio
    async def test_hermes_backend(self):
        proc = self._proc("HERMES-OK")
        with patch(
            "app.tools.subagent_tools.HERMES_BIN", "/usr/bin/hermes", create=True
        ), patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            out = json.loads(await spawn_worker("hi", backend="hermes", workdir="/tmp"))
        assert out["status"] == "ok"
        assert out["summary"] == "HERMES-OK"

    @pytest.mark.asyncio
    async def test_unknown_backend(self):
        with pytest.raises(ValueError):
            await spawn_worker("hi", backend="claude")

    @pytest.mark.asyncio
    async def test_deepseek_missing_command(self):
        with patch("app.tools.subagent_tools.DSH_CMD", "", create=True), pytest.raises(
            RuntimeError, match="dsh command not configured"
        ):
            await spawn_worker("hi", backend="deepseek", workdir="/tmp")

    @pytest.mark.asyncio
    async def test_deepseek_backend(self):
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"DSH-OK", b""))
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        with (
            patch("app.tools.subagent_tools.DSH_CMD", "node /x/bin.js", create=True),
            patch("app.tools.subagent_tools.DSH_DIR", "/tmp", create=True),
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)) as exec_,
        ):
            out = json.loads(await spawn_worker("hi", backend="deepseek", workdir="/tmp"))
        assert out["status"] == "ok"
        assert out["summary"] == "DSH-OK"
        # runs from harness dir, node first, headless profile injected
        args, _ = exec_.call_args
        assert args[0] == "node" and args[1] == "/x/bin.js"
        assert "--profile" in args and "headless" in args

    @pytest.mark.asyncio
    async def test_hermes_timeout(self):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=TimeoutError())
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        with patch(
            "app.tools.subagent_tools.HERMES_BIN", "/usr/bin/hermes", create=True
        ), patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            out = json.loads(
                await spawn_worker("hang", backend="hermes", workdir="/tmp", timeout_s=1)
            )
        assert out["status"] == "timeout"
        proc.kill.assert_called_once()

    def test_registered(self):
        from app.tools.subagent_tools import spawn_worker

        assert DEFAULT_TOOLSET["spawn_worker"] is spawn_worker
