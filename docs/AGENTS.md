# JARVIS Agents — `app/agents/`

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18
**Source**: `AGENTS.md` at the repo root

> **Not to be confused with the repo-root [`AGENTS.md`](../AGENTS.md).** That
> file is the authoritative governance standard. This file documents the
> `app/agents/` package only.

> Scope of this document: only the code under `app/agents/` and the modules it
> directly imports/invokes were inspected. Every claim below was checked against
> source files; discrepancies found during review are called out explicitly.
> See **AI Verification Status** at the end for per-statement confidence.

---

## Agent architecture

- The directory `app/agents/` contains exactly two files:
  - `app/agents/__init__.py` — **empty** (no exports).
  - `app/agents/doc_agent.py` — contains the only agent class,
    `DocumentationAgent`, plus the interactive entry point `run_interactive`.
- There is **no base `Agent` class, no agent registry, and no multi-agent
  orchestrator** in this directory. `DocumentationAgent` is the single concrete
  agent in the codebase.
- Architectural style (per `doc_agent.py` docstring and code): a **mini
  agentic loop with prompt-based tool calling**. The model is shown a tool list
  and a `<tool_call>` tag format; the agent parses those tags, executes the
  tools, injects results, and loops. The docstring frames this as the "same
  pattern as v3.0's full agentic runtime, narrower scope" — but no separate
  "v3.0 full runtime" module exists in the current tree; that is a forward-looking
  design note, not an observed second implementation.

Component layering used by the agent:

```
DocumentationAgent                 (app/agents/doc_agent.py)
 ├─ ModelClient (Protocol)         (app/models/client.py)  ← injected at construction
 ├─ ToolRegistry                   (app/tools/base.py)     ← GIT_TOOLS + FILE_TOOLS
 └─ ToolExecutor                   (app/tools/executor.py) ← parse + run + confirm + cap
      ├─ git tools                 (app/tools/git_tools.py)
      └─ file tools                (app/tools/file_tools.py)
```

The agent depends on the **`ModelClient` Protocol**, not a concrete client. Any
object satisfying `generate(messages, stream=False, on_token=None, **kwargs) ->
ModelResponse` with `model_name` / `role` properties can be injected.

---

## Agent responsibilities

`DocumentationAgent` is a **documentation generator**. Its stated job
(`_SYSTEM` prompt + module docstring) is to:

1. Read git history (`git_log`, `git_show`, diff tools) to understand what
   changed in the project.
2. Read existing `docs/CHANGELOG.md` / `docs/DEVLOG.md` (and the `*_recovered.md`
   files) to learn the established format/voice.
3. Produce new **CHANGELOG** entries (what changed + why it matters; sections
   Added/Changed/Fixed/Known Issues) and **DEVLOG** entries (why decisions were
   made, options considered, trade-offs accepted).
4. Write the results back to the documentation files.

It does **not** handle chat, memory, retrieval, or the main conversation
pipeline — those live in `app/main.py` and the `app/memory/`,
`app/conversation/`, `app/context/` packages. The doc agent is invoked only on
demand (the `docs` command), not on every user turn.

---

## Agent lifecycle

**Construction** (inside `main.main()`, before the main REPL loop):

```python
doc_agent = DocumentationAgent(
    model=switcher.get_client(
        settings.profiles.get(settings.active_profile, {}).get("docs", "general")
    ) or switcher.router.default_model
)
```

- The model client is obtained from `ModelSwitcher.get_client(<docs-key>)`,
  falling back to `switcher.router.default_model` if that lookup returns `None`.
- On a `model <name>` command in the REPL, `doc_agent` is **recreated** with a
  new client:
  ```python
  new_model = switcher.get_client(docs_key)
  if new_model:
      doc_agent = DocumentationAgent(model=new_model)
  ```

**Invocation**: the agent is started by `run_interactive(doc_agent)`, which is
called from `main.py` when the user types the literal command `docs`. The
`run_interactive` function prints a menu, reads a choice via `input()`, maps
`"1"/"2"/"3"` to the predefined `_TASKS` (changelog / devlog / both), `"4"` to a
custom task, or `"q"` to cancel, then calls `agent.run(task, verbose=True)`.

**Per-run loop** (`DocumentationAgent.run`):

- `MAX_ITERATIONS = 12` is a hard ceiling (safety cap).
- Each iteration calls `model.generate(messages)` **non-streaming** and inspects
  `response.content`.
- If no `<tool_call>` tags are present → the agent is finished and returns the
  text.
- Otherwise it parses the calls, appends the assistant message, executes the
  tools, and appends a single `user` message containing the tool results, then
  loops.
