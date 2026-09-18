"""Unit tests for the JARVIS MCP mesh server (Sprint 8.5)."""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.mcp.server import _TOOLS, _dispatch


class TestMeshToolsRegistered:
    def test_mesh_tools_in_listing(self):
        names = [t["name"] for t in _TOOLS]
        for expected in (
            "jarvis_chat",
            "jarvis_brief",
            "jarvis_notify",
            "jarvis_read_emails",
            "jarvis_send_email",
            "jarvis_spawn_subagent",
        ):
            assert expected in names

    def test_mesh_tools_have_schemas(self):
        by_name = {t["name"]: t for t in _TOOLS}
        assert by_name["jarvis_chat"]["inputSchema"]["required"] == ["message"]
        assert by_name["jarvis_notify"]["inputSchema"]["required"] == ["title", "body"]
        assert by_name["jarvis_send_email"]["inputSchema"]["required"] == ["to", "subject", "body"]


class TestMeshDispatch:
    @pytest.mark.asyncio
    async def test_jarvis_brief(self):
        with patch(
            "app.integrations.brief.BriefService.generate_brief",
            new=AsyncMock(return_value={"greeting": "Hi", "sections": []}),
        ):
            out = await _dispatch("jarvis_brief", {})
        assert "Hi" in out

    @pytest.mark.asyncio
    async def test_jarvis_chat(self):
        with patch(
            "app.adapters.web.router.chat",
            new=AsyncMock(return_value={"response": "hello back"}),
        ):
            out = await _dispatch("jarvis_chat", {"message": "hi"})
        assert out == "hello back"

    @pytest.mark.asyncio
    async def test_jarvis_notify_push(self):
        with patch(
            "app.integrations.push.PushService.send",
            new=AsyncMock(return_value={"success": 1, "failed": 0, "total": 1}),
        ):
            out = await _dispatch(
                "jarvis_notify", {"title": "T", "body": "B", "channels": "push"}
            )
        assert "success" in out

    @pytest.mark.asyncio
    async def test_jarvis_spawn_subagent(self):
        with patch(
            "app.tools.subagent_tools.spawn_subagent",
            new=AsyncMock(return_value=json.dumps({"status": "ok"})),
        ):
            out = await _dispatch(
                "jarvis_spawn_subagent", {"goal": "do it", "timeout_s": 60}
            )
        assert "ok" in out

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        with pytest.raises(ValueError):
            await _dispatch("nope", {})


class TestAuth:
    def test_auth_rejects_mismatch(self):
        from app.integrations.mcp.server import _on_call_tool

        request = MagicMock()
        request.name = "jarvis_brief"
        request.arguments = {}
        with (
            patch.dict(os.environ, {"JARVIS_MCP_KEY": "secret", "JARVIS_API_KEY": "wrong"}),
            patch("app.integrations.mcp.server._dispatch", new=AsyncMock()),
        ):
            result = asyncio_run(_on_call_tool(None, request))
        assert result.is_error is True
        assert "unauthorized" in result.content[0].text


def asyncio_run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


class TestMeshWorkerBridge:
    def test_spawn_worker_tool_listed(self):
        names = [t["name"] for t in _TOOLS]
        assert "jarvis_spawn_worker" in names

    @pytest.mark.asyncio
    async def test_spawn_worker_dispatch(self):
        from app.integrations.mcp.server import _dispatch

        with patch(
            "app.tools.subagent_tools.spawn_worker",
            new=AsyncMock(return_value=json.dumps({"status": "ok"})),
        ):
            out = await _dispatch(
                "jarvis_spawn_worker", {"goal": "do", "backend": "hermes", "timeout_s": 30}
            )
        assert "ok" in out
