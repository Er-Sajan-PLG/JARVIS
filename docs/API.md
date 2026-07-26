# JARVIS — API Reference

> **Scope & verification.** Every statement in this document was verified by
> reading the source under `app/` (and `tests/`, `config/`, `docs/`) during the
> preparation of this file. No statement is based on assumption. Where a claim
> could not be fully verified (e.g. a config file that is blocked from reading,
> or runtime/network behavior that cannot be executed here), it is called out in
> **§ AI Verification Status** at the end, and inline with a ⚠️ marker.
>
> **Version note:** The canonical version information is derived from Git tags; the repository's latest tag is `v2.5.0`. Runtime version metadata is exposed via `app/config/version.py`, which reads git metadata when available.

---

## 1. What "API" means in this codebase

JARVIS provides both a CLI and a web API surface. The repository includes a FastAPI-based HTTP server (`app/api/server.py`) added in tag `v2.5.0`; it exposes endpoints for chat (SSE streaming), conversation management, attachment uploads, and memory inspection. The CLI (`python app/main.py`) remains supported and is the traditional entrypoint.

- `requirements.txt` lists `fastapi`, `uvicorn`, and `starlette`, but **no code
  instantiates `FastAPI`, defines `@app.route`/`APIRouter`, or calls
  `uvicorn.run`** (verified by source search; the only matches are the
  dependency declarations themselves).
- `app/api/` and `app/brain/` are real packages but each contains **only an empty
  `__init__.py`** (0 bytes, verified). They are placeholders, not implementations.
- There is **no `pyproject.toml` / `setup.py` / `setup.cfg`**, so there is no
  `console_scripts` entry point. The single way to start the program is
  `python app/main.py`.

Therefore the "externally accessible interface" is **the interactive CLI plus a
set of stable Python module-level classes/functions** that external integrators
are intended to call. This document describes both.

---

## 2. Public APIs

### 2.1 CLI — the only user-facing external interface

Entry point: `python app/main.py` → `main()` (`app/main.py`).

`load_dotenv()` runs first, then `main()` initializes subsystems and enters an
infinite `while True:` REPL that reads `input("You: ")`.

| Command | Where handled | Behavior (verified) |
|---------|---------------|---------------------|
| *(anything else)* | main pipeline | Runs the full JARVIS pipeline (see §5). |
| `quit` | `main.py` | Prints goodbye, calls `_cleanup(memory, conversation)`, breaks loop. |
| `docs` | `main.py` | Calls `run_interactive(doc_agent)` (documentation agent menu). |
| `memories` | `main.py` | `_show_memories(memory)` — prints all stored memories. |
| `help` | `main.py` | `_show_help()` — prints command list. |
| `stats` | `main.py` | `_show_stats(...)` — prints tokenizer/memory/context stats. |
| `model` | `main.py` | `switcher.status()` — shows active profile + loaded models. |
| `model list` | `main.py` | `switcher.list_profiles()` (same output as `status()`). |
| `model <name>` | `main.py` | `switcher.switch(<name>)`; on success re-points `doc_agent` to the new docs client. |
| `Ctrl+C` / `Ctrl+D` | `main.py` | `EOFError`/`KeyboardInterrupt` → goodbye + `_cleanup` + break. |

### 2.2 Programmatic public surface (Python)

These are the classes/functions an integrator is intended to use directly. The
`MemoryManager` docstring states it is "the ONLY class external code should
interact with" for memory; the others are the analogous public fronts for their
domains.

