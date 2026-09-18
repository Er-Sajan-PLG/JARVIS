# JARVIS Tool System (app/tools/)

**Status**: ACTIVE
**Type**: reference
**Source**: `app/tools/` at HEAD
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18
> Source-verified documentation. Every claim below was checked against the code in
> `app/tools/` (`base.py`, `executor.py`, `file_tools.py`, `git_tools.py`,
> `workspace_tools.py`, `comms_tools.py`, `__init__.py`)
> and the consuming code in `app/agents/doc_agent.py` and `app/bootstrap.py`.
> There are **two** tool surfaces — the runner toolset and the doc-agent-only
> toolset — and they are documented separately below. Where the source
> contradicts itself, that is called out explicitly.
> See **AI Verification Status** at the end for per-statement confidence.

---

## Tool architecture

The tool system is a **prompt-based tool-calling framework** (not native model
function calling). The model emits `<tool_call>` tags in its text; the executor parses
and runs them. It is composed of six source files plus the package init:

- `base.py` — three building blocks: `ToolResult`, `ToolDefinition`, `ToolRegistry`.
- `executor.py` — `ToolExecutor`: parses `<tool_call>` tags out of model text and runs them.
- `file_tools.py` — **doc-agent-only** file handlers and the `FILE_TOOLS` list.
- `workspace_tools.py` — **runner-facing** sandboxed file primitives and `WORKSPACE_TOOLS`.
- `comms_tools.py` — **runner-facing** email/notification/brief handlers and `COMMS_TOOLS`.
- `git_tools.py` — read-only git handlers and the `GIT_TOOLS` list.
- `__init__.py` — composition root: defines `DEFAULT_TOOLSET` (the runner toolset).

### Core data types (`base.py`)

`ToolResult` (dataclass) — the uniform return value of every tool.

- Fields: `success: bool`, `output: str`, `error: str = ""`.
- `__str__`: returns `output` on success, else `"Error: {error}"`.
- `__bool__`: returns `success` (a result is truthy iff it succeeded).

`ToolDefinition` (dataclass) — one tool’s metadata + behaviour.

- Fields: `name`, `description`, `parameters` (a JSON Schema `dict`), `handler: Callable`,
  plus `risk_level: str = "low"` and `requires_confirmation: bool = False`.
- `execute(**kwargs) -> ToolResult`: calls `handler`, wrapping any exception in a
  `ToolResult(success=False, ...)`. `PermissionError` becomes `"Permission denied: ..."`;
  any other `Exception` becomes `error=str(e)`. On success returns
  `ToolResult(success=True, output=str(result))`.
- `to_openai_schema() -> dict`: returns an OpenAI‑style
  `{"type":"function","function":{...}}` dict. **Not called anywhere in the code today**
  (reserved for v3.0).

`ToolRegistry` (class) — holds tools in a `dict[str, ToolDefinition]` keyed by `name`.

- `register(tool)` / `register_many(tools)` — add tools.
- `get(name)` / `all()` — lookup.
- `to_openai_schemas()` — list of OpenAI schemas. **Defined but unused in the current
  code** (forward-compat for v3.0).
- `format_for_prompt() -> str` — builds a human-readable tool list for the system prompt.
  Tools whose `risk_level` is not `"none"`/`"low"` get a ` [<risk> risk]` suffix (so
  `write_file` shows `[medium risk]`; git tools and `read_file` do not).

### The runner toolset — `DEFAULT_TOOLSET` (15 entries, verified)

`app/tools/__init__.py` defines `DEFAULT_TOOLSET`, the composition-root wiring
table the ExecutionRunner executes tools *by name* from (`app/bootstrap.py`
registers this mapping at boot). It holds **14 entries**: 5 workspace + 3 git
+ 6 comms (from `app/tools/comms_tools.py`).

