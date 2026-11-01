# Model Router

**Status**: ACTIVE
**Type**: reference
**Source**: `app/models/router.py` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Status: abandoned (unwired)

`ModelRouter` (`app/models/router.py`) is **not on the request path**.
Nothing in `app/` constructs it; `tests/unit/test_router_call_sites.py`
asserts that no call site exists, and `tests/unit/test_dead_code_register.py`
covers the surrounding abandoned components. The live model path is
`container.create_model_client(config)` in `app/adapters/web/router.py`
(see ADR-019).

This document is retained as a record of the intended design and the
interface the tests exercise, not as a description of running behaviour.

## Intended architecture (not live)

```
models/
├── client.py (ModelClient Protocol)
├── router.py (ModelRouter)   # abandoned
├── factory.py (create_client)
└── providers/
    ├── openai_provider.py
    ├── anthropic_provider.py
    ├── ollama_provider.py
    └── openrouter_provider.py
```

## Provider selection strategy (intended, never wired)

1. Intent-based routing: DIRECT_CHAT → fast provider, MULTI_STEP → capable provider
2. Circuit breaker: failed provider → 30-second cooldown
3. Fallback chain: primary → secondary → tertiary
4. Cost optimization: prefer cheaper providers for simple tasks

## Error handling (intended)

- All provider errors wrapped in `ProviderError`
- Circuit breaker prevents cascading failures
- Automatic retry with exponential backoff (max 3 attempts)

## Do not use

```python
# NOT live — construction is prohibited by test_router_call_sites.py
from app.models.router import ModelRouter
router = ModelRouter()
```

Use `container.create_model_client(config)` instead.