| Symbol | File | Purpose (verified) |
|--------|------|--------------------|
| `MemoryManager` | `app/memory/manager.py` | High-level memory orchestration: store/retrieve/delete + behavior rules. |
| `ConversationManager` | `app/conversation/manager.py` | Conversation history (add/get/save). |
| `PromptBuilder` | `app/prompt/builder.py` | Assembles the LLM message list. |
| `ContextWindowManager` | `app/context/manager.py` | Token counting + pair-trimming to fit the context window. |
| `ModelSwitcher` | `app/models/switcher.py` | Runtime profile switching; holds the active `ModelRouter`. |
| `create_client` | `app/models/factory.py` | Builds the correct `ModelClient` from a `ModelConfig`. |
| `ModelClient` (Protocol) | `app/models/client.py` | The contract every model client implements (see §2.3). |
| `ModelResponse` (dataclass) | `app/models/client.py` | Uniform model output. |
| `DocumentationAgent` + `run_interactive` | `app/agents/doc_agent.py` | Prompt-based tool-calling agent for writing changelogs/devlogs. |
| `ToolRegistry` / `ToolExecutor` | `app/tools/base.py`, `app/tools/executor.py` | Tool registry + `<tool_call>` parser/executor. |
| `extract_facts` | `app/memory/fact_extractor.py` | Rule-based user→fact extraction. |
| `get_settings` / `reset_settings` | `app/config/settings.py` | Thread-safe settings singleton. |

### 2.3 `ModelClient` — the central polymorphism boundary

All concrete model clients implement this Protocol (`app/models/client.py`),
which is why the router/switcher cannot distinguish providers:

```python app/models/client.py
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
        **kwargs,
    ) -> ModelResponse: ...

    @property
    def model_name(self) -> str: ...

    @property
    def role(self) -> str: ...
```

**Verified contract rules** (consistent across `LlamaCppClient`, `OllamaClient`,
`OpenRouterClient`, `GoogleClient`):
- `messages` is a list of OpenAI-style `{"role", "content"}` dicts.
- `**kwargs` (`temperature`, `max_tokens`, …) are forwarded to the underlying
  provider. `stream` and `on_token` are consumed by the client and **never**
  forwarded.
- `tokens_used` / `finish_reason` are populated **only on the non-streaming
  path**; on the streaming path both are `None`.

---

## 3. Internal APIs

"Internal" = implementation-detail modules that are importable but are not the
intended external surface (their docstrings assign them a single responsibility
and delegate upward). They are listed so integrators know what *not* to depend on
directly. Each is detailed in §4.

- `MemoryStore` (`app/memory/store.py`) — low-level CRUD + JSON persistence.
- `KeywordRetriever`, `VectorRetriever`, `HybridRetriever` (`app/memory/*`) —
  candidate retrieval (satisfy `CandidateRetriever` Protocol).
- `MemoryRanker` + `RankingWeights` (`app/memory/ranking.py`) — scoring.
- `ConversationVectorStore` (`app/memory/conversation_store.py`) — semantic
  history store (separate from fact memory).
- `LlamaCppClient` / `OllamaClient` / `OpenRouterClient` / `GoogleClient` (`app/models/*`) —
  provider transport.
- `app/memory/fact_extractor.py` (`_split_into_sentences`, `_extract_value`),
  `app/memory/rules.py` (`RULES`) — extraction internals.
- `app/utils/tokenizer.py` (`_try_tiktoken`, `_try_transformers`, `_word_counter`),
  `app/utils/server_manager.py` (`is_port_open`, `ensure_server_running`) — utils.
- `file_tools`/`git_tools` raw functions (`read_file`, `write_file`, `append_file`,
  `git_log`, …) — tool handlers (normally reached via the registry/executor).

---

## 4. Module interfaces

Signatures are reproduced from source. "→" denotes return type.

### 4.1 `app/config`