| Tool | Source | Safety tier (`@safety_gate`) | requires_confirmation |
|---|---|---|---|
| `read_file` | `workspace_tools.py` (`workspace_read_file`) | SAFE | no |
| `write_file` | `workspace_tools.py` (`workspace_write_file`) | SENSITIVE | **yes** |
| `append_file` | `workspace_tools.py` (`workspace_append_file`) | SENSITIVE | **yes** |
| `create_directory` | `workspace_tools.py` (`workspace_create_directory`) | DESTRUCTIVE → HITL | **yes** |
| `list_dir` | `workspace_tools.py` (`workspace_list_dir`) | SAFE | no |
| `git_log` | `git_tools.py` | SAFE | no |
| `git_diff_stat` | `git_tools.py` | SAFE | no |
| `git_diff_full` | `git_tools.py` | SAFE | no |
| `read_emails` | `comms_tools.py` (`comms_read_emails`) | SAFE | no |
| `search_emails` | `comms_tools.py` (`comms_search_emails`) | SAFE | no |
| `send_email` | `comms_tools.py` (`comms_send_email`) | SENSITIVE | no |
| `reply_email` | `comms_tools.py` (`comms_reply_email`) | SENSITIVE | no |
| `send_notification` | `comms_tools.py` (`comms_notify`, push and/or Telegram) | SENSITIVE | no |
| `get_brief` | `comms_tools.py` (`comms_brief`, generates the morning brief) | SAFE | no |
| `spawn_subagent` | `subagent_tools.py` (OpenCode worker: goal, agent, model, workdir, session_id, timeout_s) | SENSITIVE | no |

Safety tiers are `SafetyTier` (`app/domain/plan.py`: SAFE / SENSITIVE /
DESTRUCTIVE), enforced at runtime by `@safety_gate` (`app/guardrails/`), not
to be confused with the advisory `risk_level` metadata on `ToolDefinition`.
A DESTRUCTIVE tier means the ExecutionRunner pauses for human approval
(HITL) — that is why `create_directory` is DESTRUCTIVE → HITL-gated, while
the SENSITIVE sends (email, notifications) are rate-limited and
policy-checked but not HITL-gated per message.

### Workspace sandbox (`workspace_tools.py`)

The runner file primitives are sandboxed, fail closed:

- The sandbox root is the repo root by default, overridden by
  `JARVIS_WORKSPACE_ROOT`; the system temp dir and `JARVIS_EXTRA_ALLOWED_ROOTS`
  entries are additionally allowed (`_allowed_roots()`).
- Paths are resolved (symlinks and `..` collapse) before any decision; a
  resolved path outside every allowed root raises `PermissionError`.
- Inside the workspace root, protected prefixes are refused for writes:
  `PROTECTED_PREFIXES = ("app", "tests", "scripts", ".git", ".github", "legacy")`.
- Secret-shaped names are refused for reads and writes regardless of location:
  `SECRET_NAMES` (`.env`, `.env.local`, `.env.production`, `.ci-bridge.env`,
  `credentials.json`, `id_rsa`, `id_ed25519`, `.netrc`, `.npmrc`, `.pypirc`).

### Comms tools (`comms_tools.py`)

6 tools. Reads are SAFE (no side effects): `read_emails`, `search_emails`,
`get_brief`. Anything that sends — `send_email`, `reply_email`,
`send_notification` (push and/or Telegram) — is SENSITIVE: rate-limited and
policy-checked like other network writes, but not HITL-gated per message
(that would make every alert wait on a human). Handlers are async and return
compact JSON strings. WhatsApp is intentionally absent here: it is send-only
via `app/integrations/whatsapp/`, not a runner tool.

### Sub-agent workers (`subagent_tools.py`, ADR-017)

1 tool. `spawn_subagent(goal, agent, model, workdir, session_id, timeout_s)`
shells `opencode run --format json` and folds the event stream into a worker
receipt (`status`, `session_id`, `summary`, `tokens`, `cost`, `error`).
SENSITIVE, policy-capped from day one: allowlisted agents only
(`JARVIS_SUBAGENTS`, default `build,plan,general`), per-spawn timeout
(default 600 s, kill on expiry), workdir jailed to the workspace or temp,
output bounded at 20 k chars. Model defaults to `opencode/big-pickle`
(override per call). `OPENCODE_BIN` overrides binary discovery.

### Doc-agent-only toolset (`file_tools.py` + `GIT_TOOLS`, 9 tools)

