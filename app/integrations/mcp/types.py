"""MCP protocol types: JSON-RPC message envelope, tool/resource/config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.domain.plan import SafetyTier


class TransportType(str, Enum):
    """MCP transport type identifier."""

    STDIO = "stdio"
    HTTP = "http"


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    """Configuration for connecting to an MCP server.

    Transport:
      - STDIO: spawns a subprocess, communicates over stdin/stdout.
      - HTTP: connects to a remote Streamable HTTP + SSE endpoint.
    """

    name: str
    transport: TransportType
    command: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    timeout_seconds: float = 30.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.transport == TransportType.STDIO and not self.command:
            raise ValueError(f"Stdio server '{self.name}' requires a command")
        if self.transport == TransportType.HTTP and not self.url:
            raise ValueError(f"HTTP server '{self.name}' requires a url")


@dataclass(frozen=True, slots=True)
class MCPTool:
    """A callable tool exposed by an MCP server.

    Mirrors the MCP ``tools/list`` response shape, enriched with the originating
    server name so tools from multiple servers can be namespaced.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    # External MCP tools may have side effects; default to SENSITIVE so they are
    # gated by the safety policy before execution.
    safety_tier: SafetyTier = SafetyTier.SENSITIVE


@dataclass(frozen=True, slots=True)
class MCPResource:
    """A readable resource exposed by an MCP server."""

    uri: str
    name: str
    description: str | None
    mime_type: str | None
    server_name: str


@dataclass
class JSONRPCMessage:
    """A single JSON-RPC 2.0 envelope used by MCP."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JSONRPCMessage:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    @property
    def is_request(self) -> bool:
        return self.method is not None and self.id is not None

    @property
    def is_notification(self) -> bool:
        return self.method is not None and self.id is None

    @property
    def is_response(self) -> bool:
        return self.id is not None and self.method is None


@dataclass
class MCPToolCallResult:
    """Normalized result of an MCP ``tools/call`` invocation."""

    content: list[dict[str, Any]] | None = None
    is_error: bool = False
    error_message: str | None = None
