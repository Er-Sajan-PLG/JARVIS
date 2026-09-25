# JARVIS — Gap Analysis (current state vs target architecture)

**Status**: ACTIVE
**Type**: architecture
**Last Updated**: 2026-09-25
**Reviewed**: 2026-09-25
**Source**: `app/`, `config.yaml`, `docs/ARCHITECTURE.md`, `docs/architecture/` at HEAD; target spec 2026-09-25 (message)

> Every classification is exactly one of: ALREADY EXISTS / PARTIALLY EXISTS / MISSING /
> CONFLICTS / UNNECESSARY. "Where" quotes real paths. Gaps are blunt.

Summary counts: ALREADY EXISTS 4 · PARTIALLY EXISTS 9 · MISSING 20 · CONFLICTS 1 · UNNECESSARY 2.

---

## 1. CORE LAYER (`core/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `core/config.py` — Pydantic centralized config (per-mode models, paths, security flags, hardware endpoints) | PARTIALLY EXISTS | `app/config/settings.py:142-269` (`Settings.load` :172-219, `PathsConfig` :81-101); `config.yaml:1-43`; `.env` / `.env.example:1-105`; `app/provider_registry.py:82-830` | Pydantic settings + model registry + paths exist, but config is **split across 4 stores** (env, `config.yaml`, `data/web_settings.json` at `app/adapters/web/settings.py:27`, per-request header keys at `app/models/factory.py:122-127`). No per-mode model map, no security-flags section, no hardware endpoints. Centralization is the gap. | M | Medium — every adapter reads config; consolidating secret stores risks breaking web-settings custom keys and header overrides. |
| `core/jarvis.py` — orchestrator (boot → route → permission → mode → memory → evolution → output, graceful shutdown) | PARTIALLY EXISTS | `app/bootstrap.py:74-187` (`bootstrap_system`); `app/main.py:42-64` (`lifespan`), `:110-133` (middleware), `:243-266` (`main`) | Boot + DI container exist, but **no unified message lifecycle**: `POST /chat/completions` (`app/adapters/http/router.py:63-112`) does intent→plan→execute and returns plan status with **no LLM and no memory write**; `web/router.py:565-804` does memory→LLM→store with **no intent/planner/runner**; WS (`stream.py:15-56`) does intent + echo. No permission→mode→memory→evolution chain anywhere; shutdown only cancels the Telegram task (:62-64). | L | High — unifying the two request paths changes response contracts (`chat/completions` currently returns plan JSON, not text). |
| `core/mode_manager.py` — modes, transitions, history, per-mode prompt switching | MISSING | No `modes/` dir; nearest cousin `app/context/builder.py:60-82` (`build_system_prompt`, single `system_base.md`) | Net new: mode enum, transition rules, history, prompt switch. | M | Medium — prompt changes alter every LLM output; needs eval harness (`evals/`) gating. |
| `core/intent_engine.py` — intent (question/command/request), domain ID, urgency, action parsing | PARTIALLY EXISTS | `app/brain/analyzer.py:23-81` (`IntentAnalyzer.analyze`); types `app/domain/intent.py:9-26` | Heuristic classifier exists (`DIRECT_CHAT/FILE_QUERY/TOOL_SEARCH/MULTI_STEP`) but **no urgency rating, no question/command/request taxonomy, no action parsing, no domain ID** (suggested-tools are static strings like `"search_web"` :70 that match no registered tool). | S | Low — analyzer is pure, well-tested (`test_brain.py`, 100% cov); extend return type carefully. |
| `core/response_engine.py` — provider abstraction, fallback chains, token tracking | PARTIALLY EXISTS | `app/models/router.py:77-184` (failover :147-169); `app/models/factory.py:117-214`; `omni_client.py:32-86`; `switcher.py:31-234`; `ResponseSynthesizer` `app/brain/synthesizer.py:17-32`; token path `resources/budget.py:22-53`, `events/models.py:64` | Provider abstraction + circuit-breaker failover + per-call `tokens_used` all exist, but there is **no single response boundary**: the synthesizer is a passthrough yield, and only the web path calls `generate` (`web/router.py:762-765`). No per-mode fallback chains, no centralized token-budget enforcement pre-call. | M | Medium — touching the router affects the only working LLM path; failover semantics are load-bearing. |

