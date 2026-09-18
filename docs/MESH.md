# Sub-agents, AGY and MCP mesh

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-19
**Source**: `app/integrations/mcp/server.py`, `app/tools/subagent_tools.py`, `app/adapters/integrations/agy.py` at HEAD

> Drift trap for this type: The fastest-rotting type. Every default, field and endpoint is duplicated from code, so every code change makes it stale.

---

## Overview

JARVIS orchestrates a fleet instead of reimplementing it (ADR-017). Three
surfaces make that real:

1. **Sub-agent workers** — JARVIS spawns OpenCode workers via `spawn_subagent`.
2. **AGY** — a Google-brained CLI, threaded and stateful through the adapter.
3. **MCP mesh** — JARVIS itself exposes tools over MCP so other agents
   (PROFESSOR-J, OpenCode, Hermes) can call JARVIS back.

---

## 1. Sub-agent workers (`app/tools/subagent_tools.py`)

Tool: `spawn_subagent(goal, agent, model, workdir, session_id, timeout_s)`.

- Shells `opencode run --format json` and folds the event stream into a
  worker receipt: `status` (`ok|error|timeout`), `session_id`, `summary`,
  `tokens`, `cost`, `error`.
- Tier SENSITIVE (not DESTRUCTIVE): spawning stays usable without a phone
  approval per worker; the worker's own destructive acts stay inside its
  subprocess permissions.
- Policy caps, enforced from day one:

| Cap | Value | Env |
|---|---|---|
| Allowlisted agents | `build,plan,general` | `JARVIS_SUBAGENTS` |
| Per-spawn timeout | 600 s, kill on expiry | via `timeout_s` arg |
| Workdir jail | workspace root or system temp only | `_resolve_workdir` |
| Output cap | 20 000 chars | `MAX_OUTPUT_CHARS` |

Default model: **Muse Spark 1.3 Free** (`opencode/muse-spark-1.3-contributor-free`,
OpenCode Zen — not OpenRouter). Override per call with `model=`. `OPENCODE_BIN`
overrides binary discovery.

## 2. AGY (`app/adapters/integrations/agy.py`)

`agy` is the Antigravity CLI (v1.2.6, no API key — signed-in Google session).
`chat()` runs `agy --print= --output-format json`:

- **Stateful**: pass `conversation_id` to resume a CLI conversation
  (`--conversation`); the chat route threads `jarvis-<session_id>` per chat.
- **Passthrough**: `--effort`, `--agent`, `--mode` (`plan`|`accept-edits`),
  `--add-dir` (repeatable), `--project`.
- `--print-timeout` rounds **up** to whole minutes (90 s → `2m`).
- Token usage parsed from the CLI JSON `usage` block.
- Default model `gemini-3.8-flash-medium`; `analyze_file` reads locally
  (60 k cap) with a MIME hint.

There is no `AGYClient` class and no `AGY_CLI_PATH` env var (an old doc
claimed both — they never existed).

## 3. MCP mesh (`app/integrations/mcp/server.py`)

Run: `python -m app.integrations.mcp.server` (stdio). External agents get the
JARVIS capability surface as MCP tools — workspace, git, session, memory, plus
the mesh tools below.

| Tool | Purpose |
|---|---|
| `jarvis_chat` | Ask JARVIS through its chat pipeline (memory + comms context) |
| `jarvis_brief` | Generate the morning brief |
| `jarvis_notify` | Send a notification (push and/or telegram) |
| `jarvis_read_emails` | Read email as a compact unread digest |
| `jarvis_send_email` | Send an email |
| `jarvis_spawn_subagent` | Delegate a goal to an OpenCode worker |

Every tool call routes through the same `ToolSafetyPolicy` as the local loop.
**Auth:** stdio has no HTTP headers, so a client presents the shared key via
the server environment. When `JARVIS_MCP_KEY` is set, the client's
`JARVIS_API_KEY` must equal it or the call is refused (fail closed). Unset
disables the check (local dev). The `fitz` deprecation warning is suppressed
on the stdio channel so the JSON stream stays clean.

---

## Configuration / Interface

| Variable | Meaning | Default |
|---|---|---|
| `JARVIS_SUBAGENTS` | allowlisted worker agents | `build,plan,general` |
| `OPENCODE_BIN` | worker binary override | auto-detected |
| `JARVIS_MCP_KEY` | shared key for MCP clients (stdio auth) | unset (no check) |

## Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `worker exceeded {s}s and was killed` | worker hung past timeout | raise `timeout_s` or split the goal |
| `agent 'x' not allowlisted` | agent not in `JARVIS_SUBAGENTS` | add it or use a listed agent |
| `sub-agent workdir refused` | workdir outside workspace/temp | point it inside the sandbox |
| MCP stdio client reports invalid JSON | stray stderr/warning on stdout | warnings suppressed; ensure no `print()` in tool paths |
| `No payment method` from Zen | free Zen model exhausted | add payment or use another model via `model=` |

---

## Where to go next

- `docs/TOOLS.md` — full runner toolset + safety tiers
- `docs/COMMS.md` — notify dispatcher, Telegram approvals, WhatsApp
- `docs/adr/ADR-017-orchestrator-subagents-opencode-first.md` — the ADR
- `docs/ROADMAP.md` §10 — Sprint 8 phases and status
