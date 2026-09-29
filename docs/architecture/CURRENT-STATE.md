# JARVIS — Current State (pre-migration audit)

**Status**: ACTIVE
**Type**: architecture
**Last Updated**: 2026-09-25
**Reviewed**: 2026-09-25
**Source**: `app/`, `config.yaml`, `requirements.txt`, `pyproject.toml`, `tests/`, `.env.example` at HEAD

> Read-only audit. ZERO code changes made. Anything not verified against source is marked
> `UNKNOWN — needs human review`. Line numbers verified 2026-09-25.

---

## 0. System overview

JARVIS is a single-tenant FastAPI + WebSocket personal-AI server (`app/main.py`,
`app/adapters/`). One composition root (`app/bootstrap.py`) wires a heuristic
cognitive pipeline (`app/brain/`: intent → plan → execute; the primary REST path
returns plan status, only the web-console path calls an LLM), a multi-provider
model pool with failover (`app/models/`), hybrid BM25+ChromaDB memory
(`app/memory/`, `app/session/`), and a tiered safety gate with persisted
human-in-the-loop approvals (`app/guardrails/`). State lives in `data/`
(files/SQLite/Chroma) with optional Postgres; secrets are split across env,
`config.yaml`, `data/web_settings.json`, and per-request headers. The sections
below inventory every module, trace one request end to end, and list what is
dead, half-finished, or abandoned.

## 1. Language, runtime, package manager, key dependencies

- **Language**: Python, `requires-python = ">=3.11"` (`pyproject.toml:10`), `target-version = "py311"`
  (`pyproject.toml:26`), `mypy python_version = "3.11"` (`pyproject.toml:36`).
  Active venv is Python 3.11.16 (`.venv/`); system `python3` is 3.14.7 — **mismatch, use `.venv`**.
- **Runtime**: FastAPI + uvicorn. Entry `app/main.py:243-266` (`main()` → `uvicorn.run(app, host, port)`).
  ASGI app object `app/main.py:93-98`. Lifespan `app/main.py:42-64`.
- **Package managers**: pip (only). `requirements.txt` (172 lines, almost all `==` pinned).
  `package-lock.json` exists (npm) but root `package.json:1-135` is docs-diagram tooling only
  (mermaid/puppeteer/react/d3, `"test": "echo \"Error: no test specified\""`).
  No `yarn.lock`/`pnpm-lock.yaml`/`bun.lock*`/`poetry` in use. `frontend/package.json` has no deps;
  `"test": "echo \"No tests specified for frontend\""`.
- **Key dependencies** (`requirements.txt`):
  - Web: `fastapi==0.141.1` (:25), `uvicorn==0.53.0` (:151), `websockets==17.1` (:156),
    `pydantic==2.13.5` (:103), `pydantic-settings==2.15.0` (:104), `python-dotenv==1.2.3` (:115).
  - LLM: `openai==3.14.0` (:80), `ollama==0.6.2` (:78), `langgraph==1.2.11` (:165), `mcp==2.2.0` (:161).
  - Memory/vectors: `chromadb==1.5.9` (:14), `sentence-transformers==6.0.1` (:130),
    `torch==2.14.0` (:142), `transformers==5.17.0` (:144), `numpy==2.4.6` (:61).
  - DB: `asyncpg==0.30.1` (:160), `psycopg==3.2.3` (:163), `psycopg2-binary==2.9.10` (:164).
  - Observability: `opentelemetry-*==1.44.0` (:81-86, :166-170), `structlog==24.4.0` (:158),
    `tiktoken==0.8.0` (:159).
  - Voice/OCR: `faster-whisper==1.2.1` (:118), `edge-tts==7.2.8` (:119), `paddleocr==2.7.0` (:162).
  - Quality gates: `pytest==9.1.1` (:111), `pytest-asyncio==1.4.0` (:112), `coverage==7.16.1` (:17),
    `ruff==0.16.7` (:126), `mypy==2.3.1` (:57). Only unpinned: `aiosmtplib>=3.0.0`, `aioimaplib>=1.1.0` (:171-172).
- **Version**: `pyproject.toml:7` says `3.0.1` but authority is git tags
  (`app/config/version.py`, `docs/VERSIONING.md`); `README.md:28` reports `v3.22.1+dev`.

---

## 2. Entry points and full execution path of one user request

### 2.1 Entry points