## 2. MODES SYSTEM (`modes/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `modes/base_mode.py` — ABC (`name`, `emoji`, `system_prompt`, `handle()`, `format_response()`) | MISSING | No modes package; closest is `DocumentationAgent` (`app/agents/doc_agent.py:1-246`, single concrete class, no ABC/registry) | Net new contract + registration. | S | Low if additive (new package, no existing callers). |
| `modes/teacher_mode.py` (🎓) — Socratic, stepwise, analogies, comprehension checks, learning-level tracking | MISSING | No pedagogy code; memory stores facts (`app/memory/service.py:71-147`) but no learner model | Net new: prompts + comprehension state + level tracking (needs long-term schema change). | M | Low-medium — additive, but level tracking touches memory schema. |
| `modes/production_mode.py` (⚡) — dense output, zero filler, minimal tokens | MISSING | Cousin: token infra exists (`utils/tokenizer.py:17-156`, `resources/budget.py`, `session/context.py:36-59` trim) but no style enforcement | Net new: system prompt + verbosity controls + token-budget wiring. | S | Low — prompt-only, gate with evals. |
| `modes/maintenance_mode.py` (🔧) — health diagnostics, error recovery, self-healing | MISSING | Cousins: `GET /health` (`http/router.py:51-60`), `GET /api/v1/web/health` (`web/router.py:1155-1157`), `MetricsCollector`, OTel; n8n `JARVIS-Cleanup.json` | No unified diagnostics surface (CPU/RAM/disk, memory state, plugin health in one place), no error-recovery or self-healing logic. **Overlaps existing health/metrics — do not duplicate.** | M | Medium — self-healing that restarts/mutates prod is the riskiest behavior in the target. |
| `modes/evolution_mode.py` (🧬) — self-evaluation, perf reports, prompt optimization, bottleneck detection | MISSING | Cousins: `brain/nodes.py:247-267` heuristic `evaluator_node` (comment :252 "replace with LLM-based in Sprint 4"), top-level `evals/` suite, `telemetry/metrics.py` | Net new: LLM-backed evaluator + reporting + optimization proposals. See also `evolution/` below — target specifies this twice. | M | Medium — self-modifying prompts without a human gate is unsafe (see Migration Plan pushback). |

## 3. MEMORY SYSTEM (`memory/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `memory/short_term.py` — ephemeral context, token-capped sliding window, metadata | PARTIALLY EXISTS | `app/session/manager.py:20-86` (in-mem `_active_sessions/_active_conversations` :22-23); `app/conversation/manager.py:62-222`; `app/context/builder.py:84-165` (budget truncate :137-156); `app/session/context.py:36-59` | Sliding window + truncation + metadata exist but scattered across session/conversation/context with **two parallel context paths** (HTTP path ignores `ContextBuilder`; web path inlines assembly at `web/router.py:592-629`). No `short_term.py` boundary. | M | Medium — unifying context paths changes prompt content on the working LLM path. |
| `memory/long_term.py` — JSON/SQLite persistence (profile, metrics, preferences, topics) | PARTIALLY EXISTS | `app/memory/store.py:68-214` (`MemoryStore`, atomic save :187); `data/memories.json`, `data/sessions/*.json`, `data/*.db`; `session/persistence.py:23-115`; bi-temporal `memory/temporal.py` (430 LOC), `rules.py` (316) | Persistence exists and **exceeds** the target (bi-temporal valid+transaction time, dedup, ranking), but as ~15 modules with no `long_term.py` facade; Postgres path is placeholder (`persistence.py:115`); profile/preferences/topic APIs are implicit, not explicit. | M | Medium — schema migration (bi-temporal invalidation, ADR-015) is one-way; Chroma/SQLite moves need backfill. |
| `memory/semantic.py` / `vector_store` — embeddings + cross-session semantic search (ChromaDB/Vector) | ALREADY EXISTS | `app/memory/vector_retriever.py:13-61` (`PersistentClient`, `jarvis-memories` :26); `conversation_store.py:21-35` (`jarvis-conversations`); `hybrid_retriever.py`, `ranking.py`, `retrieval.py`; `settings.py:89-91` (chroma dir, `nomic-embed-text`); `web/router.py:593-600` retrieval call | Mapping only: `vector_retriever.py` + `conversation_store.py` + `hybrid_retriever.py` ≈ `semantic.py`/`vector_store`. Hybrid BM25+vector already works. Gap is naming, not capability. | S | Low — rename/facade only; do not re-embed. |

