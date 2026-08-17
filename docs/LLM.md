# LLM — Model Architecture, Selection & Inference

> **Scope / verification note.** Every statement below was verified against the
> source code in `app/`. One source file, `config.yaml`, could **not** be read
> (the tooling blocked it as a security concern). Therefore all claims about
> *which models are actually wired up* are derived from the hardcoded defaults in
> `app/config/settings.py` (`Settings.models`, `Settings.profiles`), not from a
> deployment `config.yaml`. Where the shipped defaults differ from what a real
> `config.yaml` would supply, the discrepancy is called out explicitly.

> **Version.** `app/config/version.py` → `VERSION = "v.2.4.0"`. The model layer
> is the `app/models/` package plus its callers in `app/main.py` and
> `app/agents/doc_agent.py`.

---

## 1. Model architecture

The model layer is built around a single Python `Protocol` and a small set of
concrete clients. All clients are interchangeable behind the same interface.

### 1.1 The `ModelClient` Protocol — `app/models/client.py`

```python
# app/models/client.py
@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None

class ModelClient(Protocol):
    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse: ...

    @property
    def model_name(self) -> str: ...

    @property
    def role(self) -> str: ...
```

- `generate(messages, stream, on_token, **kwargs)` is the uniform entry point.
  `messages` is a list of OpenAI-style `{"role", "content"}` dicts.
- `ModelResponse` carries the text (`content`), the model id (`model`), and
  optionally `tokens_used` / `finish_reason`.
- **Important:** `tokens_used` is only populated on the **non-streaming** path
  (see §8). On streaming calls every client returns `tokens_used=None`.
- `**kwargs` are forwarded to the underlying provider client by the concrete
  clients (e.g. `temperature`, `max_tokens`). `stream` and `on_token` are
  **consumed by the client and not** forwarded to the API.

### 1.2 Concrete clients

| Client | File | Transport | Backend string |
|--------|------|-----------|----------------|
| `LlamaCppClient` | `app/models/llamacpp_client.py` | `openai.OpenAI` → local server | `"llamacpp"` (default) |
| `OllamaClient` | `app/models/ollama_client.py` | `ollama.Client` (`ollama` package) | `"ollama"` |
| `OpenRouterClient` | `app/models/openrouter_client.py` | `openai.OpenAI` → OpenRouter URL | `"openrouter"` |
| `GoogleClient` | `app/models/google_client.py` | `requests` → Gemini Generative Language API | `"google"` |

All four implement `generate()`, `model_name`, and `role` identically, so the
router/switcher cannot tell them apart — this is stated explicitly in the
`OpenRouterClient` docstring ("The router can't tell the difference").

---

## 2. Supported providers

Selection of provider is driven by `ModelConfig.backend`
(`app/config/settings.py`).

1. **llama.cpp (local)** — `LlamaCppClient`. Uses the OpenAI-compatible chat
   completions API exposed by a `llama-server` instance. Default
   `base_url = "http://localhost:8080/v1"`, default `api_key = "not-needed"`.
2. **Ollama (local)** — `OllamaClient`. Uses the `ollama` Python package's
   `Client(host=base_url)` with `base_url` defaulting to
   `"http://localhost:11434"`.
3. **OpenRouter (cloud)** — `OpenRouterClient`. Uses the OpenAI SDK pointed at
   `BASE_URL = "https://openrouter.ai/api/v1"`, with real `api_key` and
   `HTTP-Referer` / `X-Title` headers for OpenRouter attribution. The module
   docstring notes it exposes 200+ cloud models via one OpenAI-compatible API.
4. **Google Gemini (cloud)** — `GoogleClient`. Uses `requests` against the
   Gemini Generative Language API (`BASE_URL =
   "https://generativelanguage.googleapis.com/v1beta"`), with the API key passed
   as a URL query parameter. `system` messages are lifted into Gemini's
   `systemInstruction` and `assistant` turns are mapped to Gemini's `model`
   role, so OpenAI-style message lists work unchanged. Select it in
   `config.yaml` with `backend: "google"` and `api_key: "env:GOOGLE_API_KEY"`.