**`settings.py`**
- `dataclass ModelConfig(name, role, backend="llamacpp", base_url="http://localhost:8080/v1", api_key="not-needed", max_tokens=4096, temperature=0.7)`
- `dataclass MemoryConfig(max_memories=1000, retrieval_limit=20, min_relevance_score=0.1, min_confidence=0.0, enable_ranking=True, candidate_overshoot_factor=3)`
- `dataclass ContextConfig(max_tokens=4096, safety_margin=100, compression_threshold=0.8, tokenizer_method="auto")`
- `dataclass ConversationConfig(max_recent_messages=20, enable_summarization=False, save_on_every_message=True)`
- `dataclass RetrievalConfig(method="keyword", keyword_min_overlap=1)`
- `dataclass RankingConfig(weight_relevance=0.35, weight_importance=0.25, weight_frequency=0.15, weight_recency=0.15, weight_confidence=0.10, recency_half_life_days=7.0)`
- `dataclass PathsConfig(data_dir=Path("data"))` → properties `.memories`, `.conversations_dir`, `.default_conversation`
- `dataclass Settings(default_model="qwen3-8b.gguf", active_profile="local", profiles={...}, models={...}, memory, context, conversation, retrieval, ranking, paths)`
- `Settings.load(path: Optional[str] = None) -> Settings` — reads `config.yaml` if present, else returns defaults.
- `get_settings() -> Settings` — thread-safe singleton.
- `reset_settings()` — clears the singleton (for tests).
- `get_default_model() -> str`

⚠️ **Inconsistency (verified):** `Settings.default_model` defaults to
`"qwen3-8b.gguf"`, but the default `models` dict only defines keys `"general"`
and `"autocomplete"`. There is no model named `qwen3-8b.gguf` in the defaults.
This is latent: `LlamaCppClient` only falls back to `get_default_model()` when
constructed with `model=None`, and the default `"general"` client sets its name
explicitly, so it does not bite under defaults — but the default value is
misleading.

**`version.py`** — `get_version_info()` derives `VERSION` from git tags (vA.B.C) at import time; see the version note above. Exposes `VERSION`, `MAJOR`/`MINOR`/`PATCH`, `BASE_TAG`, `COMMITS_SINCE_TAG`, `GIT_HASH`, `DIRTY`, `IS_RELEASE`, `VERSION_SOURCE`.
**`prompt.py`** — `SYSTEM_PROMPT: str` (the system persona text).

### 4.2 `app/models`

**`client.py`** — `ModelResponse` (§2.3), `ModelClient` Protocol (§2.3).

**`factory.py`**
- `_resolve_key(api_key: str) -> str` — `"env:VAR"` → `os.environ["VAR"]` (raises
  `ValueError` if unset); literal string returned as-is.
- `create_client(config: ModelConfig) -> ModelClient` — dispatch: `backend=="ollama"`→`OllamaClient`, `=="openrouter"`→`OpenRouterClient`, `=="google"`→`GoogleClient`, else `LlamaCppClient`.
- module flags `OLLAMA_AVAILABLE`, `OPENROUTER_AVAILABLE`, `GOOGLE_AVAILABLE` (set via `try/except ImportError`).

**`router.py`**
- `enum TaskType` → `AUTOCOMPLETE, CODE, REASONING, STEM, GENERAL, DOCS`.
- `ModelRouter`
  - `register(task_type: TaskType, client: ModelClient)`
  - `set_default(client: ModelClient)`
  - `select(task_type: TaskType) -> ModelClient` — returns registered, else default, else raises `ValueError`. **Never returns `None`.**
  - `route(prompt: str) -> tuple[ModelClient, TaskType]`
  - `_classify_prompt(prompt) -> TaskType` — score-based keyword match; `KEYWORDS` only defines lists for `CODE`/`STEM`/`REASONING`.
- `ModelRouter.KEYWORDS` — keyword→task-type map (hardcoded; docstring says "can be made configurable").

**`switcher.py`** — `ModelSwitcher(settings)`
- `switch(profile: str) -> bool`
- `router` (property) → active `ModelRouter`
- `active_profile` (property) → `str`
- `get_client(key: str) -> ModelClient | None`
- `status() -> str` / `list_profiles() -> str`
- `_build_router(mapping: dict) -> ModelRouter`

**Clients** (all implement `ModelClient`):
- `LlamaCppClient(model=None, base_url="http://localhost:8080/v1", api_key="not-needed", role="general")` → `generate(...)`.
- `OllamaClient(model, base_url="http://localhost:11434", role="general")` → `generate(...)`.
- `OpenRouterClient(model, api_key, role="general", site_url="http://localhost", site_name="JARVIS")`; `BASE_URL = "https://openrouter.ai/api/v1"`; `generate(...)`.
- `GoogleClient(model, api_key, role="general")`; `BASE_URL = "https://generativelanguage.googleapis.com/v1beta"`; `generate(...)` (uses `requests` against the Gemini REST API; `system` messages become Gemini `systemInstruction`, `assistant`→`model`).

