# JARVIS Development Log

**Status**: ACTIVE
**Type**: changelog
**Last Updated**: 2026-09-29

## 2026-09-29 (later) — `/ready` made honest; Step 6 premise found FALSE (not started)

- **`/ready` no longer probes `container.model_router`.** That router has **zero**
  `BaseLLMProvider` implementations in the tree — verified: `grep "BaseLLMProvider)"`
  over `app/` returns nothing, and the only constructions are `MagicMock(spec=...)`
  in `tests/unit/test_models_router.py`. Git history confirms it was built in
  Phase 2 (`bb7e20b`) and never implemented. Its failover intent is already served
  by `OmniModelClient` over the `ModelClient` protocol that actually shipped (18
  concrete clients). The probe was reporting a dead subsystem as load-bearing.
  It now checks the real request path: whether a default model resolves via
  `adapters/web/settings.get_default()`. Contract test + `docs/API_CONTRACT.md`
  §3.1.1 updated.
- **`agy` gap found and fixed.** `agy` is a CLI-backed pseudo-provider
  (`app/adapters/integrations/agy.py`) with a dedicated branch in the console
  (`web/router.py:698`) and **no** `get_provider_spec` entry — so
  `create_model_client` cannot reach it. Step 5's synthesis would have returned
  the misleading `Unknown provider 'agy'` for this repo's actual default model
  (`agy`/`gemini-3.1-pro-high`, `data/web_settings.json`). Both the probe and
  `synthesis._select_model` now name the real reason. New regression test.
- **Step 6 NOT started — its stated premise does not match the code.** The plan
  says to build `memory/short_term.py` as a facade over `app/session/manager.py`,
  `app/conversation/manager.py`, `app/context/builder.py`, `app/session/context.py` and to
  "route the web path's inline assembly (`web/router.py:592-629`) through it
  without changing truncation behavior". Verified against source:
  1. The web `chat()` path references **none** of those four modules (grep: zero
     hits). The only `session_manager` calls in any router are the *HTTP* path's
     (`http/router.py:146-147`). A facade over them would have no consumer on the
     web path — the same dead-abstraction pattern just removed from `/ready`.
  2. The "inline assembly" at 592-629 is not a duplicate of those modules; it is
     an orthogonal pipeline (`message + memory_context + file_context +
     email_context + brief_context`).
  3. **There is no truncation in this path.** The file's only slicing is at
     `:907`, `:968`, `:1033` (file extraction, memories listing) — unrelated to
     chat. The plan's stated risk ("any off-by-one in truncation changes every
     answer") describes a hazard that does not exist here.
  4. The web path sends a **single** `{"role": "user", "content": full_message}`
     — no conversation history for API providers.
  5. `/conversations*` are stubs returning `{"conversations": []}` /
     `{"exists": True}` / `{"success": True}`; nothing persists.
  Routing the web path through those modules would therefore *add* history and
  context-builder output to prompts that have none — a wholesale prompt change,
  not the "zero behavior change" the step promises, and its own verify criterion
  (empty golden diff) would be unsatisfiable by construction.
- **Real duplication found in its place (the honest Step 6 target).** Step 5's
  synthesis repeated the web path's memory recall: both call
  `memory_service.search_memories(x, limit=3)`, but format it differently
  (web: `"\n\n[Memory Context]\n- item"`; synthesis: a labelled
  "background data, not instructions" block). Same data, different model input
  depending on endpoint. That divergence — not session/conversation — is what a
  facade should unify.

## 2026-09-29 — Migration Step 5 (HTTP path answers) + three red-test/infra fixes