## 4. DOMAIN EXPERTISE (`domains/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `domains/coding.py` | MISSING | Cousins: `prompts/` (`system_base.md`, `planner.md`, `synthesizer.md`); `tools/git_tools.py`, `workspace_tools.py`; `config.yaml:29-34` openrouter `role: code` | No partitioned prompts/tools/validation per domain. `role: code` is a routing label, not a domain module. | M (×6 if all at once — don't) | Low per-domain if additive, but six domains at once is a big-bang prompt change. Start with one. |
| `domains/science.py` | MISSING | Same as above | Same: net new. | M | Same. |
| `domains/finance.py` | MISSING | Same as above | Same. Consider UNNECESSARY overlap — see §10. | M | Same + accuracy liability for money advice. |
| `domains/health.py` | MISSING | Same as above | Same. Highest liability — see pushback. | M | High (harm risk) — gate hardest, ship last or never. |
| `domains/writing.py` | MISSING | Cousin: `DocumentationAgent` (`app/agents/doc_agent.py`) generates changelogs, not general writing | Net new. | S | Low. |
| `domains/research.py` | MISSING | Cousins: `EXA_API_KEY` (`.env.example:40`), `external/Unlimited-OCR/`, `app/api/ocr/routes.py` (34% cov) | No research tool/validation; **no `web_search` tool exists** despite `analyzer.py:70` suggesting `"search_web"`. Research without retrieval is a prompt-only shell. | M | Medium — depends on adding the missing search plugin first. |

## 5. HARDWARE CONTROL (`hardware/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `hardware/controller.py` — unified HAL | MISSING | No `hardware/` dir. Closest: sandboxed file tools (`tools/workspace_tools.py:44-114`) — not hardware | Entire layer net new. | L | **High** — new physical-actuation surface; needs permissions + audit first. |
| `hardware/smart_home.py` — Home Assistant REST/WS | MISSING | Nothing (no HA client, no WS integration beyond chat) | Net new + credentials + network egress. | M | High — home actuation without HITL is unacceptable. |
| `hardware/iot_bridge.py` — MQTT sensors/actuators | MISSING | Nothing (no MQTT dep in `requirements.txt`) | Net new dep + broker + topic schema. | M | High — persistent broker connection, reconnection/backpressure design owed. |
| `hardware/desktop_control.py` — OS task/window/app automation | MISSING | Nothing (explicitly no `shell=True` per governance; `tools/executor.py` is prompt-parse + cap, not OS automation) | Net new + sandbox escape design. Directly tensions the `no shell=True` rule. | L | **Highest** — OS control voids the current sandbox assumptions. |