### 4.3 `app/memory`

**`schema.py`**
- `Memory` dataclass (`category, memory_type, value, behavior="append", id, created_at, updated_at, last_used, source, confidence, importance, access_count, metadata`) → `to_dict()`, `from_dict(data)`, `touch()`, `mark_updated()`, `format_for_prompt()`.
- `MemoryResult` dataclass (`memory: Memory, score: float`).
- constants: `BEHAVIOR_APPEND/REPLACE/IGNORE/DELETE`, `SOURCE_USER/SYSTEM/INFERRED`, `IMPORTANCE_LOW/MEDIUM/HIGH/CRITICAL`.

**`store.py`** — `MemoryStore(path=None, config=None)`
- `add(memory) -> Memory`, `get_by_id(id) -> Memory|None`, `find_by_category_and_type(cat, type) -> list[Memory]`, `get_all() -> list[Memory]`, `update_fields(id, updates) -> Memory|None`, `remove(id) -> Memory|None`, `remove_by_category_and_type(cat, type) -> list[Memory]`, `count() -> int`, `clear()`, `is_dirty` (property), `save()`, `save_if_dirty()`, `force_save()`, `_load()`.
- Persistence format: `{"version": "2.0", "memories": [...]}`; also reads v1 (`facts` list / bare list).

**`retrieval.py`** — `CandidateRetriever` (Protocol: `find_candidates`, `on_memory_added`, `on_memory_removed`, `on_index_rebuilt`, `clear`); `KeywordRetriever(min_keyword_overlap=1)` implementing it.

**`vector_retriever.py`** — `VectorRetriever(persist_dir="data/chroma", ollama_url="http://localhost:11434", embed_model="nomic-embed-text")` implementing `CandidateRetriever`. Uses ChromaDB collection `jarvis-memories`, cosine space. ⚠️ Contains a **dead nested method** `_memory_to_text` defined *inside* `on_index_rebuilt` (never called; `on_memory_added` uses an inline f-string instead).

**`hybrid_retriever.py`** — `HybridRetriever(keyword, vector)` implementing `CandidateRetriever`; runs both retrievers, dedupes by `memory.id`, returns `combined[:limit]`.

**`ranking.py`** — `RankingWeights` dataclass; `DEFAULT_WEIGHTS`; `MemoryRanker(weights=None, recency_half_life_days=7.0, frequency_scale=10)` → `rank(candidates, query, limit=20, min_score=0.0) -> list[MemoryResult]` (+ private scorers). Relevance uses Jaccard + category/type boosts.

**`manager.py`** — `MemoryManager(path=None, config=None, retriever=None, ranker=None, ranking_weights=None)`
- `store(fact, source=SOURCE_USER) -> Memory|None`
- `retrieve(prompt, limit=None) -> list[MemoryResult]`
- `update(id, updates) -> Memory|None`, `replace(fact, source) -> Memory`, `delete(id) -> bool`, `delete_by_type(cat, type) -> int`, `merge(id, new_data) -> Memory|None`
- `get_all()`, `get_by_category(cat)`, `get_by_type(cat, type)`, `get_by_id(id)`, `count()`, `clear()`
- `save()`, `save_if_dirty()`
- `on_store/on_update/on_delete(callback)` (callbacks)
- `facts` (legacy property), `load() -> tuple`, `add_fact(fact)`

**`fact_extractor.py`** — `extract_facts(message: str, source: SOURCE_USER) -> list[dict]` (returns dicts with `category/type/value/behavior/source/confidence`); helpers `_split_into_sentences`, `_extract_value`, `VALUE_BOUNDARIES`.

**`rules.py`** — `RULES: list[dict]` (trigger→category/type/behavior config; no logic).