| Entry | File | Notes |
|---|---|---|
| HTTP REST (primary) | `app/main.py:146` `app.include_router(http_router)` → `app/adapters/http/router.py:24` (`prefix="/api/v1"`) | `POST /api/v1/chat/completions` (:63-112), `GET /hitl/pending` (:115-123), `POST /hitl/approve` (:126-180), `POST /hitl/notified` (:217-244), `GET /health` (:51-60) |
| WebSocket / SSE | `app/main.py:147` → `app/adapters/websocket/stream.py:15-81` | `websocket_chat` (:15-56), `websocket_endpoint` (:59-63), `sse_stream_endpoint` (:66-81). Voice WS `app/adapters/websocket/voice_handler.py:16-82` |
| Web console (direct-LLM path) | `app/main.py:148` → `app/adapters/web/router.py` (1157 LOC), `chat()` at :565-804 | Bypasses `ExecutionRunner`; calls LLM client directly (:762-765) |
| Voice REST | `app/adapters/web/voice_routes.py:25-29` (`/api/v1/voice`) | STT `:53-73` (faster-whisper), TTS `:76-99` (edge-tts) |
| OCR | `app/main.py:149` → `app/api/ocr/routes.py` (167 LOC) | Thin extra API surface |
| Email/notify/push/brief | `app/main.py:150-155` → `app/adapters/web/email_routes.py` (91), `notify_routes.py` (88), `push_routes.py` (99), `brief_routes.py` (49) | Comms satellites |
| SPA/PWA shell | `app/main.py:170-240` | `GET /` (:170-176), `/manifest.json` (:179-184), `/service-worker.js` (:187-202), `/offline.html` (:205-211), icons (:235-240) |
| Telegram poller | `app/main.py:48-60` inside `lifespan` | Background `asyncio.create_task(poller.run_forever())` only if `TelegramConfig.from_env().ready` |
| CLI | NONE — no `cli.py`, no REPL entry in `app/` | Target `interfaces/cli.py` has no counterpart |

Boot: `python -m app.main` → `main()` (:243) → `uvicorn.run` (:266) → `lifespan` (:42) →
`bootstrap_system()` (:45). Every request re-calls `bootstrap_system()` (singleton guard
`app/bootstrap.py:91-92` returns existing container).

### 2.2 Traced request: `POST /api/v1/chat/completions` (the brain-pipeline path)

This is the only path that exercises Intent → Plan → Execute → Synthesize. The web-console
`chat()` path does NOT use it (it calls the LLM directly).

1. **Transport + auth.** `POST /api/v1/chat/completions` hits
   `app/adapters/http/router.py:63-64`. `Depends(validate_api_key)` (:63) →
   `validate_api_key()` (:34-48) → `app/adapters/security.py:53-74` `is_authorized()`
   (`hmac.compare_digest`, :74). If `JARVIS_API_KEY` unset → auth disabled, all requests allowed
   (documented :41-44; same warning at `app/main.py:259-264`).
   `logging_middleware` (`app/main.py:110-133`) stamps `X-Correlation-ID` (:114) and `X-Process-Time` (:131).
2. **Composition root.** `chat_completions()` :72 `container = bootstrap_system()`.
   `app/bootstrap.py:74-187` builds (once) `ApplicationContainer` (:30-68): event bus, telemetry,
   `PromptLoader`/`ContextBuilder` (:130-131), session/artifact/workspace (:134-137),
   `MemoryService`/`ResourceManager` (:140-141), `ModelRouter` (:144),
   `ToolSafetyPolicy(auto_approve_sensitive=True)` + `set_global_policy` + `ApprovalRegistry(data/approvals.json)` (:147-151),
   brain `IntentAnalyzer`/`TaskPlanner`/`ExecutionRunner` + `DEFAULT_TOOLSET` registration (:154-161),
   `ResponseSynthesizer` (:162).
3. **Session.** :86-87 `session_manager.get_or_create_session(session_id)` +
   `get_or_create_conversation`. Impl `app/session/manager.py:42-86`.
4. **Intent (NO LLM — keyword heuristic).** :90 `container.intent_analyzer.analyze(prompt)`.
   Impl `app/brain/analyzer.py:23-81`: attachments → `FILE_QUERY` (:35-41); keywords
   (`refactor/build/audit/deploy/...`) → `MULTI_STEP` (:44-62); (`search for/find file/read /ocr`) →
   `TOOL_SEARCH` (:64-72); else `DIRECT_CHAT` (:77-81). Returns `IntentAnalysis`
   (`app/domain/intent.py:18-26`).
5. **Plan (deterministic).** :91 `task_planner.create_plan(prompt, analysis)`.
   Impl `app/brain/planner.py:54-153`: destructive-path → `DESTRUCTIVE create_directory` step (:76-89);
   `DIRECT_CHAT` → single `tool_call=None` step (:90-98); `FILE_QUERY` → `read_file` (:99-120);
   multi-step → `list_dir` + synthesis (:122-143). Types `app/domain/plan.py:12-87`
   (`SafetyTier`, `StepStatus`, `ToolCall`, `ExecutionStep`, `ExecutionPlan`).