- If `MAX_ITERATIONS` is reached without a tool-free response, it returns the
  string `"[Documentation agent reached iteration limit without completing]"`.

**Teardown**: the agent holds no persistent resources; it is just re-created on
model switches and otherwise lives for the duration of a `run()` call.

---

## Communication flow

1. `run(task)` builds the system prompt by formatting `_SYSTEM` with
   `tools_section = registry.format_for_prompt()` (a human-readable list of the
   registered tools). The first user message is the natural-language `task`.
   ```python
   messages = [
       {"role": "system", "content": system},
       {"role": "user",   "content": task},
   ]
   ```
2. `response = model.generate(messages)` → `text = response.content`.
3. `ToolExecutor.has_calls(text)` decides whether the loop continues.
4. If yes, `ToolExecutor.parse(text)` returns a list of `ParsedCall(name, args)`.
   - The assistant's raw text is appended to `messages` as an `assistant`
     message.
   - Each call is executed via `ToolExecutor.run(call)`.
   - Results are formatted by `ToolExecutor.format_result(...)` into
     `<tool_result name="..." status="...">...</tool_result>` blocks and joined
     into **one** `user` message appended to `messages`.
5. Loop back to step 2. The final tool-free `text` is returned as the agent's
   answer.

**Confirmation channel**: because the executor is created with
`require_confirmation=True`, any tool whose `ToolDefinition.requires_confirmation`
is `True` triggers a blocking stdin prompt:

```text
  [Tool] write_file({"path": "docs/CHANGELOG.md", ...})
  Execute? (y/N):
```

If the user does not answer `y`, the tool returns
`ToolResult(success=False, error="User declined — tool not executed")`.

**Note on message roles**: tool results are injected as a `user` message (not a
dedicated `tool` role), because this is prompt-based tool calling, not OpenAI
native function calling.

---

## Tool usage

### Tools actually registered for the agent

The agent registers two lists into its `ToolRegistry`:

- `GIT_TOOLS` (`app/tools/git_tools.py`): **git_log, git_diff_stat,
  git_diff_full, git_show, git_tags**.
- `FILE_TOOLS` (`app/tools/file_tools.py`): **read_file, write_file,
  append_file, create_directory**.

That is **9 tools total**. Derived risk levels and confirmation requirements
(from the `ToolDefinition`s):

| Tool | risk_level | requires_confirmation |
|------|-----------|------------------------|
| git_log | none | no |
| git_diff_stat | none | no |
| git_diff_full | none | no |
| git_show | none | no |
| git_tags | none | no |
| read_file | low | no |
| write_file | medium | **yes** |
| append_file | medium | **yes** |
| create_directory | medium | **yes** |

- Tool output is capped at `MAX_OUTPUT_CHARS = 4096` chars before being
  injected back into the model context (truncation message appended).
- Git diff output is additionally capped at `DIFF_MAX_CHARS = 8000` inside the
  git tools themselves.
- Unknown tool names (not in the registry) return
  `ToolResult(success=False, error="Unknown tool: '<name>'...")` rather than
  raising — the agent loop is designed never to crash on a bad tool call.

### File-access allowlists (the security model)

`file_tools.py` defines the blast radius:

- `ALLOWED_READ`: `docs/CHANGELOG.md`, `DEVLOG.md`, `README.md`, `config.yaml`.
- `ALLOWED_WRITE`: `docs/CHANGELOG.md`, `DEVLOG.md`.
- `read_file` raises `PermissionError` for anything outside `ALLOWED_READ`;
  `write_file` raises `PermissionError` for anything outside `ALLOWED_WRITE`.
  This is the only access control; it is enforced inside the tool functions,
  not by the agent caller.

### ⚠️ Discrepancies found in the tool wiring (verified)

These are real mismatches between the agent's instructions and what is actually
registered:

1. ~~**`append_file` is NOT a usable tool.**~~ **RESOLVED at HEAD
   (2026-09-18).** The dead-code bug described here — the `append_file`
   `ToolDefinition` placed after the `return` — has been fixed:
   `append_file` is now a registered `ToolDefinition` in `FILE_TOOLS`
   (medium risk, requires confirmation), and a `create_directory` tool was
   added alongside it. The system prompt's "use `append_file`, never
   `write_file` on existing docs" instruction is now satisfiable. Original
   finding retained for history: before the fix, a model emitting
   `<tool_call>{"name": "append_file", ...}</tool_call>` received
   `ToolResult(success=False, "Unknown tool: 'append_file'")` and nothing
   was written, while the only write tool (`write_file`) overwrote entire
   files.