The `DocumentationAgent` (`app/agents/doc_agent.py`) does **not** use
`DEFAULT_TOOLSET`. It registers `GIT_TOOLS` (5: `git_log`, `git_diff_stat`,
`git_diff_full`, `git_show`, `git_tags`) plus `FILE_TOOLS` (4: `read_file`,
`write_file`, `append_file`, `create_directory`) — **9 tools total** — via
`register_many(GIT_TOOLS)` + `register_many(FILE_TOOLS)`.

| Tool | risk_level | requires_confirmation |
|------|-----------|------------------------|
| `git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags` | none | no |
| `read_file` | low | no |
| `write_file`, `append_file`, `create_directory` | medium | **yes** |

---

## Tool registration

Registration is **hardcoded** on both surfaces:

- Runner: `app/tools/__init__.py` builds `DEFAULT_TOOLSET` from the workspace
  callables, three git functions, and `**COMMS_TOOLS`. `app/bootstrap.py`
  registers this mapping at boot; the ExecutionRunner executes tools *by name*.
- Doc agent: `DocumentationAgent.__init__` (`app/agents/doc_agent.py`)
  registers `GIT_TOOLS` + `FILE_TOOLS` into its own `ToolRegistry`:

```python
self._registry = ToolRegistry()
self._registry.register_many(GIT_TOOLS)
self._registry.register_many(FILE_TOOLS)
self._executor = ToolExecutor(registry=self._registry, require_confirmation=True)
```

- There is **no dynamic/plugin discovery**; tools are added only by extending
  those lists/mappings and re-registering.
- `main.py` constructs one `DocumentationAgent` (with a model client) and reuses it for the `docs` command
  (and rebuilds it on model switch). `main.py` does not touch the registry directly.

---

## Execution flow

The agent loop lives in `DocumentationAgent.run(task, verbose=True)` and is a **mini
agentic loop**:

1. Build the system prompt by calling `self._registry.format_for_prompt()` and injecting it
   into `_SYSTEM` (which contains the tool list, the `<tool_call>` format instructions, and
   the documentation rules).
2. Initialize `messages` with system + the user `task`.
3. Loop for `iteration` in range(1, `MAX_ITERATIONS` + 1) where `MAX_ITERATIONS = 12`:
   - a. `response = self._model.generate(messages)`; `text = response.content`
   - b. If `not self._executor.has_calls(text)`: **return `text`** — no tool calls → agent is done; final text returned.
        (The assistant turn is *not* appended in this case.)
   - c. `calls = self._executor.parse(text)` — extract `<tool_call>` blocks.
   - d. Append the assistant message `{"role":"assistant","content"}`.
   - e. For each call, `result = self._executor.run(call)`; collect
        `self._executor.format_result(call, result)` into `result_blocks`.
   - f. Append a single user message
        `{"role":"user","content":"\n\n".join(result_blocks)}` containing all results.
4. If the loop hits `MAX_ITERATIONS` without a tool‑free response, return the string
   `"[Documentation agent reached iteration limit without completing]"`.

Key points:

- Results are **batched**: all tool results from one model turn are concatenated into **one**
  user message (not one message per tool).
- `format_result` wraps each result as
  `<tool_result name="..." status="success|error">...</tool_result>` so the model can
  correlate results to calls.
- The model is expected to emit **one `<tool_call>` per line** and wait for results before
  the next call.

---

## Parsing (`ToolExecutor.parse`)

Three regexes are tried, in order, and every match is returned (no
deduplication at HEAD — an earlier revision collapsed same-name calls to the
first, and that `seen` set is gone):

1. `_TOOL_CALL_RE` — JSON form: `<tool_call>{"name": "...", "args": {...}}</tool_call>`
2. `_HYBRID_CALL_RE` — `<tool_call>name({"k":"v"})</tool_call>` (what some models emit)
3. `_FUNC_CALL_RE` — `<tool_call>name("positional")</tool_call>`; the first quoted string
   becomes `args={"path": ...}`

`has_calls(text)` returns `True` if any of the three regexes match. Malformed JSON, missing
`name`, or empty `args` are silently skipped (the call is dropped, not raised).

---

## Safety model

