# app/models

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Models Package. | — |
| `anthropic_client.py` | Anthropic (Claude) model client for JARVIS. | `AnthropicClient` |
| `cerebras_client.py` | Cerebras model client for JARVIS. | `CerebrasClient` |
| `client.py` | (no module docstring) | `ModelClient`, `ModelResponse` |
| `cloudflare_ai_client.py` | Cloudflare Workers AI model client for JARVIS. | `CloudflareAIClient` |
| `cohere_client.py` | Cohere model client for JARVIS. | `CohereClient` |
| `exceptions.py` | Typed errors raised by model clients. | `ModelConnectionError`, `ModelError`, `ModelRateLimitError`, `ModelResponseError`, `ModelTimeoutError`, `_httpx_timeout_errors()`, `map_ollama_error()`, `map_openai_error()` |
| `factory.py` | (no module docstring) | `create_client()` |
| `github_models_client.py` | GitHub Models client for JARVIS. | `GitHubModelsClient` |
| `google_client.py` | Google Gemini model client for JARVIS. | `GoogleClient`, `_loads()` |
| `groq_client.py` | Groq model client for JARVIS. | `GroqClient` |
| `hf_client.py` | Hugging Face model client for JARVIS. | `HuggingFaceClient` |
| `interface.py` | BaseLLMProvider Interface & Data Contracts for Multi-Provider Inference Subsystem. | `BaseLLMProvider`, `LLMResponse` |
| `llamacpp_client.py` | LlamaCpp model client for JARVIS v2.0 | `LlamaCppClient` |
| `mistral_client.py` | Mistral AI model client for JARVIS. | `MistralClient` |
| `nvidia_nim_client.py` | NVIDIA NIM model client for JARVIS. | `NVIDIANIMClient` |
| `ollama_client.py` | (no module docstring) | `OllamaClient` |
| `omni_client.py` | OmniModelClient — routes requests across multiple underlying ModelClient | `OmniModelClient` |
| `openai_client.py` | OpenAI model client for JARVIS. | `OpenAIClient` |
| `openrouter_client.py` | OpenRouter model client for JARVIS. | `OpenRouterClient` |
| `router.py` | Model Router & Provider Failover Pool for Multi-Provider Inference. | `ModelRouter`, `TaskType`, `_classify_provider_failure()` |
| `switcher.py` | Runtime model profile switcher. | `ModelSwitcher` |
| `together_client.py` | Together AI model client for JARVIS. | `TogetherClient` |
| `utils.py` | (no module docstring) | `resolve_env_key()` |
| `zhipu_client.py` | Zhipu AI (GLM) model client for JARVIS. | `ZhipuClient` |

<!-- generated:module_readmes end -->
