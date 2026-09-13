"""MCP Client Manager — owns multiple MCP clients and their lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from app.guardrails.policy import ToolSafetyPolicy
from app.integrations.mcp.client import MCPClient
from app.integrations.mcp.transports import (
    MCPTransport,
    StdioTransport,
    StreamableHTTPTransport,
)
from app.integrations.mcp.types import (
    MCPResource,
    MCPServerConfig,
    MCPTool,
    TransportType,
)

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages multiple MCP server connections and their tool/resource registries.

    Responsibilities:
      - Register server configs and create the appropriate transport + client.
      - Connect/disconnect all servers.
      - Discover and cache tools/resources from each server.
      - Route tool calls through the safety gate before execution.
    """

    def __init__(self, policy: ToolSafetyPolicy | None = None) -> None:
        self._configs: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._server_tools: dict[str, list[str]] = {}
        self._policy = policy

    @property
    def policy(self) -> ToolSafetyPolicy | None:
        return self._policy

    @policy.setter
    def policy(self, value: ToolSafetyPolicy | None) -> None:
        self._policy = value

    def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration and create its client."""
        if not config.enabled:
            logger.info("Skipping disabled MCP server: %s", config.name)
            return
        self._configs[config.name] = config
        transport = self._create_transport(config)
        self._clients[config.name] = MCPClient(
            transport=transport,
            server_name=config.name,
            timeout=config.timeout_seconds,
        )
        logger.info("Registered MCP server: %s (%s)", config.name, config.transport.value)

    def _create_transport(self, config: MCPServerConfig) -> MCPTransport:
        """Instantiate the correct transport for a server config."""
        if config.transport == TransportType.STDIO:
            return StdioTransport(config.command, config.env)  # type: ignore[arg-type]
        if config.transport == TransportType.HTTP:
            return StreamableHTTPTransport(config.url, config.headers)  # type: ignore[arg-type]
        raise ValueError(f"Unsupported transport: {config.transport}")

    async def connect_all(self) -> dict[str, bool]:
        """Connect to all registered servers and discover their tools."""
        results: dict[str, bool] = {}
        for name, client in self._clients.items():
            try:
                await client.connect()
                await self._discover_tools(name, client)
                await self._discover_resources(name, client)
                results[name] = True
                logger.info("Connected to MCP server: %s", name)
            except Exception as exc:
                logger.error("Failed to connect to MCP server %s: %s", name, exc)
                results[name] = False
        return results

    async def _discover_tools(self, server_name: str, client: MCPClient) -> None:
        """Discover and cache tools from a connected server."""
        try:
            tools = await client.list_tools()
            self._server_tools[server_name] = []
            for tool in tools:
                self._tools[tool.name] = tool
                self._server_tools[server_name].append(tool.name)
            logger.info("Discovered %d tools from MCP server %s", len(tools), server_name)
        except Exception as exc:
            logger.error("Failed to discover tools from %s: %s", server_name, exc)

    async def _discover_resources(self, server_name: str, client: MCPClient) -> None:
        """Discover and cache resources from a connected server."""
        try:
            resources = await client.list_resources()
            for resource in resources:
                self._resources[resource.uri] = resource
            logger.info(
                "Discovered %d resources from MCP server %s",
                len(resources),
                server_name,
            )
        except Exception as exc:
            logger.error("Failed to discover resources from %s: %s", server_name, exc)

    async def disconnect_all(self) -> None:
        """Disconnect from all servers and clear caches."""
        for name, client in self._clients.items():
            try:
                await client.disconnect()
            except Exception as exc:
                logger.warning("Error disconnecting from %s: %s", name, exc)
        self._clients.clear()
        self._tools.clear()
        self._resources.clear()
        self._server_tools.clear()
        logger.info("MCP Client Manager shut down")

    def list_tools(self) -> list[MCPTool]:
        """List all discovered tools from all connected servers."""
        return list(self._tools.values())

    def get_tool(self, tool_name: str) -> MCPTool | None:
        """Get a tool by name."""
        return self._tools.get(tool_name)

    def get_server_tools(self, server_name: str) -> list[MCPTool]:
        """List tools for a specific server."""
        tool_names = self._server_tools.get(server_name, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def list_resources(self) -> list[MCPResource]:
        """List all discovered resources."""
        return list(self._resources.values())

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool by name, routed through the safety gate.

        Raises:
            ValueError: if the tool is not found.
            RuntimeError: if the server is not connected.
            PolicyViolationError: if the safety policy rejects the call.
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Route through safety gate — external capability must be gated.
        if self._policy is not None:
            self._policy.evaluate_tool_call(
                tool_name=tool_name,
                tier=tool.safety_tier,
                args=arguments,
                description=tool.description,
            )

        client = self._clients.get(tool.server_name)
        if not client or not client.is_connected:
            raise RuntimeError(f"Server {tool.server_name} not connected")
        return await client.call_tool(tool_name, arguments)

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource by URI from its owning server."""
        resource = self._resources.get(uri)
        if not resource:
            raise ValueError(f"Resource not found: {uri}")
        client = self._clients.get(resource.server_name)
        if not client or not client.is_connected:
            raise RuntimeError(f"Server {resource.server_name} not connected")
        return await client.read_resource(uri)
