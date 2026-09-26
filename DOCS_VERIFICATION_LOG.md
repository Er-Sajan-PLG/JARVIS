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

## Stash-cycle incident — root cause and structural fix (review follow-up §2)

**What happened**: during scenario runs, probe content reappeared in
`app/tools/workspace_tools.py` (staged) after an explicit `git reset` +
`git checkout --` had verified it gone. Twice.

**Root-causing**: Layer-1 scripts were exonerated — `check-changed.py`,
`check-full.py`, and `generate.py --check` never write to the worktree (only
`generate.py --apply` writes, and no hook calls it). The mechanism was the
pre-commit framework's stash/pop cycle interacting with rapid interleaved
manual `git reset`/`git checkout` commands issued between hook runs while
earlier failed commits had left probe content staged: a `git checkout -- <f>`
restores worktree from the INDEX, and if the index still held probe content
from a previously failed (still-staged) commit, the "cleanup" restored the
probe instead of removing it. Operator sequencing error amplified by stash
noise — not a Layer-1 write bug (proven: Layer 1 has no write path).

**Structural hardening anyway** (so the class cannot bite real usage):
- R1 now most-specific-cover-wins (broad `[app/]` overviews warn; deepest match
  blocks) — the earlier over-match would have demanded staging four overviews
  per change.
- R5 (worktree fact re-check) REMOVED from Layer 1: with unstaged work stashed,
  any worktree read evaluates a Frankenstein tree. Layer 1 is now strictly
  index-based (staged snapshot + HEAD).
- New regression test `test_layer1_ignores_unstaged_worktree_noise`: unstaged
  worktree changes cannot alter Layer-1 output; the touched file is restored
  and the test asserts the tree is untouched afterward.

## Fact-sync stale-write — root cause and fix (review follow-up §1)

**Root cause**: `sync_doc_facts.py --apply --facts-json <cache>` (the exact
invocation in `githooks/pre-commit` step 3) loaded the injected JSON with NO
provenance check — unlike `_read_cache()`, which enforces commit equality.
A cache measured at an older commit (test_count 1694) was written into docs
while the suite collected a higher live total. Simultaneously, `collect_cheap()` reports a
SHORT commit while caches carry the FULL sha, so naive equality could never
match — fixed with prefix-either-way comparison.

**Fixes**:
- `reconcile_injected_facts()`: cheap facts always recomputed live; expensive
  facts (`test_count`, `coverage`) survive only on commit match, else
  `"unknown"` (apply skips, check reports cannot-verify instead of passing).
- F7 live cross-validation in `check-full.py` (cheap facts + `--collect-only`
  count vs every marker; coverage keeps its own live gate).
- Regression tests: stale snapshot rejected, current snapshot accepted,
  F7 pure-function catch/noise cases.
- **Single authoritative number** (the live `--collect-only` total at the time,
  deterministic). Every doc marker re-verified against it.

## Enforcement status: LOCAL-ONLY.

Server-side gate (`gate_docs_layer2` in CI) is implemented and dormant, pending
GitHub Actions billing re-enable + branch protection rule. Until both are
enabled, this system relies on every contributor having hooks installed; it is
not yet unbypassable at the repo level. Mitigations shipped in this branch:
`scripts/setup.sh` (hook installation is setup automation, verified exit 0),
CONTRIBUTING + DEVELOPMENT.md pointing at it, and the exact re-enable recipe
in `DOCS_SYSTEM_DESIGN.md` §7 (verified accurate: owner `Er-Sajan-PLG`,
repo `JARVIS`, context name matches the governance job).

## Review follow-ups — resolutions (2026-09-26, same branch)

- **Fact-sync (§1)**: fixed via `reconcile_injected_facts()` (provenance on the
  `--facts-json` path; cheap facts always live; expensive survives only on commit
  match) + F7 live cross-validation + 3 regression tests. Short/full commit
  mismatch found and fixed the same day (cheap=short vs cache=full sha).
  **Single authoritative number** (the live `--collect-only` total, re-verified
  at each run rather than quoted here).
- **Stash-cycle (§2)**: entry above; R1 specificity + R5 removal + regression test.
- **Orphan ratchet**: baseline pinned at **75** with review date **2027-01-15**;
  growth past baseline fails the build (`F6 orphan ratchet`).
- **Dead allowlist**: filed as issue **#107** (medium, code fix, docs untouched).
- **Scheduled sweep**: verified wired — cron `0 8 */15 * *` (active) →
  ci-bridge `/docs` → `scheduled_doc_maintenance.py` → auto-issue with
  `documentation, automation` labels.
- **Hook install**: `scripts/setup.sh` (exit 0, idempotent); DEVELOPMENT.md +
  CONTRIBUTING.md point at it. Gap closed: framework was unpinned and native
  hooks had no automated install.
- **ARCHITECTURE/ROADMAP prose**: medium edits, deferred to follow-up PR with
  owner input (sizing in final summary, not silently dropped).

## Lessons / follow-ups baked in during verification

1. R1 most-specific-cover-wins (broad overviews warn, deepest match blocks).
2. R5 demoted to warning: pre-commit evaluates a stashed Frankenstein tree and
   `sync --apply` is partial — hard enforcement stays at Layer 2 (real trees).
3. `sync --apply` (no `--run-tests`) writes a STALE `test_count`; hand-set from
   collection totals. 9 live `gate_count` markers hand-synced 26→28 the same way.
4. Framework stash-pop + interleaved manual `git reset` can resurrect probe
   content — verification hygiene: unscoped `git status` + file-tail checks
   between scenarios (used above).
