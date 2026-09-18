# ADR-017 — JARVIS orchestrates subagents; OpenCode first

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

- **Date**: 2026-09-18
- **Author**: JARVIS session (operator-approved gap analysis)
- **Related**: `app/brain/runner.py`, `app/tools/__init__.py`
  (`DEFAULT_TOOLSET`), `app/adapters/integrations/agy.py`,
  `docs/ROADMAP.md` (Sprint 8), `docs/ACCEPTED_RISKS.md`
- **Supersedes**: nothing. Companion to ADR-013 (JARVIS orchestrates,
  n8n executes): orchestration now extends to *agent harnesses*, not just
  workflows.

## Context

The 2026-09-18 comparison (DeepSeek harness, Hermes, OpenCode, AGY) found
JARVIS holds the best safety model (`@safety_gate` tiers + HITL) and the
richest personal context (memory, mail, phone, voice) but cannot delegate:
the brain executes only its own 14 tools. Meanwhile on the same machine sit
a coding-agent fleet (OpenCode, 25 subagents, JSON event streams), a
Google-brained CLI (AGY, half-wired adapter), a generalist (Hermes), and a
plugin harness (DeepSeek `dsh`). JARVIS should orchestrate them, not
reimplement them.

## Alternatives considered

- **AGY-first.** Rejected: single-vendor brain, no local subagent fleet,
  sessions need adapter work anyway. AGY stays a specialist (phase 3).
- **Hermes-first.** Rejected for v1: generalist overlap with JARVIS itself,
  less to gain per integration line than OpenCode's 25 coding subagents.
- **In-process-only tools (no subprocesses).** Rejected: reimplements what
  OpenCode/AGY already do; process isolation also bounds a rogue worker's
  blast radius better than in-process calls.
- **Do nothing (chat-only JARVIS).** Rejected by the operator: orchestration
  is the agreed direction.

## Decision

1. **Sub-agent runner v1, OpenCode first.** `spawn(agent, goal, dir)` shells
   `opencode run --format json --agent <sub>`, parses the event stream into
   a worker receipt (status, artifacts, follow-ups), threads `ses_*` for
   multi-turn workers. OpenCode first because the binary, auth, and
   subagents already exist locally.
2. **Delegation policy with caps** (depth ≤ 2, per-worker timeout, allowlisted
   agents), copied from Hermes' `delegate_task` limits. An agent spawning
   agents is how bills explode; the caps are load-bearing, not advisory.
3. **AGY adapter completion.** Thread `--conversation`, pass
   `--effort/--agent/--mode`, preserve history, refresh stale defaults, fix
   the fictitious `docs/modules/integrations/agy.md`.
4. **Worker HITL routing.** A spawned worker hitting DESTRUCTIVE pauses to
   the phone (notify + Telegram approve/deny), reusing the existing HITL
   registry.
5. **Deferred:** Hermes bridge (after v1 proves out), DeepSeek harness
   (only on a DeepSeek-specific workload), JARVIS-as-MCP-server (mesh
   phase — lets the others subcontract back).

## Consequences

### Positive

- Coding leverage without new models: OpenCode's planner/tdd/e2e agents
  become JARVIS skills; AGY covers Google-brained work.
- Safety composes: worker DESTRUCTIVE steps inherit the HITL gate instead
  of each harness's weaker local policy.

### Negative

- Shell-out orchestration is latency-heavy (process spawn + model think per
  worker); v1 suits background/delegated work, not interactive chat turns.
- Worker receipts must be validated — a subagent's JSON is untrusted input
  until parsed against the receipt schema.
- Hermes/deepseek paths stay manual until their phases; partial mesh in
  the meantime.

## Migration Plan

Sprint 8 implements phases 1–4 in order with tests + coverage per phase
(see `docs/ROADMAP.md` §9). No existing behavior changes: the runner gains
tools, nothing is removed or re-tiered.