Safety is layered and enforced inside the tool handlers and the executor, not by the caller.

### Doc-agent path allowlists (`file_tools.py`, doc-agent-only)

`file_tools.py` defines two module-level sets that bind **only** the
DocumentationAgent's tools (the runner uses the workspace sandbox above,
not these sets):

- `ALLOWED_READ`: `docs/CHANGELOG.md`, `docs/DEVLOG.md`,
  `docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`, `docs/V3_ROADMAP.md`,
  `CHANGELOG.md`, `DEVLOG.md`, `README.md`, `config.yaml`.
- `ALLOWED_WRITE`: `docs/CHANGELOG.md`, `docs/DEVLOG.md`, `CHANGELOG.md`, `DEVLOG.md`.

`read_file` raises `PermissionError` if `path` not in `ALLOWED_READ`; `write_file` and
`append_file` raise `PermissionError` if `path` not in `ALLOWED_WRITE`. The check is an
**exact string match** plus a rejection of absolute/traversal paths — equivalent paths
that don’t match the literal entries are blocked.
(Verified by reading the handlers.)

- `read_file` returns a placeholder string (`file not found: ...`) for an allowed path
  that doesn’t exist yet (it does **not** raise).
- `write_file` creates parent directories (`mkdir(parents=True)`) and overwrites the
  whole file; `append_file` appends without overwriting.
- `create_directory` is gated by `ALLOWED_CREATE_DIR`, which is **empty**, so every
  doc-agent `create_directory` call raises `PermissionError` — the doc agent cannot
  create directories at all.

### Read‑only git (git tools)

Every git tool calls only read subcommands via
`subprocess.run(["git", ...], capture_output=True, text=True)` — `log`, `diff`, `status`,
`show`, `tag`, `rev-parse`. There is **no** `git commit`/`checkout`/`push`/`reset`, so the
repo cannot be mutated by the agent. `shell=True` is not used (args are a list → no shell
injection).

### Output truncation

Two caps prevent context‑window overflow:

- `ToolExecutor.MAX_OUTPUT_CHARS = 4096` — any successful tool output longer than this is
  truncated with a `"(N chars trimmed)"` note.
- `git_tools.DIFF_MAX_CHARS = 8000` — `git_diff_full` and `git_show` truncate their own output.

### No raw exceptions escape

`ToolDefinition.execute` catches everything and returns a `ToolResult`. The agent loop only
ever sees `ToolResult` objects.

---

## Permission model

Two independent permission layers:

1. **Path allowlist / sandbox** (mandatory, enforced in handlers)
   Doc-agent tools use the `file_tools.py` allowlists above; runner tools use the
   workspace sandbox. Both are always applied (no flag disables them).

2. **Confirmation gate** (optional, in the executor)
   `ToolExecutor.__init__(registry, require_confirmation=True)`.
   In `run()`, before executing, if `self._require_confirmation` and
   `tool.requires_confirmation`:
   - It prints `[Tool] name(args)` (args preview capped at 120 chars),
   - then blocks on `input(" Execute? (y/N): ")`.
   Answer `"y"` → execute; anything else → returns
   `ToolResult(success=False, error="User declined — tool not executed")`.

    On the doc-agent surface `write_file`, `append_file` and `create_directory`
    have `requires_confirmation=True`, so they prompt; git tools and `read_file`
    never prompt. `doc_agent` always constructs the executor with
    `require_confirmation=True`; the test suite disables it by setting
    `_executor._require_confirmation = False`.

⚠️ **Caveat**: the confirmation uses a blocking `input()` on stdin. It works in the
interactive `docs` flow in `main.py`, but would block in any non‑interactive/headless
deployment unless `require_confirmation` is disabled.

### `risk_level`

`risk_level` (`none`/`low`/`medium`/`high`) is **metadata only** — it drives the ` [risk]`
label in `format_for_prompt()` but is not itself a gate. The docstring in `base.py` defines
`high` as “executes code or shell commands (run_python) — v3.0+”, but no high‑risk tool
exists in the current code.

---

## Error handling

