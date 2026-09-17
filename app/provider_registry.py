"""
Comprehensive provider registry for JARVIS.

Manages all AI model providers supported by JARVIS, including status tracking,
API key requirements, capabilities, and dynamic model catalog integration.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProviderStatus:
    """Status enumeration for provider availability."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    KEYS_MISSING = "keys_missing"
    CONFIG_ERROR = "config_error"


class ProviderCapability:
    """Classification of provider capabilities."""

    def __init__(self):
        self.is_openai_compatible = False
        self.is_reasoning_capable = False
        self.is_code_generation_capable = False
        self.is_stem_capable = False
        self.is_documentation_capable = False
        self.is_realtime_capable = False
        self.has_free_models = False
        self.context_window_size = 0
        self.max_output_tokens = 0


class AIProvider:
    """
    Represents a single AI model provider with all metadata and capabilities.
    """

    def __init__(
        self,
        key: str,
        name: str,
        description: str,
        website: str,
        api_endpoint: str | None = None,
        requires_api_key: bool = True,
        api_key_env_var: str | None = None,
        capabilities: ProviderCapability | None = None,
        model_categories: list[str] | None = None,
    ):
        self.key = key
        self.name = name
        self.description = description
        self.website = website
        self.api_endpoint = api_endpoint
        self.requires_api_key = requires_api_key
        self.api_key_env_var = api_key_env_var
        self.capabilities = capabilities or ProviderCapability()
        self.model_categories = model_categories or []
        self.status = ProviderStatus.UNAVAILABLE
        self.last_checked = None
        self.models = []
        self.free_models = []
        self.error_message: str | None = None

    def has_api_key(self) -> bool:
        """Check if the provider has an API key configured."""
        if not self.api_key_env_var:
            return True
        return bool(os.environ.get(self.api_key_env_var, ""))

    def update_status(self, status: str, error: str | None = None):
        """Update provider status."""
        self.status = status
        self.error_message = error
        self.last_checked = datetime.now(UTC)

    def add_models(self, models: list[dict[str, Any]]):
        """Add models to the provider."""
        self.models = models
        self.free_models = [m for m in models if m.get("free", False)]
        self.has_api_key = self.has_api_key()

    def to_dict(self) -> dict[str, Any]:
        """Convert provider to dictionary for API responses."""
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "website": self.website,
            "api_endpoint": self.api_endpoint,
            "status": self.status,
            "has_api_key": self.has_api_key(),
            "requires_api_key": self.requires_api_key,
            "api_key_env_var": self.api_key_env_var,
            "capabilities": {
                "is_openai_compatible": self.capabilities.is_openai_compatible,
                "is_reasoning_capable": self.capabilities.is_reasoning_capable,
                "is_code_generation_capable": self.capabilities.is_code_generation_capable,
                "is_stem_capable": self.capabilities.is_stem_capable,
                "is_documentation_capable": self.capabilities.is_documentation_capable,
                "is_realtime_capable": self.capabilities.is_realtime_capable,
                "has_free_models": self.capabilities.has_free_models,
                "context_window_size": self.capabilities.context_window_size,
                "max_output_tokens": self.capabilities.max_output_tokens,
            },
            "model_categories": self.model_categories,
            "model_count": len(self.models),
            "free_model_count": len(self.free_models),
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "error_message": self.error_message,
            "models": self.models,
            "free_models": self.free_models,
        }


