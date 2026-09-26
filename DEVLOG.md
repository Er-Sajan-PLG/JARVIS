# JARVIS Development Log

**Status**: ACTIVE
**Type**: changelog
**Last Updated**: 2026-09-25

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
