"""
Unified provider catalog for JARVIS.

Consolidates live model catalogs from all supported providers so the web UI
can offer a single "Browse models" experience instead of separate search
boxes per provider. Includes both provider metadata (name, capabilities) and
live model listings.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import threading
from collections import defaultdict
from urllib.parse import urlparse

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_CATALOG_TTL_SECONDS = 600  # 10 minutes
_catalog_lock = threading.Lock()
_global_cache: Dict[str, Any] = {"providers": {}, "updated_at": 0.0}

def _normalize_provider_key(provider: str) -> str:
    return provider.lower().replace(" ", "-").replace("/", "-").strip()
def _get_model_categories(models: List[Dict]) -> List[str]:
    cats: set[str] = set()
    for m in models:
        role = (m.get("role") or "").lower()
        name = (m.get("name") or m.get("id") or "").lower()
        desc = (m.get("description") or "").lower()
        text = f"{role} {name} {desc}"
        if "reasoning" in text or "analysis" in text or "think" in text:
            cats.add("reasoning")
        if "code" in text or "programming" in text or "developer" in text or "function" in text:
            cats.add("code")
        if "math" in text or "scientific" in text or "stem" in text or "calculation" in text:
            cats.add("stem")
        if "doc" in text or "documentation" in text or "readme" in text or "tutorial" in text:
            cats.add("docs")
        if "autocomplete" in text or "completion" in text or "summariz" in text:
            cats.add("autocomplete")
        if "general" in text or "chat" in text or "conversation" in text:
            cats.add("general")
    return list(cats) if cats else ["general"]
def _build_provider_models(provider_key: str, client: Any) -> List[Dict]:
    cat = client.__class__.__name__.replace("Client", "").lower()
    default_models = {
        "openrouter": [{"id": "anthropic/claude-3.5-sonnet:free", "name": "Claude 3.5 Sonnet (free)", "description": "Anthropic's powerful model, free tier", "context_length": 200000, "pricing": {"prompt": "0", "completion": "0"}}],
        "google": [{"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash", "description": "Google's fast multimodal model", "context_length": 1000000, "pricing": {}}],
        "groq": [{"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B Versatile", "description": "Meta's large language model on Groq", "context_length": 8192, "pricing": {}}],
        "github": [{"id": "openai/gpt-4", "name": "GPT-4", "description": "OpenAI's powerful model", "context_length": 8192, "pricing": {}}],
        "mistral": [{"id": "mistral-large-latest", "name": "Mistral Large", "description": "Mistral AI's largest model", "context_length": 32768, "pricing": {}}],
        "cohere": [{"id": "command-r-plus", "name": "Command R+", "description": "Cohere's advanced reasoning model", "context_length": 4096, "pricing": {}}],
        "huggingface": [{"id": "meta-llama/Llama-2-7b-chat-hf", "name": "Llama-2 7B Chat", "description": "Facebook's LLaMA model", "context_length": 4096, "pricing": {}}],
        "nvidia_nim": [{"id": "nv-mistral-ai/mistral-large", "name": "Mistral Large", "description": "NVIDIA-hosted Mistral model", "context_length": 32768, "pricing": {}}],
        "zhipu": [{"id": "glm-4-flash", "name": "GLM-4 Flash", "description": "Zhipu AI's fast reasoning model", "context_length": 8192, "pricing": {}}],
        "cloudflare": [{"id": "@cf/meta-llama/llama-2-7b-chat-hf", "name": "Llama-2 7B Chat", "description": "Cloudflare-hosted Llama model", "context_length": 4096, "pricing": {}}],
        "llamacpp": [{"id": "llama-2-7b-chat.gguf", "name": "Llama-2 7B Chat", "description": "Local llama.cpp model", "context_length": 4096, "pricing": {}}],
        "ollama": [{"id": "llama2", "name": "Llama 2", "description": "Meta's Llama 2 model", "context_length": 4096, "pricing": {}}],
    }
    return default_models.get(provider_key, [])
def _is_free_model(model: Dict) -> bool:
    pricing = model.get("pricing", {})
    if not pricing:
        return False
    prompt = str(pricing.get("prompt", "") or pricing.get("price_per_token", "")).strip()
    completion = str(pricing.get("completion", "") or pricing.get("price_per_token", "")).strip()
    return prompt in ("0", "0.0") and completion in ("0", "0.0")

def search_google_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Google AI Studio (Gemini) models."""
    models = [
        {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash", "description": "Google's fast multimodal model", "context_length": 1000000, "pricing": {"prompt": "0.00000075", "completion": "0.000003"}},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google's most capable model", "context_length": 2000000, "pricing": {"prompt": "0.0000035", "completion": "0.0000105"}},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google's fast efficient model", "context_length": 1000000, "pricing": {"prompt": "0.000000075", "completion": "0.0000003"}},
        {"id": "gemini-1.0-pro", "name": "Gemini 1.0 Pro", "description": "Google's balanced model", "context_length": 32768, "pricing": {"prompt": "0.0000005", "completion": "0.0000015"}},
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]

