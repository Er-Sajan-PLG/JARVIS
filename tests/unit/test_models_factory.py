"""Unit tests for app/models/factory.py."""

import pytest

from app.config.settings import ModelConfig
from app.models import factory
from app.models.anthropic_client import AnthropicClient
from app.models.cerebras_client import CerebrasClient
from app.models.cloudflare_ai_client import CloudflareAIClient
from app.models.cohere_client import CohereClient
from app.models.factory import create_client
from app.models.github_models_client import GitHubModelsClient
from app.models.google_client import GoogleClient
from app.models.groq_client import GroqClient
from app.models.hf_client import HuggingFaceClient
from app.models.llamacpp_client import LlamaCppClient
from app.models.mistral_client import MistralClient
from app.models.nvidia_nim_client import NVIDIANIMClient
from app.models.ollama_client import OllamaClient
from app.models.openai_client import OpenAIClient
from app.models.openrouter_client import OpenRouterClient
from app.models.together_client import TogetherClient
from app.models.zhipu_client import ZhipuClient


def make_config(
    backend: str,
    name: str = "model-x",
    api_key: str = "test-key",
    base_url: str = "http://localhost:8080",
    role: str = "general",
) -> ModelConfig:
    return ModelConfig(
        backend=backend,
        name=name,
        api_key=api_key,
        base_url=base_url,
        role=role,
    )


def test_create_client_user_keys_override():
    cfg = make_config(backend="anthropic", api_key="env:CUSTOM_KEY_VAR")
    client = create_client(cfg, user_keys={"CUSTOM_KEY_VAR": "header-provided-key"})
    assert isinstance(client, AnthropicClient)
    assert client._api_key == "header-provided-key"


def test_create_client_user_keys_fallback_to_env(monkeypatch):
    monkeypatch.setenv("ENV_KEY_VAR", "env-provided-key")
    cfg = make_config(backend="anthropic", api_key="env:ENV_KEY_VAR")
    client = create_client(cfg, user_keys={"OTHER_KEY": "irrelevant"})
    assert isinstance(client, AnthropicClient)
    assert client._api_key == "env-provided-key"


@pytest.mark.parametrize(
    "backend,client_class",
    [
        ("ollama", OllamaClient),
        ("openrouter", OpenRouterClient),
        ("groq", GroqClient),
        ("github", GitHubModelsClient),
        ("mistral", MistralClient),
        ("nvidia", NVIDIANIMClient),
        ("cloudflare", CloudflareAIClient),
        ("zhipu", ZhipuClient),
        ("together", TogetherClient),
        ("cerebras", CerebrasClient),
        ("openai", OpenAIClient),
        ("google", GoogleClient),
        ("cohere", CohereClient),
        ("huggingface", HuggingFaceClient),
        ("anthropic", AnthropicClient),
        ("llamacpp", LlamaCppClient),
        ("unknown-backend", LlamaCppClient),
    ],
)
def test_create_client_dispatch(backend, client_class, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "dummy-acc-id")
    cfg = make_config(backend=backend)
    client = create_client(cfg)
    assert isinstance(client, client_class)


@pytest.mark.parametrize(
    "backend,flag_name",
    [
        ("ollama", "OLLAMA_AVAILABLE"),
        ("openrouter", "OPENROUTER_AVAILABLE"),
        ("groq", "GROQ_AVAILABLE"),
        ("github", "GITHUB_MODELS_AVAILABLE"),
        ("mistral", "MISTRAL_AVAILABLE"),
        ("nvidia", "NVIDIA_NIM_AVAILABLE"),
        ("cloudflare", "CLOUDFLARE_AI_AVAILABLE"),
        ("zhipu", "ZHIPU_AVAILABLE"),
        ("together", "TOGETHER_AVAILABLE"),
        ("cerebras", "CEREBRAS_AVAILABLE"),
        ("openai", "OPENAI_AVAILABLE"),
        ("google", "GOOGLE_AVAILABLE"),
        ("cohere", "COHERE_AVAILABLE"),
        ("huggingface", "HF_AVAILABLE"),
        ("anthropic", "ANTHROPIC_AVAILABLE"),
    ],
)
def test_create_client_import_error_branches(backend, flag_name, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "dummy-acc-id")
    monkeypatch.setattr(factory, flag_name, False)
    cfg = make_config(backend=backend)
    with pytest.raises(ImportError):
        create_client(cfg)
