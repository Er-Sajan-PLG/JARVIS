# Session 20261001-0500-MACP

**Agent**: MACP
**Type**: DeepSeek Harness agent (deepseek-v4.1-flash)
**Branch**: `test/assertion-defects`
**Base commit**: `629810dbb8e4e37738a2ab4d7d5fd262dd22892d`
**Started**: 2026-10-01T14:26Z
**Status**: IN-PROGRESS
**Claims**: `state/**`, `.github/**`, `scripts/ci_gate.py`, `scripts/setup_branch_protection.py`, `scripts/pin-actions.mjs`, `scripts/install_ci_tools.sh`, `tests/unit/test_gate_action_pinning.py`, `tests/unit/test_gate_require_tools.py`, `tests/unit/test_provenance_keyless.py`, `tests/unit/test_openrouter_max_tokens.py`

---

## Objective

Two objectives, deliberately sequenced by the user:

1. **Bootstrap MACP** in this repository (no `state/` existed), then adopt the
   reviewed amendments P1–P6 (P7 deferred).
2. **Continue the in-flight CI/CD enforcement work** under the protocol:
   GitHub Actions running the real gate, keyless provenance, SHA-pinned actions,
   and a `main` ruleset that makes a red PR unmergeable.

## Scope

**In**
- `state/**` bootstrap (all nine documents + dirs)
- `.github/workflows/ci-gate.yml`, deletion of the dead `ci.yml`, repair of
  `deploy.yml`
- `scripts/ci_gate.py`: `--require-tools`, `--keyless`, `gate_action_pinning`
- `scripts/setup_branch_protection.py`: rewrite for the ruleset API
- `scripts/pin-actions.mjs`, `scripts/install_ci_tools.sh`
- F-TEST-010 assertion fixes already staged on this branch

**Out**
- Wiring the four unreachable subsystems (separate objective)
- Rotating the eight RED-class secrets (requires human action — B-003)
- Rebuilding the Chroma FTS5 index (B-002)
- Machine-checked drift (P7, deferred)

---

## Running log

`14:26` [START] Bootstrap. Git reconnaissance: branch `test/assertion-defects`,
no upstream, 27 files changed (+684/−270), `state/` absent.

`14:28` [DISCOVERY] **The repository is now PUBLIC.** This invalidates the premise
of RISK-011/RISK-012 and `AGENTS.md` §4.3, all of which assert branch protection
is impossible (HTTP 403). Re-probed: `GET /rulesets` → `200`,
`GET /branches/main/protection` → `404 not protected`. Enforcement is possible
for the first time.

`14:30` [DISCOVERY] **The only Actions runs in this repo's history are Dependabot's.**
`ci.yml` had been disabled since 2026-09-10 and had **never run** — so its six job
names are checks that never report.

`14:33` [DISCOVERY] `scripts/setup_branch_protection.py` required those six
never-reporting contexts. Adopting it as-is would have made `main` **permanently
unmergeable**. A required check that never reports does not pass.

`14:36` [DISCOVERY] **A blocking gate whose scanner is missing reports `skip`.**
`Check.failed` is `status in ("fail","error")` and `blocking_failures` filters on
`failed`, so `_missing_tool(..., blocking=True)` contributed nothing. Proven:

```
blocking=True  status='skip'  failed=False  -> counts as blocking failure: False
```

In CI this means a required check going **green while enforcing nothing** — the
most dangerous possible failure, because it is indistinguishable from a real pass.

`14:40` [DECISION] Fix by flag, not by changing the default: `--require-tools`
makes a missing *blocking* tool a failure; local behaviour is unchanged.
Test-first: `tests/unit/test_gate_require_tools.py`, 4 RED → GREEN.

`14:44` [DECISION] Provenance becomes keyless in CI (`--keyless`), addressing the
fact that a runner cannot hold the developer's cosign key. Local keyed path kept.
Tested behaviourally with a **fake `cosign` on PATH that records its argv**, so the
test observes the real command rather than matching source text.

`14:48` [DISCOVERY] `cloudflare/pages-action@v1` **no longer exists** (HTTP 404) —
it is referenced by `deploy.yml`. Additionally `deploy.yml` called
`.venv/bin/pytest` without ever creating a `.venv`, and no `CLOUDFLARE_API_TOKEN`
or `CLOUDFLARE_ACCOUNT_ID` secret is configured (`gh secret list` shows only
`JULES_API_KEY`). Three docs nonetheless recorded Cloudflare deploy as **DONE**.

`14:52` [DISCOVERY] `scripts/pin-actions.mjs` — recommended by the repo's own
audit (SUP-010) and **never written**. Wrote it; pinned all third-party actions to
commit SHAs; added `gate_action_pinning` as a blocking gate so the pin cannot
silently decay.

