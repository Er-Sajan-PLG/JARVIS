# app/utils

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | (no module docstring) | — |
| `anthropic_catalog.py` | Live Anthropic (Claude) model catalog. | `fetch_anthropic_models()`, `is_free_model()`, `search_anthropic_models()` |
| `cerebras_catalog.py` | Live Cerebras model catalog. | `fetch_cerebras_models()`, `is_free_model()`, `search_cerebras_models()` |
| `cloudflare_ai_catalog.py` | Live Cloudflare Workers AI model catalog. | `_resolve_key()`, `fetch_cloudflare_models()`, `search_cloudflare_models()` |
| `cohere_catalog.py` | Live Cohere model catalog. | `_resolve_key()`, `fetch_cohere_models()`, `search_cohere_models()` |
| `corruption.py` | Helpers for handling corrupted on-disk state. | `backup_corrupt_file()`, `report_corruption()` |
| `github_models_catalog.py` | Live GitHub Models catalog. | `_resolve_key()`, `fetch_github_models()`, `search_github_models()` |
| `google_catalog.py` | Live Google AI Studio (Gemini) model catalog. | `_resolve_key()`, `fetch_google_models()`, `search_google_models()` |
| `groq_catalog.py` | Live Groq model catalog. | `_resolve_key()`, `fetch_groq_models()`, `search_groq_models()` |
| `hf_catalog.py` | Live Hugging Face model catalog. | `_resolve_key()`, `fetch_hf_models()`, `search_hf_models()` |
| `image.py` | Image Utilities. | `get_image_info()`, `is_supported_image()`, `validate_image()` |
| `logging_setup.py` | Centralized logging setup for JARVIS. | `get_logger()`, `setup_logging()` |
| `mistral_catalog.py` | Live Mistral AI model catalog. | `_resolve_key()`, `fetch_mistral_models()`, `search_mistral_models()` |
| `model_selector.py` | Startup model selector for JARVIS. | `_build_ollama_router()`, `_categorize_cloud_models()`, `_startup_model_select()` |
| `nvidia_nim_catalog.py` | Live NVIDIA NIM model catalog. | `_resolve_key()`, `fetch_nvidia_models()`, `search_nvidia_models()` |
| `openai_catalog.py` | Live OpenAI model catalog. | `fetch_openai_models()`, `is_free_model()`, `search_openai_models()` |
| `openrouter_catalog.py` | Live OpenRouter model catalog. | `_resolve_key()`, `fetch_openrouter_models()`, `is_free_model()`, `search_openrouter_models()` |
| `pdf.py` | PDF Processing Utilities. | `Page`, `extract_pages()`, `get_image_paths()`, `is_pdf()`, `pdf_to_images()` |
| `provider_catalog.py` | Unified provider catalog for JARVIS. | `_build_provider_models()`, `_ensure_env_keys()`, `_get_model_categories()`, `_is_free_model()`, `_live_models_for()`, `_local_models_for()`, `_normalize_provider_key()`, `_pricing_is_zero()` |
| `server_manager.py` | Helpers for detecting and auto-starting the local model servers JARVIS needs. | `ensure_server_running()`, `find_llama_server_binary()`, `is_local_url()`, `is_port_open()`, `llamacpp_live_models()`, `match_ollama_model()`, `ollama_model_names()`, `port_from_url()` |
| `text.py` | Shared text utilities for memory retrieval and ranking. | `extract_keywords()` |
| `together_catalog.py` | Live Together AI model catalog. | `fetch_together_models()`, `is_free_model()`, `search_together_models()` |
| `tokenizer.py` | Token Counting for JARVIS v2.0 | `_try_tiktoken()`, `_try_transformers()`, `_word_counter()`, `estimate_tokens()`, `get_token_counter()`, `get_tokenizer_info()` |
| `zhipu_catalog.py` | Live Zhipu AI (GLM) model catalog. | `_resolve_key()`, `fetch_zhipu_models()`, `search_zhipu_models()` |

<!-- generated:module_readmes end -->
