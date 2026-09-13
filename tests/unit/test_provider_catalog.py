"""Unit tests for app/utils/provider_catalog.py."""

from unittest.mock import MagicMock

from app.utils.provider_catalog import (
    _build_provider_models,
    _get_model_categories,
    _global_cache,
    _is_free_model,
    _normalize_provider_key,
    fetch_openrouter_models,
    get_all_models_summary,
    get_all_providers,
    get_provider_models,
    search_all_providers,
    search_cloudflare_models,
    search_cohere_models,
    search_github_models,
    search_google_models,
    search_grok_models,
    search_groq_models,
    search_huggingface_models,
    search_mistral_models,
    search_nvidia_models,
    search_sambanova_models,
    search_zhipu_models,
)


def test_normalize_provider_key():
    assert _normalize_provider_key("OpenRouter") == "openrouter"
    assert _normalize_provider_key("Google AI") == "google-ai"
    assert _normalize_provider_key("meta/llama") == "meta-llama"
    assert _normalize_provider_key("Groq / Cloud") == "groq---cloud"


def test_get_model_categories():
    # Fallback
    assert _get_model_categories([]) == ["general"]

    # Categories matching
    models = [
        {"role": "assistant", "name": "thinker", "description": "reasoning model"},
        {"role": "code", "name": "dev", "description": "developer assistant"},
        {"role": "math", "name": "stem-1", "description": "calculation"},
        {"role": "docs", "name": "doc-writer", "description": "readme generator"},
        {"role": "autocomplete", "name": "tab", "description": "completion helper"},
        {"role": "chat", "name": "convo", "description": "general conversation"},
    ]
    cats = _get_model_categories(models)
    assert "reasoning" in cats
    assert "code" in cats
    assert "stem" in cats
    assert "docs" in cats
    assert "autocomplete" in cats
    assert "general" in cats


def test_build_provider_models():
    dummy_client = MagicMock()
    # Test existing keys
    models_or = _build_provider_models("openrouter", dummy_client)
    assert len(models_or) > 0
    assert models_or[0]["id"] == "anthropic/claude-3.5-sonnet:free"

    models_google = _build_provider_models("google", dummy_client)
    assert len(models_google) > 0

    # Test unknown key
    assert _build_provider_models("unknown_key_xyz", dummy_client) == []


def test_is_free_model():
    assert _is_free_model({}) is False
    assert _is_free_model({"pricing": {}}) is False
    assert _is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is True
    assert _is_free_model({"pricing": {"prompt": "0.0", "completion": "0.0"}}) is True
    assert _is_free_model({"pricing": {"price_per_token": "0"}}) is True
    assert _is_free_model({"pricing": {"prompt": "0.01", "completion": "0.02"}}) is False


def test_search_google_models():
    all_models = search_google_models()
    assert len(all_models) > 0

    # query filter
    q_models = search_google_models(query="flash")
    assert all("flash" in m["id"].lower() or "flash" in m["name"].lower() for m in q_models)

    # free_only
    free_models = search_google_models(free_only=True)
    assert all(_is_free_model(m) for m in free_models)

    # limit
    assert len(search_google_models(limit=2)) <= 2


def test_search_grok_models():
    all_models = search_grok_models()
    assert len(all_models) > 0

    q_models = search_grok_models(query="mini")
    assert all("mini" in m["id"].lower() or "mini" in m["name"].lower() for m in q_models)

    free_models = search_grok_models(free_only=True)
    assert isinstance(free_models, list)

    assert len(search_grok_models(limit=1)) <= 1


def test_search_sambanova_models():
    assert search_sambanova_models() == []