`14:56` [PIVOT] **The user changed the protocol mid-task**, introducing amendments
P1–P6 (P7 deferred). Consequence for work already done: `DASHBOARD.md` and
`DEBT.md` violated **P5** by asserting volatile counts as present truth. Both were
rewritten to carry reproduction commands and verification timestamps.
`state/PROTOCOL.md` records the amended rules.

`15:00` [PROGRESS] Bootstrap files written: `DASHBOARD.md`, `REGISTRY.md`,
`INDEX.md`, `ARCHITECTURE.md`, `DECISIONS.md` (ADR-001…ADR-005), `DEBT.md`
(D-001…D-010), `BLOCKERS.md` (B-001…B-004), `PROTOCOL.md`, and the
`sessions/ plans/ conflicts/ archive/` directories.

`15:04` [DISCOVERY] **P6-catch**: the amendments require a session-header schema,
which the original brief only implied. Adopted as five required fields
(Agent, Branch, Base commit, Started, Status) that must match `REGISTRY.md`.

`15:10` [PROGRESS] Commit history rebuilt. The first attempt produced a 28-file
mega-commit: `git add` was run with an explicit file list, but the index still
carried 26 files staged from an earlier `git add .github/ ... docs/`, so `git
commit` swept them all in. Caught it by inspecting `git show --name-status`, reset
to the session base (`git reset --mixed 629810d`), and replayed as eight focused
commits — `git restore --staged .` before every `git add`. Each commit is now
under the AGENTS.md §11 500-line threshold; the largest is 310 lines.

`15:14` [SCOPE EXPANSION] Fixed `external/Unlimited-OCR` (B-001), which was outside
the plan. Justification: the gitlink had no `.gitmodules` mapping, so
`git submodule status` failed outright and `git status` reported `-dirty` on every
run. That made a clean working tree unreachable, and MACP shutdown requires one —
an invariant that is always violated carries no information, and a real stray edit
could hide behind it. Fix was the minimal reversible form: `git rm --cached` plus a
`.gitignore` entry. The 181 MB local copy is untouched; no `app/` module imports it.

`15:16` [DISCOVERY] The history rebuild also proved the gate changes were
correctly separated: `diff /tmp/ci_gate.final.py scripts/ci_gate.py` is empty after
re-applying the three features one commit at a time, so the split lost nothing.

`15:18` [PROGRESS] `state/` preparation for shutdown. B-001 cleared; DASHBOARD §5
rewritten; session log and commit table added.

`15:20` [PROGRESS] Section 3 validation, first pass. Full suite 2143 passed; docs
clean; board 11/11. But the **gate itself FAILED with 2 blocking failures**:
`ruff_ratchet` and `trivy`.

`15:22` [DISCOVERY] `ruff_ratchet` reported "**12** changed file(s) with lint
errors". Only **1** file actually had errors (`tests/unit/test_issues.py`, 13
pre-existing violations). The summary used `len(changed)` -- the list of files
*passed to ruff* -- not the files that failed. Eleven clean files were named as
violation sites. Fixed in `59fd80c`, test-first, with a helper that parses ruff's
diagnostics and deduplicates by filename.

`15:24` [DISCOVERY] `tests/unit/test_issues.py` had **14 ruff errors at the base
commit** and 13 after my change, so I did not introduce them. But the ratchet
enforces *changed* files, so touching it made them blocking. Consolidated the
scattered imports in `fd76cbb`. I briefly added an import I had invented
(`app.workspace.git_state`); caught it on the next command and removed it before
it reached a commit.

`15:26` [SECURITY] `trivy` reported two HIGH findings against `urllib3==2.7.0`:
CVE-2026-97687 and CVE-2026-97689, **both fixed in 2.8.0**. `requirements.txt` was
not touched by this session, so these are newly-published advisories rather than
introduced regressions.

`15:28` [DECISION] Bumped urllib3 to 2.8.0 (`0ec6128`) rather than exempting it.
The user's standing rule is that a gate failure needs a *genuine* exception, and an
available fix is not one -- exempting a patchable HIGH advisory would leave the
hole open behind a green gate. Verified safe: 2147 passed, 3 skipped, 1 xfailed.

`15:30` [SCOPE EXPANSION] The urllib3 bump is a dependency change in a session
scoped to CI/CD enforcement. Justification: it blocked the merge, the fix is a
transitive patch bump with no API change, and the alternative (an ACCEPTED_RISKS
entry) would be dishonest. Logged rather than done silently.