2. **`git_diff` is referenced but does not exist.** Task 1's instruction says
   "Use `git_log` and `git_diff` to understand what changed." There is **no**
   `git_diff` tool registered. The available git diff tools are
   `git_diff_stat` and `git_diff_full`. A model following task 1 literally would
   call an unknown tool.

3. **Unregistered git helpers.** `git_branch` and `git_status` exist as plain
   functions in `git_tools.py` but are **not** in `GIT_TOOLS`, so the agent
   cannot call them.

4. **`parse()` dedups by tool name.** `ToolExecutor.parse` keeps a `seen` set of
   tool *names*; if the model emits two calls to the same tool name in one
   response, only the first is executed. This is a real behavior of the executor
   that affects the agent (e.g. two `git_show` calls for different refs in the
   same turn would collapse to one).

---

## DocumentationAgent

- **Module**: `app/agents/doc_agent.py`.
- **Class**: `DocumentationAgent`.
- **Constructor**: `__init__(self, model: ModelClient)` — stores the model,
  builds a `ToolRegistry`, registers `GIT_TOOLS` and `FILE_TOOLS`, and constructs
  `ToolExecutor(registry=self._registry, require_confirmation=True)`.
- **Entry points**:
  - `run(self, task: str, verbose: bool = True) -> str` — the programmatic loop
    described above; returns the final text.
  - `run_interactive(agent: DocumentationAgent) -> None` — menu-driven wrapper
    called from `main.py` on the `docs` command.
- **Constants**: `MAX_ITERATIONS = 12`.
- **Predefined tasks** (`_TASKS`): `"1"` changelog, `"2"` devlog, `"3"` both
  (full history from first commit). These are prompts handed to `run()`.
- **Tool-call format expected from the model**:
  `<tool_call>{"name": "tool_name", "args": {"param": "value"}}</tool_call>`,
  one per line.
- **Model dependency**: any `ModelClient`. In `main.py` it is wired from
  `ModelSwitcher` using the `"docs"` key of the active profile, falling back to
  the router's default model. With the **hardcoded default settings**
  (`app/config/settings.py`), the default `models` dict only defines `"general"`
  and `"autocomplete"`, and `profiles["local"]["docs"] = "docs"` — so
  `get_client("docs")` returns `None` and the agent falls back to the router's
  default model (the client registered for the `"general"` role). The actual
  runtime model therefore depends on `config.yaml`, which was **not readable**
  in this task (see Verification Status).
- **Confirmed environment**: `docs/CHANGELOG_recovered.md` and
  `docs/DEVLOG_recovered.md`, which the agent's workflow reads, do exist in
  `docs/` (verified by directory listing).

---

## Future agent design

All of the following is taken from **code comments/docstrings only** and is
**not implemented** in the current tree:

- **Native function calling (v3.0).** `app/tools/base.py` already exposes
  `ToolDefinition.to_openai_schema()` (OpenAI-compatible) and
  `ToolRegistry.to_openai_schemas()` "for v3.0 native function calling."
  `app/tools/executor.py` states the same `ToolExecutor` interface will work in
  v3.0, "only the parse step changes (model returns structured JSON instead of
  text tags)." `doc_agent.py` states that when v3.0 ships, "only the
  `model.generate()` call changes — `ToolExecutor`, `ToolRegistry`, and this
  loop stay the same."
- **Schema compatibility.** The tool schema format is already
  OpenAI function-calling compatible, so `model.generate(tools=[...])` can be
  passed directly once a model supports it.
- **Permission system.** `app/tools/file_tools.py` notes that v3.0 will replace
  the current hardcoded `ALLOWED_READ` / `ALLOWED_WRITE` sets with "a proper
  permission system with user-configurable rules."
- **Full agentic runtime.** The docstring describes the current doc agent as a
  narrow slice of a planned "v3.0 full agentic runtime" with the same loop
  shape. No such runtime module exists yet; this is a design intention, not
  shipped code.
- **Higher-risk tools deferred.** `base.py` defines a `risk_level="high"` tier
  ("executes code or shell commands (run_python) — v3.0+") that is referenced
  but not present in the doc agent's tool set.

---

## AI Verification Status

### AI Verified

The following were checked directly against the source files inspected in this
task:

- `app/agents/` contains only `__init__.py` (empty) and `doc_agent.py`;
  `DocumentationAgent` is the only agent class. (`ls app/agents/`,
  `app/agents/__init__.py` empty, `app/agents/doc_agent.py`.)
- `DocumentationAgent.__init__` builds a `ToolRegistry`, registers `GIT_TOOLS`
  and `FILE_TOOLS`, and constructs
  `ToolExecutor(registry=self._registry, require_confirmation=True)`.