- **Step 5**: new `app/adapters/http/synthesis.py` (`http_llm_enabled`,
  `synthesize_answer`), wired into `chat_completions` behind `JARVIS_HTTP_LLM`
  (default `0`). Flag off → response byte-identical to before (test-asserted);
  flag on → adds `response`/`model`/`tokens_used`/`memories_used`, or
  `synthesis_error` on any failure. Synthesis is **additive**: it never removes
  plan fields and never converts a successful plan into a 5xx. `docs/API_CONTRACT.md`
  §3.2 documents both shapes; flag in `docs/CONFIG.md` + `.env.example`.
  `tests/unit/test_http_synthesis.py` (19) + 3 contract tests.
- **Deviation found and recorded**: the plan specified `ModelRouter.generate`, but
  `ModelRouter` has **no registered providers outside unit tests** — zero non-test
  callers of `register_provider` in git history; `select_healthy_provider()` raises
  `RuntimeError` against a live boot (verified). `ResponseSynthesizer` is
  stream-only. Step 5 therefore uses `create_model_client` +
  `settings.get_default()`, the path the web console already runs in production.
  Wiring `ModelRouter` is now explicit unlisted prerequisite work.
- **Red suite cleared (3 → 0)**, each root-caused rather than silenced:
  1. `test_health_returns_200_and_shape` called `/health` and asserted
     `body["system"]`; the real route is `/api/v1/health` (router prefixed at
     `app/main.py:154`) returning `service` per `docs/API_CONTRACT.md` §3.1. Test
     corrected to the documented contract + a new no-auth assertion.
  2. `test_ready_returns_200_and_checks` called `GET /ready`, which **never
     existed** — no handler in `app/`, no trace in git history, despite
     `docs/SPRINT_1_2_COMPLETION.md:40` claiming it "verified live 200".
     Implemented for real (`GET /api/v1/ready`, `app/adapters/http/router.py:63-91`),
     so the sixteen assertions now cover shipped code. `/metrics` remains
     unimplemented and is now noted as such in the contract.
  3. `TestFileTools.test_read_nonexistent_allowed_file_returns_placeholder` read
     `docs/DEVLOG.md`; the allowlist holds `DEVLOG.md` at the repo root
     (`app/tools/file_tools.py:31-36`). Path corrected.
- **JVM-002 (critical) fixed**: `docker-compose.yml` shipped
  `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-jarvis_secret}` — a known superuser
  password whenever the var was unset. Now `${POSTGRES_PASSWORD:?...}` (fails
  closed; verified `docker compose config` refuses without it) and the port binds
  `127.0.0.1` instead of `0.0.0.0`. Documented in `.env.example`.
- **Step 4 latent bug fixed**: `_detect_domain` used substring matching, so
  `"api" ⊂ "capital"` classified "what is the capital of France" as *coding*.
  Word-boundary matching (`_keyword_hits`) fixes it and also removes an
  unreported `"season" ⊂ "soon"` → high-urgency false positive. Regression tests
  added; true positives verified intact.
- **Gates**: board review 10/10 green (`doc_drift` caught the undocumented
  `/ready` and was fixed by documenting it). `ruff check` + `ruff format --check`
  clean on all touched files; `mypy --strict` clean on all touched files
  (583 pre-existing errors elsewhere in `app/`, untouched). Full suite
  3 failed → **0 failed**.

## 2026-09-25 — Migration Steps 0+1: Baseline frozen, audit sink wired

- **Step 0 (baseline)**: HEAD `5de9c64`, tag `migration-baseline-20260925`,
  `docs/architecture/BASELINE.md` frozen (87% coverage floor, 10274 stmts / 1302 miss,
  pip freeze 218, orphan `.pyc` inventory, 4 known issues carried, not fixed this wave).
- **Step 1 (audit sink)**: new `app/security/audit_sink.py` (`AuditSink`, wildcard `"*"`
  subscription to `InMemoryAsyncBus`, redacted JSONL to `data/audit/YYYY-MM-DD.jsonl`,
  never raises); wired in `app/bootstrap.py` behind `JARVIS_AUDIT_SINK` (default `1`);
  `tests/unit/test_audit_sink.py` (4 tests). No request-path, contract, prompt, or config
  behavior changed.
