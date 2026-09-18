# Configuration

**Status**: ACTIVE
**Type**: reference
**Source**: `app/config/`, `.env.example` at HEAD
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

The configuration of JARVIS v2.1 is managed through a centralized system designed for clarity, modularity, and easy overrides.

## Configuration Architecture

The core of the configuration system resides in `app/config/settings.py`. It leverages Python's `dataclasses` to define structured configuration objects.

-   **`Settings` Dataclass**: This is the master configuration container. It aggregates instances of other specialized configuration dataclasses, providing a single point of access for all application settings.
-   **Specialized Dataclasses**:
    -   `ModelConfig`: Defines settings for individual models (e.g., name, backend, API details).
    -   `MemoryConfig`: Manages parameters related to the memory system (e.g., limits, retrieval scores).
    -   `ContextConfig`: Configures the context window (e.g., token limits, compression).
    -   `ConversationConfig`: Handles conversation management settings (e.g., message history, summarization).
    -   `RetrievalConfig`: Specifies parameters for memory retrieval methods.
    -   `RankingConfig`: Configures the weighting for memory ranking algorithms.
    -   `PathsConfig`: Centralizes all file system paths used by the application.

A **thread-safe singleton pattern** is implemented using `get_settings()` to ensure that only one instance of the `Settings` object is loaded and accessible throughout the application.

## Config Files

The primary source for external configuration is the `config.yaml` file located at the project root.

-   **Loading Mechanism**: The `Settings.load()` class method attempts to read and parse `config.yaml`.
-   **Default Fallback**: If `config.yaml` is not found, the application gracefully falls back to using hardcoded default values defined within the `Settings` dataclass and its nested configuration classes.
-   **Verified**: `config.yaml` is a normal tracked file in this repository and is
    read directly by `Settings.load()`. An earlier revision of this document
    claimed the file could not be inspected by automated agents and inferred its
    behaviour instead — that was a tooling artefact of the session that wrote it,
    not a property of the repository.

## Environment Variables

`app/config/settings.py` imports `load_dotenv` (from `python-dotenv`) and `yaml`.

**Verified against `app/config/settings.py` at HEAD:** `Settings` itself does not
call `os.getenv()` — environment overrides are not applied inside the dataclasses
described here. Instead the split is:

- **`config.yaml`** supplies structural configuration (models, paths, limits) via
  `Settings.load()` → `yaml.safe_load()`. A missing file, an unreadable file, or a
  YAML error each degrade to the built-in defaults with a logged warning — startup
  never fails on configuration.
- **Environment variables** are consumed by the layer *above* settings — API keys
  and service wiring in `app/bootstrap.py` and the adapters — not by `Settings`.
  `load_dotenv()` is called during application startup so a `.env` file populates
  `os.environ` before that wiring runs.

So: environment variables do affect the running system, but they are read where
the credentials and endpoints are used, not inside `app/config/settings.py`.

### Environment variable reference

Enumerated from `.env.example` at HEAD plus every `os.getenv` / `os.environ.get`
read under `app/` at HEAD. One row per variable: name, read by, default as the
code states it. Rows marked "`.env.example` only" are declared in the example
file but have no reader in `app/` at HEAD — setting them has no effect.