class ProviderRegistry:
    """
    Central registry for all AI providers supported by JARVIS.

    This class manages the comprehensive list of providers, checks their status,
    maintains catalogs, and provides unified access to all provider information.
    """

    def __init__(self):
        self.providers: dict[str, AIProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all providers with their metadata and capabilities."""
        provider_configs = [
            {
                "key": "openrouter",
                "name": "OpenRouter",
                "description": "OpenAI-compatible access to 200+ cloud models",
                "website": "https://openrouter.ai/",
                "api_endpoint": "https://openrouter.ai/api/v1",
                "requires_api_key": True,
                "api_key_env_var": "OPENROUTER_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 1000000,  # 1M tokens
                    "max_output_tokens": 4096,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "google",
                "name": "Google AI Studio (Gemini)",
                "description": "Google's advanced multimodal models",
                "website": "https://ai.google.dev/",
                "api_endpoint": "https://generativelanguage.googleapis.com/v1beta",
                "requires_api_key": True,
                "api_key_env_var": "GOOGLE_API_KEY",
                "capabilities": {
                    "is_openai_compatible": False,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 1000000,
                    "max_output_tokens": 8192,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "groq",
                "name": "Groq",
                "description": "Fast inference for large language models",
                "website": "https://groq.com/",
                "api_endpoint": "https://api.groq.com/openai/v1",
                "requires_api_key": True,
                "api_key_env_var": "GROQ_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "github",
                "name": "GitHub Models",
                "description": "Free access to popular models via OpenAI-compatible API",
                "website": "https://github.com/marketplace/models",
                "api_endpoint": "https://models.inference.ai.azure.com",
                "requires_api_key": True,
                "api_key_env_var": "GITHUB_TOKEN",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": False,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "nvidia",
                "name": "NVIDIA NIM",
                "description": "NVIDIA's optimized inference platform",
                "website": "https://build.nvidia.com/",
                "api_endpoint": "https://integrate.api.nvidia.com/v1",
                "requires_api_key": True,
                "api_key_env_var": "NVIDIA_NIM_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": False,
                    "context_window_size": 32768,
                    "max_output_tokens": 8192,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "mistral",
                "name": "Mistral AI",
                "description": "European AI company's advanced models",
                "website": "https://mistral.ai/",
                "api_endpoint": "https://api.mistral.ai/v1",
                "requires_api_key": True,
                "api_key_env_var": "MISTRAL_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 32768,
                    "max_output_tokens": 8192,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "cohere",
                "name": "Cohere",
                "description": "Natural language understanding and generation",
                "website": "https://cohere.com/",
                "api_endpoint": "https://api.cohere.ai/v1",
                "requires_api_key": True,
                "api_key_env_var": "COHERE_API_KEY",
                "capabilities": {
                    "is_openai_compatible": False,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": False,
                    "has_free_models": True,
                    "context_window_size": 4096,
                    "max_output_tokens": 2048,
                },
                "model_categories": ["general", "reasoning", "docs"],
            },
            {
                "key": "huggingface",
                "name": "Hugging Face Inference",
                "description": "Access to thousands of open-source models",
                "website": "https://huggingface.co/inference-api",
                "api_endpoint": "https://api-inference.huggingface.co",
                "requires_api_key": True,
                "api_key_env_var": "HF_API_TOKEN",
                "capabilities": {
                    "is_openai_compatible": False,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": False,
                    "has_free_models": True,
                    "context_window_size": 4096,
                    "max_output_tokens": 2048,
                },
                "model_categories": ["general", "code", "reasoning", "stem", "docs"],
            },
            {
                "key": "cloudflare",
                "name": "Cloudflare Workers AI",
                "description": "Edge AI inference with global reach",
                "website": "https://developers.cloudflare.com/workers-ai/",
                "api_endpoint": "https://api.cloudflare.com/client/v4/accounts",
                "requires_api_key": True,
                "api_key_env_var": "CLOUDFLARE_API_TOKEN",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 4096,
                    "max_output_tokens": 2048,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "zhipu",
                "name": "Zhipu AI (GLM)",
                "description": "Chinese AI company's language models",
                "website": "https://open.bigmodel.cn/",
                "api_endpoint": "https://open.bigmodel.cn/api/paas/v4",
                "requires_api_key": True,
                "api_key_env_var": "ZHIPU_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
            {
                "key": "ollama",
                "name": "Local Ollama Models",
                "description": "Local deployment of LLMs using Ollama",
                "website": "https://ollama.ai/",
                "api_endpoint": "http://localhost:11434",
                "requires_api_key": False,
                "api_key_env_var": None,
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "together",
                "name": "Together AI",
                "description": "Fast inference for open-source models",
                "website": "https://together.ai/",
                "api_endpoint": "https://api.together.xyz/v1",
                "requires_api_key": True,
                "api_key_env_var": "TOGETHER_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "cerebras",
                "name": "Cerebras",
                "description": "Ultra-fast inference on Cerebras hardware",
                "website": "https://cerebras.ai/",
                "api_endpoint": "https://api.cerebras.ai/v1",
                "requires_api_key": True,
                "api_key_env_var": "CEREBRAS_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": True,
                    "context_window_size": 8192,
                    "max_output_tokens": 4096,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "openai",
                "name": "OpenAI",
                "description": "Direct access to OpenAI's models",
                "website": "https://openai.com/",
                "api_endpoint": "https://api.openai.com/v1",
                "requires_api_key": True,
                "api_key_env_var": "OPENAI_API_KEY",
                "capabilities": {
                    "is_openai_compatible": True,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": False,
                    "context_window_size": 128000,
                    "max_output_tokens": 16384,
                },
                "model_categories": [
                    "general",
                    "code",
                    "reasoning",
                    "docs",
                    "stem",
                    "autocomplete",
                ],
            },
            {
                "key": "anthropic",
                "name": "Anthropic (Claude)",
                "description": "Direct access to Anthropic's Claude models",
                "website": "https://anthropic.com/",
                "api_endpoint": "https://api.anthropic.com/v1",
                "requires_api_key": True,
                "api_key_env_var": "ANTHROPIC_API_KEY",
                "capabilities": {
                    "is_openai_compatible": False,
                    "is_reasoning_capable": True,
                    "is_code_generation_capable": True,
                    "is_stem_capable": True,
                    "is_documentation_capable": True,
                    "is_realtime_capable": True,
                    "has_free_models": False,
                    "context_window_size": 200000,
                    "max_output_tokens": 8192,
                },
                "model_categories": ["general", "code", "reasoning", "docs", "stem"],
            },
        ]

        for config in provider_configs:
            capability_obj = ProviderCapability()
            for attr, value in config["capabilities"].items():
                setattr(capability_obj, attr, value)

            provider = AIProvider(
                key=config["key"],
                name=config["name"],
                description=config["description"],
                website=config["website"],
                api_endpoint=config["api_endpoint"],
                requires_api_key=config["requires_api_key"],
                api_key_env_var=config["api_key_env_var"],
                capabilities=capability_obj,
                model_categories=config["model_categories"],
            )
            self.providers[config["key"]] = provider

    def check_provider_status(self, provider_key: str) -> AIProvider:
        """Check the status of a specific provider and update its information."""
        if provider_key not in self.providers:
            raise ValueError(f"Unknown provider key: {provider_key}")

        provider = self.providers[provider_key]

        try:
            if not provider.has_api_key():
                if not provider.requires_api_key:
                    provider.update_status(ProviderStatus.AVAILABLE)
                    provider.models = self._get_models_from_provider(provider)
                else:
                    provider.update_status(ProviderStatus.KEYS_MISSING, "API key not configured")
                return provider

            provider.models = self._get_models_from_provider(provider)
            if provider.models:
                provider.update_status(ProviderStatus.AVAILABLE)
            else:
                provider.update_status(ProviderStatus.UNAVAILABLE, "No models available")

        except Exception as e:
            logger.error(f"Error checking provider {provider_key}: {e}")
            provider.update_status(ProviderStatus.CONFIG_ERROR, str(e))

        return provider

    def _get_models_from_provider(self, provider: AIProvider) -> list[dict[str, Any]]:
        """Get models from a specific provider based on its type."""
        models = []

        try:
            if provider.key == "openrouter":
                models = self._fetch_openrouter_models()
            elif provider.key == "google":
                models = self._fetch_google_models()
            elif provider.key == "groq":
                models = self._fetch_groq_models()
            elif provider.key == "github":
                models = self._fetch_github_models()
            elif provider.key == "nvidia":
                models = self._fetch_nvidia_models()
            elif provider.key == "mistral":
                models = self._fetch_mistral_models()
            elif provider.key == "cohere":
                models = self._fetch_cohere_models()
            elif provider.key == "huggingface":
                models = self._fetch_huggingface_models()
            elif provider.key == "cloudflare":
                models = self._fetch_cloudflare_models()
            elif provider.key == "zhipu":
                models = self._fetch_zhipu_models()
            elif provider.key == "ollama":
                models = self._fetch_ollama_models()

            # Add free status to models
            for model in models:
                model["free"] = model.get("free", False)

        except Exception as e:
            logger.warning(f"Could not fetch models for {provider.key}: {e}")

        return models

    def _fetch_openrouter_models(self) -> list[dict[str, Any]]:
        """Fetch models from OpenRouter API."""
        try:
            url = "https://openrouter.ai/api/v1/models"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            models = []
            for item in response.json().get("data", []):
                model_info = {
                    "id": item.get("id", ""),
                    "name": item.get("name", item.get("id", "")),
                    "description": item.get("description", ""),
                    "context_length": item.get("context_length", 0),
                    "pricing": item.get("pricing", {}),
                    "free": self._is_free_pricing(item.get("pricing", {})),
                    "architecture": item.get("architecture", {}),
                }
                models.append(model_info)

            return models
        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter models: {e}")
            return []

    def _is_free_pricing(self, pricing: dict[str, Any]) -> bool:
        """Check if a model has free pricing."""
        if not pricing:
            return False
        prompt = str(pricing.get("prompt", "")).strip()
        completion = str(pricing.get("completion", "")).strip()
        return prompt in ("0", "0.0") and completion in ("0", "0.0")

    def get_all_providers(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get all providers with their current status."""
        result = []

        for key, provider in self.providers.items():
            # Refresh status if requested
            if force_refresh or provider.last_checked is None:
                self.check_provider_status(key)

            result.append(provider.to_dict())

        return sorted(result, key=lambda x: x["name"])

    def get_provider(self, provider_key: str) -> dict[str, Any] | None:
        """Get a specific provider by key."""
        if provider_key in self.providers:
            self.check_provider_status(provider_key)
            return self.providers[provider_key].to_dict()
        return None

    def get_providers_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get providers that support a specific category."""
        category_lower = category.lower()
        result = []

        for key, provider in self.providers.items():
            if any(cat.lower() == category_lower for cat in provider.model_categories):
                self.check_provider_status(key)
                result.append(provider.to_dict())

        return result

    def search_providers(self, query: str) -> list[dict[str, Any]]:
        """Search providers by name, description, or categories."""
        query_lower = query.lower()
        result = []

        for key, provider in self.providers.items():
            search_text = (
                f"{provider.name} {provider.description} " f"{' '.join(provider.model_categories)}"
            ).lower()

            if query_lower in search_text:
                self.check_provider_status(key)
                result.append(provider.to_dict())

        return result

    def _fetch_google_models(self) -> list[dict[str, Any]]:
        """Fetch models from Google AI Studio."""
        return [
            {
                "id": "gemini-2.0-flash-exp",
                "name": "Gemini 2.0 Flash",
                "description": "Google's fast multimodal model",
                "context_length": 1000000,
                "free": True,
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "description": "Google's large context window model",
                "context_length": 1000000,
                "free": False,
            },
        ]

    def _fetch_groq_models(self) -> list[dict[str, Any]]:
        """Fetch models from Groq."""
        return [
            {
                "id": "llama-3.1-70b-versatile",
                "name": "Llama 3.1 70B Versatile",
                "description": "Meta's Llama 3.1 model on Groq",
                "context_length": 8192,
                "free": True,
            },
            {
                "id": "mixtral-8x7b-32768",
                "name": "Mixtral 8x7B",
                "description": "Mistral's mixture of experts model",
                "context_length": 32768,
                "free": True,
            },
        ]

    def _fetch_github_models(self) -> list[dict[str, Any]]:
        """Fetch models from GitHub Models."""
        return [
            {
                "id": "openai/gpt-4",
                "name": "GPT-4",
                "description": "OpenAI's powerful model",
                "context_length": 8192,
                "free": False,
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "description": "Anthropic's advanced model",
                "context_length": 8192,
                "free": False,
            },
        ]

    def _fetch_nvidia_models(self) -> list[dict[str, Any]]:
        """Fetch models from NVIDIA NIM."""
        return [
            {
                "id": "nv-mistral-ai/mistral-large",
                "name": "Mistral Large",
                "description": "NVIDIA-hosted Mistral model",
                "context_length": 32768,
                "free": False,
            },
        ]

    def _fetch_mistral_models(self) -> list[dict[str, Any]]:
        """Fetch models from Mistral AI."""
        return [
            {
                "id": "mistral-large-latest",
                "name": "Mistral Large",
                "description": "Mistral AI's largest model",
                "context_length": 32768,
                "free": False,
            },
            {
                "id": "mistral-small-latest",
                "name": "Mistral Small",
                "description": "Mistral's efficient model",
                "context_length": 8192,
                "free": True,
            },
        ]

    def _fetch_cohere_models(self) -> list[dict[str, Any]]:
        """Fetch models from Cohere."""
        return [
            {
                "id": "command-r-plus",
                "name": "Command R+",
                "description": "Cohere's advanced reasoning model",
                "context_length": 4096,
                "free": True,
            },
        ]

    def _fetch_huggingface_models(self) -> list[dict[str, Any]]:
        """Fetch models from Hugging Face."""
        return [
            {
                "id": "meta-llama/Llama-2-7b-chat-hf",
                "name": "Llama-2 7B Chat",
                "description": "Facebook's LLaMA model",
                "context_length": 4096,
                "free": True,
            },
        ]

    def _fetch_cloudflare_models(self) -> list[dict[str, Any]]:
        """Fetch models from Cloudflare Workers AI."""
        return [
            {
                "id": "@cf/meta-llama/llama-2-7b-chat-hf",
                "name": "Llama-2 7B Chat",
                "description": "Cloudflare-hosted Llama model",
                "context_length": 4096,
                "free": True,
            },
        ]

    def _fetch_zhipu_models(self) -> list[dict[str, Any]]:
        """Fetch models from Zhipu AI."""
        return [
            {
                "id": "glm-4-flash",
                "name": "GLM-4 Flash",
                "description": "Zhipu AI's fast reasoning model",
                "context_length": 8192,
                "free": True,
            },
        ]

    def _fetch_ollama_models(self) -> list[dict[str, Any]]:
        """Fetch models from Ollama."""
        try:
            from app.utils.server_manager import ollama_model_names

            ollama_url = "http://localhost:11434"
            models = ollama_model_names(ollama_url)

            ollama_models = []
            for model_name in models:
                ollama_models.append(
                    {
                        "id": model_name,
                        "name": model_name,
                        "description": f"Ollama model: {model_name}",
                        "context_length": 4096,
                        "free": True,
                    }
                )

            return ollama_models
        except Exception:
            logger.warning("Could not fetch Ollama models")
            return []


# Global registry instance
_registry_instance: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProviderRegistry()
    return _registry_instance
