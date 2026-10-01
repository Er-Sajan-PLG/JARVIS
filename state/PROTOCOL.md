# MACP PROTOCOL — Amended (P1–P6 in force, P7 deferred)

**Status**: ACTIVE
**Type**: governance
**Source**: `state/` at HEAD
**Last Updated**: 2026-10-01

This repository operates under **MACP (Multi-Agent Coordination Protocol)**. This
file records the protocol **as amended on 2026-10-01**, so an agent that receives
only the original brief still follows the current rules.

**If this file conflicts with a brief you were given, this file wins.**

---

## 0. The unifying principle

The original protocol specified **actions** without **verifications**, which is why
records rot. Every amendment below closes a loop:

| # | Loop closed | Rule |
|---|---|---|
| P1 | Finalize claim ↔ actual stopping | Shutdown has a hard stop; new findings abort it |
| P2 | Shutdown summary ↔ repo reality | Terminal verification loop, max 3 iterations |
| P3 | COMPLETED status ↔ continued work | Re-open is an explicit, timestamped transition |
| P4 | Event occurrence ↔ file update | Every state file has a triggering event |
| P5 | Written claim ↔ reproducibility | No unverifiable assertions |
| P6 | Session file ↔ git truth | Record verification in Section 3 |

> **Every assertion needs a verifier. Every state needs a transition. Every file
> needs an owner.**

---

## P1 — Shutdown Step 0: stop working

Before writing the shutdown summary, **stop producing changes.**

Any of these **aborts shutdown** and returns you to work mode:

- a code change
- a config change
- a commit touching repo content
- a state-file change other than the session file being finalized

These do **not** abort shutdown:

- typo or formatting fixes **inside the session file currently being finalized**

**Cap: 3 shutdown restarts per session.** A fourth abort means something is wrong
with your definition of done. Halt, set outcome `BLOCKED`, and log `[NEEDS HUMAN]`
in `BLOCKERS.md`.

**Root cause, addressed directly:** declare completion only when every plan item is
checked **and** Section 3 validation passes. *User satisfaction is not a completion
signal.* "Are you done?" is a question, not a verdict.

**Interaction with P3:** a mid-shutdown abort is **not** a re-open. Re-open applies
only after a shutdown *completed* and REGISTRY shows `COMPLETED`.

---

## P2 — Terminal verification loop (max 3 iterations)

After the shutdown summary is written, re-read the record against reality:

```bash
git log <base>..HEAD --oneline    # every commit appears in the session file?
git status                        # clean, or the dirt is documented?
```

Then re-read `DASHBOARD.md` §Active Agents, `REGISTRY.md`, and your own summary.

Classify each discrepancy and act on the class:

| Class | Example | Action |
|---|---|---|
| **Record error** | Commit list missing a commit; status stale | Fix the record, re-verify |
| **Reality error** | Code or git state is actually wrong | This is a **bug in your work** → return to work mode → **P1 aborts shutdown** |

**Do not perform new work inside the loop.** The loop verifies; it does not build.

**Non-convergence:** if three iterations do not converge, set outcome to `PARTIAL`
or `BLOCKED` — **never `COMPLETED`** — and record it in `BLOCKERS.md`. A
non-converging loop means the session did not complete, whatever shipped.

**P2 requires P4.** Verification without ownership produces "found rot, don't know
whose job it is." They ship together.

---

## P3 — Re-open transition

`COMPLETED` is not terminal. It can be re-opened, but only explicitly:

1. Fetch and compare against the last session commit list. If the branch diverged,
   handle that first.
2. Set REGISTRY status back to `IN-PROGRESS`.
3. Add a dated header entry:
   `**Re-opened**: <UTC> — triggered by <what>; could not wait for a new session
   because <why>; delta from completed state: <what>`
4. **Re-execute the full shutdown** afterward.

**Re-open the same session** when: same objective, same calendar day, no other
agent worked in between.
**Start a new session** when: new objective, next day, or another agent's session
is interleaved.

Re-opened sessions carry non-linear timestamps; the header entry is what makes
that auditable rather than suspicious.

---

## P4 — State-file ownership (event → file)

An **event** is anything that would make an existing claim in a state file become
false or incomplete.