| Variable | Read by | Default |
|---|---|---|
| JARVIS_API_KEY | `app/adapters/security.py`, `app/main.py` (required when binding beyond localhost) | unset (empty) |
| OPENROUTER_API_KEY | `app/provider_registry.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py`, `config.yaml` | unset |
| XAI_API_KEY | `config.yaml`, `app/models/groq_client.py`, `app/utils/model_selector.py` | unset |
| GOOGLE_API_KEY | `app/provider_registry.py`, `app/models/google_client.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py`, `config.yaml` | unset |
| GROQ_API_KEY | `app/provider_registry.py`, `app/models/groq_client.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py` | unset |
| CEREBRAS_API_KEY | `app/provider_registry.py`, `app/models/cerebras_client.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py` | unset |
| CLOUDFLARE_API_KEY | `app/utils/cloudflare_ai_catalog.py` | unset |
| ZHIPU_API_KEY | `app/utils/provider_catalog.py`, `app/adapters/web/settings.py` | unset |
| ZHIPUAI_API_KEY | `app/utils/provider_catalog.py` (alias) | unset |
| COHERE_API_KEY | `app/models/cohere_client.py` | unset |
| GEMINI_API_KEY | `app/models/google_client.py` | unset |
| GITHUB_API_KEY | `app/models/github_models_client.py` | unset |
| GITHUB_TOKEN | `scripts/ci_bridge.py`, tooling | unset |
| HUGGINGFACE_API_KEY | `app/models/hf_client.py` | unset |
| JARVIS_DATABASE_URL | `app/db/`, Postgres checkpointer | unset |
| JARVIS_ELEVENLABS_API_KEY | `app/integrations/voice/` (server TTS alt) | unset |
| JARVIS_LOG_LEVEL | logging, server | unset |
| JARVIS_OTEL_ENABLED | `app/telemetry/` | unset |
| JARVIS_OTEL_ENDPOINT | `app/telemetry/` | unset |
| JARVIS_OTEL_HEADERS | `app/telemetry/` | unset |
| JARVIS_OTEL_SERVICE_NAME | `app/telemetry/` | unset |
| JARVIS_SAMPLE_RATE | `app/integrations/voice/` | unset |
| JARVIS_TTS_PROVIDER | `app/integrations/voice/` (default `pyttsx3`) | unset |
| JARVIS_VERSION | `app/config/version.py` (version override) | unset |
| JARVIS_WAKE_WORD | `app/integrations/voice/` (default `jarvis`) | unset |
| LLAMA_SERVER_PATH | `app/models/llamacpp_client.py` | unset |
| MISTRAL_API_KEY | `app/models/mistral_client.py` | unset |
| SAMBANOVA_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| NVIDIA_API_KEY | `app/utils/provider_catalog.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py` | unset |
| NVIDIA_NIM_API_KEY | `app/provider_registry.py`, `app/models/nvidia_nim_client.py`, `app/utils/provider_catalog.py` | unset |
| SINGULARITY_API_KEY | `app/adapters/web/router.py`, `app/adapters/web/settings.py` | unset |
| QWEN_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| OPENCODE_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| UNOROUTER_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| TOKENROUTER_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| TOKENHARBOUR_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| EXA_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| XKIRO_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| CHUTES_AI_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| CHUTES_AI_FINGLERPRINT | `.env.example` only — no reader in `app/` at HEAD | unset |
| REQUESTY_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| CF_API_KEY | `.env.example` only — no reader in `app/` at HEAD (Cloudflare inference reads CLOUDFLARE_API_TOKEN below) | unset |
| CLOUDFLARE_API_TOKEN | `app/models/cloudflare_ai_client.py`, `app/utils/cloudflare_ai_catalog.py`, `app/utils/provider_catalog.py`, `app/provider_registry.py` | unset |
| CLOUDFLARE_ACCOUNT_ID | `app/models/cloudflare_ai_client.py` | unset |
| HF_API_URL | `app/utils/hf_catalog.py` | `https://huggingface.co/api/models` |
| HF_TOKEN | `app/utils/hf_catalog.py`, `app/utils/provider_catalog.py`, `app/adapters/web/router.py`, `app/adapters/web/settings.py` | unset |
| LEARNING_COMMONS_API_KEY | `.env.example` only — no reader in `app/` at HEAD | unset |
| TELEGRAM_BOT_TOKEN | `app/integrations/telegram/__init__.py` (falls back to TELEGRAM_API_KEYS) | unset |
| TELEGRAM_ALLOWED_CHAT_IDS | `app/integrations/telegram/__init__.py` | unset (empty — no chat is answered) |
| TELEGRAM_ENABLED | `app/integrations/telegram/__init__.py`, `app/main.py` (poller starts only when `true` with a token) | `false` |
| WHATSAPP_TOKEN | `app/integrations/whatsapp/__init__.py` | unset |
| WHATSAPP_PHONE_ID | `app/integrations/whatsapp/__init__.py` | unset |
| WHATSAPP_TO | `app/integrations/whatsapp/__init__.py` | unset |
| WHATSAPP_TEMPLATE | `app/integrations/whatsapp/__init__.py` | `hello_world` |
| WHATSAPP_ENABLED | `app/integrations/whatsapp/__init__.py` | `false` |
| JARVIS_EMAIL_ADDRESS | `app/integrations/email/client.py` | unset |
| JARVIS_EMAIL_PASSWORD | `app/integrations/email/client.py` | unset |
| JARVIS_EMAIL_IMAP_HOST | `app/integrations/email/client.py` | `imap.gmail.com` |
| JARVIS_EMAIL_IMAP_PORT | `app/integrations/email/client.py` (not listed in `.env.example`) | `993` |
| JARVIS_EMAIL_SMTP_HOST | `app/integrations/email/client.py` | `smtp.gmail.com` |
| JARVIS_EMAIL_SMTP_PORT | `app/integrations/email/client.py` (not listed in `.env.example`) | `587` |
| JARVIS_BRIEF_ENABLED | `app/integrations/brief/__init__.py` | `false` |
| JARVIS_BRIEF_TIME | `app/integrations/brief/__init__.py` | `08:00` |
| JARVIS_BRIEF_DELIVERY | `app/integrations/brief/__init__.py` | `slack` (`.env.example` comments `push`) |
| JARVIS_BRIEF_EMAIL | `app/integrations/brief/__init__.py` | unset |
| JARVIS_BRIEF_SLACK_WEBHOOK | `app/integrations/brief/__init__.py` (actual name — there is no JARVIS_SLACK_WEBHOOK) | unset |
| VAPID_PRIVATE_KEY | `app/integrations/push/__init__.py` | unset |
| VAPID_PUBLIC_KEY | `app/adapters/web/push_routes.py` | unset |
| VAPID_CLAIMS_EMAIL | `app/integrations/push/__init__.py` | `mailto:jarvis@localhost` |
| CORS_ALLOWED_ORIGINS | `app/main.py` | `http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000,http://127.0.0.1:3000,capacitor://localhost,http://localhost,https://localhost` |
| JARVIS_PUBLIC_ORIGIN | `app/main.py` (appended to the CORS allowlist when set) | unset |
| JARVIS_HOST | `app/main.py` | `0.0.0.0` |
| JARVIS_PORT | `app/main.py` | `8000` |
| JARVIS_STT_MODEL | `app/adapters/web/voice_routes.py` (default `tiny`), `app/integrations/voice/__init__.py` (default `base`) | `tiny` on the web route, `base` in the integration |
| JARVIS_TTS_VOICE | `app/adapters/web/voice_routes.py` | `en-US-ChristopherNeural` |
| JARVIS_WORKSPACE_ROOT | `app/tools/workspace_tools.py` | repo root |
| JARVIS_EXTRA_ALLOWED_ROOTS | `app/tools/workspace_tools.py` (actual name; system temp dir is always allowed) | unset (empty) |
| JARVIS_SUBAGENTS | `app/tools/subagent_tools.py` (allowlisted worker agents) | `build,plan,general` |
| OPENCODE_BIN | `app/tools/subagent_tools.py` (worker binary override) | auto-detected |
| HERMES_BIN | `app/tools/subagent_tools.py` (hermes worker override) | auto-detected |
| DSH_CMD | `app/tools/subagent_tools.py` (deepseek harness command, e.g. `node .../apps/cli/lib/bin.js`) | harness default |
| DSH_DIR | `app/tools/subagent_tools.py` (deepseek harness cwd) | harness default |
| JARVIS_MCP_KEY | `app/integrations/mcp/server.py` (shared key for MCP clients) | unset (no check) |

