# Multi-Provider Inference Subsystem (`app/models/`) - Version-by-Version History

## Version-by-Version Evolutionary History

### Version v0.1.0 (`e13ee67`)
- **Single Ollama Client**: `app/models/client.py` connecting strictly to local Ollama server at `http://localhost:11434`.

### Version v2.1.0 (`df45be2`)
- **Multi-Backend Runtime**: Added `LlamaCppClient` alongside `OllamaClient`; added token streaming.

### Version v2.4.0 (`6ea9796`)
- **Cloud Provider Integration**: Extended provider support for OpenAI, Groq, Cerebras, SambaNova, OpenRouter, Mistral, and HuggingFace.

### Version v3.0.0 (`81e45f0`)
- **Live Provider Catalog**: Dynamic detection of available local and cloud API endpoints.

### Version v3.0.0 Refactored (`bb7e20b` - `ec0dc4e`) - Current HEAD
- **Standardized Base Interface & Circuit Breaker Pool**:
  - `BaseLLMProvider` (`interface.py`): Abstract base class defining `generate_text()` and `stream_text()`.
  - `LLMResponse` (`interface.py`): Standardized response container tracking content, model IDs, and token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`).
  - `ModelRouter` (`router.py`): Failover pool manager checking `ResourceManager` circuit breaker status and routing around 429/503 errors to fallback providers.
- **Active Invariants at HEAD**:
  1. All LLM backends implement `BaseLLMProvider`.
  2. Automatic circuit breaker failover on rate limit (429) or service outage (503) status codes.
