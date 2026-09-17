# Provider Registry

**Status**: ACTIVE
**Type**: reference
**Source**: `app/provider_registry.py` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Registry for managing LLM provider configurations. Provides a unified interface for listing, adding, updating, and removing providers without restarting JARVIS.

## Architecture

```
provider_registry.py (ProviderRegistry)
├── get_provider(name) → ProviderSpec
├── list_providers() → list[ProviderSpec]
├── register_provider(name, spec)
├── update_provider(name, spec)
└── remove_provider(name)
```

## Data Model

```python
class ProviderSpec:
    name: str
    display_name: str
    api_key_env: str
    base_url: str | None
    models: list[str]
    enabled: bool
    capabilities: list[str]  # ["chat", "embeddings", "images"]
```

## Configuration

Providers are stored in two places:
1. **Static config**: `app/resources/manager.py` (shipped defaults)
2. **Runtime overrides**: `~/jarvis_providers.json` (user customizations)

Runtime overrides take precedence.

## API

```python
from app.provider_registry import get_provider_registry

registry = get_provider_registry()
providers = registry.list_providers()
registry.register_provider("my-provider", ProviderSpec(...))
```

## Validation

- API key env var must be set (or explicitly marked as local/no-key)
- Base URL must be valid URL (if provided)
- At least one model must be specified
- Duplicate names rejected
