"""MCP client layer: connects to MCP servers, discovers tools, executes calls.

JARVIS port of the PROFESSOR-J MCP client, adapted to use ToolSafetyPolicy
for gating external capability calls.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from app.integrations.mcp.transports import (
    MCPTransport,
)
from app.integrations.mcp.types import (
    JSONRPCMessage,
    MCPResource,
    MCPTool,
)

logger = logging.getLogger(__name__)


class MCPClient:
    """High-level MCP client: connect, list tools, call tools.

    Each client wraps a single MCP server. The manager (``MCPClientManager``)
    owns multiple clients.
    """

    def __init__(
        self,
        transport: MCPTransport,
        server_name: str,
        timeout: float = 30.0,
    ) -> None:
        self._transport = transport
        self._server_name = server_name
        self._timeout = timeout
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._initialized = False
        self._server_info: dict[str, Any] = {}
        self._capabilities: dict[str, Any] = {}

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    @property
    def server_info(self) -> dict[str, Any]:
        return dict(self._server_info)

    @property
    def capabilities(self) -> dict[str, Any]:
        return dict(self._capabilities)

    async def connect(self) -> None:
        """Connect transport, start reader task, and initialize the session."""
        await self._transport.connect()
        self._reader_task = asyncio.create_task(self._read_messages())
        await self._initialize()

    async def disconnect(self) -> None:
        """Cancel the reader task and disconnect the transport."""
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        await self._transport.disconnect()
        self._initialized = False

    async def _initialize(self) -> None:
        """Send the MCP ``initialize`` request and notify initialized."""
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "clientInfo": {"name": "JARVIS", "version": "3.0.1"},
            },
        )
        self._server_info = result.get("serverInfo", {})
        self._capabilities = result.get("capabilities", {})
        self._initialized = True
        await self._send_notification("notifications/initialized", {})
        logger.info(
            "MCP client initialized with server '%s'",
            self._server_name,
        )

    async def _read_messages(self) -> None:
        """Background task: dispatch incoming messages to pending futures."""
        while self.is_connected:
            try:
                message = await self._transport.receive()
                if message is None:
                    break
                self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("MCP message reader error: %s", exc)
                break

    def _handle_message(self, message: JSONRPCMessage) -> None:
        """Route a received JSON-RPC message to its waiting future."""
        if message.id is not None and isinstance(message.id, int) and message.id in self._pending:
            future = self._pending.pop(message.id)
            if message.error:
                future.set_exception(
                    RuntimeError(message.error.get("message", "Unknown MCP error"))
                )
            else:
                future.set_result(message.result)

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and await the correlated response."""
        if not self.is_connected:
            raise RuntimeError("Not connected")
        self._request_id += 1
        request_id = self._request_id
        message = JSONRPCMessage(id=request_id, method=method, params=params or {})
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future
        await self._transport.send(message)
        try:
            return await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"MCP request '{method}' timed out after {self._timeout}s") from None

    async def _send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self.is_connected:
            raise RuntimeError("Not connected")
        message = JSONRPCMessage(method=method, params=params or {})
        await self._transport.send(message)

    # ── MCP Protocol Operations ─────────────────────────────────────────────

    async def list_tools(self) -> list[MCPTool]:
        """List tools available on this MCP server."""
        result = await self._send_request("tools/list", {})
        tools: list[MCPTool] = []
        for tool_data in result.get("tools", []):
            tools.append(
                MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=self._server_name,
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on this MCP server."""
        return await self._send_request("tools/call", {"name": name, "arguments": arguments})

    async def list_resources(self) -> list[MCPResource]:
        """List resources available on this MCP server."""
        result = await self._send_request("resources/list", {})
        resources: list[MCPResource] = []
        for res_data in result.get("resources", []):
            resources.append(
                MCPResource(
                    uri=res_data["uri"],
                    name=res_data.get("name", ""),
                    description=res_data.get("description"),
                    mime_type=res_data.get("mimeType"),
                    server_name=self._server_name,
                )
            )
        return resources

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource from this MCP server."""
        return await self._send_request("resources/read", {"uri": uri})

    async def subscribe_resource(self, uri: str) -> None:
        """Subscribe to resource update notifications."""
        await self._send_request("resources/subscribe", {"uri": uri})

    async def unsubscribe_resource(self, uri: str) -> None:
        """Unsubscribe from resource update notifications."""
        await self._send_request("resources/unsubscribe", {"uri": uri})
