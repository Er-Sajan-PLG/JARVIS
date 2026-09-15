"""
Unified provider catalog for JARVIS.

Consolidates live model catalogs from all supported providers so the web UI
can offer a single "Browse models" experience instead of separate search
boxes per provider. Includes both provider metadata (name, capabilities) and
live model listings.
"""

from __future__ import annotations

import importlib
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_CATALOG_TTL_SECONDS = 600  # 10 minutes
_catalog_lock = threading.Lock()
_global_cache: dict[str, Any] = {"providers": {}, "updated_at": 0.0}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Provider catalogue modules read keys straight from os.environ; the web server
# may not have exported .env, so load it once before any live fetch.
_ENV_LOADED = False


def _ensure_env_keys() -> None:
    """Load .env into os.environ exactly once (idempotent)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_PROJECT_ROOT / ".env", override=False)
    except Exception as exc:  # noqa: BLE001 - best effort
        logger.debug("dotenv load skipped: %s", exc)
    _ENV_LOADED = True


def _provider_key_env_names(provider_key: str) -> list[str]:
    """Environment variable names that can carry a provider's credential."""
    return {
        "openrouter": ["OPENROUTER_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "huggingface": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
        "nvidia": ["NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"],
        "github": ["GITHUB_TOKEN", "GITHUB_API_KEY"],
        "cloudflare": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY"],
        "zhipu": ["ZHIPU_API_KEY", "ZHIPUAI_API_KEY"],
    }.get(provider_key, [])


def _normalize_provider_key(provider: str) -> str:
    return provider.lower().replace(" ", "-").replace("/", "-").strip()


def _get_model_categories(models: list[dict]) -> list[str]:
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


# Providers that let you call some models at no cost. This is knowledge about
# the *provider's* offering, not a guess about a model: an entry here means the
# provider publishes a free tier, free endpoint, or genuinely $0 models.
#
#  always      — every model the provider serves is free to call
#  named       — specific model ids served free (matched case-insensitively as
#                a substring of the model id)
#  price_zero  — decide per-model from the pricing block the API returns
FREE_PROVIDER_POLICY: dict[str, dict[str, Any]] = {
    # Local runtimes cost nothing by definition.
    "ollama": {"always": True},
    "llamacpp": {"always": True},
    # Groq publishes a free tier with generous limits on every model.
    "groq": {"always": True},
    # NVIDIA NIM serves a set of models on a free-credits endpoint.
    "nvidia": {
        "named": (
            "nemotron",
            "llama-3.1-8b",
            "llama-3.2-1b",
            "llama-3.2-3b",
            "mistral-7b",
            "gemma-2-2b",
            "qwen2.5-7b",
            "phi-3",
            "deepseek-r1-distill-qwen-7b",
            "mixtral-8x7b",
        ),
        "price_zero": True,
    },
    # OpenRouter marks genuinely free models with a :free suffix and/or zero
    # pricing on every field.
    "openrouter": {"price_zero": True, "suffix": ":free"},
    # Hugging Face Inference Providers include a monthly free allowance that
    # covers the listed models. The API returns no pricing block at all, so
    # there is nothing per-model to check — treat them as free to call.
    "huggingface": {"always": True},
    # Google AI Studio has a free tier for the Flash/Pro families.
    "google": {"price_zero": True, "named": ("flash", "gemini-2.0", "gemma")},
    # GitHub Models is free to use within rate limits for every listed model.
    "github": {"always": True},
    # Cloudflare Workers AI is included in the free Workers plan quota.
    "cloudflare": {"always": True},
    # Mistral and Cohere both publish free experimentation tiers.
    "mistral": {
        "price_zero": True,
        "named": ("open-mistral", "open-mixtral", "mistral-7b", "ministral", "pixtral-12b"),
    },
    "cohere": {"price_zero": True, "named": ("command-r", "command-a", "embed", "rerank", "aya")},
    "cerebras": {"price_zero": True},
    "together": {"price_zero": True, "named": ("free",)},
    # Zhipu exposes free GLM Flash variants.
    "zhipu": {"price_zero": True, "named": ("flash", "glm-4-flash", "air", "free")},
}


def _pricing_is_zero(pricing: Any) -> bool:
    """True when every non-empty price field in a pricing block is zero."""
    if not isinstance(pricing, dict) or not pricing:
        return False
    checked = 0
    for key in ("prompt", "completion", "request", "image", "price_per_token", "input", "output"):
        if key not in pricing:
            continue
        raw = str(pricing.get(key, "") or "").strip()
        if not raw:
            continue
        checked += 1
        try:
            if float(raw) != 0.0:
                return False
        except (TypeError, ValueError):
            return False
    return checked > 0


def _tag_free(model: dict, provider_key: str) -> dict:
    """Annotate a model dict with a trustworthy ``free`` flag.

    The flag means "you can call this without paying" — derived from the
    provider's published free offering plus, where the API exposes it, the
    actual pricing block. It is never set merely because pricing is missing.
    """
    policy = FREE_PROVIDER_POLICY.get(provider_key)
    if policy is None:
        model.setdefault("free", False)
        return model

    if policy.get("always"):
        model["free"] = True
        model["free_reason"] = "provider free tier"
        return model

    mid = str(model.get("id") or model.get("name") or "").lower()
    suffix = policy.get("suffix")
    if suffix and mid.endswith(suffix):
        model["free"] = True
        model["free_reason"] = f"free variant ({suffix})"
        return model

    for needle in policy.get("named", ()):
        if needle in mid:
            model["free"] = True
            model["free_reason"] = f"free endpoint ({needle})"
            return model

    if policy.get("price_zero") and _pricing_is_zero(model.get("pricing")):
        model["free"] = True
        model["free_reason"] = "zero pricing"
        return model

    model.setdefault("free", False)
    return model


def _live_models_for(provider_key: str, limit: int = 200) -> list[dict]:
    """Fetch LIVE models for a provider via its catalog module.

    Returns an empty list when the provider has no key configured or the
    upstream call fails — callers must treat that as "unavailable", never as
    "one model".
    """
    _ensure_env_keys()
    loaders = {
        "openrouter": ("app.utils.openrouter_catalog", "search_openrouter_models"),
        "google": ("app.utils.google_catalog", "search_google_models"),
        "groq": ("app.utils.groq_catalog", "search_groq_models"),
        "mistral": ("app.utils.mistral_catalog", "search_mistral_models"),
        "cohere": ("app.utils.cohere_catalog", "search_cohere_models"),
        "huggingface": ("app.utils.hf_catalog", "search_hf_models"),
        "nvidia": ("app.utils.nvidia_nim_catalog", "search_nvidia_models"),
        "github": ("app.utils.github_models_catalog", "search_github_models"),
        "cloudflare": ("app.utils.cloudflare_ai_catalog", "search_cloudflare_models"),
        "zhipu": ("app.utils.zhipu_catalog", "search_zhipu_models"),
    }
    entry = loaders.get(provider_key)
    if entry is None:
        return []
    mod_name, fn_name = entry
    try:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        return [_tag_free(m, provider_key) for m in (fn("", limit=limit) or [])]
    except Exception as exc:  # noqa: BLE001 - provider availability is best-effort
        logger.debug("live model fetch failed for %s: %s", provider_key, exc)
        return []


def _local_models_for(provider_key: str) -> list[dict]:
    """Fetch models from locally-running servers (Ollama, llama.cpp)."""
    try:
        from app.config.settings import get_settings

        settings = get_settings()
        if provider_key == "ollama":
            from app.utils.server_manager import ollama_model_names

            return [
                _tag_free(
                    {"id": m, "name": m, "description": f"Ollama model: {m}", "pricing": {}},
                    provider_key,
                )
                for m in ollama_model_names(settings.paths.ollama_url)
            ]
        if provider_key == "llamacpp":
            from app.utils.server_manager import llamacpp_live_models

            return [
                _tag_free(
                    {
                        "id": m["key"],
                        "name": m["name"],
                        "description": f"llama.cpp server: {m['name']}",
                        "pricing": {},
                    },
                    provider_key,
                )
                for m in llamacpp_live_models(settings)
            ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("local model fetch failed for %s: %s", provider_key, exc)
    return []


def _build_provider_models(provider_key: str, client: Any) -> list[dict]:
    """Live models first, then local runtimes. No fabricated fallbacks."""
    models = _live_models_for(provider_key)
    if models:
        return models
    return _local_models_for(provider_key)


def _is_free_model(model: dict) -> bool:
    pricing = model.get("pricing", {})
    if not pricing:
        return False
    prompt = str(pricing.get("prompt", "") or pricing.get("price_per_token", "")).strip()
    completion = str(pricing.get("completion", "") or pricing.get("price_per_token", "")).strip()
    return prompt in ("0", "0.0") and completion in ("0", "0.0")


def search_google_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Google AI Studio (Gemini) models."""
    models = [
        {
            "id": "gemini-2.0-flash-exp",
            "name": "Gemini 2.0 Flash",
            "description": "Google's fast multimodal model",
            "context_length": 1000000,
            "pricing": {"prompt": "0.00000075", "completion": "0.000003"},
        },
        {
            "id": "gemini-1.5-pro",
            "name": "Gemini 1.5 Pro",
            "description": "Google's most capable model",
            "context_length": 2000000,
            "pricing": {"prompt": "0.0000035", "completion": "0.0000105"},
        },
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash",
            "description": "Google's fast efficient model",
            "context_length": 1000000,
            "pricing": {"prompt": "0.000000075", "completion": "0.0000003"},
        },
        {
            "id": "gemini-1.0-pro",
            "name": "Gemini 1.0 Pro",
            "description": "Google's balanced model",
            "context_length": 32768,
            "pricing": {"prompt": "0.0000005", "completion": "0.0000015"},
        },
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]


def search_grok_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Grok (XAI) models."""
    models = [
        {
            "id": "grok-beta",
            "name": "Grok Beta",
            "description": "xAI's conversational AI with real-time knowledge",
            "context_length": 131072,
            "pricing": {"prompt": "0.000005", "completion": "0.000015"},
        },
        {
            "id": "grok-2",
            "name": "Grok 2",
            "description": "xAI's improved reasoning model",
            "context_length": 131072,
            "pricing": {"prompt": "0.000002", "completion": "0.00001"},
        },
        {
            "id": "grok-2-mini",
            "name": "Grok 2 Mini",
            "description": "xAI's fast smaller model",
            "context_length": 131072,
            "pricing": {"prompt": "0.0000008", "completion": "0.000003"},
        },
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]


def search_sambanova_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search SambaNova models."""
    # SambaNova doesn't have a public catalog API yet, return curated models
    models = [
        {
            "id": "Meta-Llama-3.1-405B-Instruct",
            "name": "Meta Llama 3.1 405B Instruct",
            "description": "Meta's largest open model on SambaNova",
            "context_length": 128000,
            "pricing": {"prompt": "0.000001", "completion": "0.000001"},
        },
        {
            "id": "Meta-Llama-3.1-70B-Instruct",
            "name": "Meta Llama 3.1 70B Instruct",
            "description": "Meta's 70B model on SambaNova",
            "context_length": 128000,
            "pricing": {"prompt": "0.0000005", "completion": "0.0000005"},
        },
        {
            "id": "Meta-Llama-3.1-8B-Instruct",
            "name": "Meta Llama 3.1 8B Instruct",
            "description": "Meta's 8B model on SambaNova",
            "context_length": 128000,
            "pricing": {"prompt": "0.0000001", "completion": "0.0000001"},
        },
        {
            "id": "Mixtral-8x7B-Instruct",
            "name": "Mixtral 8x7B Instruct",
            "description": "Mistral's mixture of experts",
            "context_length": 32768,
            "pricing": {"prompt": "0.0000005", "completion": "0.0000005"},
        },
        {
            "id": "Qwen2-72B-Instruct",
            "name": "Qwen2 72B Instruct",
            "description": "Alibaba's large model",
            "context_length": 32768,
            "pricing": {"prompt": "0.0000005", "completion": "0.0000005"},
        },
    ]
    if free_only:
        models = [m for m in models if _is_free_model(m)]
    if query:
        q = query.lower()
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]


def invalidate_catalogue_cache() -> None:
    """Drop the cached provider catalogue.

    Called after any settings mutation (custom provider/model added or
    removed, default changed) so the next read reflects the write. Without
    this the UI would show a stale catalogue until the TTL expired.
    """
    with _catalog_lock:
        _global_cache["providers"] = {}
        _global_cache["updated_at"] = 0.0


def get_all_providers(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return provider metadata WITH their live model lists.

    Providers whose credential is missing, or whose upstream lookup fails,
    report ``status="unavailable"`` and an empty ``models`` list — we never
    invent placeholder models.
    """
    now = datetime.now(UTC).timestamp()
    with _catalog_lock:
        if not force_refresh and _global_cache["providers"]:
            age = now - _global_cache["updated_at"]
            if age < _CATALOG_TTL_SECONDS:
                return [dict(p) for p in _global_cache["providers"].values()]

    _ensure_env_keys()

    provider_map = {
        "openrouter": "OpenRouter",
        "google": "Google AI Studio",
        "groq": "Groq",
        "github": "GitHub Models",
        "mistral": "Mistral AI",
        "cohere": "Cohere",
        "huggingface": "Hugging Face",
        "nvidia": "NVIDIA NIM",
        "zhipu": "Zhipu AI (GLM)",
        "cloudflare": "Cloudflare Workers AI",
        "llamacpp": "llama.cpp (local)",
        "ollama": "Ollama (local)",
    }

    results: list[dict[str, Any]] = []
    collected: dict[str, dict[str, Any]] = {}

    for key, label in provider_map.items():
        env_names = _provider_key_env_names(key)
        has_key = any(os.environ.get(n) for n in env_names)
        is_local = key in ("ollama", "llamacpp")

        try:
            models = _build_provider_models(key, None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("provider %s model build failed: %s", key, exc)
            models = []

        if models:
            status = "available"
        elif is_local:
            status = "unavailable"
        elif not env_names:
            status = "available"
        elif has_key:
            status = "error"
        else:
            status = "no_key"

        results.append(
            {
                "key": key,
                "name": label,
                "status": status,
                "has_key": has_key,
                "is_local": is_local,
                "model_count": len(models),
                "models": models,
                "categories": _get_model_categories(models),
                "is_openai_compatible": key
                in ["openrouter", "groq", "github", "mistral", "nvidia_nim", "zhipu", "cloudflare"],
                "free_models_available": any(_is_free_model(m) for m in models),
            }
        )
        collected[key] = results[-1]

    with _catalog_lock:
        _global_cache["providers"] = {k: dict(v) for k, v in collected.items()}
        _global_cache["updated_at"] = now

    return results


def fetch_openrouter_models(force: bool = False) -> list[dict[str, Any]]:
    from app.utils.openrouter_catalog import fetch_openrouter_models as fetch

    return fetch(force)


def search_groq_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Groq models."""
    from app.utils.groq_catalog import search_groq_models as _search

    return _search(query, limit=limit)


def search_mistral_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Mistral models."""
    from app.utils.mistral_catalog import search_mistral_models as _search

    return _search(query, limit=limit)


def search_cohere_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Cohere models."""
    from app.utils.cohere_catalog import search_cohere_models as _search

    return _search(query, limit=limit)


def search_huggingface_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Hugging Face models."""
    from app.utils.hf_catalog import search_hf_models as _search

    return _search(query, limit=limit)


def search_nvidia_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search NVIDIA NIM models."""
    from app.utils.nvidia_nim_catalog import search_nvidia_models as _search

    return _search(query, limit=limit)


def search_github_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search GitHub Models."""
    from app.utils.github_models_catalog import search_github_models as _search

    return _search(query, limit=limit)


def search_cloudflare_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Cloudflare Workers AI models."""
    from app.utils.cloudflare_ai_catalog import search_cloudflare_models as _search

    return _search(query, limit=limit)


def search_zhipu_models(
    query: str = "", limit: int = 50, free_only: bool = False
) -> list[dict[str, Any]]:
    """Search Zhipu AI models."""
    from app.utils.zhipu_catalog import search_zhipu_models as _search

    return _search(query, limit=limit)


def get_provider_models(
    provider_key: str, limit: int = 50, free_only: bool = False, query: str = ""
) -> list[dict[str, Any]]:
    """Return live models for one provider.

    Delegates to the same discovery path used by ``get_all_providers``, so the
    chat selector and the settings UI never disagree.
    """
    for p in get_all_providers():
        if p["key"] == provider_key:
            models = list(p.get("models") or [])
            if free_only:
                models = [m for m in models if m.get("free")]
            q = query.strip().lower()
            if q:
                models = [
                    m
                    for m in models
                    if q in str(m.get("id", "")).lower() or q in str(m.get("name", "")).lower()
                ]
            return models[:limit]
    return []


def get_all_models_summary() -> list[dict[str, Any]]:
    providers = get_all_providers()
    all_models = []
    for provider in providers:
        models = get_provider_models(provider["key"], limit=10)
        all_models.extend(
            [{"provider": provider["key"], "provider_name": provider["name"], **m} for m in models]
        )
    return all_models


def search_all_providers(query: str, limit: int = 50) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    all_models = get_all_models_summary()
    filtered = []
    for m in all_models:
        q_match = (
            q in m.get("id", "").lower()
            or q in m.get("name", "").lower()
            or q in m.get("description", "").lower()
        )
        if q_match:
            filtered.append(m)
    return filtered[:limit]
