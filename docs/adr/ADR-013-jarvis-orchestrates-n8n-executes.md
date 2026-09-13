# ADR-013 — JARVIS orchestrates its own work; n8n is a workflow executor it drives


**Status**: ACTIVE
**Last Updated**: 2026-09-12
- Status: Accepted
- Date: 2026-09-12
- Related: ADR-011 (tool wiring + HITL gate), ADR-012 (GitHub identity per function),
  `docs/CI-GATE-SOTA.md`, `docs/N8N-SETUP.md`, `docs/GOVERNANCE.md`
- Supersedes the authority claim in `docs/GOVERNANCE.md` §3.1 ("n8n as Single Source
  of Automation Truth"), which described a topology this repository does not have.

## Context

The repository's governance documents described n8n as the single source of
automation truth, with named workflows (`JARVIS-CI`, `JARVIS-Deploy`,
`JARVIS-Dependabot`, `JARVIS-Security`, `JARVIS-Release`) performing the CI,
release, and security work. Measured on 2026-09-12, that is not what exists.

What actually exists:

| Thing | Reality |
|---|---|
| n8n workflows in the live DB | `JARVIS-CI-Local`, `JARVIS-HITL`, `JARVIS-Cleanup` — three, not seven |
| The CI decision | `scripts/ci_gate.py` — 22 checks against a detached worktree, publishing 8 commit-status contexts |
| Who invokes it | `scripts/ci_bridge.py`, reached over a localhost HTTP bridge |
| What n8n does for CI | schedules the poll; receives the result. It does not run the checks. |
| Branch protection | `GET /branches/main/protection` → **403** on this private free-tier repo (RISK-012) |
| Commit signing | last commits report `N`/`E`, not verified signatures (RISK-011) |

So the documents named an authority (n8n) that in practice makes no decisions,
and a set of workflows that do not exist. The question this ADR settles is the
one the drift exposed: **who is the top-level orchestrator — JARVIS, or n8n?**

## Decision

**JARVIS is the top-level orchestrator of its own work. n8n is a workflow
executor that JARVIS drives.**

JARVIS owns: intent → plan → execute → synthesize; the tool registry and the
`@safety_gate` policy that classifies tools; the HITL decision record; memory,
session, and workspace state; and the contract it must satisfy.

n8n owns: *when* scheduled work runs, and *how* the outside world is told about
it. It is a scheduler and a notifier — a durable, UI-ownable, restart-surviving
cron-with-an-inbox. It is not the policy engine and not the state store.

Where the two can disagree, **the repository's code and contracts win**: a
status posted by n8n is a claim about a gate result, and the gate result lives
in `scripts/ci_gate.py`.

## The boundary, stated as a rule

> If a decision is deterministic and belongs to JARVIS (auth, authorization,
> secrets, permissions, budget/token accounting, concurrency, retries, process
> management, deterministic state transitions, git operations, test execution,
> schema validation, logging, audit, safety), it is implemented in JARVIS code
> and merely *invoked* by n8n.
>
> If a decision is about durable workflow *sequencing* the owner wants to edit
> in a UI, survive restarts, branch on, or schedule — that is n8n's job, and
> JARVIS must not grow a second copy of it.

This is the same line drawn by the owner's Q1 answer: JARVIS is scoped to
itself — its own development and personal-AI-OS work — and does not become a
second n8n for ecosystem development. That keeps the
`docs/CAPABILITY-CONTRACT.md` §7 split intact (ecosystem-development
orchestration is unique to PROFESSOR-J; JARVIS is explicitly out of it), so no
cross-repo contract change is required.

## Why not "n8n is the authority"

The alternative reading — n8n decides, JARVIS obeys — fails on three measured
facts, not on taste:

1. **It has never been true.** The gate that decides CI is a Python file in this
   repository. n8n has only ever triggered it. Adopting n8n as authority would
   mean *building* a structure that does not exist, not describing one that does.
2. **It would put enforcement in a UI.** Branch protection is unavailable here
   (403), so the only thing standing between a red gate and `main` is that the
   pipeline stops and a human does not press merge. Moving the *decision* into
   n8n moves the last deterministic checkpoint into a mutable, hand-editable
   place — the opposite of the "deterministic enforcement" rule above.
3. **It contradicts the contract.** `CAPABILITY-CONTRACT.md` §7 lists
   ecosystem-development orchestration as unique to PROFESSOR-J. A JARVIS that
   orchestrates the ecosystem would need a cross-repo contract change and would
   duplicate a capability another repo already owns.

## Consequences

- **Good**: authority matches reality, so the docs stop describing a system
  nobody runs. n8n stays replaceable — it is a scheduler behind an HTTP bridge
  (`scripts/ci_bridge_server.py`), and swapping it out changes no policy.
- **Good**: the "don't build a second n8n" rule is now written down, which is
  what keeps JARVIS from re-implementing durable workflow state, retries, and
  scheduling internally.
- **Cost**: n8n can no longer be described as *the* automation plane. Its role
  shrinks in the documents to scheduling + notification + HITL fan-out, which is
  exactly the work it is doing today.
- **Follow-up**: `docs/GOVERNANCE.md` §3 and §4 were corrected in the same
  change to name the three real workflows and the real gate, because a governance
  document that asserts non-existent enforcement is a bug by the rule in
  `docs/README.md` ("if a document and the code disagree, the code wins").

## Alternatives rejected

- **Keep n8n as the declared single source of truth.** Rejected: it is
  aspirational prose about a system that was never built, and the gap between
  the claim and the reality is what let false "✅ enforced" rows survive
  review.
- **Promote `ci_gate.py` to a hosted GitHub Action so GitHub owns the
  authority.** Not available: Actions is billing-blocked on this private repo,
  which is the entire reason the local plane exists.
- **Give JARVIS its own embedded scheduler and drop n8n.** Rejected: that is
  precisely "become a second n8n". Durable scheduling with a UI the owner can
  edit is n8n's competence; JARVIS's competence is deciding what the work means.
- **Split authority by domain (n8n owns CI, JARVIS owns everything else).**
  Rejected as the same error at smaller scale: CI *is* JARVIS work — it runs
  this repository's gates against this repository's commits — so scheduling it
  elsewhere does not move the decision.

## The invariant any future change must preserve

**Enforcement stays in code JARVIS owns and can test; scheduling may live
outside it.** A change that makes a deterministic gate decision reachable only
by editing an n8n workflow — or by pressing a button in an n8n UI — has moved
enforcement out of code and into a UI, and must be rejected or recorded as an
accepted risk with an owner and a review date.
