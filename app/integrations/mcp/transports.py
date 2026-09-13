"""MCP transport implementations (stdio + Streamable HTTP)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.integrations.mcp.types import JSONRPCMessage

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """Abstract transport for MCP communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish the transport connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport connection."""

    @abstractmethod
    async def send(self, message: JSONRPCMessage) -> None:
        """Send a message."""

    @abstractmethod
    async def receive(self) -> JSONRPCMessage | None:
        """Receive a message. Returns None on EOF/close."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""


class StdioTransport(MCPTransport):
    """Stdio transport for MCP servers launched as subprocesses."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._reader = self._process.stdout
        self._writer = self._process.stdin
        self._connected = True
        logger.info("MCP stdio transport connected: %s", self._command)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._writer:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
        if self._process:
            self._process.terminate()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            if self._process.returncode is None:
                self._process.kill()
                await self._process.wait()
        self._connected = False
        logger.info("MCP stdio transport disconnected")

    async def send(self, message: JSONRPCMessage) -> None:
        if not self._connected or not self._writer:
            raise RuntimeError("Transport not connected")
        data = json.dumps(message.to_dict()) + "\n"
        self._writer.write(data.encode())
        await self._writer.drain()

    async def receive(self) -> JSONRPCMessage | None:
        if not self._connected or not self._reader:
            return None
        try:
            line = await self._reader.readline()
            if not line:
                return None
            text = line.decode("utf-8").strip()
            if not text:
                return None
            return JSONRPCMessage.from_dict(json.loads(text))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Failed to decode MCP message: %s", exc)
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None and self._process.returncode is None


class StreamableHTTPTransport(MCPTransport):
    """Streamable HTTP transport for MCP servers over HTTP/SSE."""

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._client: Any = None
        self._connected = False
        self._message_queue: asyncio.Queue[JSONRPCMessage] = asyncio.Queue()
        self._sse_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        if self._connected:
            return
        import httpx

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=httpx.Timeout(self._timeout),
        )
        self._sse_task = asyncio.create_task(self._listen_sse())
        self._connected = True
        logger.info("MCP HTTP transport connected: %s", self._base_url)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._sse_task:
            self._sse_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sse_task
        if self._client:
            await self._client.aclose()
        self._connected = False
        logger.info("MCP HTTP transport disconnected")

    async def _listen_sse(self) -> None:
        """Background task reading server-sent events into the message queue."""
        try:
            async with self._client.stream(
                "GET",
                "/events",
                headers={"Accept": "text/event-stream"},
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            msg = JSONRPCMessage.from_dict(json.loads(data))
                            await self._message_queue.put(msg)
                        except json.JSONDecodeError:
                            pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("SSE listener error: %s", exc)

    async def send(self, message: JSONRPCMessage) -> None:
        if not self._connected or not self._client:
            raise RuntimeError("Transport not connected")
        response = await self._client.post(
            "/messages",
            json=message.to_dict(),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    async def receive(self) -> JSONRPCMessage | None:
        if not self._connected:
            return None
        try:
            return await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
        except TimeoutError:
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None
