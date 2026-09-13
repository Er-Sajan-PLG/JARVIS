"""Unit tests for app/provider_registry.py."""

from datetime import datetime

import pytest

from app.provider_registry import (
    AIProvider,
    ProviderCapability,
    ProviderRegistry,
    ProviderStatus,
    get_provider_registry,
)


def test_provider_status_constants():
    assert ProviderStatus.AVAILABLE == "available"
    assert ProviderStatus.UNAVAILABLE == "unavailable"
    assert ProviderStatus.KEYS_MISSING == "keys_missing"
    assert ProviderStatus.CONFIG_ERROR == "config_error"


def test_provider_capability_defaults():
    cap = ProviderCapability()
    assert cap.is_openai_compatible is False
    assert cap.is_reasoning_capable is False
    assert cap.is_code_generation_capable is False
    assert cap.is_stem_capable is False
    assert cap.is_documentation_capable is False
    assert cap.is_realtime_capable is False
    assert cap.has_free_models is False
    assert cap.context_window_size == 0
    assert cap.max_output_tokens == 0


def test_aiprovider_init_and_attributes():
    cap = ProviderCapability()
    cap.is_reasoning_capable = True
    provider = AIProvider(
        key="custom",
        name="Custom AI",
        description="A test provider",
        website="https://custom.ai",
        api_endpoint="https://api.custom.ai/v1",
        requires_api_key=True,
        api_key_env_var="CUSTOM_API_KEY",
        capabilities=cap,
        model_categories=["general", "code"],
    )

    assert provider.key == "custom"
    assert provider.name == "Custom AI"
    assert provider.description == "A test provider"
    assert provider.website == "https://custom.ai"
    assert provider.api_endpoint == "https://api.custom.ai/v1"
    assert provider.requires_api_key is True
    assert provider.api_key_env_var == "CUSTOM_API_KEY"
    assert provider.capabilities.is_reasoning_capable is True
    assert provider.model_categories == ["general", "code"]
    assert provider.status == ProviderStatus.UNAVAILABLE
    assert provider.last_checked is None
    assert provider.models == []
    assert provider.free_models == []
    assert provider.error_message is None


def test_aiprovider_has_api_key(monkeypatch):
    provider = AIProvider(
        key="test",
        name="Test",
        description="desc",
        website="https://test.ai",
        requires_api_key=True,
        api_key_env_var="TEST_PROV_KEY",
    )

    monkeypatch.delenv("TEST_PROV_KEY", raising=False)
    assert provider.has_api_key() is False

    monkeypatch.setenv("TEST_PROV_KEY", "secret")
    assert provider.has_api_key() is True

    provider_no_env = AIProvider(
        key="local",
        name="Local",
        description="desc",
        website="http://localhost",
        requires_api_key=False,
        api_key_env_var=None,
    )
    assert provider_no_env.has_api_key() is True


def test_aiprovider_update_status():
    provider = AIProvider(
        key="test",
        name="Test",
        description="desc",
        website="https://test.ai",
    )
    provider.update_status(ProviderStatus.AVAILABLE, error="none")
    assert provider.status == ProviderStatus.AVAILABLE
    assert provider.error_message == "none"
    assert isinstance(provider.last_checked, datetime)


def test_aiprovider_add_models():
    provider = AIProvider(
        key="test",
        name="Test",
        description="desc",
        website="https://test.ai",
        api_key_env_var="TEST_KEY",
    )
    models = [
        {"id": "m1", "free": True},
        {"id": "m2", "free": False},
        {"id": "m3"},
    ]
    provider.add_models(models)
    assert provider.models == models
    assert len(provider.free_models) == 1
    assert provider.free_models[0]["id"] == "m1"


def test_aiprovider_to_dict():
    provider = AIProvider(
        key="test",
        name="Test Provider",
        description="desc",
        website="https://test.ai",
        api_endpoint="https://api.test.ai",
        requires_api_key=True,
        api_key_env_var="TEST_KEY",
        model_categories=["general"],
    )
    provider.update_status(ProviderStatus.AVAILABLE)
    d = provider.to_dict()

    assert d["key"] == "test"
    assert d["name"] == "Test Provider"
    assert d["description"] == "desc"
    assert d["website"] == "https://test.ai"
    assert d["api_endpoint"] == "https://api.test.ai"
    assert d["status"] == ProviderStatus.AVAILABLE
    assert d["requires_api_key"] is True
    assert d["api_key_env_var"] == "TEST_KEY"
    assert "capabilities" in d
    assert d["model_categories"] == ["general"]
    assert d["model_count"] == 0
    assert d["free_model_count"] == 0
    assert d["last_checked"] is not None


def test_provider_registry_initialization():
    registry = ProviderRegistry()
    assert len(registry.providers) >= 10
    assert "openrouter" in registry.providers
    assert "google" in registry.providers
    assert "groq" in registry.providers
    assert "github" in registry.providers
    assert "ollama" in registry.providers


def test_check_provider_status_unknown_key():
    registry = ProviderRegistry()
    with pytest.raises(ValueError, match="Unknown provider key"):
        registry.check_provider_status("unknown_key_xyz")


