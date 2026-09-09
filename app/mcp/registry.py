"""MCP Registry for JARVIS.

Manages MCP (Model Context Protocol) server connections and tool discovery.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class MCPTransport(str, Enum):
    """MCP transport protocols."""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


@dataclass
class MCPServer:
    """MCP Server configuration."""
    name: str
    transport: MCPTransport
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    enabled: bool = True


@dataclass
class MCPTool:
    """MCP Tool representation."""
    name: str
    description: str
    parameters: dict
    server_name: str


class MCPRegistry:
    """Registry for MCP servers and their tools."""
    
    def __init__(self) -> None:
        self._servers: Dict[str, MCPServer] = {}
        self._tools: Dict[str, MCPTool] = {}
    
    def register_server(self, server: MCPServer) -> None:
        """Register an MCP server."""
        self._servers[server.name] = server
    
    def unregister_server(self, name: str) -> None:
        """Unregister an MCP server and its tools."""
        if name in self._servers:
            del self._servers[name]
            # Remove tools from this server
            tools_to_remove = [k for k, v in self._tools.items() if v.server_name == name]
            for k in tools_to_remove:
                del self._tools[k]
    
    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool from an MCP server."""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[MCPTool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get server by name."""
        return self._servers.get(name)
    
    def list_servers(self) -> List[MCPServer]:
        """List all registered servers."""
        return list(self._servers.values())


# Global registry instance
_registry: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    """Get the global MCP registry instance."""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry