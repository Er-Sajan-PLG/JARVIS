# JARVIS — Migration Plan (toward the target architecture)

**Status**: ACTIVE
**Type**: architecture
**Last Updated**: 2026-09-25
**Reviewed**: 2026-09-25
**Source**: `docs/architecture/CURRENT-STATE.md`, `docs/architecture/GAP-ANALYSIS.md`, `app/` at HEAD

> Ordered smallest-risk first. Every step states what changes, what could break, and how to
> verify. Labels are binary: **REVERSIBLE** (flag-off or revert restores prior behavior) or
> **ONE-WAY DOOR** (data/schema/contract change that cannot be un-taken). When in doubt it is
> marked ONE-WAY.

---

## System overview

Fourteen migration steps move JARVIS from its current two-request-path reality
(HTTP plan-status + web direct-LLM) toward the target architecture (core/modes/
memory/domains/hardware/interfaces/evolution/plugins/security) in smallest-risk
order: audit sink, search plugin, correlation tracing, and mode facade first
(all reversible and additive); the HTTP-path LLM fix and context unification
behind flags next; hardware last as ADR-gated one-way doors. Each step records
what changes, what could break, how to verify, and whether it is reversible.

## 0. Freeze the baseline (do first, before any migration step) — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: nothing in `app/`. Tag HEAD, record `.coverage` totals (currently 87%, 10274 stmts /
  1302 miss), save `coverage report --show-missing` output, `pip freeze`, `node --version` (v24.21.0),
  list orphan `.pyc` (`tests/e2e`, `tests/sprint4`, `tests/utils`, `tests/integration`, `stress_test`).
- Could break: nothing.
- Verify: `.venv/bin/pytest tests/ -q` green; `.venv/bin/python scripts/board/review.py` green;
  `curl -s http://localhost:8000/api/v1/health -H "Authorization: Bearer $JARVIS_API_KEY"`.
- **Done 2026-09-25** (HEAD `5de9c64`, tag `migration-baseline-20260925`):
  `docs/architecture/BASELINE.md` frozen (87% / 10274 stmts / 1302 miss, pip freeze 218,
  orphan `.pyc` list, known issues carried). Board review: all green. Suite: every
  previously-passing test still passes, plus the new audit-sink tests; the only failures are
  pre-existing ones (contract 404s + check_docs findings on prior-wave audit docs — verified
  failing without this wave's changes).

## 1. Append-only audit sink (no behavior change) — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: add a durable JSONL writer (`security/audit_log.py` as a thin sink) subscribed to the
  existing `InMemoryAsyncBus` (`app/events/bus.py:28-57`) for `TokenUsageEvent` (`app/events/models.py:64`),
  step events (`app/brain/runner.py:137-149`), and HITL decisions (`app/guardrails/approvals.py:316-365`).
  Correlate with the existing `X-Correlation-ID` (`app/main.py:114-131`). Redact keys, mail bodies, voice
  bytes; add rotation. Do NOT reroute any request path.
- Could break: disk growth, PII in logs, perf on the hot path (keep it fire-and-forget like `bus.publish`).
- Verify: run one `POST /api/v1/chat/completions` (`app/adapters/http/router.py:63-112`) + one web
  `chat()` (`app/adapters/web/router.py:565-804`); assert both triples appear in the JSONL with matching
  correlation IDs; `pytest tests/unit/test_events.py tests/unit/test_telemetry.py -q`.
- Reverse: delete the subscriber; prior logging (`telemetry/logger.py:31-54`) is untouched.
- **Done 2026-09-25** (HEAD `5de9c64` + working tree): shipped as `app/security/audit_sink.py`
  (plan said `security/audit_log.py` — actual path `app/security/audit_sink.py`; `AuditSink` +
  `maybe_attach_sink` + `audit_sink_enabled`), wired in `app/bootstrap.py` (+4 lines, env-gated
  `JARVIS_AUDIT_SINK`, default on),   `tests/unit/test_audit_sink.py` (new tests green).
  Wildcard-only (`"*"`) subscription — verified against `app/events/bus.py:28-43` that concrete +
  wildcard double-subscribing would double-write. Kill-switch + new env var documented in
  `docs/CONFIG.md`; `docs/FINAL_STATE.md` test_count 1717 → 1721. Ruff + `mypy --strict` +
  board review (11/11) green on new code. STOPPED here per plan — Step 2 awaits review of JSONL.

## 2. `web_search` plugin (additive, fills a lie) — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: new tool registered in `DEFAULT_TOOLSET` (`app/tools/__init__.py:40-53`) backed by the
  already-documented `EXA_API_KEY` (`.env.example:40`), with timeout, result cap (follow the 4096-char
  precedent in `app/tools/executor.py:43`), and PII redaction. This makes `analyzer.py:70`
  `suggested_tools=["search_web", ...]` true for the first time and unblocks `domains/research.py`.
- Could break: new network egress; slow provider stalls the runner loop (`runner.py:49-63` has no per-step
  timeout — add one with the tool, not around it).
- Verify: `pytest tests/unit/test_tools.py tests/unit/test_brain.py -q`; manual `TOOL_SEARCH` prompt
  (`"search for ..."`, `analyzer.py:65`) returns cited results; disable via feature flag → old behavior.
- Reverse: unregister the tool (flag-off).
- **Done 2026-09-25** (HEAD `5de9c64` + working tree): shipped as `app/tools/web_search_tool.py`
  (`web_search(query, max_results=5, timeout_sec=5)`, Exa `POST /search` via aiohttp,
  `@safety_gate(SAFE)`, per-result 500-char truncation, key redaction, errors-as-text);
  registered in `DEFAULT_TOOLSET` only when `JARVIS_WEB_SEARCH=1` (default `0` — default boot
  byte-identical). `tests/unit/test_web_search_tool.py` (new tests green). `EXA_API_KEY` row in
  `docs/CONFIG.md` corrected (now has a reader) + `JARVIS_WEB_SEARCH` row added; `.env.example`
  documents the flag. Note: plan text above says result cap follows a 4096-char precedent — actual
  per-result cap is 500 chars (Step 2 spec). STOPPED here per plan — Step 3 awaits review.

## 2.5. Correlation ID propagation (tracing before prompt changes) — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: new leaf module `app/telemetry/correlation.py` (`correlation_id_ctx`
  contextvar defaulting to `"none"` + set/get/reset helpers); `logging_middleware`
  (`app/main.py`) sets the var per request and resets in `finally`; `publish_async`
  (`app/events/bus.py`) stamps the active ID onto events lacking one (explicit IDs win).
  Covers `publish()` too (it forwards to `publish_async`). No middleware rewrite, no Event
  changes, no signature changes.
- Could break: context leaks (guarded by `finally`), import cycle `events ↔ telemetry`
  (avoided via function-local import — verified; top-level would break when `app.events`
  imports first). Six ruff findings in `bus.py` are pre-existing HEAD debt, untouched.
- Verify: `tests/unit/test_correlation_propagation.py` (stamp, fallback, explicit-wins,
  middleware set/reset); full suite; coverage floor.
- Reverse: remove the set/reset + hook; default `"none"` behavior restored.
- **Done 2026-09-25** (HEAD `5de9c64` + working tree): `app/telemetry/correlation.py`,
  middleware + bus hook, new propagation tests green. STOPPED here per plan — Step 3
  not started.

## 3. Mode facade with zero behavior change — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: new `modes/` package with `base_mode.py` ABC (`name/emoji/system_prompt/handle/format_response`)
  plus a `mode_manager.py` whose default route returns **today's exact behavior** (HTTP path → plan JSON;
  web path → direct LLM). No prompt text changes; `ContextBuilder.build_system_prompt`
  (`app/context/builder.py:60-82`) stays authoritative. Add `production_mode.py` as a pass-through first
  (it's the smallest prompt delta), leave teacher/maintenance/evolution as stubs that route to default.
- Could break: import cycles (respect `scripts/board/review.py` layering: adapters → bootstrap/brain only);
  prompt drift if anyone "improves" wording — forbid it in this step.
- Verify: contract tests unchanged (`tests/contract/test_api_contract.py`, `test_comms.py`,
  `test_console_auth.py`, `test_mobile_pwa.py`); `evals/` golden outputs byte-identical before/after;
  `ruff check`, `mypy --strict app/`, `scripts/board/review.py` green.
- Reverse: remove the router call; adapters call bootstrap directly as today.
- **Done 2026-09-25** (HEAD `5de9c64` + working tree): `app/modes/` (`base_mode.py` ABC,
  `production_mode.py` ⚡, `teacher_mode.py` 🎓, `maintenance_mode.py` 🔧, `evolution_mode.py` 🧬,
  shared `default_prompt.py` helper) + `app/core/` (`mode_manager.py`: default production,
  timestamped history, `ValueError` on unknown, prompt/format delegation) + `container.mode_manager`
  in `app/bootstrap.py`. Zero drift proven: every mode renders through `ContextBuilder` for the
  default session (same default the HTTP adapter uses), asserted by test, not by copy-paste.
  `tests/unit/test_mode_system.py` (new tests green). No caller wired yet — facade only.
  Incidental: Step 2.5's bus hook violated the `app.events`-standalone layering rule (caught by
  board review); fixed by moving the var to `app/events/correlation.py` with
  `app/telemetry/correlation.py` kept as a same-object re-export. STOPPED here per plan.

