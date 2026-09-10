# ADR-011: Tool Wiring, the Destructive-Action Gate, and the HITL Trigger

**Status**: Accepted
**Date**: 2026-09-10
**Author**: Hermes (autonomous session; decisions reviewed with the user afterwards)
**Supersedes**: nothing
**Related**: ADR-006 (Pragmatic Hybrid), ADR-008 (Tiered Tool Safety Policy), RISK-014

## Context

`app/guardrails/` contained a complete Human-in-the-Loop approval mechanism
(`ApprovalRegistry`, `ToolSafetyPolicy`, `@safety_gate`, `/api/v1/hitl/*`) and it was
fully unit-tested — but it could never fire in the running system, for three independent
reasons:

1. `ExecutionRunner._tool_registry` was **never populated**. Nothing called
   `register_tool`, so `if tool_name in self._tool_registry` was always False and every
   step was marked `COMPLETED` without executing anything.
2. `TaskPlanner.create_plan` only ever emitted `SafetyTier.SAFE` steps (`read_file`,
   `list_dir`), so no DESTRUCTIVE step could exist to gate.
3. Nothing informed the automation plane (n8n) that a plan had paused. The
   `JARVIS-HITL` workflow was webhook-triggered, but no client code ever posted to that
   webhook, and its payload shape (`approval_id`/`tool`) did not match the API's real
   contract (`plan_id`/`step_id`).

A fourth latent defect: the planner asked for `list_dir` with
`arguments={"DirectoryPath": "."}` while the tool's parameter is `path`, so even a
registered tool would have failed on a keyword mismatch.

## Decision

1. **The composition root wires tools.** `app.tools` exposes `DEFAULT_TOOLSET`
   (name → callable) and `app.bootstrap` registers it on the `ExecutionRunner`. This is
   the composition root's job, and it is why `app.tools` is now an allowed dependency of
   `app.bootstrap` in `scripts/board/review.py` and `AGENTS.md`.
2. **A SAFE `list_dir` tool is registered** (bounded to 200 entries) because the planner
   already referenced it; its argument key is corrected to `path`.
3. **Destructive-intent routing lives in the planner.** `create_directory` is currently
   the only DESTRUCTIVE-tier tool, so it is the sole route into the gate. Routing is
   deliberately conservative: it requires BOTH a directory-creating verb
   ("create directory", "mkdir", …) AND a path-like token. An ambiguous prompt must never
   pause the loop or invent a filesystem target.
4. **n8n PULLS, it is not pushed to.** A Schedule Trigger polls
   `GET /api/v1/hitl/pending` (bearer-authenticated) every minute, then notifies Slack.
   There is no coupling from the app to n8n: the app needs no knowledge that n8n exists.
5. **Notification state is owned by the app, not n8n.** `POST /api/v1/hitl/notified`
   stamps `notified_at` on a pending approval (idempotent, first write wins).
   `GET /hitl/pending` returns it, and the poll filters on it, so each approval is
   announced exactly once.
6. **The decision comes back over a webhook.** n8n's `hitl/callback` webhook POSTs
   `{plan_id, step_id, decision, approver}` to `/api/v1/hitl/approve`, which resumes the
   plan.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Notify n8n from the app on pause (push) | Couples the app to the automation plane (the app would need an n8n URL and failure handling). Polling keeps the dependency one-directional and lets n8n be stopped without breaking the app. |
| Store notification dedupe in n8n workflow static data | Tried first. Does not persist in this n8n build — `workflow_entity.staticData` stayed NULL, so every tick re-notified. Also invisible to tests. |
| n8n Variables (the built-in key/value store) | Not writable from a Code node; needs an API key and extra moving parts for no gain. |
| Accept repeated notifications | Spams the channel every minute; unusable. |
| Route destructive intents via the LLM analyzer | The analyzer currently produces only complexity, not tool intent. Spawning an LLM call to decide "is this destructive" makes the gate non-deterministic — unacceptable for a safety control. Keyword routing is boring, testable and predictable. |

## Consequences

Positive: the gate is reachable and verified end-to-end (pause → Slack once → human
approve → tool executes). Dedupe state is testable and survives n8n restarts. The
app-to-n8n dependency is one-directional.

Negative / accepted: keyword routing is not semantic — a phrased request such as
"please make me a new folder for invoices" without a path token does not pause (it also
does not act, because no DESTRUCTIVE step is created). Only one DESTRUCTIVE tool exists,
so the gate's real coverage is narrow until more destructive tools are added.