6. **Execute + guardrails.** :94 `execution_runner.execute_plan(plan)`.
   Impl `app/brain/runner.py:35-64` loop, `_execute_step` (:66-135):
   `tool_call=None` → `COMPLETED` (:73-77); else `safety_policy.evaluate_tool_call(...)` (:84-90)
   (`app/guardrails/policy.py:40-88`: `SAFE` auto-pass :66-67, `SENSITIVE` policy-check :69-75,
   `DESTRUCTIVE` requires `hitl_approved is True` else `HITLRequiredError` :77-86);
   registry invoke (:93-104); `HITLRequiredError` → `AWAITING_APPROVAL` + `event_bus.publish(HITLRequestEvent)` (:110-127);
   generic → `FAILED` (:129-132). Tools from `DEFAULT_TOOLSET` (`app/tools/__init__.py:40-53`:
   `read_file/write_file/append_file/create_directory/list_dir` + git + comms + subagent tools),
   registered at `app/bootstrap.py:160-161`. Workspace tools sandboxed
   (`app/tools/workspace_tools.py:44-114`, `_check_sandbox` fail-closed).
7. **Metrics + HITL registration.** :97 `metrics.record_request()`; :101
   `approval_registry.register_paused_plan(executed_plan)` (impl `app/guardrails/approvals.py:245-276`,
   persists to `data/approvals.json`).
8. **Response (NO LLM on this path).** :103-112 returns
   `{session_id, plan_id, status, steps_count, complexity, requires_tools, awaiting_approval}`.
   **Blunt fact: this endpoint never calls an LLM and never returns generated text.**
   `ResponseSynthesizer.synthesize_stream` (`app/brain/synthesizer.py:17-32`) is a passthrough yield.
   Actual text generation happens only on the web-console path
   (`app/adapters/web/router.py:762-765` `client.generate(...)`).
9. **HITL resume (if paused).** Client polls `GET /hitl/pending` (:115-123) → decides
   `POST /hitl/approve` (:126-180) → `_approve_pending_via_registry` (:183-214) →
   `registry.decide(...)` (:200) + `execution_runner.execute_plan(plan, hitl_approvals=...)` (:205) +
   `register_paused_plan(resumed)` (:206). `POST /hitl/notified` (:217-244) stops n8n re-announce.

Alt paths: WS echo (`stream.py:33-50` — intent analysis then fake `token_chunk` echo, **no real LLM**);
voice WS (`voice_handler.py:64` `# TODO: Process command through brain` — not wired);
web `chat()` (:567-804 — memory search :595, email/brief inject :610-623, catalogue resolve :637-681,
`create_model_client` :762 + `generate` :763-765, `store_memory` :780, Telegram voice :794).

---

## 3. Every module/file: path, purpose, ~LOC, dependents

`app/` total: 184 `.py` files. Key files (`wc -l` verified); rest summarized per package.

