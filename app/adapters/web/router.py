"""API routes for the JARVIS web application."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.adapters.security import is_authorized
from app.bootstrap import bootstrap_system

logger = logging.getLogger(__name__)

web_router = APIRouter(prefix="/api", tags=["JARVIS Web API"])


def _validate_api_key(request: Request) -> bool:
    authorization = request.headers.get("authorization")
    x_api_key = request.headers.get("x-api-key")
    if is_authorized(authorization=authorization, x_api_key=x_api_key):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@web_router.get("/models")
async def list_models() -> dict[str, Any]:
    from app.utils.provider_catalog import get_all_providers
    providers = get_all_providers()
    return {"providers": providers}


@web_router.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    container = bootstrap_system()

    message = payload.get("message", "")
    model_info = payload.get("model", {})
    session_id = payload.get("session_id", str(uuid.uuid4()))
    memory_enabled = payload.get("memory_enabled", True)
    files = payload.get("files", [])

    if not message and not files:
        raise HTTPException(status_code=400, detail="Message or files required")

    # Get memory context
    memory_context = ""
    if memory_enabled:
        try:
            memories = await container.memory_service.search_memories(message, limit=3)
            if memories:
                memory_context = "\n\n[Memory Context]\n" + "\n".join(
                    f"- {m.value}" for m in memories
                )
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")

    full_message = f"{message}{memory_context}" if memory_context else message

    # Get model client
    try:
        from app.config.settings import ModelConfig
        from app.models.factory import create_client

        provider = model_info.get("provider", "nvidia")
        model_id = model_info.get("id", "deepseek-ai/deepseek-v4-flash-0731")

        config = ModelConfig(
            name=model_id,
            role="general",
            backend=provider,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        client = create_client(config)
    except Exception as e:
        logger.error(f"Failed to create model client: {e}")
        return {"error": f"Model initialization failed: {str(e)}"}

    # Generate response
    try:
        messages = [{"role": "user", "content": full_message}]
        response = client.generate(messages)

        # Store in memory
        if memory_enabled:
            try:
                await container.memory_service.store_memory(
                    key=f"user_{session_id}",
                    value=message,
                    category="conversation",
                )
                await container.memory_service.store_memory(
                    key=f"assistant_{session_id}",
                    value=response.content,
                    category="conversation",
                )
            except Exception as e:
                logger.warning(f"Memory store failed: {e}")

        return {
            "response": response.content,
            "model": model_info,
            "session_id": session_id,
            "tokens_used": response.tokens_used,
        }
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        return {"error": f"Generation failed: {str(e)}"}


@web_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    __=Depends(_validate_api_key),
) -> dict[str, Any]:
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    content = await file.read()
    file_path.write_bytes(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": file.content_type,
    }


@web_router.get("/memory")
async def list_memories(session_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    container = bootstrap_system()
    try:
        memories = await container.memory_service.search_memories("", limit=limit)
        return {
            "memories": [
                {
                    "id": m.id,
                    "value": m.value,
                    "category": m.category,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories[:limit]
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@web_router.get("/health")
async def web_health() -> dict[str, Any]:
    return {"status": "ok", "service": "JARVIS Web API"}
