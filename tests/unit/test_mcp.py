"""Unit tests for app/mcp/registry.py (MCPRegistry, MCPServer, MCPTool)."""

from app.mcp.registry import (
    MCPRegistry,
    MCPServer,
    MCPTool,
    MCPTransport,
    get_mcp_registry,
)


def test_mcp_transport_enum() -> None:
    assert MCPTransport.STDIO.value == "stdio"
    assert MCPTransport.HTTP.value == "http"
    assert MCPTransport.SSE.value == "sse"


def test_mcp_server_and_tool_dataclasses() -> None:
    server = MCPServer(
        name="github",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "secret"},
    )
    assert server.name == "github"
    assert server.transport == MCPTransport.STDIO
    assert server.command == "npx"
    assert server.args == ["-y", "@modelcontextprotocol/server-github"]
    assert server.env == {"GITHUB_TOKEN": "secret"}
    assert server.url is None
    assert server.enabled is True

    tool = MCPTool(
        name="get_file_contents",
        description="Retrieve repository file content",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        server_name="github",
    )
    assert tool.name == "get_file_contents"
    assert tool.description == "Retrieve repository file content"
    assert tool.server_name == "github"


def test_mcp_registry_workflow() -> None:
    reg = MCPRegistry()

    # Empty state
    assert reg.list_servers() == []
    assert reg.list_tools() == []
    assert reg.get_server("non_existent") is None
    assert reg.get_tool("non_existent") is None

    # Register server
    srv1 = MCPServer(name="srv1", transport=MCPTransport.HTTP, url="http://localhost:3000")
    reg.register_server(srv1)
    assert reg.get_server("srv1") == srv1
    assert len(reg.list_servers()) == 1

    # Register tools
    t1 = MCPTool(name="tool_1", description="Tool 1", parameters={}, server_name="srv1")
    t2 = MCPTool(name="tool_2", description="Tool 2", parameters={}, server_name="srv1")
    t3 = MCPTool(name="tool_3", description="Tool 3", parameters={}, server_name="other_srv")

    reg.register_tool(t1)
    reg.register_tool(t2)
    reg.register_tool(t3)

    assert len(reg.list_tools()) == 3
    assert reg.get_tool("tool_1") == t1
    assert reg.get_tool("tool_2") == t2

    # Unregister server srv1 should cascade and remove tool_1 and tool_2, but keep tool_3
    reg.unregister_server("srv1")
    assert reg.get_server("srv1") is None
    assert len(reg.list_servers()) == 0
    assert reg.get_tool("tool_1") is None
    assert reg.get_tool("tool_2") is None
    assert reg.get_tool("tool_3") == t3
    assert len(reg.list_tools()) == 1

    # Unregister non-existent server is a no-op
    reg.unregister_server("missing")


def test_get_mcp_registry_singleton() -> None:
    r1 = get_mcp_registry()
    r2 = get_mcp_registry()
    assert r1 is r2
    assert isinstance(r1, MCPRegistry)
