"""Tests for the MCP client (Sprint 3 Capability Contract)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain import SafetyTier
from app.guardrails import ToolSafetyPolicy
from app.integrations.mcp.client import MCPClient
from app.integrations.mcp.manager import MCPClientManager
from app.integrations.mcp.registry import MCPRegistry, MCPToolSearch
from app.integrations.mcp.types import (
    JSONRPCMessage,
    MCPResource,
    MCPServerConfig,
    MCPTool,
    TransportType,
)

# ---------------------------------------------------------------------------
# JSONRPCMessage
# ---------------------------------------------------------------------------


class TestJSONRPCMessage:
    def test_request_round_trip(self):
        msg = JSONRPCMessage(id=1, method="tools/list", params={})
        parsed = JSONRPCMessage.from_dict(msg.to_dict())
        assert parsed.id == 1
        assert parsed.method == "tools/list"

    def test_result_is_response(self):
        msg = JSONRPCMessage(id="a", result={"tools": []})
        assert msg.is_response
        assert not msg.is_request

    def test_notification(self):
        msg = JSONRPCMessage(method="notifications/initialized")
        assert msg.is_notification
        assert not msg.is_request

    def test_error_round_trip(self):
        msg = JSONRPCMessage(id=1, error={"code": -1, "message": "fail"})
        parsed = JSONRPCMessage.from_dict(msg.to_dict())
        assert parsed.error["message"] == "fail"


# ---------------------------------------------------------------------------
# MCPServerConfig
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    def test_stdio_requires_command(self):
        with pytest.raises(ValueError, match="requires a command"):
            MCPServerConfig(name="x", transport=TransportType.STDIO)

    def test_http_requires_url(self):
        with pytest.raises(ValueError, match="requires a url"):
            MCPServerConfig(name="x", transport=TransportType.HTTP)

    def test_valid_stdio_config(self):
        cfg = MCPServerConfig(
            name="local", transport=TransportType.STDIO, command=["python", "s.py"]
        )
        assert cfg.name == "local"
        assert cfg.timeout_seconds == 30.0
        assert cfg.enabled is True


# ---------------------------------------------------------------------------
# MCPClientManager
# ---------------------------------------------------------------------------


class TestMCPClientManager:
    def _config(self) -> MCPServerConfig:
        return MCPServerConfig(
            name="test",
            transport=TransportType.STDIO,
            command=["echo", "hello"],
        )

    def test_register_creates_client(self):
        mgr = MCPClientManager(policy=ToolSafetyPolicy())
        mgr.register_server(self._config())
        assert "test" in mgr._clients
        assert isinstance(mgr._clients["test"], MCPClient)

    def test_register_disabled_skips(self):
        cfg = MCPServerConfig(
            name="disabled",
            transport=TransportType.STDIO,
            command=["echo"],
            enabled=False,
        )
        mgr = MCPClientManager()
        mgr.register_server(cfg)
        assert "disabled" not in mgr._clients

    def test_list_tools_empty(self):
        mgr = MCPClientManager()
        assert mgr.list_tools() == []

    def test_get_tool_missing(self):
        mgr = MCPClientManager()
        assert mgr.get_tool("nope") is None

    def test_policy_default_none(self):
        mgr = MCPClientManager()
        assert mgr.policy is None


# ---------------------------------------------------------------------------
# MCPRegistry
# ---------------------------------------------------------------------------


def _make_tool(name: str, server: str = "s1", desc: str = "") -> MCPTool:
    return MCPTool(name=name, description=desc, input_schema={"type": "object"}, server_name=server)


class TestMCPRegistry:
    def test_ingest_and_list(self):
        reg = MCPRegistry()
        reg.ingest_tools("s1", [_make_tool("t1"), _make_tool("t2")])
        assert len(reg.list_tools()) == 2

    def test_ingest_replaces_server_tools(self):
        reg = MCPRegistry()
        reg.ingest_tools("s1", [_make_tool("t1")])
        reg.ingest_tools("s1", [_make_tool("t2"), _make_tool("t3")])
        assert len(reg.tools_by_server("s1")) == 2

    def test_tools_by_server_filter(self):
        reg = MCPRegistry()
        reg.ingest_tools("s1", [_make_tool("t1")])
        reg.ingest_tools("s2", [_make_tool("t2")])
        assert len(reg.tools_by_server("s1")) == 1
        assert len(reg.tools_by_server()) == 2

    def test_invalidate_tools(self):
        reg = MCPRegistry()
        reg.ingest_tools("s1", [_make_tool("t1")])
        reg.invalidate_tools()
        assert reg.list_tools() == []


# ---------------------------------------------------------------------------
# MCPToolSearch
# ---------------------------------------------------------------------------


class TestMCPToolSearch:
    def _search(self) -> MCPToolSearch:
        reg = MCPRegistry()
        reg.ingest_tools(
            "s1",
            [
                _make_tool("search_web", desc="Search the web"),
                _make_tool("read_file", desc="Read a file"),
            ],
        )
        return MCPToolSearch(reg)

    def test_search_by_name(self):
        results = self._search().search("search")
        assert len(results) == 1
        assert results[0].name == "search_web"

    def test_search_by_description(self):
        results = self._search().search("file")
        assert len(results) == 1
        assert results[0].name == "read_file"

    def test_tool_schema(self):
        search = self._search()
        assert search.tool_schema("search_web") == {"type": "object"}

    def test_tool_schema_missing(self):
        search = self._search()
        with pytest.raises(KeyError, match="Tool not found"):
            search.tool_schema("missing")

    def test_best_for_task(self):
        search = self._search()
        # "search" appears in search_web's name (score 10) — clear winner.
        best = search.best_for_task("search")
        assert best is not None
        assert best.name == "search_web"

    def test_filter_by_params(self):
        reg = MCPRegistry()
        reg.ingest_tools(
            "s1",
            [
                MCPTool(
                    name="has_q",
                    description="",
                    input_schema={"type": "object", "properties": {"q": {}}},
                    server_name="s1",
                ),
                MCPTool(
                    name="no_q",
                    description="",
                    input_schema={"type": "object", "properties": {"x": {}}},
                    server_name="s1",
                ),
            ],
        )
        search = MCPToolSearch(reg)
        results = search.filter_by_params(["q"])
        assert [t.name for t in results] == ["has_q"]

    def test_invalidate_cache(self):
        search = self._search()
        search.tool_schema("search_web")
        assert search._schema_cache
        search.invalidate_cache()
        assert search._schema_cache == {}

    def test_search_no_match(self):
        results = self._search().search("nonexistent")
        assert results == []


class TestMCPRegistryResources:
    def test_ingest_resources(self):
        reg = MCPRegistry()
        res = MCPResource(
            uri="file:///a", name="a", description=None, mime_type=None, server_name="s1"
        )
        reg.ingest_resources([res])
        assert reg.list_resources() == [res]

    def test_invalidate_resources(self):
        reg = MCPRegistry()
        res = MCPResource(
            uri="file:///a", name="a", description=None, mime_type=None, server_name="s1"
        )
        reg.ingest_resources([res])
        reg.invalidate_resources()
        assert reg.list_resources() == []

    def test_invalidate_all(self):
        reg = MCPRegistry()
        reg.ingest_tools("s1", [_make_tool("t1")])
        res = MCPResource(
            uri="file:///a", name="a", description=None, mime_type=None, server_name="s1"
        )
        reg.ingest_resources([res])
        reg.invalidate_all()
        assert reg.list_tools() == []
        assert reg.list_resources() == []


# ---------------------------------------------------------------------------
# MCPClient (transport mocked)
# ---------------------------------------------------------------------------


class TestMCPClient:
    def _client(self) -> MCPClient:
        transport = MagicMock()
        transport.is_connected = True
        return MCPClient(transport=transport, server_name="test", timeout=5.0)

    def test_client_construction(self):
        c = self._client()
        assert c.server_name == "test"
        assert c.is_connected is True

    async def test_list_tools_parses(self):
        c = self._client()
        c._send_request = AsyncMock(
            return_value={
                "tools": [{"name": "t1", "description": "d1", "inputSchema": {"type": "object"}}]
            }
        )
        tools = await c.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "t1"
        assert tools[0].server_name == "test"
        assert tools[0].safety_tier == SafetyTier.SENSITIVE

    async def test_list_resources_parses(self):
        c = self._client()
        c._send_request = AsyncMock(return_value={"resources": [{"uri": "file:///x", "name": "x"}]})
        resources = await c.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == "file:///x"

    async def test_send_request_times_out_pending_entry_removed(self):
        # A bare client whose transport never resolves should time out cleanly.
        c = self._client()
        c._timeout = 0.05
        c._transport.send = AsyncMock()
        with pytest.raises(TimeoutError):
            await c._send_request("tools/list", {})
        # The pending entry is cleaned up on timeout.
        assert c._pending == {}

    async def test_read_resource(self):
        c = self._client()
        c._send_request = AsyncMock(return_value={"contents": [{"uri": "file:///x"}]})
        result = await c.read_resource("file:///x")
        assert result["contents"][0]["uri"] == "file:///x"

    async def test_call_tool(self):
        c = self._client()
        c._send_request = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
        result = await c.call_tool("search_web", {"q": "cats"})
        assert result["content"][0]["text"] == "ok"

    async def test_initialize_sets_capabilities(self):
        c = self._client()
        c._send_request = AsyncMock(
            return_value={"serverInfo": {"name": "s"}, "capabilities": {"tools": {}}}
        )
        # _send_notification uses transport.send
        c._transport.send = AsyncMock()
        await c._initialize()
        assert c.server_info == {"name": "s"}
        assert c.capabilities == {"tools": {}}
        assert c._transport.send.called

    async def test_connect_and_disconnect(self):
        c = self._client()
        c._transport.connect = AsyncMock()
        c._transport.disconnect = AsyncMock()
        c._initialize = AsyncMock()
        await c.connect()
        assert c._transport.connect.called
        assert c._reader_task is not None
        await c.disconnect()
        assert c._transport.disconnect.called


# ---------------------------------------------------------------------------
# MCPClientManager connection lifecycle
# ---------------------------------------------------------------------------


class TestMCPClientManagerLifecycle:
    def _config(self) -> MCPServerConfig:
        return MCPServerConfig(
            name="test",
            transport=TransportType.STDIO,
            command=["echo", "hello"],
        )

    async def test_connect_all_success(self):
        mgr = MCPClientManager()
        mgr.register_server(self._config())
        client = mgr._clients["test"]
        client.connect = AsyncMock()
        client.list_tools = AsyncMock(return_value=[_make_tool("t1", server="test")])
        client.list_resources = AsyncMock(return_value=[])
        results = await mgr.connect_all()
        assert results == {"test": True}
        assert mgr.get_tool("t1") is not None

    async def test_connect_all_failure_isolated(self):
        mgr = MCPClientManager()
        mgr.register_server(self._config())
        client = mgr._clients["test"]
        client.connect = AsyncMock(side_effect=RuntimeError("boom"))
        results = await mgr.connect_all()
        assert results == {"test": False}

    async def test_disconnect_all(self):
        mgr = MCPClientManager()
        mgr.register_server(self._config())
        client = mgr._clients["test"]
        client.disconnect = AsyncMock()
        await mgr.disconnect_all()
        assert client.disconnect.called
        assert mgr._clients == {}

    async def test_call_tool_routes_through_gate(self):
        policy = ToolSafetyPolicy(auto_approve_sensitive=True)
        mgr = MCPClientManager(policy=policy)
        mgr.register_server(self._config())
        client = mgr._clients["test"]
        # MCPClient.is_connected delegates to the transport; make it report connected.
        client._transport = MagicMock()
        client._transport.is_connected = True
        client.call_tool = AsyncMock(return_value={"ok": True})
        mgr._tools = {"t1": _make_tool("t1", server="test")}
        result = await mgr.call_tool("t1", {"a": 1})
        assert result == {"ok": True}

    async def test_call_tool_server_not_connected(self):
        mgr = MCPClientManager()
        mgr.register_server(self._config())
        mgr._tools = {"t1": _make_tool("t1", server="test")}
        with pytest.raises(RuntimeError, match="not connected"):
            await mgr.call_tool("t1", {})

    async def test_read_resource_not_found(self):
        mgr = MCPClientManager()
        with pytest.raises(ValueError, match="Resource not found"):
            await mgr.read_resource("file:///missing")