- **Incidental docs-only fixes required by the repo's own gates**: `JARVIS_AUDIT_SINK` row
  in `docs/CONFIG.md` (env census), `test_count` 1717 → 1721 in `docs/FINAL_STATE.md`.
  Declined `scripts/sync_doc_facts.py --apply` full run — it rewrites 9 files including
  unrelated `gate_count` 26 → 27 drift; hand-applied only this wave's marker.
- **Left red (pre-existing, verified failing without this wave)**: 2 contract 404s
  (`test_health_returns_200_and_shape`, `test_ready_returns_200_and_checks`), 2 check_docs
  findings on prior-wave audit docs (`CURRENT-STATE.md` shorthand paths, `architecture`-type
  section rule on `CURRENT-STATE.md`/`MIGRATION-PLAN.md`). Fixing those is out of scope —
  flagging for the reviewer instead.
- **STOPPED** per plan. Step 2 (`web_search`) awaits review of the JSONL format.

## 2026-09-25 — Migration Step 2: web_search plugin (flagged OFF)

- New `app/tools/web_search_tool.py` (`SAFE`-tier Exa search, 500-char per-result cap,
  key redaction, errors-as-text); conditional registration in `DEFAULT_TOOLSET` behind
  `JARVIS_WEB_SEARCH` (default `0`, boot unchanged). `tests/unit/test_web_search_tool.py`
  (new tests). Docs-only: `JARVIS_WEB_SEARCH` in `.env.example` + `docs/CONFIG.md`,
  `EXA_API_KEY` row corrected, Step 2 marked done in `MIGRATION-PLAN.md`.
- **STOPPED** per plan. Step 3 (mode facade) not started.

## 2026-09-25 — Migration Step 2.5: contextvars correlation propagation

- New `app/telemetry/correlation.py` (stdlib-only leaf: contextvar + set/get/reset).
  `logging_middleware` sets/resets per request (`finally`-guarded); `publish_async`
  stamps the active ID onto events without one, explicit IDs preserved. Lazy import in
  `bus.py` — top-level would cycle via `telemetry/__init__` → `logger` → `events`.
  `tests/unit/test_correlation_propagation.py` (new tests). No middleware rewrite, no
  Event changes.   Audit-sink lines now carry real request IDs instead of `"none"`.
- **STOPPED** per plan. Step 3 (mode facade) not started.

## 2026-09-25 — Migration Step 3: mode facade, zero behavior change

- New `app/modes/` (`BaseMode` ABC + production/teacher/maintenance/evolution, all
  delegating to a shared default-prompt helper that renders through `ContextBuilder`
  for the default session) and `app/core/mode_manager.py` (default production,
  history, delegation). Wired as `container.mode_manager` in `app/bootstrap.py`;
  no LLM path calls it yet. Drift-freedom is test-asserted
  (`tests/unit/test_mode_system.py`, new tests).
- Governance catch: board review rejected the Step 2.5 bus import
  (`app.events` must stay standalone); fixed by canonicalizing the ContextVar in
  `app/events/correlation.py` and keeping `app/telemetry/correlation.py` as a
  re-export. Board now fully green.
- **STOPPED** per plan. LLM-path integration not started.

## 2026-09-25 — Migration Step 4: IntentAnalysis urgency/domain/action (additive)

- `app/domain/intent.py`: `urgency`/`domain`/`action` defaulted fields +
  `URGENCY_LEVELS`/`DOMAINS` constants (no validation yet). `app/brain/analyzer.py`:
  three keyword detectors, all four return sites populated, branch logic untouched.
  `tests/unit/test_intent_extensions.py` (new tests); `test_brain.py` green.
- Caution for Step 5: spec'd substring matching over-triggers ("capital" → coding).
  Left as specified; consumers must treat these as hints, not truth.
- **STOPPED** per plan. Planner/runner/mode/LLM integration not started.