def test_provider_searches_delegations(monkeypatch):
    # Test that each search_* delegates to its respective catalog module
    fake_list = [{"id": "test-model", "name": "Test"}]

    monkeypatch.setattr(
        "app.utils.openrouter_catalog.fetch_openrouter_models", lambda force: fake_list
    )
    assert fetch_openrouter_models() == fake_list

    monkeypatch.setattr("app.utils.groq_catalog.search_groq_models", lambda q, limit=50: fake_list)
    assert search_groq_models() == fake_list

    monkeypatch.setattr(
        "app.utils.mistral_catalog.search_mistral_models", lambda q, limit=50: fake_list
    )
    assert search_mistral_models() == fake_list

    monkeypatch.setattr(
        "app.utils.cohere_catalog.search_cohere_models", lambda q, limit=50: fake_list
    )
    assert search_cohere_models() == fake_list

    monkeypatch.setattr("app.utils.hf_catalog.search_hf_models", lambda q, limit=50: fake_list)
    assert search_huggingface_models() == fake_list

    monkeypatch.setattr(
        "app.utils.nvidia_nim_catalog.search_nvidia_models", lambda q, limit=50: fake_list
    )
    assert search_nvidia_models() == fake_list

    monkeypatch.setattr(
        "app.utils.github_models_catalog.search_github_models", lambda q, limit=50: fake_list
    )
    assert search_github_models() == fake_list

    monkeypatch.setattr(
        "app.utils.cloudflare_ai_catalog.search_cloudflare_models", lambda q, limit=50: fake_list
    )
    assert search_cloudflare_models() == fake_list

    monkeypatch.setattr(
        "app.utils.zhipu_catalog.search_zhipu_models", lambda q, limit=50: fake_list
    )
    assert search_zhipu_models() == fake_list


def test_get_all_providers(monkeypatch):
    # Reset cache
    _global_cache["providers"] = {}
    _global_cache["updated_at"] = 0.0

    # Mock create_client
    monkeypatch.setattr("app.models.factory.create_client", lambda cfg: MagicMock())

    providers = get_all_providers(force_refresh=True)
    assert len(providers) >= 10
    assert any(p["key"] == "openrouter" for p in providers)

    # Test cache hit
    providers_cached = get_all_providers(force_refresh=False)
    assert len(providers_cached) == len(providers)


def test_get_all_providers_server_manager_fallbacks(monkeypatch):
    _global_cache["providers"] = {}
    _global_cache["updated_at"] = 0.0

    def fail_client(cfg):
        raise RuntimeError("client creation failed")

    monkeypatch.setattr("app.models.factory.create_client", fail_client)
    monkeypatch.setattr(
        "app.utils.server_manager.ollama_model_names", lambda url: ["local-ollama-1"]
    )
    monkeypatch.setattr(
        "app.utils.server_manager.llamacpp_live_models",
        lambda s: [{"key": "k1", "name": "llama-local"}],
    )

    providers = get_all_providers(force_refresh=True)
    ollama_prov = next((p for p in providers if p["key"] == "ollama"), None)
    assert ollama_prov is not None
    assert ollama_prov["status"] == "available"
    assert ollama_prov["model_count"] == 1

    llamacpp_prov = next((p for p in providers if p["key"] == "llamacpp"), None)
    assert llamacpp_prov is not None
    assert llamacpp_prov["status"] == "available"
    assert llamacpp_prov["model_count"] == 1


def test_get_all_providers_top_level_exception(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.get_settings", MagicMock(side_effect=RuntimeError("settings err"))
    )
    _global_cache["providers"] = {}
    _global_cache["updated_at"] = 0.0
    res = get_all_providers(force_refresh=True)
    assert res == []


def test_get_provider_models(monkeypatch):
    fake_models = [{"id": "m1", "name": "M1"}]
    monkeypatch.setattr(
        "app.utils.openrouter_catalog.search_openrouter_models",
        lambda q, limit=50, free_only=False: fake_models,
    )

    assert get_provider_models("openrouter", free_only=True) == fake_models
    assert get_provider_models("openrouter", free_only=False) == fake_models
    assert get_provider_models("other_provider") == []


def test_get_all_models_summary_and_search(monkeypatch):
    monkeypatch.setattr(
        "app.utils.provider_catalog.get_all_providers",
        lambda: [{"key": "openrouter", "name": "OpenRouter"}],
    )
    fake_models = [
        {"id": "anthropic/claude", "name": "Claude 3.5 Sonnet", "description": "Powerful AI"},
        {"id": "openai/gpt-4o", "name": "GPT-4o", "description": "Omni model"},
    ]
    monkeypatch.setattr(
        "app.utils.provider_catalog.get_provider_models", lambda k, limit=10: fake_models
    )

    summary = get_all_models_summary()
    assert len(summary) == 2
    assert summary[0]["provider"] == "openrouter"

    # Search with empty query
    assert search_all_providers("") == []
    assert search_all_providers("   ") == []

    # Search match
    res = search_all_providers("claude")
    assert len(res) == 1
    assert res[0]["id"] == "anthropic/claude"

    # Search description match
    res_desc = search_all_providers("omni")
    assert len(res_desc) == 1
    assert res_desc[0]["id"] == "openai/gpt-4o"
