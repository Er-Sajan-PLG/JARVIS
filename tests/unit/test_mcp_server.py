"""Tests for the JARVIS MCP server."""

import pytest

from app.integrations.mcp.server import (
    _dispatch,
    create_server,
    get_global_policy,
)


class TestMCPServer:
    def test_create_server_is_the_capability_server(self):
        """The server carries JARVIS's identity, not merely a truthy value.

        ``assert server is not None`` could never fail -- ``create_server()``
        constructs a ``Server`` unconditionally -- so it asserted nothing about
        the thing it named (F-TEST-010). The name is the observable contract the
        MCP handshake advertises.
        """
        server = create_server()
        assert server.name == "jarvis-capability-server"

    def test_get_global_policy_returns_a_policy_and_reuses_it(self):
        """The policy is a ``ToolSafetyPolicy``, and the singleton is stable.

        ``assert policy is not None`` was the same unsatisfiable form. The
        function's actual contract is in its body: it creates a default only when
        none is set, then returns the global. Pinning identity is what makes a
        regression from "reuse" to "new object each call" visible.
        """
        first = get_global_policy()
        second = get_global_policy()
        assert type(first).__name__ == "ToolSafetyPolicy"
        assert first is second, "get_global_policy() stopped returning the shared policy"

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
        assert len(names) == 18