## 4. Extend `IntentAnalysis` (additive fields, defaulted) — REVERSIBLE — ✅ DONE 2026-09-25

- What changes: add `urgency`, `domain`, `action` fields to `app/domain/intent.py:18-26` with defaults
  preserving current classification (`app/brain/analyzer.py:23-81` logic untouched). Update
  `IntentState` (`app/domain/state.py:18-52`) and `nodes.py:39-65` passthrough. No new taxonomy enforced yet.
- Could break: dataclass consumers (`planner.py:54-153`, graph nodes) if a required field is added — keep
  everything `Optional`/defaulted.
- Verify: `pytest tests/unit/test_brain.py tests/unit/test_domain.py tests/unit/test_cognitive_graph.py -q`;
  `mypy --strict app/` (strict mode is on, `pyproject.toml:35-38`).
- Reverse: revert the dataclass; old callers ignore extra fields.
- **Done 2026-09-25** (HEAD `5de9c64` + working tree): `urgency`/`domain`/`action`
  (defaulted) + `URGENCY_LEVELS`/`DOMAINS` constants in `app/domain/intent.py`; three
  detectors + field population in `app/brain/analyzer.py` (branch logic untouched).
  No consumer reads the fields yet (planner/runner/modes untouched). Known spec-limitation
  found in testing: substring matching makes "capital" hit coding ("api" ⊂ "capital") —
  inherent to the specified algorithm, flagged for Step 5 consumers, not worked around.
  `tests/unit/test_intent_extensions.py` (new tests green) + `test_brain.py` green.
  STOPPED here per plan.

## 5. Wire the HTTP path to actually answer (the core fix) — REVERSIBLE (flag-gated) — ✅ DONE 2026-09-29

- What changes: behind a flag, `chat_completions` (`http/router.py:63-112`) synthesizes text via the
  existing `ModelRouter.generate` (`app/models/router.py:120-169`) + `ResponseSynthesizer`
  (`brain/synthesizer.py:17-32`) instead of returning plan-status JSON only. Memory read
  (`memory_service.search_memories`, cf. `web/router.py:593-600`) goes before, `store_memory` (cf. :780)
  after. Keep the old JSON shape available under the flag for existing HITL clients
  (`hitl/pending` :115-123, `hitl/approve` :126-214).
- Could break: **the response contract** (today: plan JSON, no text; after: text). HITL polling clients,
  n8n `JARVIS-HITL.json`, Telegram `/approve` resume (`router.py:183-214`) all assume plan JSON.
- Verify: flag off → contract tests pass unchanged; flag on → new test asserts
  `{response, model, session_id, tokens_used}` shape (mirror `web/router.py:798-804`); evals golden diff
  reviewed; `pytest tests/contract/ tests/unit/test_models_router.py -q`.
- Reverse: flag off. Do NOT remove the old shape until all HITL consumers migrate (that's the one-way part —
  not this step).
