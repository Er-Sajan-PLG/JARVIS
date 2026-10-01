# Plan — agent-MACP — CI/CD platform enforcement

**Agent**: MACP · **Branch**: `test/assertion-defects` · **Created**: 2026-10-01
**Status**: IN-PROGRESS

---

## Objective

Make CI/CD enforcement **real** rather than procedural. Before this work, the
repository had a 29-check local gate that no one was required to pass: branch
protection returned HTTP 403 (private Free repo), so RISK-012 recorded that the
gate "cannot make a PR unmergeable on GitHub."

The repository became public on 2026-10-01, which makes enforcement possible for
the first time. This plan installs it.

## Success criteria

1. GitHub Actions runs the **same** `scripts/ci_gate.py` a developer runs.
2. The gate cannot go green with a missing blocking scanner.
3. Every third-party action is pinned to a commit SHA, and a new unpinned one
   fails the gate.
4. A ruleset on `main` requires the `ci-gate` check, signed commits, linear
   history, and rejects force-push/deletion.
5. The repo's own documentation stops asserting the opposite (AGENTS.md §4.3,
   RISK-011, RISK-012, three Cloudflare claims).

## Approach

| # | Step | Status |
|---|---|---|
| 1 | Add `--require-tools` so a missing blocking scanner fails | done |
| 2 | Add `--keyless` provenance (Fulcio + Rekor, identity-pinned verify) | done |
| 3 | Write `scripts/pin-actions.mjs`; pin all actions | done |
| 4 | Add `gate_action_pinning` as a blocking gate | done |
| 5 | Write `scripts/install_ci_tools.sh` (one installer, local + CI) | done |
| 6 | Write `.github/workflows/ci-gate.yml`; delete dead `ci.yml` | done |
| 7 | Repair `deploy.yml` (dead action, missing venv) | done |
| 8 | Rewrite `setup_branch_protection.py` for the ruleset API | done |
| 9 | Correct the docs that assert the old state | done |
| 10 | Full verification + commit + gate + push + PR | in progress |
| 11 | **Install the ruleset — only after `ci-gate.yml` is on `main`** | pending |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Required check never reports → `main` unmergeable forever | Install the ruleset **after** the workflow is on `main` and has run once. The old script made exactly this mistake with six never-reporting contexts. |
| CI fails on first run for setup reasons, not code reasons | Expected friction; `BLOCKERS.md` B-004 records it as first-run, fix-forward. |
| Linear history breaks the existing `--merge` habit | Documented in `AGENTS.md` §4.3 and the session handoff: use `--squash`. |
| Keyless signing silently degrades to a skip if `id-token: write` is dropped | The permission is in the workflow with a comment explaining that removing it converts provenance to a skip. |
| Two gates diverge again | `ci.yml` deleted; `ci-gate.yml` calls `ci_gate.py` rather than reimplementing it. |

## Rollback

Each step is independently revertible:

- **Workflow**: delete `.github/workflows/ci-gate.yml`. No other file depends on it.
- **Ruleset**: `gh api -X DELETE repos/Er-Sajan-PLG/JARVIS/rulesets/<id>`, or set
  `enforcement: "disabled"` in the payload.
- **Gate flags**: `--require-tools` and `--keyless` default to `False`; omitting
  them restores prior behaviour exactly.
- **Pinning**: `git revert` the pin commit; the gate check can be dropped
  independently of the pins themselves.
- **`ci.yml`**: recoverable from git history at `629810d`.

Nothing here is a one-way door.

## Consistency check

This plan touches the following state files (P4 ownership; all updated):

| Event | Files |
|---|---|
| CI/CD + gate change | `ARCHITECTURE.md` §CI/CD, `DECISIONS.md` ADR-001…004, session |
| New gate checks (2) | `DASHBOARD.md` (gate count), `DEBT.md` (D-R5, D-R6 resolved) |
| Risk changes | `docs/ACCEPTED_RISKS.md` (RISK-009/011/012), `BLOCKERS.md` (B-000 cleared) |
| New blockers | `BLOCKERS.md` B-001…B-004 |