| Event | Files that MUST be updated |
|---|---|
| Structure change (module added/moved/removed, new package) | `ARCHITECTURE.md`, session |
| Dependency added/removed/upgraded | `ARCHITECTURE.md` §Data, `DEBT.md` if it carries risk, session |
| CI/CD, hook, or gate change | `ARCHITECTURE.md` §CI/CD, `DECISIONS.md` if it changes policy, session |
| Architectural decision | `DECISIONS.md`, and `docs/adr/` when it meets `AGENTS.md` §5.1 |
| New/changed risk | `docs/ACCEPTED_RISKS.md`, `BLOCKERS.md` if it blocks, session |
| Debt introduced or discovered | `DEBT.md`, session |
| Blocker hit or cleared | `BLOCKERS.md`, session |
| Test-suite restructure | `ARCHITECTURE.md`, session |
| Env var added/removed | `ARCHITECTURE.md`, `DEBT.md` if undocumented, session |

**All triggered files must be updated in the same session that produced the
event.** A partial update is a failed session, not a partial success.

**This table is incomplete by design.** When an event occurs that no row covers,
add the row as part of shutdown.

---

## P5 — Records must be reproducible, not asserted

> **Principle.** Any claim in a record must be either (a) a durable historical fact
> that cannot change, or (b) a current-state claim **paired with the command and
> timestamp that reproduce it**.

**Unverifiable assertions rot.**

Allowed:
- Action timestamps — "Commit `abc123` made at 15:30 UTC." (durable)
- Deltas and historical markers — "+30 tests this session", "at session start: 1100 passing."
- Verified current state with provenance — "Mypy: 504 errors — `mypy --strict app/`, run 2026-10-01."

Forbidden:
- Bare counts asserted as present truth — "We have 1130 passing tests."
- Bare state timestamps as freshness evidence with no verification context.
- Any number a reader cannot re-derive.

Note this is a **positive** requirement, not a ban. Citation is the fix; silence is
not compliance — vague prose that cannot be wrong is also useless.

---

## P6 — Record verification (Section 3 addition)

Before declaring ready to shut down, verify the **record**, not just the code:

- [ ] Every commit in `git log <base>..HEAD` appears in the session file
- [ ] REGISTRY statuses match session files
- [ ] No checked-off plan item for unfinished work
- [ ] Session header matches the REGISTRY row
- [ ] DASHBOARD §Active Agents matches REGISTRY

### Session file header schema (required)

Every session file MUST open with exactly this block:

```markdown
# Session <YYYYMMDD-HHMM>-<AGENT-ID>

**Agent**: <AGENT-ID>
**Type**: <model/tool>
**Branch**: <branch>
**Base commit**: <40-hex or short sha at session start>
**Started**: <UTC>
**Status**: IN-PROGRESS | COMPLETED | PARTIAL | BLOCKED | PIVOTED
**Claims**: <comma-separated paths>
```

These five fields — Agent, Branch, Base commit, Started, Status — **MUST** match
the agent's row in `REGISTRY.md`. Without the schema "matches REGISTRY" is
unenforceable, which is why the schema is part of the rule.

---

## P7 — Machine-checked drift: **DEFERRED**

Not adopted. Self-checking tooling encodes assumptions about a protocol that just
changed significantly. Shipping P1–P6, observing what still fails after 20+
sessions, then automating the **residual** failures produces a checker that catches
real problems rather than guesses.

If eventually implemented: a pre-commit hook must **warn, not block** (a blocking
hook trains `--no-verify`), CI blocks at merge, and it is a **completeness**
checker — "were the required files touched?" — never a correctness checker.

---

## Known gaps not yet addressed

Logged for the next amendment batch, not solved here:

1. **Context-window pressure degrades records first**, because record quality feels
   optional. There is no "stop and hand off" rule for a context-constrained agent.
2. **User-induced violation** ("just do X, skip the protocol") has no defined
   response. Silence means agents comply silently — the worst option.
3. **Protocol version drift**: if this file changes mid-session, the agent is
   operating under different rules than it started with. No rule covers it.
4. **The "boring update" skip**: small sessions skip state updates as
   disproportionate. Needs a minimum viable record for trivial changes.

---

## Quick reference — shutdown order

```
0. STOP WORKING                          (P1)
1. Finalize session file
2. Update REGISTRY (release claims)
3. Clean state/plans/
4. Add INDEX.md row
5. Git cleanup (clean tree, pushed)
6. Reconcile if last active agent
   -> TERMINAL VERIFICATION LOOP, max 3   (P2)
   -> converge, or outcome = PARTIAL/BLOCKED
```

Abort at any point before step 6 → back to work mode; a **fourth** abort halts.
