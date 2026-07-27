"""JARVIS Adapters Package (I/O Protocol Layer).

Exposes REST HTTP routes, WebSocket / SSE streaming adapters, and Bearer token security.
"""

from app.adapters.http.router import http_router, validate_api_key
from app.adapters.websocket.stream import ws_router

__all__ = [
    "http_router",
    "ws_router",
    "validate_api_key",
]
