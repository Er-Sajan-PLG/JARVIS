# MACP DASHBOARD — JARVIS

**Last Reconciled**: 2026-10-01T05:00Z
**Reconciled by**: MACP (bootstrap audit)
**Freshness rule (P5)**: this stamp is freshness *evidence* only. It is valid only
when nothing has been committed since. Check with
`git log --oneline -1 --since="2026-10-01T05:00Z"` before trusting any count below.

**Protocol**: see `PROTOCOL.md` (amended P1–P6). Read it before shutting down.

---

## 1. Project Snapshot

**JARVIS** — a personal AI assistant: FastAPI backend, LangGraph-driven agent
runtime, hybrid memory (BM25 + ChromaDB), multi-provider model routing, a
Telegram integration, and an OCR pipeline backed by Tesseract.

Per **P5**, numbers below carry the command that reproduces them. Anything that
can change is written as *verified-at*, never as standing truth. Re-run before
trusting.

| Field | Value | Reproduce with | Verified |
|---|---|---|---|
| Repository | `Er-Sajan-PLG/JARVIS` — **PUBLIC** | `gh repo view --json visibility` | 2026-10-01 |
| Default branch | `main` | `gh repo view --json defaultBranchRef` | 2026-10-01 |
| Interpreter | `.venv/bin/python` is **3.11.16**; system `python3` is 3.14.7 — **always use `.venv/bin/python`** | `.venv/bin/python --version` | 2026-10-01 |
| Test suite | 2142 passed, 3 skipped, 1 xfailed, 0 failed | `.venv/bin/python -m pytest tests/ -q` (~120 s) | 2026-10-01 |
| Coverage | 86% line+branch, floor 80% — **opt-in and non-blocking** (DEBT D-007) | `ci_gate.py --with-coverage` | 2026-10-01 |
| mypy --strict | 504 errors in 86 files — the ratchet ceiling, ⚠️ **may have moved; re-measure** | `.venv/bin/mypy --strict app/` | 2026-10-01 |
| Lint | ruff clean on *changed* files only; whole-tree debt ratcheted (D-005) | `scripts/lint_changed.sh` | 2026-10-01 |
| Docs | 99 markdown files scanned, clean | `.venv/bin/python scripts/check_docs.py --strict` | 2026-10-01 |
| ADRs | 19 | `git ls-files 'docs/adr/*.md' \| wc -l` | 2026-10-01 |
| Risk register | 24 entries | `grep -c '^\| RISK-' docs/ACCEPTED_RISKS.md` | 2026-10-01 |
| CI gate | 29 checks | `grep -c 'def gate_' scripts/ci_gate.py` | 2026-10-01 |
| Governance | 11/11 checks pass | `.venv/bin/python scripts/board/review.py` | 2026-10-01 |

**Durable facts** (cannot change, need no reproduction):
`Er-Sajan-PLG/JARVIS` became public on 2026-10-01; that is what removed the HTTP
403 walls on branch protection and rulesets. The four unreachable subsystems and
the `external/Unlimited-OCR` gitlink are structural, not counts.

---

## 2. What Changed Most Recently

The repository was made **public** on 2026-10-01. This is the single
highest-impact change in this window, because it dissolved the constraint that
shaped the entire CI story:

| | Private (before) | Public (now) |
|---|---|---|
| `GET /branches/main/protection` | **403** "Upgrade to GitHub Pro" | **404 not protected** → settable |
| `GET /repos/.../rulesets` | **403** | **200** |
| Actions minutes | billing-blocked; runs died in ~5 s | **unlimited** (free on public repos) |
| Workflows ever run | — | **Dependabot only** |

Enforcement was *process, not policy* (RISK-011, RISK-012). It is now policy.

In-flight on branch `test/assertion-defects` (uncommitted at reconciliation —
see §5): GitHub Actions enforcement (`ci-gate.yml` running the local gate),
keyless provenance, action SHA pinning, the `main` ruleset, and a batch of
F-TEST-010 assertion fixes.