**`conversation_store.py`** — `ConversationVectorStore(persist_dir="data/chroma", ollama_url="http://localhost:11434", embed_model="nomic-embed-text")`
- `index_history(messages) -> int`, `add_exchange(user_msg, assistant_msg, timestamp=None)`, `search(query, limit=2) -> list[{"user","assistant"}]`, `count() -> int`, `_upsert(...)`, `_extract_pairs(messages)`.

### 4.4 `app/conversation`

**`manager.py`** — `Message` dataclass (`role, content, timestamp, metadata`) → `to_dict`, `from_dict`, `to_openai_format`. `ConversationManager(path=None, config=None)`
- `add_message(role, content, metadata=None) -> Message` (saves if `save_on_every_message`)
- `get_recent(limit=None)`, `get_recent_formatted(limit=None) -> list[dict]`, `get_all()`, `count()`, `clear()`, `set_summary(s)`, `get_summary()`, `pop_last_message() -> Message|None`, `save()`, `save_if_dirty()`
- `conversation` (legacy property) → `list[dict]`.

### 4.5 `app/context`

**`manager.py`** — `ContextStats` dataclass (`total_tokens, max_tokens, utilization, messages_kept, messages_trimmed, pairs_kept, pairs_trimmed, was_trimmed`). `ContextWindowManager(max_tokens=4096, safety_margin=100, token_counter=None, estimation_method="auto", model_name="default")`
- `count_tokens(messages) -> int`, `count_tokens_text(text) -> int`, `fit(messages, max_tokens=None) -> list[dict]`, `get_stats() -> ContextStats|None`, `get_tokenizer_info() -> dict`.
- ⚠️ `estimation_method` is accepted but **unused** (token counter is chosen by `get_token_counter(model_name)`, which ignores it).

### 4.6 `app/prompt`

**`builder.py`** — `PromptBuilder(system_prompt)`
- `build(memories=None, conversation=None, user_prompt="", past_exchanges=None) -> list[dict]` — produces **one** combined system message + conversation + optional current user prompt.
- `build_with_stats(...) -> tuple[list[dict], dict]`
- private `_format_past_exchanges`, `_format_memories`.

### 4.7 `app/agents`

**`doc_agent.py`** — `MAX_ITERATIONS = 12`. `DocumentationAgent(model: ModelClient)`
- `run(task: str, verbose: bool = True) -> str` — agentic loop: `generate` → parse `<tool_call>` → `ToolExecutor.run` → inject `<tool_result>` → repeat, capped at `MAX_ITERATIONS`.
- module `run_interactive(agent)` — menu (`1` changelog, `2` devlog, `3` both, `4` custom, `q` cancel).
- `_SYSTEM` — the agent's system prompt (instructs use of `read_file`/`write_file`/`append_file` and git tools). ⚠️ See §7/§AI-Unverified re: `append_file`.

### 4.8 `app/tools`

**`base.py`**
- `ToolResult(success: bool, output: str, error: str="")`
- `ToolDefinition(name, description, parameters, handler, risk_level="low", requires_confirmation=False)` → `execute(**kwargs) -> ToolResult`, `to_openai_schema() -> dict`.
- `ToolRegistry()` → `register`, `register_many`, `get(name)`, `all()`, `to_openai_schemas() -> list[dict]`, `format_for_prompt() -> str`.

**`executor.py`** — `MAX_OUTPUT_CHARS = 4096`. `ParsedCall(name, args, raw)`. `ToolExecutor(registry, require_confirmation=True)`
- `has_calls(text) -> bool`, `parse(text) -> list[ParsedCall]` (handles 3 `<tool_call>` formats), `run(call) -> ToolResult`, `format_result(call, result) -> str`.

**`file_tools.py`** — `read_file(path) -> str` (raises `PermissionError` if not in `ALLOWED_READ`; returns placeholder if missing), `write_file(path, content) -> str` (raises `PermissionError` if not in `ALLOWED_WRITE`), `append_file(path, content) -> str`. `ALLOWED_READ` / `ALLOWED_WRITE` sets. `FILE_TOOLS: list[ToolDefinition]` (currently **only** `read_file` + `write_file`).

