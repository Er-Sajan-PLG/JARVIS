# Docs System — Verification Log (Phase 4)

**Status**: ACTIVE
**Type**: snapshot
**Last Updated**: 2026-09-26
**Reviewed**: 2026-09-26
**Source**: live hook + gate runs on `verify/docs-system` (Phase 4)

**Date**: 2026-09-26 · **Branch**: `verify/docs-system` (throwaway; deleted after)
All scenarios ran against the real hooks (`githooks/pre-commit` + pre-commit
framework + `scripts/docs/`). No bypass flags used anywhere.

## Scenario 1 — code change without docs: BLOCKED pre-commit

Appended an undocumented `probe_new_capability()` to
`app/tools/workspace_tools.py`, staged only the code file, attempted
`feat(tools): probe capability without docs`. Result — commit refused:

```text
error: R1 co-change: app/tools/workspace_tools.py changes public surface
  (added probe_new_capability()) but mapped doc(s) not staged:
  app/tools/README.md, docs/CAPABILITY_TRACKER.md,
  docs/architecture/GAP-ANALYSIS.md, docs/architecture/MIGRATION-PLAN.md,
  docs/architecture/components.md, docs/modules/tools/workspace.md —
  stage the doc update too
error: R2 docstring: app/tools/workspace_tools.py:224
  functiondef probe_new_capability() has no docstring
check-changed: 3 error(s), 0 warning(s)
❌ pre-commit failed.
```

(R1 initially over-matched broad `[app/]` covers and was fixed same-session to
most-specific-wins with the rest as warnings — see §4 lessons.)

## Scenario 2 — doc-only breakage: BLOCKED pre-commit

Appended a link to a nonexistent page inside `docs/VOICE.md`, staged,
attempted `docs(voice): probe broken link`. Result — commit refused:

```text
error: R3 links: docs/VOICE.md links missing file: docs/NO_SUCH_PAGE.md
check-changed: 2 error(s), 0 warning(s)
```

## Scenario 3 — correct code+doc change: PASSES

Added documented `probe_mode_helper()` to `app/modes/production_mode.py`,
regenerated (`scripts/docs/generate.py --apply` updated `app/modes/README.md`),
staged code + generated README, attempted `feat(modes): probe documented
helper`. Result — **commit `ca65723` created** (R1 satisfied via the staged
generated README, R2 via the docstring, R3/R4 clean, R5 warning-only). Probe
reverted afterward; scratch branch deleted.

## CI-catch demonstration (bypass simulation)

With the VOICE.md breakage present in the worktree but uncommitted (what a
`--no-verify` bypass would leave behind), ran the exact Layer-2 entry the gate
uses:

```text
$ .venv/bin/python scripts/docs/check-full.py
error: F2 links: docs/VOICE.md links missing file: docs/NO_SUCH_PAGE.md
check-full: 1 error(s), 78 warning(s)
```

`gate_docs_layer2` fails on this output (verified gate wiring separately), so a
bypassed commit is caught at push/CI time. Restored afterward → 0 errors.

## Full Layer-2 + suite state at sign-off

- `check-full.py`: 0 errors, 78 warnings (all F6 orphan, v1-ratchet accepted).
- `manifest-validate.py`: 0 findings. `generate.py --check`: 0 diffs.
- `pytest tests/`: green except the 5 pre-existing/environmental failures
  documented in prior waves (2 contract 404s, 1 live-NVIDIA flake, 2 audit-doc
  prose findings); coverage above the 87% floor.
- `ruff check`, `ruff format --check`, `mypy --strict` (hook flag set): clean on
  all new scripts; board review 11/11.

## Lessons / follow-ups baked in during verification

1. R1 most-specific-cover-wins (broad overviews warn, deepest match blocks).
2. R5 demoted to warning: pre-commit evaluates a stashed Frankenstein tree and
   `sync --apply` is partial — hard enforcement stays at Layer 2 (real trees).
3. `sync --apply` (no `--run-tests`) writes a STALE `test_count`; hand-set from
   collection totals. 9 live `gate_count` markers hand-synced 26→28 the same way.
4. Framework stash-pop + interleaved manual `git reset` can resurrect probe
   content — verification hygiene: unscoped `git status` + file-tail checks
   between scenarios (used above).