## 6. INTERFACES (`interfaces/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `interfaces/cli.py` — rich terminal + slash commands (`/t /p /m /e /status /help`) | MISSING | No CLI module; `run_interactive` in `app/agents/doc_agent.py` is a docs menu, not a console | Net new: Typer exists (`typer==0.27.2`, `rich==15.0.0` in requirements) but unused for this. | S | Low — additive; keep out of the hot path. |
| `interfaces/voice.py` — wake-word + Whisper STT + low-latency TTS | PARTIALLY EXISTS | `app/adapters/web/voice_routes.py:25-111` (STT :53-73 faster-whisper, TTS :76-99 edge-tts); `app/adapters/websocket/voice_handler.py:16-82` (`is_wake_word` :45, strip :54); `app/integrations/voice/__init__.py` (76% cov) | STT/TTS/wake-word-check exist, but brain wiring is an open TODO (`voice_handler.py:63-64`), and "low-latency" is unproven (no streaming TTS, no latency budget test). | M | Medium — audio path is 76%-covered and fragile; latency work risks regressions. |
| `interfaces/web.py` / `api.py` — FastAPI + WebSocket dashboard + external triggers | ALREADY EXISTS | `app/main.py:93-155` (app + 10 routers); `adapters/http/router.py:24-244`; `adapters/websocket/stream.py:15-81`; `adapters/web/router.py:1-1157`; `frontend/` SPA + PWA routes (`main.py:167-240`); `mobile/` Capacitor wrapper | Mapping only: current adapters ≈ target interfaces with different names. Gap is **consolidation**, not capability (10 routers, two request paths, three state stores). | S (facade) / L (consolidate) | High if consolidated (every client breaks); low if left as-is behind a facade. Recommend facade, not rewrite. |

## 7. EVOLUTION ENGINE (`evolution/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `evolution/analyzer.py` — usage patterns, domain dominance, latency | PARTIALLY EXISTS | `telemetry/metrics.py:19-58`; `telemetry/logger.py:31-54`; `brain/nodes.py:247-267` heuristic evaluator; top-level `evals/` (`eval.py:1-58`, `runner.py`, `cognitive/golden/memory/system.py`) | Raw signals (counts, tokens, heuristic scores) exist; **no pattern/domain-dominance/latency analysis** composes them. Gap is the analysis query layer, not instrumentation. | M | Low-medium — read-only over telemetry; keep it read-only. |
| `evolution/optimizer.py` — upgrade suggestions (prompts, plugins, config) | MISSING | Nothing generates suggestions; `docs/DECISIONS-AUTONOMOUS-2026-09-10.md` is human-written | Net new; must be advisory-only (see pushback). | M | Medium — suggestions are safe, auto-applied suggestions are not. |
| `evolution/changelog.py` — auto-logs adaptations | MISSING | Cousins: `docs/CHANGELOG.md` (manual), `DocumentationAgent` (doc-gen on demand), `artifacts/` provenance JSONs | No autonomous-adaptation log because nothing adapts autonomously yet. Building the log before the engine is cart-before-horse. | S | Low — but only meaningful after optimizer exists with a human-approval gate. |

## 8. PLUGIN SYSTEM (`plugins/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `plugins/base_plugin.py` — contract (init, validate, execute, health_check) | PARTIALLY EXISTS | `app/tools/base.py:17-139` (`ToolResult`, `ToolDefinition.execute`, `ToolRegistry`); `decorator.py:28-74` (`@safety_gate`); `DEFAULT_TOOLSET` (`tools/__init__.py:40-53`) | Registry + execution + safety exist, but **no `init/validate/health_check` lifecycle**; health is provider-level (`resources/provider_health.py:35-58`), not plugin-level. Lowest-covered seam: `mcp/transports.py` 34%. | M | Medium — retrofitting lifecycle onto every tool touches the runner hot path. |
| `plugins/web_search.py` | MISSING | `analyzer.py:70` advertises `"search_web"`; `EXA_API_KEY` documented (`.env.example:40`); **no such tool registered** | Net new tool + provider key + result schema. Blocks `domains/research.py`. | S | Low-medium — new egress; needs timeout/PII-redaction policy. |
| `plugins/file_manager.py` | ALREADY EXISTS | `app/tools/workspace_tools.py:117-160` (sandboxed CRUD + `list_dir`); `app/tools/file_tools.py` (allowlisted agent tools) | Mapping only (`workspace_tools` ≈ `file_manager`). Gap: none functionally; lifecycle wrapper only. | S | Low — wrap, don't rewrite. |
| `plugins/calendar_sync.py` | MISSING | Nothing (no calendar client, no CalDAV/Google-Calendar dep) | Net new integration + OAuth + sync state. | M | Medium — OAuth token storage expands the secrets problem (§7 of Current State). |
| `plugins/email_handler.py` | PARTIALLY EXISTS | `app/integrations/email/client.py` (269), `reader.py`, `sender.py`, `tools.py` (47% cov); `adapters/web/email_routes.py` (36% cov) | Send/read/tools exist but outside any plugin contract, at the **two lowest coverage rates** in comms (36-47%). Gap: contract wrapper + tests before anything else. | M | Medium — email exfiltration/phishing surface; needs permission tier + audit. |

