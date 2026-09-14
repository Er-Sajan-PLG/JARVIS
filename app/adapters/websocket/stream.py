"""WebSocket & SSE Streaming Adapter Layer."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from app.adapters.security import is_authorized_for_streaming
from app.bootstrap import bootstrap_system

ws_router = APIRouter(prefix="/ws", tags=["Streaming"])


@ws_router.websocket("/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str) -> None:
    """Real-time chat via WebSocket."""
    if not is_authorized_for_streaming(websocket.headers, websocket.query_params):
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    container = bootstrap_system()

    try:
        raw_text = await websocket.receive_text()
        data = json.loads(raw_text)
        prompt = data.get("content", data.get("prompt", data.get("message", "")))

        try:
            # Analyze intent
            analysis = container.intent_analyzer.analyze(prompt)
            await websocket.send_json(
                {
                    "type": "intent_analysis",
                    "complexity": analysis.complexity.value,
                    "requires_tools": analysis.requires_tools,
                }
            )

            # For now, echo back (cognitive graph integration pending real LLM)
            await websocket.send_json(
                {
                    "type": "token_chunk",
                    "content": f"Echo: {prompt}",
                }
            )

            await websocket.send_json({"type": "stream_end"})

        except Exception as e:
            await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass


@ws_router.websocket("")
@ws_router.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Legacy WebSocket endpoint — redirects to default session."""
    await websocket_chat(websocket, "default")


@ws_router.get("/stream")
async def sse_stream_endpoint(request: Request, prompt: str = "hello") -> StreamingResponse:
    """Server-Sent Events (SSE) streaming endpoint."""
    if not is_authorized_for_streaming(request.headers, request.query_params):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    async def _event_generator() -> AsyncGenerator[str, None]:
        container = bootstrap_system()
        analysis = container.intent_analyzer.analyze(prompt)
        intent = {"type": "intent", "complexity": analysis.complexity.value}
        yield f"data: {json.dumps(intent)}\n\n"
        chunk = {"type": "chunk", "content": f"JARVIS streaming response for: {prompt}"}
        yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