| Path | Purpose | ~LOC | Depended on by |
|---|---|---|---|
| `app/main.py` | FastAPI app, CORS, middleware, router mounts, SPA/PWA routes, Telegram boot, `main()` | 270 | uvicorn / process entry; imports adapters + bootstrap |
| `app/bootstrap.py` | Composition root: `ApplicationContainer` + `bootstrap_system()` singleton | 187 | every adapter (`http`, `ws`, `web`), health checks |
| `app/provider_registry.py` | Provider catalogue/status (no inference) | 838 | `ApplicationContainer.get_provider_registry()`; web model list |
| `app/brain/__init__.py` | Re-exports brain classes | 18 | `bootstrap.py` |
| `app/brain/analyzer.py` | Heuristic intent classifier (no LLM) | 81 | `bootstrap.py`, `app/adapters/http/router.py`, `app/adapters/websocket/stream.py`, graph nodes |
| `app/brain/planner.py` | Deterministic `ExecutionPlan` builder | 153 | same as analyzer |
| `app/brain/runner.py` | Plan execution loop + tool dispatch + HITL pause | 149 | same; HITL resume path |
| `app/brain/synthesizer.py` | Passthrough stream (provenance TODO in docstring) | 32 | `bootstrap.py`, graph |
| `app/brain/graph.py` | LangGraph wrapper (`build_cognitive_graph`, `run/stream_cognitive_loop`); `None` if langgraph missing | 233 | UNKNOWN — needs human review (no adapter imports it directly; covered by `test_cognitive_graph.py`) |
| `app/brain/nodes.py` | Pure `CognitiveState→CognitiveState` nodes + heuristic evaluator (`quality_score`) | 267 | `graph.py` only |
| `app/domain/` (8 files, ~675 total) | Pure dataclasses, stdlib-only (intent/plan/state/session/conversation/memory/content/safety/cognitive/tool_result) | `plan.py` 87, `state.py` 52, `intent.py` 26, +5 more | `brain/*`, `guardrails/*`, `session/*`, `memory/*` |
| `app/adapters/__init__.py` | Re-exports `http_router`, `ws_router` | ~10 | `app/main.py` |
| `app/adapters/security.py` | `is_authorized()` / streaming variant, `hmac.compare_digest` | 91 | `app/adapters/http/router.py`, `app/adapters/websocket/stream.py`, web router |
| `app/adapters/http/router.py` | REST: chat/completions (plan status), HITL approve/pending/notified, health | 244 | mounted in `main.py` |
| `app/adapters/websocket/stream.py` | WS chat (intent + echo chunks), SSE endpoint | 81 | mounted in `main.py` |
| `app/adapters/websocket/voice_handler.py` | Voice WS: wake-word → STT → **TODO brain** → TTS | 82 | mounted? UNKNOWN — needs human review (no mount seen in `main.py`) |
| `app/adapters/web/router.py` | Web console: direct-LLM `chat()`, files, memories, conversations, health | 1157 | mounted in `main.py` |
| `app/adapters/web/settings.py` | `data/web_settings.json` store (defaults, custom providers, keys) | 332 | web router |
| `app/adapters/web/voice_routes.py` | STT/TTS/status REST | 111 | mounted in `main.py` |
| `app/adapters/web/brief_routes.py`, `email_routes.py`, `notify_routes.py`, `push_routes.py` | Comms satellite routers | 49/91/88/99 | mounted in `main.py` |
| `app/adapters/integrations/agy.py` | Subprocess CLI agent bridge (`agy_chat`) | 282 | web router `agy` branch |
| `app/models/` (~3240 total, 20+ files) | Provider clients + `ModelRouter` + `factory.create_client` + `ModelSwitcher` + `OmniModelClient` | `router.py` 184, `factory.py` 214, `switcher.py` 250, `google_client.py` 288, `anthropic_client.py` 229, `openrouter_client.py` 166, 12 more clients ~30-110 each, `interface.py` 58, `client.py` 32 | web router, doc agent, `switcher`; `router` also used by NOTHING on the HTTP path (wired but uncalled there) |
| `app/memory/` (~2929 total, 15+ files) | Hybrid BM25+Chroma memory: `service.py` 207, `manager.py` 291, `store.py` 301, `temporal.py` 430, `rules.py` 316, `ranking.py` 178, `pipeline.py` 131, `llm_extractor.py` (~160), `vector_retriever.py`, `conversation_store.py`, etc. | ~2929 | `bootstrap.py` (`MemoryService`), web router (search/store), context builder |
| `app/guardrails/policy.py` | Tier evaluation (`SAFE/SENSITIVE/DESTRUCTIVE`) | 88 | `runner.py`, `decorator.py` |
| `app/guardrails/decorator.py` | `@safety_gate` decorator + `set_global_policy` | 74 | tool functions; called at `bootstrap.py:148` |
| `app/guardrails/approvals.py` | `ApprovalRegistry`: persist/list/decide/mark_notified, paused-plan store | 365 | `app/adapters/http/router.py` HITL endpoints; `runner.py` (via exception) |
| `app/session/manager.py` | In-memory session/conversation cache + CRUD/fork/archive | 145 | `app/adapters/http/router.py`, `bootstrap.py` |
| `app/session/persistence.py` | JSON file + (placeholder) Postgres session persistence | 124 | `app/session/manager.py` |
| `app/session/checkpointer.py` | `MemorySaverAdapter` (dev, in-mem dict) + sqlite import | 279 | `bootstrap.py:98-109` |
| `app/session/postgres_checkpointer.py` | Prod checkpointer (`checkpoints` table) | 220 | `bootstrap.py` (best-effort; falls back on exception) |
| `app/session/context.py` | Token-count + trim helpers | 105 | context builder |
| `app/context/builder.py` | `build_system_prompt` + `assemble_context` (token-budget truncation) | 165 | UNKNOWN — needs human review (HTTP path doesn't call it; web path inlines its own assembly) |
| `app/context/manager.py` | Context window manager | 219 | same as builder |
| `app/conversation/manager.py` | `ConversationManager` lifecycle (`add_message/get_recent/save`, corrupt-quarantine) | 257 | `legacy/server.py`; current wiring UNKNOWN — needs human review |
| `app/prompt/loader.py` | Jinja prompt loader (mtime cache) | 84 | `bootstrap.py` → `ContextBuilder` |
| `app/config/settings.py` | `Settings.load(config.yaml)`, `ModelConfig/MemoryConfig/.../PathsConfig` | 269 | memory store paths, model registry |
| `app/config/version.py` + `config/version.py` | Git-tag-derived version | 194 + small | `main.py`, `app/adapters/http/router.py` health |
| `app/resources/` (4 files) | `TokenBudgetManager` (128k max), rate limits, provider health, `ResourceManager` | ~214 | `app/models/router.py` (health/rate), telemetry |
| `app/events/bus.py` + `models.py` | `InMemoryAsyncBus` (passive telemetry only) + event types incl. `TokenUsageEvent` | 69 + 76 | `runner.py` (step/HITL events), telemetry subscribers |
| `app/telemetry/` (5 files) | `EventLogger`, `MetricsCollector`, `Tracer`, OTel exporter, `trace_new.register_tracer` | ~430 | `bootstrap.py`; `logging_middleware` |
| `app/tools/__init__.py` | `DEFAULT_TOOLSET` (workspace + git + comms + subagent) | 74 | `bootstrap.py:160-161` registration |
| `app/tools/workspace_tools.py` | Sandboxed `read/write/append/create_dir/list_dir` | 221 | via `DEFAULT_TOOLSET` |
| `app/tools/file_tools.py` | Agent file tools (allowlisted) | 223 | doc agent |
| `app/tools/git_tools.py` | `git_log/diff_stat/diff_full/show/tags` (+ unregistered `branch/status`) | 153 | via `DEFAULT_TOOLSET` + doc agent |
| `app/tools/comms_tools.py` | Comms runner tools | 101 | via `DEFAULT_TOOLSET` |
| `app/tools/subagent_tools.py` | Sub-agent worker tools (ADR-017) | 307 | via `DEFAULT_TOOLSET` |
| `app/tools/executor.py` | Prompt-based alt executor (`parse/run`, 4096-char cap) | 171 | doc agent (`ToolExecutor`) |
| `app/tools/base.py` | `ToolResult/ToolDefinition/ToolRegistry` | 139 | executor, doc agent |
| `app/integrations/` (~3827 total) | External systems: email (client/reader/sender/tools), telegram, brief, push, whatsapp, voice, mcp (server/client/manager/transports), ocr, vector | e.g. `app/integrations/mcp/server.py` 481, `app/integrations/email/client.py` 269, `app/integrations/brief/__init__.py` ~224 | adapters (email/voice/push/brief routes), memory (OCR/vector) |
| `app/agents/doc_agent.py` | `DocumentationAgent` (only agent class; `MAX_ITERATIONS=12`) | 246 | on-demand `docs` command only, NOT the request path |
| `app/mcp/registry.py` | Thin MCP dataclass shim (no transport logic) | 91 | UNKNOWN — needs human review (real logic in `app/integrations/mcp/`) |
| `app/utils/` (~2825 total) | Provider catalogs (`provider_catalog.py` 637, `model_selector.py` 322, 14 `*-catalog.py`), `tokenizer.py` 199, `server_manager.py` 197 | ~2825 | provider registry, context builder, switcher |
| `app/artifacts/manager.py` | `ArtifactManager` (`spill_bytes`, sha256 names) | 106 | `bootstrap.py` |
| `app/workspace/manager.py` + `project.py` + `watcher.py` | Workspace sandbox root/project/watcher | 171 + 22 + 35 | workspace tools |
| `app/api/ocr/routes.py` | OCR extra routes | 167 | mounted in `main.py` |
| `app/backend/providers/` | EMPTY — only `__pycache__`, no `.py` source | 0 | nothing (abandoned) |
| `app/db/` | EMPTY — only `__pycache__`, no `.py` source | 0 | nothing (abandoned) |
| `app/evals/` | EMPTY — only orphan `.pyc`, no `.py` source | 0 | nothing (live suite is top-level `evals/`) |
| `config.yaml` | Model registry (4 entries: local/grok/openrouter/google) | 43 | `Settings.load` → factory/switcher |

---

## 4. Where state lives

- **Files (`data/`):** `approvals.json` (`bootstrap.py:151`); `memories.json`
  (`app/memory/store.py:86` via `settings.py:93`, atomic `os.replace` :187);
  `sessions/session_{id}.json` + `conv_{id}.json` (`app/session/persistence.py:31-88`);
  `conversations/default.json` + friends (`app/conversation/manager.py:72-222`);
  `web_settings.json` (0600, `app/adapters/web/settings.py:27`);
  `checkpoints.db`, `jarvis.db`, `data/sessions/jarvis.db` (SQLite, live);
  `chroma/` (`chroma.sqlite3` + UUID dirs); `artifacts/`, `attachments/`, `uploads/`, `backups/`, `projects/`.
- **DBs:** Postgres **optional/prod** (`docker-compose.yml:4` pgvector/pg16;
  `bootstrap.py:95-109` uses `PostgresCheckpointer` only if `JARVIS_DATABASE_URL` starts with
  `postgresql`, else `MemorySaverAdapter` dev fallback; `persistence.py:115` `_save_session_pg` is a
  placeholder). SQLite dev (`checkpointer.py:7` `import sqlite3`; on-disk `data/*.db`).
  ChromaDB vectors (`app/memory/vector_retriever.py:25-26` `jarvis-memories`,
  `conversation_store.py:34-35` `jarvis-conversations`, embed via Ollama `nomic-embed-text`
  `settings.py:89-91`). `app/db/` is an **empty placeholder** (no code).
- **Memory (process):** `ApplicationContainer` singleton (`bootstrap.py:71-92`);
  `SessionManager._active_sessions/_active_conversations` (`app/session/manager.py:22-23`);
  `ConversationManager._messages/_summary/_dirty` (`app/conversation/manager.py:75-77`);
  `MemoryStore` dirty-flag (`app/memory/store.py:68`); provider registries
  (`provider_registry.py:830`, `settings.py:247-248`, guardrails global policy, tracer registry).
- **Globals/singletons:** `_container_instance` (`bootstrap.py:71`); `_registry_instance`
  (`provider_registry.py:830`); `_settings` + `_lock` (`app/config/settings.py:247-248`);
  `set_global_policy` (`bootstrap.py:148`); `register_tracer` (`bootstrap.py:124`);
  `get_ocr_settings` (`app/integrations/ocr/config.py:50`).

---

## 5. Where LLM calls are made (every call site)

Only **two** runtime paths actually hit an LLM. The primary `/chat/completions` brain path does not.

| # | Call site | What happens | Token tracking |
|---|---|---|---|
| 1 | `app/adapters/web/router.py:762-765` (`chat()`) | `container.create_model_client(config)` (:762, → `app/models/factory.py:117` `create_client`) then `client.generate([{role:user, content:full_message}])` (:763-765), normalized by `_extract_content` (:558-562). Model resolved :637-681 via catalogue + `get_default()` fallback; `agy` branch :698-714 shells to CLI | `ModelResponse.tokens_used` (see per-client below); budgets `app/resources/` |
| 2 | `app/agents/doc_agent.py:135` (`DocumentationAgent.run`) | `self._model.generate(messages)` loop (non-streaming, `MAX_ITERATIONS=12`) | same `ModelResponse` contract |
| 3 | `app/memory/llm_extractor.py:59-78` (`LLMFactExtractor.extract`) | `self._model.generate([system _EXTRACTION_PROMPT, user message])` — **wired but UNKNOWN whether called in production** — needs human review (`ChatModel` Protocol :25, never constructed here) | UNKNOWN |
| 4 | `app/adapters/integrations/agy.py:96` (`chat`) | Subprocess CLI (`--agent/--mode`), parses JSON `tokens_used` (:216) | parsed from CLI JSON |

Provider fan-out (`app/models/factory.py:117-214`): `ollama` :129, `openrouter` :140, `groq` :145,
`github` :150, `mistral` :155, `nvidia` :160, `cloudflare` :165, `zhipu` :170, `together` :175,
`cerebras` :180, `openai` :185, `google` :191, `cohere` :196, `huggingface` :201, `anthropic` :206,
default `LlamaCppClient` :212-214. Wire calls: 12 OpenAI-compatible clients call
`chat.completions.create` (sync + streaming variants, e.g. `llamacpp_client.py:59/73`,
`ollama_client.py:54/68`, `openrouter_client.py:101/116`); `google_client.py:145/148/187/190`
(`generateContent`/`streamGenerateContent` via `requests.post`); `anthropic_client.py:111/113/155/157`
(`/messages`); `cohere_client.py:68/89/101` (`/chat`); `hf_client.py:64/76` (`/models/{model}`).
Router/failover: `app/models/router.py:90-169` (`select_healthy_provider` → `generate` →
`record_success/record_request` :143-144, 429/503 failover :147-169); `omni_client.py:32-86`
(round-robin + backoff); `switcher.py:31-234` (per-role routers + default-local + omni).
`app/brain/*` makes **zero** LLM calls (heuristic `analyzer.py:23`, deterministic `planner.py:54`,
passthrough `synthesizer.py:17`, tool-only `runner.py:35`). `app/prompt/loader.py:19-71` is templates only.
Per-call usage: `tokens_used=response.usage.total_tokens` (e.g. `llamacpp:66`, `ollama:61`,
`openrouter:109`); Google `usageMetadata.totalTokenCount` (:170, :237); Anthropic
`input+output_tokens` (:139, :204). Contracts `models/interface.py:16`, `models/client.py:8`.
Budgets: `resources/budget.py:22-53` (128k max), `rate_limits.py:18-37`, `provider_health.py:35-58`;
events `events/models.py:64` `TokenUsageEvent` → `telemetry/logger.py:31-49`, `metrics.py:19-33`.
Counting: `utils/tokenizer.py:17-156` (tiktoken w/ estimate fallback); `session/context.py:36-59` trim.

---

## 6. Existing tests: what's covered, what isn't

- **Layout** (`pyproject.toml:17-23`: `testpaths=["tests"]`, NO `--cov` gate):
  `tests/conftest.py` (66 lines; `TEST_API_KEY` :21, autouse env-isolation :24-47, `api_key_env` :50-61);
  `tests/unit/` **131 files**; `tests/unit/integrations/` 7 files; `tests/integration/` 1 live file
  (`test_ci_bridge_gate_loop.py`, 271 lines) + 2 orphan `.pyc` (sources deleted);
  `tests/contract/` 4 files; `tests/e2e/` **0 live** (1 orphan `.pyc`);
  `tests/sprint3/` 3 files; `tests/sprint4/` **0 live** (1 orphan `.pyc`);
  `tests/utils/` **0 live** (1 orphan `.pyc`); `tests/performance/test_security.py` (773 lines, only perf test).
- **Covered (100% in last `.coverage` run, 87% total: 10274 stmts / 1302 miss):**
  `app/domain/*`, `app/brain/analyzer.py`, `planner.py`, most `models/*_client.py`,
  `app/models/router.py`, `switcher.py`, most `utils/*_catalog.py`, `app/memory/manager.py`,
  `artifacts/manager.py`, `app/prompt/loader.py`, `resources/*`.
- **Not covered / thin:**
  - `tests/e2e`, `tests/sprint4`, `tests/utils` — zero live tests; journeys/ecosystem/tokenizer e2e uncovered.
  - Lowest: `app/integrations/mcp/transports.py` 34%, `app/api/ocr/routes.py` 34%,
    `app/adapters/web/email_routes.py` 36%, `voice_routes.py` 45%, `app/integrations/email/tools.py` 47%,
    **`app/adapters/web/router.py` 49% (541 stmts, 277 miss)** — the only real LLM path is half-untested,
    `app/integrations/telegram/__init__.py` 53%, `app/tools/comms_tools.py` 53%, `brief_routes.py` 54%, `push_routes.py` 55%,
    `app/memory/llm_extractor.py` 65%, `app/memory/dedup.py` 66%, `app/telemetry/tracer.py` 67%,
    `app/memory/pipeline.py` 69%, `app/brain/nodes.py` 73%, `app/integrations/mcp/server.py` 73%,
    `app/session/postgres_checkpointer.py` 74%, `app/brain/graph.py` 75%, `factory.py` 80%,
    `app/workspace/manager.py` 83%. `app/main.py` 86% (17 miss incl. `main()` bind/auth warning :254-266).
  - `app/api/` has no unit test (only contract `tests/contract/test_api_contract.py:1-103`).
  - `app/db/`, `app/backend/providers/`, `app/evals/` have no sources AND no tests (empty packages).
  - Env-gated skips: `test_postgres_checkpointer.py:243` (`JARVIS_TEST_DATABASE_URL`),
    live-server skips (`test_chat_model_shapes.py:60`, `test_memory_api_temporal.py:36/46`),
    `test_security.py:370` git skip.

---

## 7. Config/secrets handling

- **`.env` (real, gitignored, 44 keys — names only):** `JARVIS_API_KEY`, `OPENROUTER/XAI/GOOGLE/GROQ/CEREBRAS/
  SAMBANOVA/NVIDIA/QWEN/OPENCODE/UNOROUTER/TOKENROUTER/TOKENHARBOUR/EXA/XKIRO/CHUTES_*/REQUESTY/CF/
  HF_API_URL/LEARNING_COMMONS`, `CLIENT_ID/SECRET`, `MCP_N8N_OFFICIAL/GITHUB_MCP_PAT`, VAPID trio,
  `JARVIS_EMAIL_*`, `JARVIS_BRIEF_*`, `TELEGRAM_*` (incl. `TELEGRAM_API_KEYS`), `WHATSAPP_*`,
  `SLACK_BOT_TOKEN`, `JARVIS_HOST/PORT/PUBLIC_ORIGIN`, assorted `*_API_KEY`.
- **`.env.example:1-105`** documents all of the above; header :4 "Never commit the real `.env`".
  Loaded first-thing `app/main.py:19` (`load_dotenv`) before adapter imports.
- **`config.yaml:1-43`** — model registry only (4 entries: `local_general` llamacpp :9-16,
  `grok` :19-24, `openrouter` :29-34, `google_general` :39-43). `api_key: "env:VAR"` refs resolved by
  `app/models/utils.py:4` `resolve_env_key` (raises if unset); per-request header override
  `factory.py:122-127`. `Settings.load` (`app/config/settings.py:172-219`) loops models via `_safe_model_config` (:122).
- **`app/config/settings.py`** — `ModelConfig` :16, `MemoryConfig` :30, `ContextConfig` :42,
  `ConversationConfig` :52, `RetrievalConfig` :61, `RankingConfig` :69, `PathsConfig` :81
  (`chroma_dir=data/chroma` :89, `ollama_url=http://localhost:11434` :90), `Settings` :142,
  singleton `_settings`+`_lock` :247-248 (`get_settings` :251, `reset_settings` :261).
- **Split-brain secret stores (blunt):** env vars AND `data/web_settings.json`
  (`app/adapters/web/settings.py:27`, 0600, holds custom providers + API keys) AND
  per-request header keys AND `docker-compose.yml:9` Postgres creds AND `provider_registry.py:82`
  `has_api_key` env checks per provider. No single secrets inventory; rotation story is UNKNOWN.
- **Auth bypass by design:** unset `JARVIS_API_KEY` disables auth (`http/router.py:41-44`,
  `adapters/security.py:53-74`, `main.py:259-264` warning). Default bind is `0.0.0.0`
  (`main.py:256`) — **network-reachable with auth off unless the operator sets the key.**

---

## 8. Dead code, half-finished, clearly abandoned

- **`legacy/` (1969 LOC):** `server.py` (1114 lines, header :1-30), `web_api_server.py` (855 lines, :1-6).
  Dead by design; excluded from mypy (`pyproject.toml:40-48`, "Duplicate module named app" comment).
- **`app/backend/providers/`, `app/db/`, `app/evals/`:** EMPTY source dirs (only `__pycache__`/orphan `.pyc`
  from 2026-07-28). No `.py`, no tests. `app/evals` superseded by top-level `evals/` (`eval.py:1-58`, `runner.py`,
  `reporters.py`, `evals/cognitive|golden|memory|system.py`).
- **`app/mcp/registry.py:1-91`:** thin dataclass shim; real MCP lives in `app/integrations/mcp/`
  (6 files incl. 481-line `server.py`). Half-finished split; no `test_mcp_registry*`.
- **`app/brain/graph.py` + `nodes.py` (73-75% covered):** LangGraph wrapper around the same heuristic
  nodes; evaluator is heuristic with `nodes.py:252` "replace with LLM-based in Sprint 4" comment.
  No adapter calls it on the hot path — parallel universe, UNKNOWN if anything production uses it.
- **Voice WS brain gap:** `app/adapters/websocket/voice_handler.py:63` `# TODO: Process command through brain` —
  wake-word/STT/TTS wired, cognition not.
- **`agy.py:250`** `# TODO: Use agy's native file upload when available`.
- **Orphan bytecode (deleted sources):** `tests/e2e`, `tests/sprint4`, `tests/utils`,
  `tests/integration` (2 files), `tests/performance/stress_test.*` — `.pyc` without `.py`.
- **Committed build/vendor/scratch:** `frontend/out/`, `frontend/.next/`, `frontend/_next/`,
  `frontend/node_modules/`, `mobile/www/` (committed build output), `mobile/node_modules/`,
  `tgcall/node_modules/`, `external/Unlimited-OCR/` (+ 1 `.whl`),
  `artifacts/` (174 committed provenance/SBOM outputs), `.archaeology/` (research notes),
  `node_modules/` at root. `frontend`/`mobile`/`tgcall` have `"test": "echo ...no test..."` — no JS tests.
  Root scratch (`tmp/`, e.g. `lib_code.js`, `styles_append.css`) is **gitignored and untracked**, so it is
  absent from a fresh clone and is not listed as committed. (Corrected: this line previously named those
  two scratch files as committed; `git ls-files tmp/` returns nothing.)
- **`pass`-only stubs (21 hits):** `models/llamacpp_client.py:40`, `switcher.py:128/196/234`,
  `cohere_client.py:117`, `memory/vector_retriever.py:47/61`, `memory/store.py:214`,
  `session/postgres_checkpointer.py:37/43/49`, `tokenizer.py:107`, `model_selector.py:73`,
  `tools/executor.py:94/104`, `conversation/manager.py:213`, `otel_exporter.py:120`,
  `integrations/mcp/transports.py:170/172` (correlates with 34% coverage), `ws/stream.py:56`, `ocr/service.py:19`.
- **`n8n/` + `n8n-workflows/`:** 3 + 1 workflow JSONs; per ADR-013 the executor plane, no Python tests.