def search_grok_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Grok (XAI) models."""
    models = [
        {"id": "grok-beta", "name": "Grok Beta", "description": "xAI's conversational AI with real-time knowledge", "context_length": 131072, "pricing": {"prompt": "0.000005", "completion": "0.000015"}},
        {"id": "grok-2", "name": "Grok 2", "description": "xAI's improved reasoning model", "context_length": 131072, "pricing": {"prompt": "0.000002", "completion": "0.00001"}},
        {"id": "grok-2-mini", "name": "Grok 2 Mini", "description": "xAI's fast smaller model", "context_length": 131072, "pricing": {"prompt": "0.0000008", "completion": "0.000003"}},
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]


def search_sambanova_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search SambaNova models."""
    # SambaNova doesn't have a public catalog API yet, return curated models
    models = [
        {"id": "Meta-Llama-3.1-405B-Instruct", "name": "Meta Llama 3.1 405B Instruct", "description": "Meta's largest open model on SambaNova", "context_length": 128000, "pricing": {"prompt": "0.000001", "completion": "0.000001"}},
        {"id": "Meta-Llama-3.1-70B-Instruct", "name": "Meta Llama 3.1 70B Instruct", "description": "Meta's 70B model on SambaNova", "context_length": 128000, "pricing": {"prompt": "0.0000005", "completion": "0.0000005"}},
        {"id": "Meta-Llama-3.1-8B-Instruct", "name": "Meta Llama 3.1 8B Instruct", "description": "Meta's 8B model on SambaNova", "context_length": 128000, "pricing": {"prompt": "0.0000001", "completion": "0.0000001"}},
        {"id": "Mixtral-8x7B-Instruct", "name": "Mixtral 8x7B Instruct", "description": "Mistral's mixture of experts", "context_length": 32768, "pricing": {"prompt": "0.0000005", "completion": "0.0000005"}},
        {"id": "Qwen2-72B-Instruct", "name": "Qwen2 72B Instruct", "description": "Alibaba's large model", "context_length": 32768, "pricing": {"prompt": "0.0000005", "completion": "0.0000005"}},
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]

