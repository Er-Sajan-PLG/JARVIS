"""JARVIS integration with the Model Context Protocol (MCP).

Port of the MCP client pattern from PROFESSOR-J, adapted to JARVIS's
architecture (ToolSafetyPolicy for safety gating, SafetyTier for tiers).

Supports two transports:

- **stdio**: launch an MCP server as a subprocess, communicate over pipes.
- **Streamable HTTP**: connect to a remote MCP server over HTTP/SSE.

External MCP capability calls are *always* routed through the safety policy
(fail closed — if no policy is wired, external tool execution is refused).
"""

from app.integrations.mcp.client import MCPClient
from app.integrations.mcp.manager import MCPClientManager
from app.integrations.mcp.registry import MCPRegistry, MCPToolSearch
from app.integrations.mcp.transports import (
    MCPTransport,
    StdioTransport,
    StreamableHTTPTransport,
)
from app.integrations.mcp.types import (
    JSONRPCMessage,
    MCPResource,
    MCPServerConfig,
    MCPTool,
    MCPToolCallResult,
    TransportType,
)

__all__ = [
    # Client / Manager
    "MCPClient",
    "MCPClientManager",
    # Registry / Search
    "MCPRegistry",
    "MCPToolSearch",
    # Transports
    "MCPTransport",
    "StdioTransport",
    "StreamableHTTPTransport",
    # Types
    "JSONRPCMessage",
    "MCPServerConfig",
    "MCPResource",
    "MCPTool",
    "MCPToolCallResult",
    "TransportType",
]
