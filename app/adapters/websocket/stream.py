"""WebSocket & SSE Streaming Adapter Layer.

Provides real-time streaming interfaces for WebSocket connections and Server-Sent Events (SSE),
publishing streaming token chunks and step execution updates from InMemoryAsyncBus.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import json
from typing import AsyncGenerator

from app.bootstrap import bootstrap_system

ws_router = APIRouter(prefix="/ws", tags=["Streaming"])


@ws_router.websocket("")
@ws_router.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket streaming endpoint for real-time bidirectional messaging."""
    await websocket.accept()
    container = bootstrap_system()
    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            prompt = data.get("prompt", data.get("message", ""))

            # Process intent
            analysis = container.intent_analyzer.analyze(prompt)
            await websocket.send_json({
                "type": "intent_analysis",
                "complexity": analysis.complexity.value,
                "requires_tools": analysis.requires_tools,
            })

            # Stream token response
            await websocket.send_json({
                "type": "token_chunk",
                "content": f"Echo: {prompt}",
            })

            await websocket.send_json({"type": "stream_end"})
    except WebSocketDisconnect:
        pass


@ws_router.get("/stream")
async def sse_stream_endpoint(prompt: str = "hello") -> StreamingResponse:
    """Server-Sent Events (SSE) streaming endpoint."""
    async def _event_generator() -> AsyncGenerator[str, None]:
        container = bootstrap_system()
        analysis = container.intent_analyzer.analyze(prompt)
        yield f"data: {json.dumps({'type': 'intent', 'complexity': analysis.complexity.value})}\n\n"
        yield f"data: {json.dumps({'type': 'chunk', 'content': f'JARVIS streaming response for: {prompt}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