def test_check_provider_status_keys_missing(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    groq = registry.check_provider_status("groq")
    assert groq.status == ProviderStatus.KEYS_MISSING
    assert groq.error_message == "API key not configured"


def test_check_provider_status_no_key_required(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(
        registry, "_get_models_from_provider", lambda p: [{"id": "llama3", "free": True}]
    )
    res = registry.check_provider_status("ollama")
    assert res.status == ProviderStatus.AVAILABLE
    assert len(res.models) == 1


def test_check_provider_status_with_key_and_models(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key")
    res = registry.check_provider_status("google")
    assert res.status == ProviderStatus.AVAILABLE
    assert len(res.models) > 0


def test_check_provider_status_empty_models(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key")
    monkeypatch.setattr(registry, "_get_models_from_provider", lambda p: [])
    res = registry.check_provider_status("google")
    assert res.status == ProviderStatus.UNAVAILABLE
    assert res.error_message == "No models available"


def test_check_provider_status_exception_handled(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key")

    def fail_get(p):
        raise RuntimeError("network down")

    monkeypatch.setattr(registry, "_get_models_from_provider", fail_get)
    res = registry.check_provider_status("google")
    assert res.status == ProviderStatus.CONFIG_ERROR
    assert res.error_message is not None and "network down" in res.error_message


def test_get_models_all_branches(monkeypatch):
    registry = ProviderRegistry()
    for key in [
        "google",
        "groq",
        "github",
        "nvidia",
        "mistral",
        "cohere",
        "huggingface",
        "cloudflare",
        "zhipu",
    ]:
        prov = registry.providers[key]
        models = registry._get_models_from_provider(prov)
        assert isinstance(models, list)
        assert len(models) > 0
        assert all("free" in m for m in models)


def test_get_models_ollama_success(monkeypatch):
    registry = ProviderRegistry()
    prov = registry.providers["ollama"]
    monkeypatch.setattr(
        "app.utils.server_manager.ollama_model_names", lambda url: ["model1", "model2"]
    )
    models = registry._get_models_from_provider(prov)
    assert len(models) == 2
    assert models[0]["id"] == "model1"
    assert models[0]["free"] is True


def test_get_models_ollama_failure(monkeypatch):
    registry = ProviderRegistry()
    prov = registry.providers["ollama"]

    def boom(url):
        raise RuntimeError("offline")

    monkeypatch.setattr("app.utils.server_manager.ollama_model_names", boom)
    models = registry._get_models_from_provider(prov)
    assert models == []


def test_fetch_openrouter_models(monkeypatch):
    registry = ProviderRegistry()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {
                        "id": "openrouter/free-model",
                        "name": "Free Model",
                        "description": "desc",
                        "context_length": 8192,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "openrouter/paid-model",
                        "name": "Paid Model",
                        "pricing": {"prompt": "0.01", "completion": "0.02"},
                    },
                ]
            }

    monkeypatch.setattr("requests.get", lambda url, timeout: FakeResp())
    models = registry._fetch_openrouter_models()
    assert len(models) == 2
    assert models[0]["free"] is True
    assert models[1]["free"] is False


def test_fetch_openrouter_models_error(monkeypatch):
    registry = ProviderRegistry()

    def fail_req(*a, **k):
        raise RuntimeError("timeout")

    monkeypatch.setattr("requests.get", fail_req)
    assert registry._fetch_openrouter_models() == []


def test_is_free_pricing():
    registry = ProviderRegistry()
    assert registry._is_free_pricing({}) is False
    assert registry._is_free_pricing({"prompt": "0", "completion": "0"}) is True
    assert registry._is_free_pricing({"prompt": "0.0", "completion": "0.0"}) is True
    assert registry._is_free_pricing({"prompt": "0.001", "completion": "0"}) is False


def test_get_all_providers(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(registry, "check_provider_status", lambda key: registry.providers[key])
    all_p = registry.get_all_providers(force_refresh=True)
    assert len(all_p) == len(registry.providers)
    assert sorted(all_p, key=lambda x: x["name"]) == all_p


def test_get_provider_found_and_not_found(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(registry, "check_provider_status", lambda key: registry.providers[key])
    p = registry.get_provider("google")
    assert p is not None
    assert p["key"] == "google"

    assert registry.get_provider("non_existent") is None


def test_get_providers_by_category(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(registry, "check_provider_status", lambda key: registry.providers[key])
    code_providers = registry.get_providers_by_category("code")
    assert len(code_providers) > 0
    assert all("code" in [c.lower() for c in p["model_categories"]] for p in code_providers)


def test_search_providers(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(registry, "check_provider_status", lambda key: registry.providers[key])
    results = registry.search_providers("gemini")
    assert any(p["key"] == "google" for p in results)


def test_get_provider_registry_singleton():
    import app.provider_registry as pr

    pr._registry_instance = None
    r1 = get_provider_registry()
    r2 = get_provider_registry()
    assert r1 is r2
    assert isinstance(r1, ProviderRegistry)