| Situation | Behaviour |
|-----------|-----------|
| Unknown tool | `ToolExecutor.run` returns `ToolResult(success=False, error="Unknown tool: '<name>'. Available: [...]")` — **never raises**. |
| Tool handler raises | `ToolDefinition.execute` catches `PermissionError` → `"Permission denied: <e>"`, any other `Exception` → `str(e)`, both as `ToolResult(success=False)`. |
| Git failure | `_run_git` raises `RuntimeError` on non‑zero exit; `git_tags` additionally catches `RuntimeError` and returns `"(no tags found)"`. Other git tools let the error propagate to `execute` and become a `ToolResult` error. |
| Missing allowed file | `read_file` returns a placeholder string (success, not an error). |
| Truncation | Executor (4096) and git tools (8000) cap output and append a truncation note. |
| Malformed tool‑call text | `parse` silently drops unparsable blocks; `has_calls` keeps the loop going. |
| Max iterations | If the model never stops calling tools, the loop returns the iteration‑limit message instead of looping forever. |

All failures are turned into `<tool_result status="error">` blocks and fed back to the
model, so the loop continues and the model can recover.

---

## ⚠️ Discrepancies found in the tool wiring (verified)

These are real mismatches between the agent’s instructions and what is actually registered:

1. **`git_diff` is referenced but does not exist.** Task 1’s instruction in
   `app/agents/doc_agent.py` says “Use `git_log` and `git_diff` to understand
   what changed.” There is **no** `git_diff` tool registered. The available git
   diff tools are `git_diff_stat` and `git_diff_full`. A model following task 1
   literally would call an unknown tool.

2. **Unregistered git helper.** `git_status` exists as a plain function in
   `git_tools.py` but is **not** in `GIT_TOOLS`, so the agent cannot call it.

Resolved since the previous revision of this document: `append_file` **is**
now implemented and registered in `FILE_TOOLS` (the old dead-code finding no
longer holds — verified by listing `FILE_TOOLS`), and `ToolExecutor.parse`
no longer deduplicates calls by tool name (no `seen` set at HEAD — every
emitted call is executed).

---

## Future improvements

Derived from the code, its own comments, and verified gaps:

- **Register `git_status` or remove it.** The function exists in `git_tools.py`
  but is not in `GIT_TOOLS`, so it is unusable as a tool (only directly
  callable from Python). Decide whether to expose it.
- **Align task 1 with registered tools.** It references `git_diff`, which does
  not exist; point it at `git_diff_stat` / `git_diff_full`.
- **Canonicalise paths** instead of exact‑match allowlists. Resolving paths against a
  configured root would be more robust and still safe (v3.0 comment in `file_tools.py`
  already anticipates this). The runner sandbox in `workspace_tools.py` already
  resolves paths; the doc-agent allowlist does not.
- **Wire up native function calling (v3.0).** `ToolDefinition.to_openai_schema()` and
  `ToolRegistry.to_openai_schemas()` already exist but are unused; switching to
  `model.generate(tools=[...])` would only require changing the parse step in
  `ToolExecutor`.
- **Make confirmation non‑blocking / pluggable.** Replace the `input()` call with an
  injectable confirmation callback so the executor works headless and in tests without
  monkey‑patching `_require_confirmation`.
- **Surface error type to the model.** Today `PermissionError` and generic errors are both
  `ToolResult(success=False)`; only the `"Permission denied:"` prefix distinguishes them. A
  structured `error_type` could help the model respond appropriately.

---

## AI Verification Status

### AI Verified (2026-09-18 re-read)

- `app/tools/__init__.py` defines `DEFAULT_TOOLSET` (composition root for the
  ExecutionRunner, registered at boot by `app/bootstrap.py`); the doc agent
  imports `GIT_TOOLS`/`FILE_TOOLS` from the submodules directly.
- The tool system is **prompt‑based**: `ToolExecutor` parses `<tool_call>` tags; no native
  function calling is wired in. (`executor.py`, `doc_agent.py`.)
- Runner surface is **14 entries**: 5 workspace callables (`read_file`,
  `write_file`, `append_file`, `create_directory`, `list_dir`), 3 git
  (`git_log`, `git_diff_stat`, `git_diff_full`), 6 comms (`read_emails`,
  `search_emails`, `send_email`, `reply_email`, `send_notification`,
  `get_brief`). (Counted from `DEFAULT_TOOLSET` and `COMMS_TOOLS`.)