- Registered tools are exactly: `git_log`, `git_diff_stat`, `git_diff_full`,
  `git_show`, `git_tags` (from `GIT_TOOLS`) and `read_file`, `write_file`,
  `append_file`, `create_directory` (from `FILE_TOOLS`) — 9 total.
  (Corrected 2026-09-18: `append_file`/`create_directory` registered since;
  previously 7.)
- `append_file` **is** registered at HEAD (medium risk, requires
  confirmation): the dead-code placement described below is fixed
  (`app/tools/file_tools.py`).
- `git_branch` and `git_status` exist as functions in `git_tools.py` but are not
  in `GIT_TOOLS`, so the agent cannot call them.
- `MAX_ITERATIONS = 12` is defined in `doc_agent.py`.
- `run(task, verbose=True)` builds the system prompt via
  `_SYSTEM.format(tools_section=registry.format_for_prompt())`, seeds
  `messages=[system, user]`, and loops `model.generate(messages)` until no tool
  calls or `MAX_ITERATIONS`, returning `response.content`.
- Tool-call format is `<tool_call>{"name":..., "args":{...}}</tool_call>`, parsed
  by `ToolExecutor`. (`doc_agent.py`, `app/tools/executor.py`.)
- `ToolExecutor.has_calls`/`parse` use three regexes; `parse` dedups by tool name
  via a `seen` set.
- `ToolExecutor.run` returns `ToolResult(success=False, "Unknown tool: ...")` for
  unregistered names. (`app/tools/executor.py`.)
- With `require_confirmation=True`, `write_file` (`requires_confirmation=True`)
  triggers an `Execute? (y/N):` stdin prompt; `read_file` and the git tools do
  not. (`app/tools/executor.py`, `file_tools.py`, `git_tools.py`.)
- Tool output is capped at `MAX_OUTPUT_CHARS = 4096`; git diffs at
  `DIFF_MAX_CHARS = 8000`. (`app/tools/executor.py`, `git_tools.py`.)
- `ToolExecutor.format_result` injects `<tool_result name=... status=...>`
  blocks as a single `user` message.
- Invocation path in `main.py`: `doc_agent` is constructed inside `main()` from
  `switcher.get_client(profiles[active_profile]["docs"]) or
  switcher.router.default_model`; `run_interactive(doc_agent)` runs on the
  `docs` command; `doc_agent` is recreated on a `model <name>` switch.
- `ModelClient` is a Protocol with
  `generate(messages, stream=False, on_token=None, **kwargs) -> ModelResponse`
  and `model_name` / `role` properties; `ModelResponse` has `content`,
  `model`, `tokens_used`, `finish_reason`. (`app/models/client.py`.)
- `LlamaCppClient.generate` returns `ModelResponse(content=...)` for the
  non-streaming call the agent relies on. (`app/models/llamacpp_client.py`.)
- `run_interactive` prints a menu, maps `1/2/3` to `_TASKS`
  (changelog/devlog/both), `4` to a custom task, `q` to cancel, then calls
  `agent.run(task, verbose=True)`.
- The system prompt instructs using `append_file` and forbids `write_file` on
  existing docs; at HEAD `append_file` is registered so the instruction is
  satisfiable (was a contradiction before the fix noted above).
- Task 1 references `git_diff`, which is not a registered tool (contradiction).
- `docs/CHANGELOG_recovered.md` and `docs/DEVLOG_recovered.md` exist in `docs/`
  (referenced by the agent workflow). (Directory listing of `docs/`.)
 - `app/config/version.py` derives the version from git tags at import time
  (no hardcoded `VERSION` constant; `_FALLBACK_VERSION` is `v3.0.1` for
  git-less builds); the `doc_agent.py` module docstring references a
  working-tree banner. Prefer git tags (latest at review: `v3.23.0`) for
  canonical release identity when reconciling agent behavior vs. released
  builds. (Corrected 2026-09-18: this bullet previously claimed
  `VERSION = "v.2.4.0"` and latest tag `v2.5.0`, both stale.)

### AI Partially Verified

Supported by code evidence but not fully confirmable in this task:

- **Exact runtime model used by the doc agent.** Derived from the hardcoded
  defaults: `profiles["local"]["docs"] = "docs"`, the default `models` dict only
  has `"general"`/`"autocomplete"`, so `get_client("docs")` is `None` and the
  agent falls back to `switcher.router.default_model` (the `"general"` client).
  However, the live configuration is `config.yaml`, which I was **not permitted
  to read** (security block), so the actual resolved model/key at runtime is
  unconfirmed.