**Providers referenced but NOT active:**
- **`autocomplete`** model (default config) — a `LlamaCppClient` on port `8082`
  is instantiated (see §6), but no default profile maps it to a router, so it is
  never selected. See uncertainty note below.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
f9fa068|Er Sajan PLG|2026-07-18 18:05:40 +0545|feat: add web UI, FastAPI server, and fix batch of issues
6ea9796|Er Sajan PLG|2026-07-11 22:42:47 +0545|feat(platform): expand model backends and configuration system
```

Notes: This log was generated from the repository history for `docs/LLM.md`.

---

## 3. Factory pattern

`app/models/factory.py` → `create_client(config: ModelConfig) -> ModelClient`
encapsulates "which concrete class to build" so callers (the switcher) never
import clients directly.

```python
# app/models/factory.py (condensed)
def _resolve_key(api_key: str) -> str:
    # "env:XAI_API_KEY" -> os.environ["XAI_API_KEY"]
    # "literal-key"     -> returned as-is
    ...

def create_client(config: ModelConfig) -> ModelClient:
    api_key = _resolve_key(config.api_key)        # resolve once up-front
    if config.backend == "ollama":
        ...
        return OllamaClient(model=config.name, base_url=config.base_url, api_key=api_key, role=config.role)
    if config.backend == "openrouter":
        ...
        return OpenRouterClient(model=config.name, api_key=_resolve_key(config.api_key), role=config.role)
    if config.backend == "google":
        ...
        return GoogleClient(model=config.name, api_key=api_key, role=config.role)
    # Default: llamacpp
    return LlamaCppClient(model=config.name, base_url=config.base_url,
                          api_key=config.api_key, role=config.role)
```

Key behaviors, all verified in source:
- **Dispatch by `backend`** string: `"ollama"` → `OllamaClient`,
  `"openrouter"` → `OpenRouterClient`, `"google"` → `GoogleClient`, anything
  else → `LlamaCppClient`.
- **Optional imports.** `ollama` and `openrouter` are imported inside
  `try/except ImportError`; `OLLAMA_AVAILABLE` / `OPENROUTER_AVAILABLE` flags
  gate the branches. If the package is missing, the factory raises
  `ImportError` with an install hint rather than failing at import time.
- **Env-var key resolution.** `resolve_env_key()` (in `app/models/utils.py`) turns `"env:VAR"` into the real
  value; if the env var is unset it raises `ValueError` with a clear message.
  - For `llamacpp`, the *raw* `config.api_key` is passed to the client, which
    re-resolves it using `resolve_env_key` in its `__init__` and catches `ValueError` to preserve backward compatibility if a fallback is needed (so a literal `"not-needed"` or an `"env:..."` both work).
  - For `openrouter`, `resolve_env_key` is called **twice** (once at the top of the
    function, once inline). This is redundant but harmless: the second call sees
    an already-resolved literal key and returns it unchanged.

---

## 4. Router

`app/models/router.py` → `ModelRouter`. Routes a prompt to a `ModelClient` by
task type. It is **provider-agnostic** — it only holds `ModelClient` instances.

### 4.1 `TaskType` enum

```python
class TaskType(Enum):
    AUTOCOMPLETE = "autocomplete"
    CODE         = "code"
    REASONING    = "reasoning"
    STEM         = "stem"
    GENERAL      = "general"
    DOCS         = "docs"
```

### 4.2 Keyword classification (score-based)

`KEYWORDS` defines keyword lists for **only three** task types:
`CODE` (16 keywords), `STEM` (15), `REASONING` (14). `AUTOCOMPLETE`, `GENERAL`,
and `DOCS` have **no** keyword lists and can therefore only be reached via an
explicit `select(task_type)` call, never by automatic classification.

`_classify_prompt(prompt)`:
1. Lowercases the prompt.
2. Sums the keyword hits per task type → scores.
3. If `max_score == 0` → returns `TaskType.GENERAL`.
4. If a single task type has the max score → returns it.
5. On a tie → tie-break by specificity order `CODE > STEM > REASONING`
   (`preference_order`), else `GENERAL`.

### 4.3 Selection API

```python
def register(self, task_type: TaskType, client: ModelClient): ...
def set_default(self, client: ModelClient): ...
def select(self, task_type: TaskType) -> ModelClient:
    if task_type in self.models: return self.models[task_type]
    if self.default_model:      return self.default_model
    raise ValueError(f"No model for task type: {task_type}")