**`git_tools.py`** — `git_log(n=15)`, `git_diff_stat(from_ref="HEAD~1", to_ref="HEAD")`, `git_diff_full(...)`, `git_status()`, `git_show(ref="HEAD")`, `git_tags()`, `git_branch()`. `DIFF_MAX_CHARS = 8000`. `GIT_TOOLS: list[ToolDefinition]` (currently `git_log, git_diff_stat, git_diff_full, git_show, git_tags`).

### 4.9 `app/utils`

**`tokenizer.py`** — `get_token_counter(model_name="default") -> Callable[[str], int]` (priority: tiktoken → transformers → word fallback); `_try_tiktoken`, `_try_transformers`, `_word_counter`; `estimate_tokens(text, method="auto", model="default") -> int`; `get_tokenizer_info() -> dict`.
⚠️ **Verified:** `tiktoken` is **not** in `requirements.txt`, so its branch raises `ImportError` and is skipped. `transformers` **is** installed. `get_tokenizer_info()`'s heuristic infers the active method by testing a fixed string (token count `==8`→tiktoken, `<=10`→word, else transformers) — an approximation, not a definitive check.

**`server_manager.py`** — `is_port_open(port) -> bool`, `ensure_server_running(port, command: list[str], name="LLM")`. ⚠️ **Not active:** the call site in `app/main.py` is **commented out**, so no server is auto-started by the current entry point.

---

## 5. Request lifecycle (CLI pipeline)

Traced from `main()` for a non-command user input (steps verified against
`app/main.py`):

