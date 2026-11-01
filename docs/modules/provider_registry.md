# Provider Registry

**Status**: ACTIVE
**Type**: reference
**Source**: `app/provider_registry.py` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Overview

Registry for managing LLM provider configurations and live model catalogs.
Provides a unified interface for listing providers, their status, API-key
requirements, capabilities and fetched model lists.

## Classes

- `ProviderStatus` — status constants (`available`, `unavailable`,
  `keys_missing`, `config_error`)
- `ProviderCapability` — capability flags (OpenAI-compatible, reasoning,
  code generation, free models, context window, max output tokens, …)
- `AIProvider` — one provider: metadata, status, model list, key check
- `ProviderRegistry` — the registry; constructed once, cached by
  `get_provider_registry()`

## Key methods (`ProviderRegistry`)

- `get_all_providers(force_refresh=False)` → list[dict]
- `get_provider(provider_key)` → dict | None
- `get_providers_by_category(category)` → list[dict]
- `search_providers(query)` → list[dict]
- `check_provider_status(provider_key)` → AIProvider

## Configuration

Providers are initialised in `ProviderRegistry._initialize_providers()` from
shipped defaults; some fetch live catalogs (OpenRouter, Google, Groq, …).
Runtime overrides are not stored in `~/jarvis_providers.json` — earlier
versions of this document described that, but it does not exist.

## API

```python
from app.provider_registry import get_provider_registry

registry = get_provider_registry()
providers = registry.get_all_providers()
one = registry.get_provider("openrouter")
```

## Validation

- API key env var must be set (or the provider is marked `keys_missing`)
- At least the shipped default model list is present
- Duplicate provider keys are not registered
