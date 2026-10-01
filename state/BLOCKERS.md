# MACP BLOCKERS — JARVIS

Active blockers and dependencies. **Check this before starting work.** A blocked
task is not a task.

An entry is `ACTIVE` until explicitly cleared. Clearing requires evidence (a commit,
a command output), not an assertion — see `PROTOCOL.md` P5.

---

## B-001 — `external/Unlimited-OCR` gitlink, 94 MB, unreferenced

**Severity**: HIGH (clone cost) · **Status**: `CLEARED 2026-10-01` (`fbcbbdd`) · **Blocks**: nothing

**What**: `external/Unlimited-OCR` is a git submodule entry with **no
`.gitmodules` file**. It points at commit `026090f…` and reports `-dirty`
(modified submodule working tree), which makes `git status` perpetually unclean
and confuses agents and hooks alike.

**Evidence**: `git diff external/Unlimited-OCR` shows
`Subproject commit 026090f…` → `…-dirty`. No `.gitmodules` exists. No code path
imports it — it was the abandoned OCR backend superseded by Tesseract
(ADR-018, PR #134).

**Why it is HIGH despite being unused**: 94 MB on every clone, and the `-dirty`
marker means a clean tree is impossible to reach, which undermines the whole
"working tree is clean" startup check.

**Removal** (do this deliberately, in its own commit):
```bash
git rm --cached external/Unlimited-OCR
rm -rf external/Unlimited-OCR
# no .gitmodules to edit
git commit -m "chore(external): remove the unused Unlimited-OCR gitlink"
```

**Blocker owner**: unassigned.

---

## B-002 — Chroma FTS5 index is corrupt

**Severity**: HIGH · **Status**: `ACTIVE` · **Blocks**: Tier 4 memory work

**What**: The ChromaDB SQLite FTS5 index under `data/` is corrupt. Any memory
work that exercises the full-text index will fail or produce wrong results until
it is rebuilt.

**Consequence**: **Do not start Tier 4 memory work before rebuilding this.**
Work on the memory subsystem that does not touch FTS5 can proceed.

**Remediation**: rebuild the index from the vector store, or delete and re-ingest
`data/`. Back up `data/` first — it contains irreplaceable personal documents.

**Blocker owner**: unassigned.

---

## B-003 — Eight RED-class secret rotations outstanding

**Severity**: MEDIUM (security) · **Status**: `ACTIVE` · **Blocks**: nothing, but it is a live exposure

**What**: These were identified for rotation and have not been rotated:

`JARVIS_API_KEY` · Telegram bot token · Google API key · `JARVIS_MCP_KEY` ·
n8n HITL webhook · `N8N_LISTEN_ADDRESS` · default provider still `agy` ·
`JARVIS_BRIEF_DELIVERY=push`

**Note**: the repository is **public as of 2026-10-01**. Any credential that was
ever committed is now public. This raises the urgency of the rotation batch.

**Requires human action** — an agent cannot rotate a third-party credential.

**Blocker owner**: User.

---

## B-005 — `requirements.txt` was unsatisfiable and 36 versions adrift

**Severity**: HIGH · **Status**: `CLEARED 2026-10-01` (`7ba4b19`) · **Blocks**: every clean install, including CI

**What**: The dependency file did not resolve. Four independent defects:

| Defect | Evidence |
|---|---|
| `asyncpg==0.30.1` | PyPI returns **HTTP 404** — the version does not exist |
| `opentelemetry==1.44.0` | No bare `opentelemetry` package exists on PyPI at all |
| duplicated OpenTelemetry block | lines 165–168 repeated 81–84 |
| `pydantic_core==2.49.0` | `pydantic==2.13.5` requires `pydantic-core==2.46.5` |

Behind those: **36 versions disagreed with the environment the suite passes in**
(`mypy` 2.3.1 vs installed 1.11.2, `ruff` 0.16.8 vs 0.8.0, `numpy` 2.4.6 vs
1.26.4, `openai` 3.16.2 vs 3.11.0).

**Why it went unnoticed**: `pyproject.toml` declares **no dependencies**, so this
file was the only record — and nothing ever installed it. Dependabot bumped it for
months. A dependency file that is never installed cannot be wrong in any
observable way, which is exactly why it drifted this far. The local gate reuses an
existing `.venv` and never installs.

**Discovered by**: the `ci-gate` workflow's first run, which failed at
`pip install -r requirements.txt` after 16 seconds.

**Resolution**: regenerated from the working `.venv` via
`pip freeze --exclude-editable`, merged with the four optional dependencies that
environment lacked but the code uses (`tiktoken`, `psycopg`, `psycopg2-binary`,
`asyncpg`). 221 pins, verified with `pip install --dry-run`.

---

## B-006 — `osv-scanner` never installs in CI

**Severity**: LOW · **Status**: `ACTIVE` · **Blocks**: nothing (the check is non-blocking)

**What**: In CI the gate reports `osv  osv unavailable — not installed`, so the
OSV advisory scan is a *skip*. `install_ci_tools.sh` attempts
`pip install osv-scanner` into the tools venv as a final, non-fatal step; on the
runner it does not succeed.

**Why it matters anyway**: this is the same "skip looks like a pass" shape that
`--require-tools` was built to close — except OSV is deliberately non-blocking, so
the degradation is invisible rather than dangerous. It is still a check that does
nothing while appearing in the report.

**Remediation**: make the install fatal or use the `google/osv-scanner` binary
release, then decide whether the check should be blocking.

---

## B-004 — `setup-env` composite action is untested end-to-end

**Severity**: LOW · **Status**: `ACTIVE` · **Blocks**: nothing yet

**What**: `.github/actions/setup-env/action.yml` is used by three workflows, but no
workflow has ever executed it (the only Actions runs in this repo's history are
Dependabot's). Its correctness is therefore unverified.

**Risk**: the first real `ci-gate` run may fail for reasons unrelated to the code
under test — a wrong Python version, a missing cache key, or a dependency install
error.

**Remediation**: watch the first `ci-gate` run on a PR after the workflow lands on
`main`, and fix forward. This is expected first-run friction, not a defect.

---

## Cleared

| ID | Was | Cleared | Evidence |
|---|---|---|---|
| B-000 | Branch protection/rulesets returned HTTP 403 on a private Free repo (RISK-011, RISK-012) | 2026-10-01 | Repo made public; `GET /rulesets` → `200`, `GET /branches/main/protection` → `404 not protected`. Ruleset installed by `scripts/setup_branch_protection.py`. |
| B-001 | `external/Unlimited-OCR` broken gitlink (no `.gitmodules`), permanently dirty tree, 181 MB | 2026-10-01 | Untracked and gitignored in `fbcbbdd`. `git status` is now clean; local copy preserved. |
| B-005 | `requirements.txt` unsatisfiable: `asyncpg==0.30.1` (404), a phantom `opentelemetry` package, a duplicated OTel block, and 36 versions adrift | 2026-10-01 | Regenerated from the verified venv in `7ba4b19`; `pip install --dry-run` resolves. |

---

## Adding a blocker

```markdown
## B-0NN — <one-line title>
**Severity**: HIGH|MEDIUM|LOW · **Status**: ACTIVE · **Blocks**: <task>
**What** / **Evidence** / **Remediation** / **Blocker owner**
```

Severity reflects **impact if ignored**, not effort to fix.