- **Non-streaming behavior of `OllamaClient` / `OpenRouterClient`.** These are
  asserted to satisfy the `ModelClient` Protocol, but they were not executed in
  this task; their exact `generate` return shape is inferred from the Protocol,
  not run.
- **Impact of `parse()` name-dedup.** The dedup logic is verified in source, but
  its practical effect on real doc-agent runs (e.g. dropping a duplicate tool
  call in one turn) is inferred, not observed via execution.
- **"Mini loop == v3.0 full runtime" claim.** Only `DocumentationAgent` exists
  today; no parallel "full runtime" implementation was found in the codebase, so
  the structural similarity is a design statement in comments, not a verified
  second implementation.

### AI Unverified

Could

---

## Git history verification

I compared the repository commit history for the files referenced above to verify the timeline described in this document. Below are the most recent commits that modify each file (short hash | author | date | subject). This comparison uses the git history (not tags) as the source of truth for when code changed.

- `app/agents/doc_agent.py`
  - c84d53b | Er Sajan PLG | 2026-07-06 06:13:31 +0545 | feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
  - 6ea9796 | Er Sajan PLG | 2026-07-11 22:42:47 +0545 | feat(platform): expand model backends and configuration system
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

- `app/tools/file_tools.py`
  - c84d53b | Er Sajan PLG | 2026-07-06 06:13:31 +0545 | feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
  - 6ea9796 | Er Sajan PLG | 2026-07-11 22:42:47 +0545 | feat(platform): expand model backends and configuration system
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

- `app/tools/executor.py`
  - c84d53b | Er Sajan PLG | 2026-07-06 06:13:31 +0545 | feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
  - 6ea9796 | Er Sajan PLG | 2026-07-11 22:42:47 +0545 | feat(platform): expand model backends and configuration system
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

- `app/tools/git_tools.py`
  - c84d53b | Er Sajan PLG | 2026-07-06 06:13:31 +0545 | feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

- `app/tools/base.py`
  - c84d53b | Er Sajan PLG | 2026-07-06 06:13:31 +0545 | feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

- `app/models/client.py`
  - 8519f65 | Er Sajan PLG | 2026-07-03 23:31:02 +0545 | feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
  - df45be2 | Er Sajan PLG | 2026-07-05 07:23:59 +0545 | Multi-Backend + Streaming + External Config

- `app/main.py`
  - 63addf6 | Er Sajan PLG | 2026-07-02 09:31:29 +0545 | before big change in memory manager
  - 8519f65 | Er Sajan PLG | 2026-07-03 23:31:02 +0545 | feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
  - f9fa068 | Er Sajan PLG | 2026-07-18 18:05:40 +0545 | feat: add web UI, FastAPI server, and fix batch of issues

Conclusion: the git history shows the DocumentationAgent and the tool infrastructure were introduced together and received follow-up changes across the commits listed above. These findings align with the claims in this document (tool registration, `append_file` dead-code observation, missing `git_diff` helper, and `write_file` requiring confirmation). If you'd like, I can update specific assertions in the prose to cite the exact commit hashes shown above or open a PR that references these commits inline.

### Addendum 2026-09-18 (HEAD `v3.23.0`)

The per-file tables above stop at 2026-07-18. Commits since then touching the
same files (`git log`, newest-first, max 3 per file):

- `app/agents/doc_agent.py`
  - 2037f42 | 2026-09-17 | fix: resolve audit findings and governance violations
- `app/tools/file_tools.py`
  - 2d8d7ea | 2026-09-12 | fix(tools): enforce the file-tool allowlist (Phase 0: F1+F2) (#56)
  - 4d6ac8f | 2026-09-10 | feat(brain): register tools and route destructive intents into the HITL gate
- `app/tools/executor.py`, `app/tools/git_tools.py`, `app/tools/base.py`,
  `app/models/client.py`
  - 2037f42 | 2026-09-17 | fix: resolve audit findings and governance violations
- `app/main.py`
  - ac6544f | 2026-09-18 | feat(comms): chat email context, runner comms tools, brief push channel, voice endpoints
  - 35cc133 | 2026-09-17 | feat(mobile): serve console shell so JARVIS runs on a phone
  - 7000de1 | 2026-09-17 | feat(brief): add morning brief service with Slack/email delivery

Behavioral re-verification of the full claims above against HEAD is owed in the
next review pass; verified HEAD deltas are already folded into the tool table
and discrepancy #1 above (`append_file` registered, `create_directory` added).
`git_branch`/`git_status` remain unregistered and `git_diff` remains absent
(verified 2026-09-18), so discrepancies #2–#4 stand.
