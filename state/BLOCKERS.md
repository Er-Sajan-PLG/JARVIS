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

---

## Adding a blocker

```markdown
## B-0NN — <one-line title>
**Severity**: HIGH|MEDIUM|LOW · **Status**: ACTIVE · **Blocks**: <task>
**What** / **Evidence** / **Remediation** / **Blocker owner**
```

Severity reflects **impact if ignored**, not effort to fix.
