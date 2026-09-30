# Model Router

**Status**: ACTIVE
**Type**: reference
**Source**: `app/models/router.py` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Routes LLM requests across multiple providers (OpenAI, Anthropic, Ollama, OpenRouter, etc.) with circuit breakers, fallback chains, and intelligent provider selection.

## Architecture

```
models/
├── client.py (ModelClient Protocol)
├── router.py (ModelRouter)
│   ├── generate(request) → ModelResponse
│   ├── register_provider(provider)
│   └── get_client(provider_name) → ModelClient
├── factory.py (create_client)
│   └── create_client(provider, config) → ModelClient
└── providers/
    ├── openai_provider.py
    ├── anthropic_provider.py
    ├── ollama_provider.py
    └── openrouter_provider.py
```

## Provider Selection Strategy

1. **Intent-based routing**: DIRECT_CHAT → fast provider, MULTI_STEP → capable provider
2. **Circuit breaker**: Failed provider → 30-second cooldown
3. **Fallback chain**: Primary → Secondary → Tertiary
4. **Cost optimization**: Prefer cheaper providers for simple tasks

## Configuration

Provider configurations stored in `app/resources/manager.py`:
```python
# Providers defined in ProviderRegistry class
providers = {
    "openai": {"api_key_env": "OPENAI_API_KEY", "models": [...]},
    "ollama": {"base_url": "http://localhost:11434", "models": [...]},
}
```

## API

```python
from app.models.router import ModelRouter

router = ModelRouter()
response = await router.generate(
    messages=[{"role": "user", "content": "Hello"}],
    provider="openai",  # optional, auto-selected if None
)
```

## Error Handling

- All provider errors wrapped in `ProviderError`
- Circuit breaker prevents cascading failures
- Automatic retry with exponential backoff (max 3 attempts)
