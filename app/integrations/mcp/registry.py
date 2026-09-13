"""MCP registry: discovery, caching, and tool search."""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.mcp.types import MCPResource, MCPTool

logger = logging.getLogger(__name__)


class MCPRegistry:
    """Discover and cache MCP tools and resources.

    Lists tools once, caches the result, and lets each run request
    a filtered view so only relevant tools are surfaced.
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._server_tools: dict[str, list[str]] = {}
        self._tools_cached = False
        self._resources_cached = False

    @property
    def is_tools_cached(self) -> bool:
        return self._tools_cached

    @property
    def is_resources_cached(self) -> bool:
        return self._resources_cached

    def ingest_tools(self, server_name: str, tools: list[MCPTool]) -> None:
        """Ingest tools from a server into the registry."""
        # Clear previous tools for this server to handle reconnection
        if server_name in self._server_tools:
            for old_name in self._server_tools[server_name]:
                self._tools.pop(old_name, None)
        self._server_tools[server_name] = []
        for tool in tools:
            self._tools[tool.name] = tool
            self._server_tools[server_name].append(tool.name)
        self._tools_cached = True

    def ingest_resources(self, resources: list[MCPResource]) -> None:
        """Ingest resources into the registry."""
        for resource in resources:
            self._resources[resource.uri] = resource
        self._resources_cached = True

    def list_tools(self) -> list[MCPTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def tools_by_server(self, server_name: str | None = None) -> list[MCPTool]:
        """List tools, optionally filtered to one server."""
        if server_name is None:
            return self.list_tools()
        names = self._server_tools.get(server_name, [])
        return [self._tools[n] for n in names if n in self._tools]

    def list_resources(self) -> list[MCPResource]:
        """List all registered resources."""
        return list(self._resources.values())

    def invalidate_tools(self) -> None:
        """Drop the cached tool list."""
        self._tools.clear()
        self._server_tools.clear()
        self._tools_cached = False

    def invalidate_resources(self) -> None:
        """Drop the cached resource list."""
        self._resources.clear()
        self._resources_cached = False

    def invalidate_all(self) -> None:
        """Drop all caches."""
        self.invalidate_tools()
        self.invalidate_resources()


class MCPToolSearch:
    """On-demand tool search across the MCP registry.

    Provides keyword search and schema retrieval for tools, following the
    on-demand loading pattern that keeps model context small.
    """

    def __init__(self, registry: MCPRegistry) -> None:
        self._registry = registry
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def search(self, query: str, server_name: str | None = None) -> list[MCPTool]:
        """Search for tools whose name or description matches the query."""
        q = query.lower()
        return [
            tool
            for tool in self._registry.tools_by_server(server_name)
            if q in tool.name.lower() or q in tool.description.lower()
        ]

    def tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Get the input schema for a tool, cached after first fetch.

        Raises:
            KeyError: if the tool is not found.
        """
        cached = self._schema_cache.get(tool_name)
        if cached is not None:
            return cached
        tool = self._registry.get_tool(tool_name)
        if not tool:
            raise KeyError(f"Tool not found: {tool_name}")
        self._schema_cache[tool_name] = tool.input_schema
        return tool.input_schema

    def filter_by_params(self, required_params: list[str]) -> list[MCPTool]:
        """Return tools whose input schema contains all required parameters."""
        result = []
        for tool in self._registry.list_tools():
            props = tool.input_schema.get("properties", {})
            if all(p in props for p in required_params):
                result.append(tool)
        return result

    def best_for_task(self, task_description: str) -> MCPTool | None:
        """Find the best matching tool for a task description.

        Uses simple scoring: name match scores higher than description match.
        """
        q = task_description.lower()
        best_tool: MCPTool | None = None
        best_score = 0
        for tool in self._registry.list_tools():
            score = 0
            if q in tool.name.lower():
                score += 10
            if q in tool.description.lower():
                score += 5
            for prop in tool.input_schema.get("properties", {}):
                if q in prop.lower():
                    score += 2
            if score > best_score:
                best_score = score
                best_tool = tool
        return best_tool

    def invalidate_cache(self) -> None:
        """Clear the schema cache."""
        self._schema_cache.clear()


__all__ = ["MCPRegistry", "MCPToolSearch"]
