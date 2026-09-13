# Multi-Provider Inference Subsystem (`app/models/`) - Version-by-Version History

**Status**: ACTIVE
**Last Updated**: 2026-09-13
**Source**: `app/models/` at HEAD

## Version-by-Version Evolutionary History

### Version v0.1.0 (`e13ee67`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27*
- **Single Ollama Client**: `app/models/client.py` connecting strictly to local Ollama server at `http://localhost:11434`.

### Version v2.1.0 (`df45be2`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 | Tag Release Date: 2026-07-05*
- **Multi-Backend Runtime**: Added `LlamaCppClient` alongside `OllamaClient`; added token streaming.

### Version v2.4.0 (`6ea9796`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 | Tag Release Date: 2026-07-14*
- **Cloud Provider Integration**: Extended provider support for OpenAI, Groq, Cerebras, SambaNova, OpenRouter, Mistral, and HuggingFace.

### Version v3.0.0 (`81e45f0`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Live Provider Catalog**: Dynamic detection of available local and cloud API endpoints.

### Version v3.0.0 Refactored (`bb7e20b` - `ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Standardized Base Interface & Circuit Breaker Pool**:
  - `BaseLLMProvider` (`interface.py`): Abstract base class defining `generate_text()` and `stream_text()`.
  - `LLMResponse` (`interface.py`): Standardized response container tracking content, model IDs, and token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`).
  - `ModelRouter` (`router.py`): Failover pool manager checking `ResourceManager` circuit breaker status and routing around 429/503 errors to fallback providers.
- **Active Invariants at HEAD**:
  1. All LLM backends implement `BaseLLMProvider`.
  2. Automatic circuit breaker failover on rate limit (429) or service outage (503) status codes.