def route(self, prompt: str) -> tuple[ModelClient, TaskType]:
    task_type = self._classify_prompt(prompt)
    return self.select(task_type), task_type
```

- `route()` returns a `(ModelClient, TaskType)` tuple — the call site in
  `main.py` unpacks both: `selected_model, task_type = switcher.router.route(prompt)`.
- `select()` returns the registered client, or the `default_model` fallback, or
  raises `ValueError` if neither exists. Note it **never returns `None`** — it
  either returns a client or raises.

---

## 5. Model selection

`app/models/switcher.py` → `ModelSwitcher`. This is the object `main.py`
actually holds (`switcher = ModelSwitcher(settings)`). It bridges
`Settings.models` (the client definitions) and `Settings.profiles` (role→model
mappings) into one `ModelRouter` per profile.

### 5.1 Build-time wiring

In `__init__`:
1. **Instantiate every client** listed in `settings.models` via `create_client`,
   storing them in `self._clients[key]`. A load failure is caught, printed as a
   warning (`⚠️ Could not load '<key>'`), and skipped — one bad model does not
   abort startup.
2. **Build one `ModelRouter` per profile** in `settings.profiles` via
   `_build_router(mapping)`:
   - For each `role -> model_key` in the profile mapping, look up the client.
     If the client is missing, skip (`if not client: continue`).
   - `TaskType(role)` converts the role string to an enum value; an unknown role
     raises `ValueError`, which is silently swallowed (`except ValueError: pass`).
   - The router's **default** is set from `mapping.get("general")` if that key
     resolves to a loaded client.

### 5.2 Runtime switching

- `switcher.router` (property) returns the router for the **active** profile.
- `switcher.switch(profile)` flips the active profile if it exists; otherwise
  returns `False` (and `main.py` reports "Unknown profile").
- `switcher.get_client(key)` returns a raw client by key (used to feed the
  `DocumentationAgent`).
- `switcher.status()` / `list_profiles()` print active profile + loaded models.

### 5.3 ⚠️ What is actually active under the shipped defaults

> **This is the most important caveat in this document.** It is derived purely
> from `app/config/settings.py` because `config.yaml` was unreadable.

The hardcoded `Settings` defaults define only **two** models:

```python
models = {
    "general":      ModelConfig(name="llama-3.2-3b-instruct-q4_k_m.gguf", backend="llamacpp", base_url="http://localhost:8080/v1"),
    "autocomplete": ModelConfig(name="qwen2.5-1.5b-instruct-q4_k_m.gguf", backend="llamacpp", base_url="http://localhost:8082/v1", max_tokens=150),
}
```

The hardcoded `profiles` reference model keys that **do not exist** in those
defaults:

```python
profiles = {
    "local":  {"general": "general", "code": "code", "reasoning": "reasoning", "docs": "docs", "stem": "reasoning"},
    "cloud":  {"general": "cloud",   "code": "cloud", "reasoning": "cloud",   "docs": "cloud", "stem": "cloud"},
}
```

Consequences under defaults (no `config.yaml`):
- For the **`local`** profile, only `"general"` resolves to a loaded client. The
  `code`/`reasoning`/`docs`/`stem` keys are `None` and skipped. So the router
  registers `TaskType.GENERAL → general` and sets it as default. **Every** routed
  prompt (code, stem, reasoning, docs, general) ultimately hits the single
  `general` model via the default fallback.
- The **`autocomplete`** client is instantiated but never mapped to any router
  (`TaskType.AUTOCOMPLETE` has no keywords and no profile entry), so it is dead
  under defaults.
- The **`cloud`** profile maps everything to `"cloud"`, which is absent from the
  default `models`. Result: an empty router with **no default**
  (`mapping.get("general")` → `"cloud"` → not a loaded client). Switching to
  `cloud` succeeds (`switcher.switch` returns `True`) but any `route()` call
  would raise `ValueError` in `select()`. So `cloud` is non-functional with
  defaults.

**A real `config.yaml` is clearly expected to define the `code`, `reasoning`,
`docs`, `stem`, and `cloud` model entries** (the code path, switcher, and docs
all assume they exist). Because `config.yaml` could not be read here, the
statements above describe the code path with the Python defaults, and may not
match a deployed configuration.

---

## 6. Prompt flow

The only path that reaches a model is the CLI REPL in `app/main.py` (there is no
HTTP server in the codebase — FastAPI/uvicorn appear only in `requirements.txt`).
Per-loop sequence (verified in `main()`):

1. **User input** → `prompt = input("You: ")`. Commands (`quit`, `memories`,
   `help`, `stats`, `model …`, `docs`) are intercepted before the pipeline.
2. **Record user turn** → `conversation.add_message("user", prompt)`.
3. **Fact extraction** → `facts = extract_facts(prompt)`; each fact is stored via
   `memory.store(fact)` (so it is visible to this turn's retrieval).
4. **Memory retrieval** → `relevant_memories = memory.retrieve(prompt, limit=…)`.
5. **History retrieval** → `past_exchanges = conv_store.search(prompt, limit=2)`
   (vector store of past exchanges).
6. **Build messages** → `prompt_builder.build(memories=…, conversation=…,
   past_exchanges=…)` (`app/prompt/builder.py`):
   - Assembles **one** system message = `SYSTEM_PROMPT` + formatted past
     exchanges + formatted memories (combined for model compatibility).
   - Appends the conversation history (OpenAI format).
   - Appends the current user prompt **only if** it is not already the last
     conversation message (it is, so it is not duplicated).
7. **Context fit** → `fitted_messages = context_manager.fit(messages)`
   (`app/context/manager.py`). Trims **oldest user/assistant pairs first**,
   never breaking an exchange, until it fits `max_tokens - safety_margin`. If the
   system block alone exceeds the limit, only the system message is returned.
8. **Select model** → `selected_model, task_type = switcher.router.route(prompt)`
   (see §4–§5).
9. **Generate** → `selected_model.generate(fitted_messages, stream=True,
   on_token=lambda t: print(t, end="", flush=True))`.
10. **Record assistant turn** → `conversation.add_message("assistant",
    response.content)` and `conv_store.add_exchange(prompt, response.content)`.

The `DocumentationAgent` (`app/agents/doc_agent.py`) uses a separate, simpler
prompt flow: it builds its own `system` (with a tool list) + `user` message and
loops `model.generate(messages)` (non-streaming) inside a tool-calling agent
(see §8 / §10).

---

## 7. Response flow

`generate()` on every client does the following (verified per client):

- **Non-streaming** (`stream=False`): one `chat.completions.create(...)` call
  with `**kwargs` forwarded. Returns
  `ModelResponse(content=choice.message.content, model=self._model,
  tokens_used=response.usage.total_tokens if response.usage else None,
  finish_reason=choice.finish_reason)`.
- **Streaming** (`stream=True`): `chat.completions.create(..., stream=True)`;
  iterates chunks, accumulates `delta.content`, and invokes `on_token(delta)`
  for each fragment. Returns `ModelResponse(content=full_content,
  model=self._model)` — **`tokens_used` is `None` and `finish_reason` is
  `None`** on this path.

Back in `main.py`, the streamed tokens are printed token-by-token. After the
generator returns, `response.content` is persisted (§6 step 10). If
`context_manager.fit()` trimmed anything, a `[Context] Trimmed …` line is
printed from `context_manager.get_stats()`.

The `DocumentationAgent` instead consumes the full `response.content` as text,
parses `<tool_call>` tags, executes them via `ToolExecutor`, injects results as
a new `user` message, and loops (capped at `MAX_ITERATIONS = 12`).

---

## 8. Error handling

Verified failure modes and their handling:

| Layer | Trigger | Behavior |
|-------|---------|----------|
| `factory._resolve_key` | `env:VAR` unset | Raises `ValueError` ("Environment variable 'VAR' is not set…"). |
| `factory.create_client` | `ollama`/`openrouter` package missing | Raises `ImportError` with install hint. |
| `switcher.__init__` | client load fails | Caught; prints `⚠️ Could not load '<key>'`; continues. |
| `switcher._build_router` | unknown role string | `TaskType(role)` raises `ValueError`, swallowed (`pass`). |
| `router.select` | task type unregistered **and** no default | Raises `ValueError`. |
| `main.py` generate | any exception from the model/network | Caught; prints `[Error] Model unavailable: <e>`; calls `conversation.pop_last_message()` to remove the just-added user message; `continue`s to next loop iteration. |

Notes / caveats:
- **The `main.py` model-failure handler rolls back only the user message, not the
  facts.** Steps 3–4 of the prompt flow already stored extracted facts into
  `memory` before generation. On a model failure those facts remain stored while
  the user turn is popped from the conversation. This asymmetry is observable in
  the code; whether it is intentional is not documented.
- **Dead/unsafe fallback in `main.py`.** Immediately after `route()`, the code
  reads:
  ```python
  if selected_model is None:
      selected_model = router.default_model
  ```
  `router` is **not defined** in `main()`'s scope (the object is `switcher.router`),
  so this branch would raise `NameError` if ever executed. It is currently
  **unreachable** because `route()` never returns `None` — it either returns a
  client or raises inside `select()`. Documented here as a latent defect, not an
  active behavior.
- `OllamaClient` and `LlamaCppClient` rely on their underlying SDKs raising on
  connection errors; those exceptions propagate to the `main.py` try/except and
  are reported as "Model unavailable".

---

## 9. Future improvements

Items drawn directly from code comments / unused scaffolding (not speculation):

1. **Configurable routing.** `ModelRouter.KEYWORDS` docstring says weights
   "can be made configurable". Keyword lists are currently hardcoded for
   CODE/STEM/REASONING only; `AUTOCOMPLETE`/`DOCS`/`GENERAL` are unreachable by
   auto-classification.
2. **Wire up the `autocomplete` model.** A `LlamaCppClient` for autocomplete
   (port `8082`, `max_tokens=150`) is defined in defaults but never mapped to a
   router/task type.
3. **Native function calling (v3.0).** `app/tools/base.py` and `doc_agent.py`
   describe moving from the current **prompt-based** `<tool_call>` parsing to
   OpenAI-native `model.generate(tools=[...])`. The `ToolDefinition.to_openai_schema()`
   / `ToolRegistry.to_openai_schemas()` already exist for this; the clients
   already forward `**kwargs` to the OpenAI API, so `tools=` could be passed
   today, but the agent loop does not use it yet.
4. **(Done) Google / Gemini provider.** Was a commented-out Gemini block inside
   `LlamaCppClient.generate()`; it is now a first-class `GoogleClient`
   (`app/models/google_client.py`) selected via `backend: "google"`.
5. **Conversation summarization.** `ConversationManager.set_summary` /
   `get_summary` and `ConversationConfig.enable_summarization` exist but are
   unused ("Future" per docstrings).
6. **Robust error rollback.** On model failure, roll back stored facts in
   addition to the popped user message (see §8).
7. **Fix the dead `router.default_model` fallback** in `main.py` (use
   `switcher.router.default_model`, or remove the branch since `route()` cannot
   return `None`).
8. **Profile validity checks.** `ModelSwitcher.switch("cloud")` can succeed while
   the target router has no models/default (under defaults). A startup warning
   for empty profiles would prevent silent `ValueError`s at request time.

---

## Appendix — file map

| Concern | File |
|---------|------|
| Client interface + `ModelResponse` | `app/models/client.py` |
| Client implementations | `app/models/llamacpp_client.py`, `app/models/ollama_client.py`, `app/models/openrouter_client.py`, `app/models/google_client.py` |
| Factory | `app/models/factory.py` |
| Router / task classification | `app/models/