- **Done 2026-09-29**: shipped as `app/adapters/http/synthesis.py` (`http_llm_enabled`,
  `synthesize_answer`), wired in `app/adapters/http/router.py` behind `JARVIS_HTTP_LLM`
  (default `0` — flag-off response is byte-identical to before, asserted by test).
  `tests/unit/test_http_synthesis.py` (19 tests) + 3 contract tests asserting the
  flag-off/flag-on boundary. `docs/API_CONTRACT.md` §3.2 documents both shapes;
  `docs/CONFIG.md` + `.env.example` carry the flag.
  **DEVIATION FROM PLAN TEXT (verified, not assumed):** the plan said to use
  `ModelRouter.generate`. That router is constructed in `app/bootstrap.py:150` but
  **no provider is ever registered on it outside unit tests** — `register_provider`
  has zero non-test callers in git history, and `select_healthy_provider()` raises
  `RuntimeError: No healthy LLM providers available in failover pool` against a
  live boot (verified). `ResponseSynthesizer` is also stream-only
  (`synthesize_stream`), with no synchronous entry point. Step 5 therefore reuses
  `ApplicationContainer.create_model_client` + `adapters/web/settings.get_default()`
  — the path the web console already exercises in production. **Wiring `ModelRouter`
  is now an unlisted prerequisite for any future step that assumes it works; the
  plan should not again cite it as "existing".** Synthesis failures degrade to
  `{"synthesis_error": ...}` and never remove the plan fields.
  Incidental fix in the same wave: `_detect_domain`'s substring matching
  (Step 4's flagged "capital" → coding bug) is fixed with word-boundary matching
  in `app/brain/analyzer.py` (`_keyword_hits`), which also fixed a latent
  `"season"` → high-urgency false positive.

## 6. Short-term context behind a facade (no prompt change yet) — REVERSIBLE

- What changes: introduce `memory/short_term.py` as a facade over `session/manager.py:20-86`,
  `conversation/manager.py:62-222`, `context/builder.py:84-165`, `session/context.py:36-59`.
  Route the web path's inline assembly (`web/router.py:592-629`) through it without changing truncation
  behavior. The HTTP path keeps ignoring context until Step 5's flag is on.
- Could break: prompt content drift (the working LLM path is 49%-covered — `app/adapters/web/router.py` 277 misses).
  Any off-by-one in truncation changes every answer.
- Verify: golden-output diff empty with facade on; `pytest tests/unit/test_context.py
  tests/unit/test_conversation.py tests/unit/test_session.py -q`; coverage on `app/adapters/web/router.py` must not drop.
- Reverse: restore direct calls.

## 7. Plugin lifecycle, additive only — REVERSIBLE

- What changes: add optional `init/validate/health_check` to `ToolDefinition` (`app/tools/base.py:17-139`)
  defaulting to no-op-healthy; expose per-plugin health beside provider health
  (`resources/provider_health.py:35-58`). Wrap `file_manager` (already exists:
  `workspace_tools.py:117-160`) and `email_handler` (exists but 36-47% covered:
  `integrations/email/`, `app/adapters/web/email_routes.py`) without changing execution semantics.
  Prioritize `app/integrations/mcp/transports.py` (34% cov) for tests, not rewrites.
- Could break: runner hot path (`runner.py:93-104` invoke) if lifecycle hooks raise — make them
  non-blocking and never fail-closed on health.
- Verify: `pytest tests/unit/test_tools.py tests/unit/test_mcp*.py -q`; health endpoint includes plugin
  section; `scripts/board/review.py` layering still green.
- Reverse: remove the wrapper; registry behavior is unchanged.

## 8. Read-only evolution analyzer — REVERSIBLE

- What changes: `evolution/analyzer.py` as pure queries over existing telemetry (`app/telemetry/metrics.py`,
  `app/telemetry/logger.py`) + `evals/` results: usage patterns, domain share, p50/p99 latency. No writers,
  no config mutation, no prompt mutation. Output is a report, not an action.
- Could break: almost nothing (read-only). Cost risk only: full-table scans over Chroma/SQLite — cap windows.
- Verify: analyzer runs on a prod snapshot in CI and its numbers match manual `coverage report`/metrics spot
  checks; `pytest tests/unit/test_telemetry.py -q`.
- Reverse: delete the report job.

## 9. One domain slice: coding — REVERSIBLE

- What changes: single `domains/coding.py` (prompts + tool allowlist + validation) served behind the Step-3
  mode facade on the web path only. Deliberately NOT six domains. Success metric defined up front
  (e.g. eval pass rate on a coding golden set from `evals/evals/cognitive|golden`).
- Could break: prompt regression on non-coding traffic — mitigate by narrow routing (only when
  `IntentAnalysis.domain == coding`, defaulting to today's prompt otherwise).
- Verify: coding golden set improves or holds; non-coding goldens byte-identical; `pytest tests/unit/test_prompts.py -q`.
- Reverse: route domain back to default prompt.

## 10. Advisory optimizer + changelog sink (human-gated) — REVERSIBLE while advisory

- What changes: `evolution/optimizer.py` emits suggestion objects (prompt tweak / plugin need / config tune)
  from Step-8 reports; `evolution/changelog.py` records **decisions humans approve**, not autonomous
  adaptations. No auto-apply. Each suggestion links the telemetry window that produced it.
- Could break: suggestion spam, stale proposals — bound with TTL + owner fields.
- Verify: a human approves/rejects one suggestion end-to-end (approval flows through the existing HITL
  registry pattern, `approvals.py:316-365`); changelog entry appears; nothing else in the system changes.
- Reverse: disable the job. **Becomes ONE-WAY the moment any suggestion auto-applies** — do not cross that
  line without a new ADR and Step-11's guardrails.

## 11. CLI (additive satellite) — REVERSIBLE

- What changes: `interfaces/cli.py` (Typer exists: `typer==0.27.2`, `rich==15.0.0`) with slash commands
  (`/t /p /m /e /status /help`) calling the same HTTP API as the web console. No new server surface.
- Could break: nothing server-side; CLI auth handling (Bearer) must not log the key.
- Verify: CLI against a dev server exercises chat/health/HITL; no `tests/` regressions.
- Reverse: remove the CLI package.

## 12. Voice brain wiring + latency budget — REVERSIBLE

- What changes: close `voice_handler.py:63` TODO (route STT text through intent→mode→response, TTS back),
  add a latency budget test (STT→first-audio-byte). Keep the REST STT/TTS (`voice_routes.py:53-99`) untouched.
- Could break: the 76%-covered voice path (`integrations/voice/`) is fragile; streaming TTS changes timing.
- Verify: `pytest tests/unit/integrations/test_voice.py -q` plus a new latency assertion; manual wake-word
  run; flag-off restores echo behavior (`stream.py:43-48`).
- Reverse: flag-off.

## 13. Hardware — ONE-WAY DOORS, last, ADR-gated (do not start until Steps 1+7+10 are live)

- Order inside hardware (each a separate ADR + threat model): `controller.py` HAL contract first (no drivers),
  then `iot_bridge.py` (read-only sensors before actuators), then `smart_home.py` (read state before scenes),
  then `desktop_control.py` **only if the `no shell=True` governance rule is explicitly amended** —
  it currently CONFLICTS with `workspace_tools.py:44-114` sandbox assumptions (see Gap Analysis §10).
- What changes: new `hardware/` package, new deps (MQTT client — none in `requirements.txt` today),
  new secrets (HA tokens, broker creds — expanding the already split-brain stores from Current State §7),
  new network egress, persistent connections.
- Could break: physical actuation, secret sprawl, sandbox escape, unattended-execution liability.
  Every actuator must sit behind the DESTRUCTIVE tier (`policy.py:77-86`) + persisted HITL
  (`approvals.py`) + Step-1 audit from day one.
- Verify: per-driver kill-switch test, approval-deny test (actuation does NOT occur), broker-outage
  backpressure test, secrets-inventory test; `pip_audit`, `gitleaks`, `trufflehog` (CI gate per README).
- Reverse: **ONE-WAY** — once hardware has actuated in a home, you cannot "un-actuate" by reverting code.
  Removal is code-reversible; consequences are not.

## 14. What NOT to do (explicit non-steps)

- Do NOT rewrite the 10-router adapter layer into a single `web.py`/`api.py` big-bang. Cost L, risk High
  (every client breaks), benefit naming-only. Facade (Step 3), don't consolidate.
- Do NOT re-embed Chroma or migrate SQLite→Postgres as part of this migration. The vector store
  ALREADY EXISTS; the Postgres path is a placeholder (`persistence.py:115`). Separate project, separate ADR.
- Do NOT "finish" `app/backend/`, `app/db/`, `app/evals/` placeholders or delete orphan `.pyc` as migration
  steps — hygiene PRs, not architecture. (Deleting bytecode is safe anytime; it proves nothing.)

---

## Thinnest vertical slice (do this first to prove the architecture)

**Slice: `production_mode` + `web_search` + audit sink on the web chat path only. Touches nothing else.**

1. Ship Step 1 (audit sink) — silent, no behavior change.
2. Ship Step 2 (`web_search` tool, flag-off default).
3. Ship Step 3 facade with exactly one real mode: `production_mode` as pass-through + dense-output prompt
   variant, routed only when the caller passes `mode: production` (default callers get today's behavior).
4. One request: web `chat()` with `mode: production` + a question needing search
   (`"search for ..."`, exercising `analyzer.py:65-72` → `TOOL_SEARCH`) →
   `mode_manager` → `intent` → `web_search` tool → `response_engine` (`factory.py:117` +
   `router.py:120-169`) → audit JSONL triple.
5. Prove: (a) the mode boundary switched prompts without touching other callers; (b) the plugin contract
   carried a new tool end-to-end; (c) the audit log captured input→action→response with the correlation ID;
   (d) flag-off reproduces today's exact response (golden diff empty); (e) `pytest tests/contract/ -q` green.

Why this slice: it exercises one component from each of core, modes, memory (read path), plugins,
interfaces, and security without migrating any data, changing any contract, adding any driver, or
spending anything on domains/hardware/evolution. If this slice cannot ship cleanly, the full plan will not.

---

## Pushback: what is WRONG with the target architecture for this codebase

1. **It ignores the two-path reality.** The target's `jarvis.py` lifecycle (input → intent → permission →
   mode → memory → evolution → output) describes neither current path: the HTTP path has no LLM/memory,
   the web path has no intent/planner. A migration that implements the lifecycle as a third path creates
   three systems. The plan above instead strangles the two paths together behind flags (Steps 3+5) — the
   target text needs rewriting to name the strangler, not the greenfield.
2. **`desktop_control.py` conflicts with governance.** The repo forbids `shell=True` and enforces a
   fail-closed workspace sandbox (`workspace_tools.py:91-114`). OS/window automation voids both. Either the
   target drops this component or an ADR amends the security model first — code must not lead that decision.
3. **Evolution is specified backwards.** `changelog.py` (log adaptations) and `evolution_mode.py`
   (self-evaluation) assume an autonomous optimizer that does not exist; the current evaluator is heuristic
   (`nodes.py:247-267`, "replace with LLM-based in Sprint 4" at :252). Auto-applying prompt/config changes
   with 49% coverage on the LLM path (`app/adapters/web/router.py`) and heuristic evals is how you corrupt the system
   unattended. Optimizer must be advisory + human-gated (Step 10) until evals are LLM-backed and green.
4. **Six domains on day one is overkill with liability attached.** No domain traffic metrics exist
   (the analyzer that would produce them is itself missing). `health.py`/`finance.py` carry harm risk
   far beyond prompt engineering — they need validation rules, disclaimers, and eval sets that the target
   never mentions. Ship coding only (Step 9), measure, then decide if the rest earn their cost.
5. **Hardware without a threat model.** Four hardware modules with REST/WS, MQTT, and OS control, and no
   mention of kill-switches, actuation tiers, secret storage, or broker failure modes — for a server that
   binds `0.0.0.0` with auth disabled when the key is unset (`main.py:256-264`). Hardware goes last (Step 13)
   behind the permissions gate that already exists (`guardrails/` is stricter than the target's
   `permissions.py` — don't dilute it).
6. **Modes without evals will drift.** Per-mode system prompts multiply the prompt surface by five with no
   gating mechanism named. The repo has the harness (`evals/`, `tests/sprint3/`) — the target should require
   golden-set parity per mode before any mode ships. Step 3 enforces this; the target should too.
7. **The target omits the actual blockers.** Secrets in four stores (Current State §7), the Postgres
   placeholder (`persistence.py:115`), 34-49% coverage on comms/OCR/MCP-transports, orphan bytecode proving
   deleted tests, zero JS tests, and the `no shell=True` conflict above — none appear in the target, yet any
   one of them can stall the migration. Fix order matters more than target order; this plan sequences by risk,
   not by target section number.