`15:32` [PROGRESS] Gate re-run in flight to confirm both blocking failures cleared.

`15:36` [PROGRESS] PR #142 opened. The `ci-gate` workflow ran on it and **FAILED in
22 seconds** -- far too fast to be the gate, so it was a setup failure.

`15:38` [DISCOVERY] **`requirements.txt` does not install.** `pip install -r
requirements.txt` fails with `No matching distribution found for asyncpg==0.30.1`.
Verified independently: PyPI returns **HTTP 404** for that version. The local gate
never caught this because it reuses an existing `.venv` and never installs.

`15:40` [DISCOVERY] Chasing that revealed three more defects and then the real
problem. A bare `opentelemetry==1.44.0` **is not a package on PyPI at all**; the
OpenTelemetry block was **duplicated**; `pydantic_core==2.49.0` conflicts with
`pydantic==2.13.5`, which requires `2.46.5`. And behind all of it: **36 pins
disagreed with the environment the suite passes in** -- `mypy` 2.3.1 vs 1.11.2,
`ruff` 0.16.8 vs 0.8.0, `numpy` 2.4.6 vs 1.26.4.

`15:42` [DECISION] The root cause is structural, so the fix had to be too.
`pyproject.toml` declares **no dependencies**; `requirements.txt` was the only
record and **nothing ever installed it**. Dependabot bumped it for months against
no feedback loop. Regenerated from the verified `.venv`
(`pip freeze --exclude-editable`), merged with the four optional deps that
environment lacked but the code uses (`tiktoken`, `psycopg`, `psycopg2-binary`,
`asyncpg`) -- a pure freeze would have silently dropped them. 221 pins; verified
by `pip install --dry-run`.

`15:44` [SCOPE EXPANSION] Regenerating the dependency file is well outside a CI/CD
enforcement session. Justification: the workflow cannot install without it, so
without this the entire PR fails at its purpose; the fix is mechanical and
verified; and the alternative -- exempting a HIGH-severity finding -- was not
genuine.

`15:46` [PROGRESS] Pushed `7ba4b19`; the workflow re-triggered. Watching.

`15:50` [PROGRESS] CI iteration 1: failed at `pip install` (asyncpg 0.30.1). Fixed by
regenerating requirements.txt.

`15:55` [PROGRESS] CI iteration 2: failed in "Install gate scanners" -- 4 of 11 tools
missing. All four were bugs in `scripts/install_ci_tools.sh`: gitleaks assets are
`_linux_x64` not `_linux_amd64`; hadolint's is `hadolint-linux-x86_64` not
`Linux-x86_64`; semgrep and cyclonedx live in the tools venv which was not on
PATH; and cyclonedx's binary is `cyclonedx-py`. The failure itself was the system
working -- `--require-tools` turned 4 missing blocking scanners into a hard
failure instead of 4 silent skips.

`16:00` [PROGRESS] CI iteration 3: the gate ran end to end for the first time.
**22 pytest failures**, plus trivy 3, plus provenance. 0 failures locally, which
was the point: the runner is a clean environment and the local venv is not.

`16:05` [DISCOVERY] Root cause of most of the 22: installing `tiktoken` -- which
`requirements.txt` pins and the venv lacked -- broke three tests that asserted
`_try_tiktoken(...) is None` and a fallback token count. They asserted an
ENVIRONMENT property. One docstring even said so: "tiktoken is pinned in
requirements.txt but is NOT installed in this environment". Absence is now forced
by patching `__import__`; the truncation test uses a history large enough to
exceed the floor under either counter. Verified both ways: 42 passed with and
without tiktoken.

`16:10` [DISCOVERY] `test_subagent_tools.py` (3 tests) failed for a different
environmental reason: `OPENCODE_BIN` is resolved with `shutil.which` at MODULE
IMPORT, so a runner without the `opencode` CLI raises before the patched
subprocess is reached. The developer machine has opencode.

`16:12` [DISCOVERY] `test_chat_uses_default_model.py` called `/api/chat` for real
and accepted "either the real call succeeds, or it fails for a reason unrelated to
an empty model id". On CI the handler returned 503 "AGY CLI not found on PATH"
before the model id was used. A test that passes for two unrelated reasons asserts
neither. Now stubbed at the provider boundary; verified by mutation -- ignoring the
saved default fails it.

`16:15` [PROGRESS] CI iteration 4: pytest **1 failed** (down from 22), trivy PASS,
provenance PASS (keyless works, identity regexp correct). The one failure was
`test_doc_facts` -- my own staging error: I ran `sync_doc_facts` but staged only
the test files, leaving the synced doc changes uncommitted.