## Default Values

All configuration parameters within the `dataclasses` in `app/config/settings.py` are assigned sensible default values. These defaults are used if no `config.yaml` file is present or if a particular setting is not specified within the YAML file.

### `ModelConfig` Defaults:
-   `backend`: `"llamacpp"`
-   `base_url`: `"http://localhost:8080/v1"`
-   `api_key`: `"not-needed"`
-   `max_tokens`: `4096`
-   `temperature`: `0.7`

### `MemoryConfig` Defaults:
-   `max_memories`: `1000`
-   `retrieval_limit`: `20`
-   `min_relevance_score`: `0.1`
-   `min_confidence`: `0.0`
-   `enable_ranking`: `True`
-   `candidate_overshoot_factor`: `3`

### `ContextConfig` Defaults:
-   `max_tokens`: `4096`
-   `safety_margin`: `100`
-   `compression_threshold`: `0.8`
-   `tokenizer_method`: `"auto"`

### `ConversationConfig` Defaults:
-   `max_recent_messages`: `20`
-   `enable_summarization`: `False`
-   `save_on_every_message`: `True`

### `RetrievalConfig` Defaults:
-   `method`: `"keyword"`
-   `keyword_min_overlap`: `1`

### `RankingConfig` Defaults:
-   `weight_relevance`: `0.35`
-   `weight_importance`: `0.25`
-   `weight_frequency`: `0.15`
-   `weight_recency`: `0.15`
-   `weight_confidence`: `0.10`
-   `recency_half_life_days`: `7.0`