def get_all_providers(force_refresh: bool = False) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).timestamp()
    with _catalog_lock:
        if not force_refresh and _global_cache["providers"]:
            age = now - _global_cache["updated_at"]
            return list(_global_cache["providers"].values())
        _global_cache["providers"] = {}
        _global_cache["updated_at"] = now

    try:
        from app.models.factory import create_client
        from app.config.settings import ModelConfig
        from app.models.router import TaskType
        from app.models.switcher import ModelSwitcher
        from app.config.settings import get_settings

        settings = get_settings()
        switcher = ModelSwitcher(settings)

        provider_map = {
            "openrouter": "OpenRouter (200+ models)",
            "google": "Google AI Studio (Gemini)",
            "groq": "Groq (fast inference)",
            "github": "GitHub Models",
            "mistral": "Mistral AI",
            "cohere": "Cohere",
            "huggingface": "Hugging Face Inference",
            "nvidia_nim": "NVIDIA NIM",
            "zhipu": "Zhipu AI (GLM)",
            "cloudflare": "Cloudflare Workers AI",
            "llamacpp": "Local llama.cpp servers",
            "ollama": "Local Ollama models",
        }

        available_providers: List[Dict[str, Any]] = []

        for key, label in provider_map.items():
            models = []
            client = None

            try:
                cfg = ModelConfig(name="test", role="general", backend=key, api_key="not-needed")
                client = create_client(cfg)
                catalog = _build_provider_models(key, client)
                models = catalog
            except Exception:
                try:
                    if key == "ollama":
                        from app.utils.server_manager import ollama_model_names
                        ollama_names = ollama_model_names(settings.paths.ollama_url)
                        models = [{"id": m, "name": m, "description": f"Ollama model: {m}"} for m in ollama_names]
                    elif key == "llamacpp":
                        from app.utils.server_manager import llamacpp_live_models
                        live = llamacpp_live_models(settings)
                        models = [{"id": m["key"], "name": m["name"], "description": f"llama.cpp server: {m['name']}"} for m in live]
                except Exception:
                    pass

            provider_entry = {
                "key": key,
                "name": label,
                "status": "available" if client or models else "unavailable",
                "has_key": False,
                "model_count": len(models),
                "categories": _get_model_categories(models),
                "is_openai_compatible": key in ["openrouter", "groq", "github", "mistral", "nvidia_nim", "zhipu", "cloudflare"],
                "free_models_available": any(_is_free_model(m) for m in models),
            }

            if key == "openrouter":
                try:
                    models = fetch_openrouter_models(force_refresh)
                except Exception:
                    pass

            available_providers.append(provider_entry)

            if models:
                _global_cache["providers"][key] = provider_entry

        return available_providers

    except Exception as e:
        logger.warning(f"Failed to build unified provider catalog: {e}")
        return []
def fetch_openrouter_models(force: bool = False) -> List[Dict[str, Any]]:
    from app.utils.openrouter_catalog import fetch_openrouter_models as fetch
    return fetch(force)

def search_groq_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Groq models."""
    from app.utils.groq_catalog import search_groq_models as _search
    return _search(query, limit=limit)

def search_mistral_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Mistral models."""
    from app.utils.mistral_catalog import search_mistral_models as _search
    return _search(query, limit=limit)

def search_cohere_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Cohere models."""
    from app.utils.cohere_catalog import search_cohere_models as _search
    return _search(query, limit=limit)

def search_huggingface_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Hugging Face models."""
    from app.utils.hf_catalog import search_hf_models as _search
    return _search(query, limit=limit)

def search_nvidia_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search NVIDIA NIM models."""
    from app.utils.nvidia_nim_catalog import search_nvidia_models as _search
    return _search(query, limit=limit)

def search_github_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search GitHub Models."""
    from app.utils.github_models_catalog import search_github_models as _search
    return _search(query, limit=limit)

def search_cloudflare_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Cloudflare Workers AI models."""
    from app.utils.cloudflare_ai_catalog import search_cloudflare_models as _search
    return _search(query, limit=limit)

def search_zhipu_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search Zhipu AI models."""
    from app.utils.zhipu_catalog import search_zhipu_models as _search
    return _search(query, limit=limit)

def search_sambanova_models(query: str = "", limit: int = 50, free_only: bool = False) -> List[Dict[str, Any]]:
    """Search SambaNova models (via provider catalog)."""
    # SambaNova uses OpenAI-compatible API, would need specific catalog
    return []

def get_provider_models(provider_key: str, limit: int = 50, free_only: bool = False, query: str = "") -> List[Dict[str, Any]]:
    import requests
    from app.utils.openrouter_catalog import fetch_openrouter_models, search_openrouter_models

    if provider_key == "openrouter":
        if free_only:
            return search_openrouter_models(query, limit=limit, free_only=True)
        return search_openrouter_models(query, limit=limit, free_only=False)

    return []
def get_all_models_summary() -> List[Dict[str, Any]]:
    providers = get_all_providers()
    all_models = []
    for provider in providers:
        models = get_provider_models(provider["key"], limit=10)
        all_models.extend([{"provider": provider["key"], "provider_name": provider["name"], **m} for m in models])
    return all_models
def search_all_providers(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    all_models = get_all_models_summary()
    filtered = []
    for m in all_models:
        q_match = q in m.get("id", "").lower() or q in m.get("name", "").lower() or q in m.get("description", "").lower()
        if q_match:
            filtered.append(m)
    return filtered[:limit]