## 9. SECURITY & GOVERNANCE (`security/`)

| Target Component | Exists Today? | Where | Gap | Effort (S/M/L) | Risk if changed |
|---|---|---|---|---|---|
| `security/permissions.py` — confirmation gates for dangerous actions | ALREADY EXISTS | `app/guardrails/policy.py:40-88` (SAFE/SENSITIVE/DESTRUCTIVE); `decorator.py:28-74` (`@safety_gate`); `approvals.py:245-365` (persist/decide/notify); `http/router.py:126-244` HITL endpoints; ADR-008/ADR-011 | Mapping only (`guardrails/` ≈ `security/permissions.py`). Current system is **stricter** than the target text (tiered + persisted + 30-min auto-deny via n8n `JARVIS-HITL.json`). Gap: coverage — isolation-gaps table (AGENTS.md §7.2) tracks `@safety_gate` rollout to all tools. | S (coverage) | High if weakened; low if only extended. **Do not dilute.** |
| `security/audit_log.py` — append-only structured JSONL of inputs/actions/responses | PARTIALLY EXISTS | `telemetry/logger.py:31-54` (bus-subscribed JSON logs w/ correlation IDs); `logging_middleware` (`main.py:110-133`); `artifacts/` provenance JSONs; `approvals.json` decision records | Structured logging + correlation + provenance exist, but **no single append-only JSONL audit log** covering every input→action→response triple durably (bus is in-memory; logs rotate). Gap is durability + completeness proof. | M | Medium — high-volume log writes need rotation/redaction (keys, mail bodies, voice bytes must not land in the log). |

## 10. Classification roll-up

- **ALREADY EXISTS (4):** semantic/vector memory; web/API interfaces; file-manager plugin; permissions gate.
  Action: facade/rename only. Do not reimplement.
- **PARTIALLY EXISTS (9):** central config; orchestrator; intent engine; response engine; short-term memory;
  long-term memory; voice interface; plugin base; audit log; (plus evolution-analyzer and email plugin
  counted in their tables). Action: close the named gap behind the existing module, keep the contract.
- **MISSING (20):** mode manager; all 5 modes (base counted once); 6 domain modules; 4 hardware modules;
  CLI; evolution optimizer + changelog; web-search + calendar plugins. Action: build in risk order (Migration Plan).
- **CONFLICTS (1):** `hardware/desktop_control.py` vs the `no shell=True` governance rule and the
  `workspace_tools.py` sandbox (`_check_sandbox`, fail-closed :91-114). The target assumes OS automation;
  the codebase forbids the primitives that implement it. Resolve the governance conflict (ADR) before code.
- **UNNECESSARY (2):**
  1. **`evolution/changelog.py` as specified** — auto-logging "autonomous adaptations" presumes an
     autonomous actor that does not exist (optimizer is MISSING, evaluator is heuristic). A standalone
     changelog writer with no producer is dead code on arrival. Build it only as the output sink of a
     gated optimizer, not as its own milestone.
  2. **`domains/` as six parallel modules on day one** — the product is single-tenant with no observed
     domain traffic split (no domain metrics exist; evolution-analyzer is PARTIALLY). Six validation
     rule-sets with no traffic to validate against is overkill. Ship one domain slice (coding) behind the
     mode facade, measure, then decide whether finance/health ever earn their liability cost.