### `PathsConfig` Defaults:
-   `data_dir`: `Path("data")` (resolves to `./data` relative to the project root)

### `Settings` Defaults:
-   `default_model`: `"qwen3-8b.gguf"`
-   `active_profile`: `"local"`
-   `profiles`: A dictionary defining `local` and `cloud` profiles with model mappings.
-   `models`: A dictionary containing default `ModelConfig` instances for `"general"` and `"autocomplete"` roles.

## Validation

The configuration system primarily relies on Python's `dataclasses` and type hints for implicit type enforcement. There is no explicit runtime validation logic (e.g., range checks, format validation, or custom business logic validation) implemented directly within the `Settings` or its associated configuration dataclasses in `app/config/settings.py`.

Should the `config.yaml` file contain values that are of incorrect types or fall outside expected ranges, it could lead to runtime errors or unexpected application behavior when these misconfigured values are used.

## Runtime Overrides

Once the `Settings` object is loaded via `get_settings()`, its attributes can theoretically be modified at runtime. For example:

```python
from app.config.settings import get_settings

settings = get_settings()
settings.memory.max_memories = 500
settings.context.max_tokens = 2048
```

However, due to the singleton pattern enforced by `get_settings()`, any modifications to the returned `Settings` instance will affect the global configuration accessible throughout the application. While this provides flexibility, it's essential to manage such overrides carefully to avoid inconsistencies, especially in multi-threaded environments or long-running processes. The architecture generally promotes a "load once, use many" philosophy for configuration.

A `reset_settings()` function is available (primarily for testing purposes) which clears the loaded singleton, forcing a reload of settings on the next `get_settings()` call. This could be leveraged to apply new configurations dynamically if needed, though it's not the primary intended use case for production.

## Configuration Lifecycle

1.  **First Access**: The first time `get_settings()` is called, it checks if a `Settings` instance (`_settings`) has already been loaded.
2.  **Thread-Safe Loading**: If no instance exists, a thread-safe lock (`_lock`) is acquired to prevent multiple threads from initializing `Settings` simultaneously.
3.  **`Settings.load()` Invocation**: Inside the locked section, `Settings.load()` is called:
    -   It first initializes a `Settings` object with all its default values.
    -   It then attempts to locate and read `config.yaml` at the project root.
    -   If `config.yaml` exists, it parses the YAML content and uses it to override the corresponding default values in the `Settings` object (e.g., `default_model`, `models`, `memory`, etc.).
    -   If `config.yaml` does not exist, the default `Settings` object is returned as is.
4.  **Singleton Assignment**: The fully constructed and configured `Settings` object is assigned to the global `_settings` variable.
5.  **Subsequent Access**: All subsequent calls to `get_settings()` will directly return this previously loaded `_settings` instance, ensuring consistent configuration across the application without repeated loading operations.
6.  **Reset Capability**: The `reset_settings()` function, when called, sets `_settings = None`. This effectively "resets" the singleton, causing the next call to `get_settings()` to go through the loading process again. This is typically used in testing scenarios or for explicit re-initialization.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
6ea9796|Er Sajan PLG|2026-07-11 22:42:47 +0545|feat(platform): expand model backends and configuration system
```

Notes: This log was generated from the repository history for `docs/CONFIG.md`.