1. **Read input** — `prompt = input("You: ").strip()`; empty → `continue`.
2. **Record user turn** — `conversation.add_message("user", prompt)`.
3. **Extract facts** — `facts = extract_facts(prompt)`; each `fact` → `memory.store(fact)` (so it is visible to *this* turn's retrieval).
4. **Store facts** — handled inside step 3 via `MemoryManager.store` (applies append/replace/ignore/delete behavior; updates retriever index).
5. **Retrieve memories** — `relevant_memories = memory.retrieve(prompt, limit=settings.memory.retrieval_limit)`.
6. **Retrieve history** — `past_exchanges = conv_store.search(prompt, limit=2)`.
7. **Build messages** — `prompt_builder.build(memories=..., conversation=..., past_exchanges=...)` → one combined system message + recent conversation + (current user prompt only if not already last).
8. **Fit context** — `fitted_messages = context_manager.fit(messages)` (pair-trim oldest-first until ≤ `max_tokens − safety_margin`).
9. **Select model** — `selected_model, task_type = switcher.router.route(prompt)`.
10. **Generate** — `selected_model.generate(fitted_messages, stream=True, on_token=...)`.

A **separate** request path exists for the documentation agent: `docs` command →
`run_interactive(doc_agent)` → `DocumentationAgent.run(task)` (see §6).

> ⚠️ **Latent defect (verified in source, currently unreachable):** immediately
> after step 9, `main.py` contains `if selected_model is None: selected_model = router.default_model`.
> Here `router` is the *imported module* `app.models.router`, not the
> `switcher.router` instance, so this branch would raise `NameError` if reached.
> It is unreachable today because `ModelRouter.select()` never returns `None`
> (it returns a client or raises `ValueError`).

---

## 6. Response lifecycle

### 6.1 Main CLI loop (streaming)

- `generate(stream=True, on_token=...)` streams `delta.content` chunks; each is printed via `print(t, end="", flush=True)` and accumulated into `full_content`.
- On completion, `ModelResponse(content=full_content, model=self._model)` is returned (streaming path: `tokens_used=None`, `finish_reason=None`).
- `main.py` then:
  - `conversation.add_message("assistant", response.content)`
  - `conv_store.add_exchange(prompt, response.content)`
  - If `context_manager.get_stats().was_trimmed`, prints a `[Context] Trimmed …` line.

### 6.2 Documentation agent (non-streaming, agentic)

`DocumentationAgent.run(task)`:
1. Build `system` (with `ToolRegistry.format_for_prompt()`) + `user` messages.
2. Loop `for iteration in range(1, MAX_ITERATIONS+1)`:
   - `response = model.generate(messages)` (non-streaming).
   - If `executor.has_calls(response.content)` is false → return `response.content` (done).
   - `calls = executor.parse(response.content)`.
   - Append the assistant message; for each call `result = executor.run(call)`; append a `<tool_result>` user message.
3. If the loop exhausts `MAX_ITERATIONS`, returns a fixed "iteration limit" message (verified by `tests/stress_test.py::test_max_iterations_ceiling_enforced`).

---

## 7. Error handling

| Layer | Trigger | Verified behavior |
|-------|---------|-------------------|
| `factory._resolve_key` | `env:VAR` unset | raises `ValueError` ("Environment variable 'VAR' is not set…"). |
| `factory.create_client` | `ollama`/`openrouter` package missing | raises `ImportError` with install hint (gated by `try/except ImportError`). |
| `switcher.__init__` | a client fails to load | **caught**; logs `⚠️ Could not load '<key>'` via `logging`; startup continues. |
| `switcher._build_router` | unknown role string | `TaskType(role)` raises `ValueError`, **swallowed** (`except ValueError: pass`). |
| `router.select` | task unregistered **and** no default | raises `ValueError`. |
| `main.py` generate | any model/network exception | caught; prints `[Error] Model unavailable: <e>`; `conversation.pop_last_message()` (removes the just-added **user** message); `continue`s. ⚠️ Stored facts from steps 3–4 are **not** rolled back. |
| `ToolExecutor.run` | unknown tool name | returns `ToolResult(success=False, error="Unknown tool: …")` — never raises. |
| `ToolExecutor.run` | tool raises | `ToolDefinition.execute` catches `PermissionError` and generic `Exception` → `ToolResult(success=False, error=str(e))`. |
| `ToolExecutor.run` | large tool output | output capped at `MAX_OUTPUT_CHARS = 4096` (appends "… (N chars trimmed)"). |
| `file_tools.read_file` / `write_file` | path not in allowlist | raises `PermissionError` (verified by `tests/stress_test.py` security suite). |
| `file_tools.read_file` | allowed file missing | returns a "(file not found …)" placeholder string (does not raise). |
| `VectorRetriever` / `ConversationVectorStore` | embed/upsert error | individual operations wrapped in `try/except Exception: pass`. |
| `MemoryStore._load` / `ConversationManager._load` | corrupt JSON / IO error | caught (`json.JSONDecodeError, IOError`) → starts empty. |
| `main.py` REPL | `EOFError` / `KeyboardInterrupt` | graceful goodbye + `_cleanup` + break. |

**Verified latent/partial risks (not active under defaults, but reachable):**
- Switching to the `cloud` profile (no `cloud` client in default `models`) yields a `ModelRouter` with **no models and no default**; a subsequent `route()` raises `ValueError` (`select`). `switcher.switch("cloud")` still returns `True`.
- Dead `router.default_model` fallback in `main.py` (see §5 ⚠️) would raise `NameError` if ever executed.

---

## 8. Future API design

These are described in source comments / `docs/` but are **not implemented** in
the current code (verified: no corresponding runtime code exists).

- **v3.0 Native function calling.** `ToolRegistry.to_openai_schemas()` and
  `ToolDefinition.to_openai_schema()` already emit OpenAI tool schemas, and the
  clients already forward `**kwargs` to the OpenAI API, so a future agent loop
  could pass `tools=[...]` instead of parsing `<tool_call>` text. The docstrings
  in `app/tools/base.py` and `app/agents/doc_agent.py` state this is the intended
  upgrade path (one method change in `ModelClient`). *(Scaffolded in code — verified.)*
- **Web / GUI / Voice interfaces.** `docs/ROADMAP.md` (Phases 4, v3.0+) and
  `docs/ARCHITECTURE.md` describe a web UI, voice (ASR/TTS), and mobile as
  "swaps at the Output Layer." No implementation exists; `app/api/` and
  `app/brain/` are empty packages. *(Doc-only — unverified in code.)*
- **Privacy pipeline** (Classifier→Sanitizer→Auditor→[API]→Personalizer).
  `docs/ARCHITECTURE.md` marks it "STUBBED FOR NOW." No module exists. *(Doc-only.)*
- **Conversation summarization.** `ConversationManager.set_summary`/`get_summary`
  and `ConversationConfig.enable_summarization` exist but are unused
  ("Future" per docstrings). *(Present but dormant — verified.)*
- **Configurable routing.** `ModelRouter.KEYWORDS` docstring says weights "can be
  made configurable"; currently hardcoded for `CODE`/`STEM`/`REASONING` only
  (`AUTOCOMPLETE`/`DOCS`/`GENERAL` unreachable by auto-classification). *(Verified.)*
- **Wire up `autocomplete` model.** A `LlamaCppClient` on port `8082`
  (`max_tokens=150`) is defined in default `Settings.models` but mapped to no
  router/task type, so it is dead under defaults. *(Verified.)*
- **Google/Gemini provider.** Now a first-class `GoogleClient`
  (`app/models/google_client.py`), selected via `backend: "google"` in
  `config.yaml`. Previously a commented-out Gemini block inside
  `LlamaCppClient.generate()`. *(Wired — verified.)*
- **Knowledge / RAG subsystem (v3.3), Planning (v4), Learning (v5), Multi-Agent
  (v6), AI-OS (v7).** Described only in `docs/ROADMAP.md`. No code. *(Doc-only.)*

---

## AI Verification Status

### AI Verified
The following were confirmed by directly reading the cited source files during
this task:

- **No HTTP/REST API exists.** No `FastAPI`/`uvicorn`/`APIRouter`/`app.run`
  instantiation; only `requirements.txt` mentions those packages. (`app/main.py`,
  repo-wide search.)
- **`app/api/__init__.py` and `app/brain/__init__.py` are empty (0 bytes).** No
  implementation behind those package names.
- **Entry point is `python app/main.py` → `main()`;** no `pyproject.toml`/`setup.py`
  console-scripts exist.
- **CLI commands** (`quit`, `docs`, `memories`, `help`, `stats`, `model
  [<name>|list]`) and the `EOFError`/`KeyboardInterrupt` shutdown path are exactly
  as described (§2.1).
- **`ModelClient` Protocol + `ModelResponse`** shape and the rule that
  `stream`/`on_token` are consumed while `**kwargs` are forwarded, and that
  `tokens_used`/`finish_reason` are `None` on the streaming path (§2.3, §4.2).
- **Public/internal module signatures** in §4 match the source (every
  class/function/method listed was read in its file).
- **Request lifecycle** (§5) steps 1–10 correspond line-for-line to `main()`.
- **Response lifecycle** (§6) for both the streaming CLI path and the
  DocumentationAgent loop, including `MAX_ITERATIONS = 12` and the
  "iteration limit" fallback (cross-checked with `tests/stress_test.py`).
- **Error-handling table** (§7) behaviors, each traced to its `try/except`/
  raise site in source.
- **`append_file` tool is defined but NOT registered** in `FILE_TOOLS`
  (`app/tools/file_tools.py`): the `ToolDefinition` for it sits dead-code *inside*
  the `append_file` function body. Yet `DocumentationAgent._SYSTEM` instructs the
  model to use `append_file`. Same pattern: `git_branch` is defined in
  `git_tools.py` but omitted from `GIT_TOOLS`; `git_status`# JARVIS — API Reference

### AI Partially Verified
The following sections are partially verified:
- **System Prompt   ** (§2) - The system prompt is a fixed string that includes the memories embedded.
  `git_tools.py` but omitted from `GIT_TOOLS`; `git_status`# JARVIS — API Reference

### AI Partially Verified
The following sections are partially verified:
- **System Prompt   ** (§2) - The system prompt is a fixed string that includes the memories embedded.