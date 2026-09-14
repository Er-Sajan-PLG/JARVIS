"""API routes for the JARVIS web application."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.adapters.security import is_authorized
from app.bootstrap import bootstrap_system

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

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
    
    # Add Google Gemini models if authenticated
    try:
        from app.integrations.google_oauth import get_google_oauth
        oauth = get_google_oauth()
        if oauth.is_authenticated:
            # Insert Google Gemini at the beginning
            providers.insert(0, {
                "key": "google_gemini",
                "name": "Google Gemini (AI Pro Account)",
                "status": "available",
                "has_key": True,
                "model_count": 6,
                "categories": ["reasoning", "code", "general"],
                "is_openai_compatible": False,
                "free_models_available": False,
                "models": [
                    {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "description": "Most capable model", "context_length": 1000000, "pricing": {}},
                    {"id": "gemini-3.1-flash", "name": "Gemini 3.1 Flash", "description": "Fast model", "context_length": 1000000, "pricing": {}},
                    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "description": "Lightweight", "context_length": 1000000, "pricing": {}},
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Previous gen capable", "context_length": 1000000, "pricing": {}},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Previous gen fast", "context_length": 1000000, "pricing": {}},
                    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Fast and efficient", "context_length": 1000000, "pricing": {}},
                ],
            })
    except Exception as e:
        logger.debug(f"Google OAuth check failed: {e}")
    
    return {"providers": providers}


@web_router.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    container = bootstrap_system()

    message = payload.get("message", "")
    model_info = payload.get("model", {})
    session_id = payload.get("session_id", str(uuid.uuid4()))
    memory_enabled = payload.get("memory_enabled", True)
    files = payload.get("files", [])
    file_contents = payload.get("file_contents", [])

    if not message and not files:
        raise HTTPException(status_code=400, detail="Message or files required")

    # Build file context
    file_context = ""
    if file_contents:
        for fname, fcontent in file_contents:
            file_context += f"\n\n[File: {fname}]\n{fcontent}"

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

    full_message = f"{message}{memory_context}{file_context}"

    # Get model client
    try:
        from app.models.factory import create_client
        from app.config.settings import ModelConfig

        provider = model_info.get("provider", "openrouter")
        model_id = model_info.get("id", "deepseek/deepseek-v4-flash-0731")

        # Handle Google Gemini
        if provider == "google_gemini":
            from app.integrations.google_genai import get_gemini_client
            client = get_gemini_client(model_id)
            if not client:
                return {"error": "Google Gemini not authenticated. Please login first."}
        else:
            provider_config = {
                "nvidia": {"key": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1"},
                "openrouter": {"key": "OPENROUTER_API_KEY", "url": "https://openrouter.ai/api/v1"},
                "groq": {"key": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1"},
                "google": {"key": "GOOGLE_API_KEY", "url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
                "github": {"key": "GITHUB_API_KEY", "url": "https://models.inference.ai.azure.com"},
                "mistral": {"key": "MISTRAL_API_KEY", "url": "https://api.mistral.ai/v1"},
                "anthropic": {"key": "ANTHROPIC_API_KEY", "url": "https://api.anthropic.com/v1"},
                "openai": {"key": "OPENAI_API_KEY", "url": "https://api.openai.com/v1"},
                "xai": {"key": "XAI_API_KEY", "url": "https://api.x.ai/v1"},
                "together": {"key": "TOGETHER_API_KEY", "url": "https://api.together.xyz/v1"},
                "cerebras": {"key": "CEREBRAS_API_KEY", "url": "https://api.cerebras.ai/v1"},
                "cohere": {"key": "COHERE_API_KEY", "url": "https://api.cohere.ai/v1"},
                "zhipu": {"key": "ZHIPU_API_KEY", "url": "https://open.bigmodel.cn/api/paas/v4"},
            }

            cfg = provider_config.get(provider, provider_config["openrouter"])
            api_key_env = cfg["key"]
            base_url = cfg["url"]

            config = ModelConfig(
                name=model_id,
                role="general",
                backend=provider,
                api_key=f"env:{api_key_env}",
                base_url=base_url,
            )
            client = create_client(config)
    except Exception as e:
        logger.error(f"Failed to create model client: {e}")
        return {"error": f"Model initialization failed: {str(e)}"}

    # Generate response
    try:
        messages = [{"role": "user", "content": full_message}]
        response = client.generate(messages)
        response_content = response.get("content", "") if isinstance(response, dict) else getattr(response, "content", "")
        response_tokens = response.get("tokens_used", None) if isinstance(response, dict) else getattr(response, "tokens_used", None)

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
                    value=response_content,
                    category="conversation",
                )
            except Exception as e:
                logger.warning(f"Memory store failed: {e}")

        return {
            "response": response_content,
            "model": model_info,
            "session_id": session_id,
            "tokens_used": response_tokens,
        }
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        return {"error": f"Generation failed: {str(e)}"}


@web_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    __=Depends(_validate_api_key),
) -> dict[str, Any]:
    """Upload a file and extract its content."""
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    content = await file.read()
    file_path.write_bytes(content)

    # Extract text based on file type
    extracted_text = ""
    content_type = file.content_type or ""

    if content_type == "application/pdf" or file.filename.lower().endswith(".pdf"):
        try:
            import pymupdf
            doc = pymupdf.open(stream=content, filetype="pdf")
            extracted_text = "\n".join(page.get_text() for page in doc)
            doc.close()
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            extracted_text = f"[PDF: {file.filename} - extraction failed]"

    elif content_type.startswith("text/") or file.filename.lower().endswith((".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".css")):
        try:
            extracted_text = content.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = content.decode("latin-1", errors="replace")

    elif content_type.startswith("image/"):
        extracted_text = f"[Image: {file.filename} - image content cannot be extracted as text]"

    else:
        # Try as text
        try:
            extracted_text = content.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = f"[File: {file.filename} - binary content]"

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": content_type,
        "extracted_text": extracted_text[:50000],  # Limit to 50KB of text
    }


@web_router.get("/memory")
async def list_memories(session_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    container = bootstrap_system()
    try:
        if session_id:
            memories = await container.memory_service.search_memories(session_id, limit=limit)
        else:
            # Return all memories
            all_mems = container.memory_service._manager.get_all()
            from app.domain import MemoryRecord
            memories = [
                MemoryRecord(
                    id=m.id,
                    key=getattr(m, "memory_type", ""),
                    value=getattr(m, "value", ""),
                    category=getattr(m, "category", "general"),
                    confidence=getattr(m, "confidence", 1.0),
                )
                for m in all_mems[:limit]
            ]
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


@web_router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    container = bootstrap_system()
    try:
        success = container.memory_service._manager.delete(memory_id)
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@web_router.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str) -> dict[str, Any]:
    """Delete a conversation and wipe all associated memories."""
    container = bootstrap_system()
    try:
        all_memories = container.memory_service._manager.get_all()
        deleted_count = 0
        to_delete = []
        for mem in all_memories:
            # Check if this memory belongs to this session
            mem_type = getattr(mem, "memory_type", "") or ""
            if session_id in mem_type:
                to_delete.append(mem.id)
        
        for mem_id in to_delete:
            if container.memory_service._manager.delete(mem_id):
                deleted_count += 1

        return {"success": True, "deleted_memories": deleted_count}
    except Exception as e:
        return {"error": str(e)}


# ── Google OAuth ─────────────────────────────────────────────────

@web_router.get("/google/auth/status")
async def google_auth_status() -> dict[str, Any]:
    """Check if Google OAuth is authenticated."""
    from app.integrations.google_oauth import get_google_oauth
    oauth = get_google_oauth()
    return {
        "authenticated": oauth.is_authenticated,
        "models": oauth.get_models() if oauth.is_authenticated else [],
    }


@web_router.post("/google/auth/login")
async def google_auth_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Login with Google OAuth.
    
    Body:
        client_id (str): Google OAuth client ID
        client_secret (str): Google OAuth client secret
    """
    from app.integrations.google_oauth import get_google_oauth
    client_id = payload.get("client_id", "")
    client_secret = payload.get("client_secret", "")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="client_id and client_secret required")
    
    oauth = get_google_oauth()
    success = oauth.login(client_id, client_secret)
    
    return {
        "success": success,
        "authenticated": oauth.is_authenticated,
    }


@web_router.post("/google/auth/logout")
async def google_auth_logout() -> dict[str, Any]:
    """Logout and remove stored credentials."""
    from app.integrations.google_oauth import get_google_oauth
    oauth = get_google_oauth()
    oauth.logout()
    return {"success": True}


@web_router.get("/google/models")
async def google_models() -> dict[str, Any]:
    """List available Gemini models from user's account."""
    from app.integrations.google_oauth import get_google_oauth
    oauth = get_google_oauth()
    if not oauth.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"models": oauth.get_models()}


@web_router.get("/health")
async def web_health() -> dict[str, Any]:
    return {"status": "ok", "service": "JARVIS Web API"}