`16:18` [PROGRESS] CI iteration 5 in flight.

---

## Commits

All on `test/assertion-defects`, from base `629810d`:

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
| `fc00b61` | chore(state): bootstrap MACP protocol with repository audit |
| `59fd80c` | fix(ci): name the files that fail the ruff ratchet, not the files it checked |
| `fd76cbb` | style(test): consolidate test_issues.py imports so the ratchet passes |
| `0ec6128` | fix(deps): bump urllib3 2.7.0 -> 2.8.0 for CVE-2026-97687 and CVE-2026-97689 |
| `b85ee5d` | chore(state): record the verification round and its three fixes |
| `7ba4b19` | fix(deps): regenerate requirements.txt so it actually installs |
| `9829b61` | fix(ci): correct the scanner installer's asset names and verify path |
| `5e74103` | test: stop three tests depending on which token counter is installed |
| `a924a5d` | fix(ci): pin the keyless provenance identity by regexp, not by literal |
| `f17640e` | fix(ci): install tesseract and poppler on the runner |
| `44526db` | test: stop two more tests depending on the machine they run on |
| `8d9397b` | fix(deps): bump virtualenv 21.7.9 -> 21.7.13 |

---

## Decisions

Recorded as ADR-001…ADR-005 in `state/DECISIONS.md`:

| ADR | Decision |
|---|---|
| 001 | One gate definition, two runners; `ci.yml` deleted, not re-enabled |
| 002 | A missing blocking scanner fails the gate (`--require-tools`) |
| 003 | Provenance is keyless in CI; local keyed path retained |
| 004 | Actions pinned by SHA, enforced by a blocking gate |
| 005 | Bootstrap with the tree dirty and document it, rather than hide it |

---

## Discoveries not yet acted on

| # | Finding | Where recorded |
|---|---|---|
| 1 | `external/Unlimited-OCR` — 94 MB gitlink, no `.gitmodules`, unused | `BLOCKERS.md` B-001 |
| 2 | Chroma FTS5 index corrupt; blocks Tier 4 memory work | `BLOCKERS.md` B-002 |
| 3 | Eight RED-class secrets unrotated, now that the repo is public | `BLOCKERS.md` B-003 |
| 4 | `setup-env` composite action has never executed | `BLOCKERS.md` B-004 |
| 5 | `docs/snippets/` absent — fenced blocks only `compile()`-checked | `DEBT.md` D-003 |
| 6 | Whole-tree ruff debt: 85 errors, 40 files unformatted | `DEBT.md` D-005 |
| 7 | Coverage gate is opt-in *and* non-blocking | `DEBT.md` D-007 |
| 8 | `pyproject.toml` ruff settings emit deprecation warnings every run | `DEBT.md` D-009 |

---

## Verification performed

| Check | Command | Result |
|---|---|---|
| Full suite | `.venv/bin/python -m pytest tests/ -q` | 2142 passed, 3 skipped, 1 xfailed, 0 failed |
| Doc structure | `.venv/bin/python scripts/check_docs.py --strict` | clean (99 files) |
| Doc consistency | `.venv/bin/python scripts/sync_doc_facts.py --sync` | clean |
| Governance | `.venv/bin/python scripts/board/review.py` | 11/11 pass |
| New gate tests | `pytest tests/unit/test_gate_*.py tests/unit/test_provenance_keyless.py` | 31 passed |
| Mutation: `DEFAULT_MAX_TOKENS = 1` | — | killed (was passing before the fix) |
| Mutation: blind `kwargs["max_tokens"] =` | — | killed |
| Mutation: rename the MCP server | — | killed |
| Mutation: `get_global_policy` returns a fresh object | — | killed |
| Action pinning | `node scripts/pin-actions.mjs --check` | OK — all pinned |

All counts above are `VERIFIED` at 2026-10-01 (P5: re-run to reconfirm).

---

## Handoff notes for the next agent

1. **The ruleset is not yet installed.** `scripts/setup_branch_protection.py
   --dry-run` is verified; the live install must happen *after* `ci-gate.yml` is
   on `main`, or the required check will never report and `main` will be blocked
   forever. **This ordering is load-bearing.**
2. **Never merge with `--merge`** once the ruleset is live — linear history is
   enforced. Use `gh pr merge --squash`.
3. **`main` is currently unprotected.** Until the ruleset lands, this branch and
   any other can push directly.
4. **Read `PROTOCOL.md` before shutting down.** P1/P2/P3 change shutdown, and P2
   forbids doing new work inside the verification loop.
5. `.github/workflows/ci.yml` is **deleted**, not disabled. Do not restore it —
   two gates with different definitions of green is the failure this removed.
