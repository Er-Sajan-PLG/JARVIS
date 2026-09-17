"""Tests for the JARVIS MCP server."""

import asyncio

import pytest

from app.integrations.mcp.server import (
    _dispatch,
    _workspace_git_state,
    create_server,
    get_global_policy,
)


class TestMCPServer:
    def test_create_server(self):
        """Server instantiates with a name."""
        server = create_server()
        assert server is not None

    def test_get_global_policy(self):
        """Global policy is available."""
        policy = get_global_policy()
        assert policy is not None

    async def test_dispatch_workspace_git_state(self):
        """workspace_git_state returns real git state."""
        result = await _dispatch("workspace_git_state", {})
        assert isinstance(result, str)
        assert "head=" in result
        assert "branch=" in result
        assert "dirty=" in result

    async def test_dispatch_session_get(self):
        """session_get returns session info."""
        result = await _dispatch("session_get", {"session_id": "default"})
        assert "session_id=default" in result

    async def test_dispatch_memory_retrieve(self):
        """memory_retrieve returns memories (even if empty)."""
        result = await _dispatch("memory_retrieve", {"query": "test"})
        assert isinstance(result, str)

    async def test_dispatch_unknown_tool(self):
        """Unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await _dispatch("bogus_tool", {})


class TestMCPServerIntegration:
    """Integration test: list tools via the server's callback."""

    async def test_list_tools(self):
        """Server lists tools correctly."""
        from app.integrations.mcp.server import _on_list_tools

        result = await _on_list_tools(None, None)
        assert hasattr(result, "tools")
        names = [t.name for t in result.tools]
        assert "read_file" in names
        assert "workspace_git_state" in names
        assert len(names) == 11