- Doc-agent surface is **9 tools**: `GIT_TOOLS =
  ['git_log','git_diff_stat','git_diff_full','git_show','git_tags']`,
  `FILE_TOOLS = ['read_file','write_file','append_file','create_directory']`.
  (Listed from the modules.)
- Safety tiers (`SafetyTier` in `app/domain/plan.py`, enforced by
  `@safety_gate` in `app/guardrails/`): workspace `read_file`/`list_dir` SAFE;
  `write_file`/`append_file` SENSITIVE; `create_directory` DESTRUCTIVE (HITL);
  comms reads + `get_brief` SAFE; comms sends SENSITIVE. Doc-agent
  `write_file`/`append_file`/`create_directory` require confirmation; git tools
  and `read_file` do not.
- Workspace sandbox: `JARVIS_WORKSPACE_ROOT` (default repo root) + temp dir +
  `JARVIS_EXTRA_ALLOWED_ROOTS`; resolved-path containment;
  `PROTECTED_PREFIXES = ("app", "tests", "scripts", ".git", ".github", "legacy")`;
  `SECRET_NAMES` refused everywhere. (`workspace_tools.py`.)
- `ToolExecutor.MAX_OUTPUT_CHARS = 4096` and `git_tools.DIFF_MAX_CHARS = 8000` cap outputs.
  (`executor.py`, `git_tools.py`.)
- `ToolDefinition.execute` wraps exceptions: `PermissionError` →
  `"Permission denied: ..."`, other `Exception` → `str(e)`, success →
  `ToolResult(success=True, output=str(result))`. (`base.py`.)
- Unknown tool → `ToolResult(success=False, error="Unknown tool: ...")` and never raises.
  (`executor.py`.)
- The agent loop returns early when `has_calls` is false; otherwise parses, appends the
  assistant message, runs each call, and injects all results as **one** user message;
  `MAX_ITERATIONS = 12` caps the loop. (`doc_agent.py`.)
- Doc-agent file handlers enforce exact‑string allowlists `ALLOWED_READ`/`ALLOWED_WRITE`;
  non‑members raise `PermissionError`; missing allowed files return a placeholder;
  `write_file` overwrites and creates parent dirs; `append_file` appends;
  `ALLOWED_CREATE_DIR` is empty so the doc agent cannot create directories.
  (`file_tools.py`.)
- Git tools use `subprocess.run` with a list (no `shell=True`) and only read‑only
  subcommands. (`git_tools.py`.)
- `to_openai_schemas()` / `ToolRegistry.to_openai_schemas()` are defined but not
  referenced anywhere in `app/` (only in docstrings) — native calling is not active.
- `parse` returns every matched call (verified: no `seen`/dedup set in
  `executor.py` at HEAD).
- Task 1 in `doc_agent.py` references `git_diff`, which is not a registered tool.
- `git_status` is defined in `git_tools.py` but is not in `GIT_TOOLS`.

### AI Partially Verified

- **`risk_level` semantics.** The `base.py` docstring classifies
  `none`/`low`/`medium`/`high`. Only the `high` tier has no live tool, so it is
  documentation-only.
- **v3.0 native function calling.** The schema methods exist, but no code path calls
  them and no test exercises them, so end-to-end behaviour is unverified.
- **Confirmation gate behaviour in production.** Verified by reading `executor.py`;
  the live `input()` UX in an interactive terminal was not observed.

### AI Unverified

- **Real LLM conformance.** The agent was not run against a live model here, so
  conformance of real model output to the `<tool_call>` format is unobserved.
- **Runtime in a non‑git or constrained environment.** Git tools’ behaviour outside a
  repository in production was not verified here.
- **Performance/scaling.** Behaviour with very large repos or diffs was not measured.
- **External systems.** No external services were invoked; their interaction with the
  tool layer is out of scope of `app/tools/`.

---

## Developer Verification

Status: ☐ Not Reviewed

Reviewer:

**Date:**
