"""WebSocket & SSE Streaming Adapter Layer.

Provides real-time streaming interfaces for WebSocket connections and Server-Sent Events (SSE),
publishing streaming token chunks and step execution updates from InMemoryAsyncBus.

Both surfaces are gated by the same single-tenant credential as the REST API
(``JARVIS_API_KEY``), enforced through ``app.adapters.security``. Because a browser
cannot attach request headers to a ``WebSocket`` or an ``EventSource``, these two
surfaces additionally accept the key as the ``api_key`` query parameter; the REST
surface does not.
"""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from app.adapters.security import is_authorized_for_streaming
from app.bootstrap import bootstrap_system

ws_router = APIRouter(prefix="/ws", tags=["Streaming"])


@ws_router.websocket("/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str) -> None:
    """Real-time chat via WebSocket — uses the full cognitive graph."""
    if not is_authorized_for_streaming(websocket.headers, websocket.query_params):
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    container = bootstrap_system()

    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            prompt = data.get("content", data.get("message", ""))
            if not prompt:
                continue

            try:
                # Use the cognitive graph for real responses
                from app.brain.graph import run_cognitive_loop
                result = await run_cognitive_loop(
                    prompt,
                    container.intent_analyzer,
                    container.task_planner,
                    container.execution_runner,
                    session_id=session_id,
                )

                # Stream tokens (word-by-word simulation for now)
                response_text = result.get("synthesized_response", "No response generated")
                words = response_text.split()
                for word in words:
                    await websocket.send_json({"type": "token", "content": word + " "})
                    import asyncio
                    await asyncio.sleep(0.05)

                await websocket.send_json({"type": "done"})

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