---

## 3. Active Agents

| Agent | Status | Branch | Owns |
|---|---|---|---|
| `MACP` | **ACTIVE** | `test/assertion-defects` | bootstrap `state/`; `scripts/ci_gate.py`, `scripts/setup_branch_protection.py`, `scripts/pin-actions.mjs`, `scripts/install_ci_tools.sh`, `.github/**`, `tests/unit/test_gate_*.py`, `tests/unit/test_provenance_keyless.py` |

No other agents are active. See `REGISTRY.md`.

---

## 4. Critical Alerts

| # | Severity | Alert | Where |
|---|---|---|---|
| 1 | **HIGH** | `external/Unlimited-OCR` is a 94 MB gitlink with no `.gitmodules`, unused by any code path | `BLOCKERS.md` B-001 |
| 2 | **HIGH** | Chroma FTS5 index is corrupt — Tier 4 memory work must not start first | `BLOCKERS.md` B-002 |
| 3 | **MEDIUM** | 8 RED-class secrets/rotations outstanding (Telegram token, Google key, n8n webhook, `N8N_LISTEN_ADDRESS`, …) | `BLOCKERS.md` B-003 |
| 4 | **MEDIUM** | `mypy --strict` ceiling 504 (verified 2026-10-01); no burn-down plan scheduled | `DEBT.md` D-001 |
| 5 | **MEDIUM** | ~519 mocks without `spec=` (0 `create_autospec`); ~122 stand in for JARVIS classes — approximate, recount before relying on it | `DEBT.md` D-002 |
| 6 | **LOW** | `docs/snippets/` does not exist (structural, not a count) — fenced markdown blocks are `compile()`-checked, never executed | `DEBT.md` D-003 |

---

## 5. Working Tree At Reconciliation

**Clean.** `git status --short` reports nothing tracked-and-modified.

The bootstrap began with 27 uncommitted files, which is why §5 originally recorded
a dirty tree: the protocol was requested mid-task, and the honest option was to
document the in-flight work rather than stash it to satisfy a checklist (ADR-005).
That work has now been committed as eight focused commits, each under the §11
500-line threshold:

| Commit | Subject |
|---|---|
| `c87bb4a` | test: repair assertions that could not fail |
| `39a5859` | feat(ci): fail the gate when a blocking scanner is missing |
| `c5ab3a0` | feat(ci): sign provenance keylessly in CI |
| `203d1a9` | feat(ci): pin actions to commit SHAs and enforce it in the gate |
| `0652d1a` | feat(ci): run the real gate in GitHub Actions |
| `e5570ea` | fix(ci): install a ruleset instead of requiring six phantom checks |
| `ccb685f` | docs: correct every claim that enforcement is impossible |
| `fbcbbdd` | chore(external): untrack the broken Unlimited-OCR gitlink |

`external/Unlimited-OCR` was untracked rather than deleted — it produced
`-dirty` on every `git status` with no `.gitmodules` mapping, making a clean tree
unreachable; the 181 MB local copy is untouched.

## 6. Recently Completed (this window)

| PR | Commit | What |
|---|---|---|
| #134 | `432ff09` | OCR: English-only Tesseract, two dead backends removed |
| #135 | `204ad11` | `@runtime_checkable` on the last two Protocols |
| #136 | `949b94f` | Dead-code register for four unreachable subsystems |
| #139 | `94069f7` | Branch coverage measured; coverage docstring can no longer drift |
| #140 | `1f38ab6` | Two security guards now fail when the guarded thing is deleted |
| #141 | `629810d` | Pre-push hook runs the whole suite (was 2011 of 2128 tests) |

---

## 7. Where To Start

1. Read `REGISTRY.md` — claim your files before editing.
2. Read `BLOCKERS.md` — do not start blocked work.
3. If touching CI, read `ARCHITECTURE.md` §CI/CD and `DECISIONS.md` ADR-001.
4. The in-flight work must be finished and merged before anything else touches
   `scripts/ci_gate.py` or `.github/`.
