## JARVIS Documentation Agent — Tool System (app/tools/)


> Source-verified documentation. Every claim below was checked against the code in
> `app/tools/` (`base.py`, `executor.py`, `file_tools.py`, `git_tools.py`, `__init__.py`)
> and the consuming code in `app/agents/doc_agent.py` and `app/main.py`, plus the
> project’s own `tests/stress_test.py`. Where the source contradicts itself, that is
> called out explicitly.  
> See **AI Verification Status** at the end for per-statement confidence.

---

## Tool architecture

The tool system is a **prompt-based tool-calling framework** (not native model
function calling). The model emits `<tool_call>` tags in its text; the executor parses
and runs them. It is composed of four source files plus an empty package init:

- `base.py` — three building blocks: `ToolResult`, `ToolDefinition`, `ToolRegistry`.
- `executor.py` — `ToolExecutor`: parses `<tool_call>` tags out of model text and runs them.
- `file_tools.py` — file read/write handlers and the `FILE_TOOLS` list.
- `git_tools.py` — read-only git handlers and the `GIT_TOOLS` list.
- `__init__.py` — **empty**; it exports nothing. Callers import directly from the submodules
  (`from app.tools.file_tools import FILE_TOOLS`, etc.).

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

### Registered tools (verified)

| Tool            | Source        | risk_level | requires_confirmation |
|-----------------|---------------|------------|-----------------------|
| `git_log`       | `git_tools.py` | none       | no                    |
| `git_diff_stat` | `git_tools.py` | none       | no                    |
| `git_diff_full` | `git_tools.py` | none       | no                    |
| `git_show`      | `git_tools.py` | none       | no                    |
| `git_tags`      | `git_tools.py` | none       | no                    |
| `read_file`     | `file_tools.py`| low        | no                    |
| `write_file`    | `file_tools.py`| medium     | **yes**               |

So **7 tools** are registered: 5 git + 2 file.

---

## Tool registration

Registration is **hardcoded** and happens only in `DocumentationAgent.__init__`
(`app/agents/doc_agent.py`):

```python
self._registry = ToolRegistry()
self._registry.register_many(GIT_TOOLS)
self._registry.register_many(FILE_TOOLS)
self._executor = ToolExecutor(registry=self._registry, require_confirmation=True)
```

- `GIT_TOOLS` (`git_tools.py`) and `FILE_TOOLS` (`file_tools.py`) are module-level lists of `ToolDefinition`.
- There is **no dynamic/plugin discovery**; tools are added only by appending to those lists and re-registering.
- `app/tools/__init__.py` is empty, so there is no package-level aggregator; the agent imports the two lists explicitly.
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

Three regexes are tried, in order, and calls are **deduplicated by tool name** (a `seen`
set; the first occurrence of a name wins):

1. `_TOOL_CALL_RE` — JSON form: `<tool_call>{"name": "...", "args": {...}}</tool_call>`
2. `_HYBRID_CALL_RE` — `<tool_call>name({"k":"v"})</tool_call>` (what some models emit)
3. `_FUNC_CALL_RE` — `<tool_call>name("positional")</tool_call>`; the first quoted string
   becomes `args={"path": ...}`

`has_calls(text)` returns `True` if any of the three regexes match. Malformed JSON, missing
`name`, or empty `args` are silently skipped (the call is dropped, not raised).

⚠️ **Verified limitation**: because deduplication is by name, if the model emits several
`<tool_call>` blocks for the same tool in one turn (e.g. `git_show` for many commits), only
the first is executed. The project’s own test `test_100_tool_calls_parsed` documents the
expectation of 100 calls but currently fails (actual: 1). See **Future improvements**.

---

## Safety model

Safety is layered and enforced inside the tool handlers and the executor, not by the caller.

### Path allowlists (file tools)

`file_tools.py` defines two module-level sets:

- `ALLOWED_READ`: `docs/CHANGELOG.md`, `docs/DEVLOG.md`,
  `docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`, `docs/V3_ROADMAP.md`,
  `CHANGELOG.md`, `DEVLOG.md`, `README.md`, `config.yaml`.
- `ALLOWED_WRITE`: `docs/CHANGELOG.md`, `docs/DEVLOG.md`, `CHANGELOG.md`, `DEVLOG.md`.

`read_file` raises `PermissionError` if `path` not in `ALLOWED_READ`; `write_file` raises
`PermissionError` if `path` not in `ALLOWED_WRITE`. The check is an **exact string match**
— there is no path normalisation or `..` resolution, so traversal/absolute/equivalent paths
are blocked simply because they don’t match the literal entries.  
(Verified by reading the handlers and by `tests/stress_test.py` Security/Adversarial
suites, which pass.)

- `read_file` returns a placeholder string (`file not found: ...`) for an allowed path
  that doesn’t exist yet (it does **not** raise).
- `write_file` creates parent directories (`mkdir(parents=True)`) and overwrites the
  whole file.

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

1. **Path allowlist** (mandatory, enforced in handlers)  
   As described above — the blast radius for file access is the two sets in `file_tools.py`.
   This is the primary v2.4 security boundary and is **always applied** (no flag disables it).

2. **Confirmation gate** (optional, in the executor)  
   `ToolExecutor.__init__(registry, require_confirmation=True)`.  
   In `run()`, before executing, if `self._require_confirmation` and
   `tool.requires_confirmation`:
   - It prints `[Tool] name(args)` (args preview capped at 120 chars),
   - then blocks on `input(" Execute? (y/N): ")`.  
   Answer `"y"` → execute; anything else → returns
   `ToolResult(success=False, error="User declined — tool not executed")`.

   In practice only `write_file` has `requires_confirmation=True`, so it is the only tool
   that prompts. Git tools and `read_file` never prompt. `doc_agent` always constructs the
   executor with `require_confirmation=True`; the test suite disables it by setting
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
| Unknown tool | `ToolExecutor.run` returns `ToolResult(success=False, error="Unknown tool: '<name>'. Available: [...]")` — **never raises**. (Verified by `test_executor_unknown_tool_returns_error_not_crash`) |
| Tool handler raises | `ToolDefinition.execute` catches `PermissionError` → `"Permission denied: <e>"`, any other `Exception` → `str(e)`, both as `ToolResult(success=False)`. (Verified by `test_tool_exception_wrapped_not_propagated`) |
| Git failure | `_run_git` raises `RuntimeError` on non‑zero exit; `git_tags` additionally catches `RuntimeError` and returns `"(no tags found)"`. Other git tools let the error propagate to `execute` and become a `ToolResult` error. (Verified by `test_git_diff_invalid_ref_returns_toolresult_error`) |
| Missing allowed file | `read_file` returns a placeholder string (success, not an error). |
| Truncation | Executor (4096) and git tools (8000) cap output and append a truncation note. |
| Malformed tool‑call text | `parse` silently drops unparsable blocks; `has_calls` keeps the loop going. |
| Max iterations | If the model never stops calling tools, the loop returns the iteration‑limit message instead of looping forever. (Verified by `test_max_iterations_ceiling_enforced`) |

All failures are turned into `<tool_result status="error">` blocks and fed back to the
model, so the loop continues and the model can recover (e.g.
`test_unknown_tool_error_propagated_to_model` shows the agent proceeds to a final answer
after an unknown‑tool error).

---

## ⚠️ Discrepancies found in the tool wiring (verified)

These are real mismatches between the agent’s instructions and what is actually registered:

1. **`append_file` is NOT a usable tool.** The agent’s system prompt repeatedly tells the
   model to “Use `append_file` to add entries. Never use `write_file` on existing docs,”
   and task 3 says “Use `append_file` for both files.” However, in `app/tools/file_tools.py`
   the `append_file` `ToolDefinition` is written **after the `return` statement** inside the
   `append_file()` function body — i.e. it is dead code and is **not** present in
   `FILE_TOOLS`. Consequently:
   - A model that emits `<tool_call>{"name": "append_file", ...}</tool_call>` receives
     `ToolResult(success=False, "Unknown tool: 'append_file'")` and nothing is written.
   - The **only** write tool actually available is `write_file`, which **overwrites the
     entire file** — directly contradicting the system prompt’s “Never use `write_file` on
     existing docs” rule.
   - Tasks 1 and 2 themselves tell the model to “Write the complete updated file with the
     new entry prepended,” which matches `write_file` semantics (overwrite) but conflicts
     with the system‑prompt prohibition. This is an internal contradiction regardless of
     the `append_file` bug.

2. **`git_diff` is referenced but does not exist.** Task 1’s instruction says “Use
   `git_log` and `git_diff` to understand what changed.” There is **no** `git_diff` tool
   registered. The available git diff tools are `git_diff_stat` and `git_diff_full`. A
   model following task 1 literally would call an unknown tool.

3. **Unregistered git helpers.** `git_branch` and `git_status` exist as plain functions in
   `git_tools.py` but are **not** in `GIT_TOOLS`, so the agent cannot call them.

4. **`parse()` dedups by tool name.** `ToolExecutor.parse` keeps a `seen` set of tool
   *names*; if the model emits two calls to the same tool name in one response, only the
   first is executed. This is a real behaviour of the executor that affects the agent (e.g.
   two `git_show` calls for different refs in the same turn would collapse to one).

---

## Future improvements

Derived from the code, its own comments, and verified gaps:

- **Implement or remove `append_file`.** Either implement+register `append_file` (medium
  risk, requires confirmation) or rewrite the prompt to use the tools that actually exist.
- **Fix the parser’s name‑deduplication** (or document it as intended). Consider keying
  `seen` on `(name, args)` or executing all occurrences.
- **Align the system prompt with registered tools.** The prompt is internally
  inconsistent (overwrite vs. append, forbidden `write_file` yet tasks ask for full
  rewrite).
- **Canonicalise paths** instead of exact‑match allowlists. Resolving paths against a
  configured root would be more robust and still safe (v3.0 comment in `file_tools.py`
  already anticipates this).
- **Wire up native function calling (v3.0).** `ToolDefinition.to_openai_schema()` and
  `ToolRegistry.to_openai_schemas()` already exist but are unused; switching to
  `model.generate(tools=[...])` would only require changing the parse step in
  `ToolExecutor`.
- **Make confirmation non‑blocking / pluggable.** Replace the `input()` call with an
  injectable confirmation callback so the executor works headless and in tests without
  monkey‑patching `_require_confirmation`.
- **Register `git_status` / `git_branch` or remove them.** They exist as functions but are
  not in `GIT_TOOLS`.
- **Surface error type to the model.** Today `PermissionError` and generic errors are both
  `ToolResult(success=False)`; only the `"Permission denied:"` prefix distinguishes them. A
  structured `error_type` could help the model respond appropriately.

---

## AI Verification Status

### AI Verified

The following were checked directly against the source files inspected in this task:

- `app/tools/__init__.py` is empty (no exports); callers import `GIT_TOOLS`/`FILE_TOOLS`
  from the submodules directly. (File read; returned empty.)
- The tool system is **prompt‑based**: `ToolExecutor` parses `<tool_call>` tags; no native
  function calling is wired in. (`executor.py`, `doc_agent.py`.)
- Exactly **7 tools** are registered: `git_log`, `git_diff_stat`, `git_diff_full`,
  `git_show`, `git_tags` (`git_tools.py`) and `read_file`, `write_file` (`file_tools.py`).
  Confirmed by importing the modules and listing `FILE_TOOLS`/`GIT_TOOLS`.  
  (`GIT_TOOLS = ['git_log','git_diff_stat','git_diff_full','git_show','git_tags']`,
  `FILE_TOOLS = ['read_file','write_file']`.)
- `write_file` is the only tool with `requires_confirmation=True` (risk medium); all git
  tools are `none` and `read_file` is `low`, none require confirmation. (Confirmed by
  iterating the definitions.)
- Registration happens only in `DocumentationAgent.__init__` via
  `register_many(GIT_TOOLS)` + `register_many(FILE_TOOLS)` + `ToolExecutor(...,
  require_confirmation=True)`. (`doc_agent.py`.)
- `ToolExecutor.MAX_OUTPUT_CHARS = 4096` and `git_tools.DIFF_MAX_CHARS = 8000` cap outputs.
  (`executor.py`, `git_tools.py`.)
- `ToolDefinition.execute` wraps exceptions: `PermissionError` →
  `"Permission denied: ..."`, other `Exception` → `str(e)`, success →
  `ToolResult(success=True, output=str(result))`. (`base.py`.)
- Unknown tool → `ToolResult(success=False, error="Unknown tool: ...")` and never raises.
  (`executor.py`, confirmed by `test_executor_unknown_tool_returns_error_not_crash`.)
- The agent loop returns early when `has_calls` is false; otherwise parses, appends the
  assistant message, runs each call, and injects all results as **one** user message;
  `MAX_ITERATIONS = 12` caps the loop. (`doc_agent.py`, confirmed by
  `test_immediate_response_no_tools`, `test_single_tool_use_then_done`,
  `test_multiple_tools_sequential`, `test_max_iterations_ceiling_enforced`,
  `test_tool_result_injected_into_messages`.)
- File handlers enforce exact‑string allowlists `ALLOWED_READ`/`ALLOWED_WRITE`;
  non‑members raise `PermissionError`; missing allowed files return a placeholder;
  `write_file` overwrites and creates parent dirs. (`file_tools.py`, confirmed by
  Security/Adversarial tests.)
- Git tools use `subprocess.run` with a list (no `shell=True`) and only read‑only
  subcommands. (`git_tools.py`.)
- `to_openai_schemas()` / `ToolRegistry.to_openai_schemas()` are defined but not
  referenced anywhere in `app/` (only in docstrings) — native calling is not active.
  (grep of `app/`.)
- `append_file` does **not** exist in `file_tools.py` (confirmed by grep, by
  `import` — `hasattr(m,'append_file')` is `False` — and by git showing neither the
  working tree nor `HEAD` contains it), yet `doc_agent.py`’s system prompt instructs the
  model to call it.
- `git_status` and `git_branch` are defined as functions in `git_tools.py` but are **not**
  in `GIT_TOOLS` (not registered). (Confirmed by import + list inspection.)
- Parser deduplicates calls by name: 3 `git_show` calls in one response parsed to 1; the
  project test `test_100_tool_calls_parsed` fails (expected 100, actual 1). (Ran
  `tests/stress_test.py`: 45 passed, 1 failed.)
- The on‑disk `file_tools.py` differs from the committed version by two uncommitted
  additions to `ALLOWED_READ` (`docs/CHANGELOG_recovered.md`,
  `docs/DEVLOG_recovered.md`). (`git status` / `git diff`.)

### AI Partially Verified

Supported by code evidence but not fully confirmable in this task:

- **`risk_level` semantics.** The `base.py` docstring classifies
  `none`/`low`/`medium`/`high` and notes `high = "executes code or shell commands
  (run_python) — v3.0+"`. I verified the `risk_level` field and its use in
  `format_for_prompt()` (only `none`/`low` suppress the `[risk]` tag), but no high‑risk
  tool exists in the code, so the `high` tier is unverifiable at runtime — only its
  documentation.
- **v3.0 native function calling.** The comments in `base.py`/`executor.py`/`doc_agent.py`
  describe a future migration to `model.generate(tools=[...])` using the already‑present
  `to_openai_schema()`. The schema methods exist, but I could not verify they work
  end‑to‑end because no code path calls them and no test exercises them.
- **`ALLOWED_READ` contents.** I verified the exact set as it exists on disk, but it is an
  uncommitted local modification vs `HEAD` (2 extra recovered‑file entries). The
  “intended/canonical” allowlist therefore depends on whether those uncommitted lines will
  be kept — intent unverified.
- **Confirmation gate behaviour in production.** I verified the logic by reading
  `executor.py` and by the tests (which disable it). I could not exercise the actual
  `input()` prompt in a real interactive terminal during this task, so the live UX of the
  prompt is supported by code but not observed.

### AI Unverified

Could not be verified within the scope of this task:

- **Real LLM conformance.** I did not run the agent against a live model, so I cannot
  verify that any actual model emits well‑formed `<tool_call>` tags, follows the “one call
  per line / wait for results” instruction, or stops within `MAX_ITERATIONS` in practice.
  The parser’s robustness against adversarially‑formed JSON containing `>` (which could
  interact with the loose closing‑tag regex) was not exercised beyond the project’s own
  tests.
- **Author intent.** Whether the missing `append_file`, the parser name‑deduplication, and
  the prompt contradictions are deliberate known gaps or bugs could not be confirmed — I
  only verified the current code/prompt state, not the developers’ intentions.
- **Runtime in a non‑git or constrained environment.** Git tools’ behaviour when run
  outside a repository in production (only the unit tests’ env was exercised) was not
  verified here.
- **Performance/scaling.** Behaviour with very large repos, extremely large diffs, or many
  iterations under real load was not measured.
- **External systems.** No external services (LLM servers, vector stores, etc.) were
  invoked or inspected; their interaction with the tool layer is out of scope of
  `app/tools/`.

---

## Developer Verification

Status: ☐ Not Reviewed

Reviewer:

**Date:**

# Notes by AI:

d but unused in the current code (forward-compat for v3.0).
format_for_prompt() -> str — builds a human-readable tool list for the system prompt. Tools whose risk_level is not "none"/"low" get a [<risk> risk] suffix (so write_file shows [medium risk]; git tools and read_file do not).
Registered tools (verified)
Tool	Source	risk_level	requires_confirmation
git_log	git_tools.py	none	no
git_diff_stat	git_tools.py	none	no
git_diff_full	git_tools.py	none	no
git_show	git_tools.py	none	no
git_tags	git_tools.py	none	no
read_file	file_tools.py	low	no
write_file	file_tools.py	medium	yes
So 7 tools are registered: 5 git + 2 file.

Tool registration
Registration is hardcoded and happens only in DocumentationAgent.__init__ (app/agents/doc_agent.py):


Apply
self._registry = ToolRegistry()
self._registry.register_many(GIT_TOOLS)
self._registry.register_many(FILE_TOOLS)
self._executor = ToolExecutor(registry=self._registry, require_confirmation=True)
GIT_TOOLS (git_tools.py) and FILE_TOOLS (file_tools.py) are module-level lists of ToolDefinition.
There is no dynamic/plugin discovery; tools are added only by appending to those lists and re-registering.
app/tools/__init__.py is empty, so there is no package-level aggregator; the agent imports the two lists explicitly.
main.py constructs one DocumentationAgent (with a model client) and reuses it for the docs command (and rebuilds it on model switch). main.py does not touch the registry directly.
Execution flow
The agent loop lives in DocumentationAgent.run(task, verbose=True) and is a mini agentic loop:

Build the system prompt by calling self._registry.format_for_prompt() and injecting it into _SYSTEM (which contains the tool list, the <tool_call> format instructions, and the documentation rules).
Initialize messages with system + the user task.
Loop for iteration in range(1, MAX_ITERATIONS + 1) where MAX_ITERATIONS = 12: a. response = self._model.generate(messages); text = response.content. b. if not self._executor.has_calls(text): return text — no tool calls → agent is done; return the final text. (The assistant turn is not appended in this case.) c. calls = self._executor.parse(text) — extract <tool_call> blocks. d. Append the assistant message {"role":"assistant","content":text}. e. For each call, result = self._executor.run(call); collect self._executor.format_result(call, result) into result_blocks. f. Append a single user message {"role":"user","content":"\n\n".join(result_blocks)} containing all results.
If the loop hits MAX_ITERATIONS without stopping, return the string "[Documentation agent reached iteration limit without completing]".
Key points:

Results are batched: all tool results from one model turn are concatenated into ONE user message (not one message per tool).
format_result wraps each result as <tool_result name="..." status="success|error">...</tool_result> so the model can correlate results to calls.
The model is expected to emit ONE <tool_call> per line and wait for results before the next call.
Parsing (ToolExecutor.parse)
Three regexes are tried, in order, and calls are deduplicated by tool name (a seen set; the first occurrence of a name wins):

_TOOL_CALL_RE — JSON form: <tool_call>{"name": "...", "args": {...}}</tool_call>.
_HYBRID_CALL_RE — <tool_call>name({"k":"v"})</tool_call> (what some models emit).
_FUNC_CALL_RE — <tool_call>name("positional")</tool_call>; the first quoted string becomes args={"path": ...}.
has_calls(text) returns True if any of the three regexes match. Malformed JSON, missing name, or empty args are silently skipped (the call is dropped, not raised).

Verified limitation: because deduplication is by name, if the model emits several <tool_call> blocks for the same tool in one turn (e.g. git_show for many commits), only the first is executed. The project's own test test_100_tool_calls_parsed documents the expectation of 100 calls but currently fails (actual: 1). See Future improvements.

Safety model
Safety is layered and enforced inside the tool handlers and the executor, not by the caller:

Path allowlists (file tools). file_tools.py defines two module-level sets:

ALLOWED_READ: docs/CHANGELOG.md, docs/DEVLOG.md, docs/CHANGELOG_recovered.md, docs/DEVLOG_recovered.md, docs/V3_ROADMAP.md, CHANGELOG.md, DEVLOG.md, README.md, config.yaml.
ALLOWED_WRITE: docs/CHANGELOG.md, docs/DEVLOG.md, CHANGELOG.md, DEVLOG.md.
read_file raises PermissionError if path not in ALLOWED_READ; write_file raises PermissionError if path not in ALLOWED_WRITE. The check is an exact string match — there is no path normalization or .. resolution, so traversal/absolute/equivalent paths are blocked simply because they don't match the literal entries. (Verified by reading the handlers and by tests/stress_test.py Security/Adversarial suites, which pass.)
read_file returns a placeholder string (file not found: ...) for an allowed path that doesn't exist yet (it does not raise).
write_file creates parent directories (mkdir(parents=True)) and overwrites the whole file.
Read-only git (git tools). Every git tool calls only read subcommands via subprocess.run(["git", ...], capture_output=True, text=True) — log, diff, status, show, tag, rev-parse. There is no git commit/checkout/push/reset, so the repo cannot be mutated by the agent. shell=True is not used (args are a list → no shell injection).

Output truncation. Two caps prevent context-window overflow:

ToolExecutor.MAX_OUTPUT_CHARS = 4096 — any successful tool output longer than this is truncated with a "(N chars trimmed)" note.
git_tools.DIFF_MAX_CHARS = 8000 — git_diff_full and git_show truncate their own output.
No raw exceptions escape. ToolDefinition.execute catches everything and returns a ToolResult. The agent loop only ever sees ToolResult objects.

Permission model
There are two independent permission layers:

Path allowlist (mandatory, enforced in handlers). As above — the blast radius for file access is the two sets in file_tools.py. This is the primary v2.4 security boundary and is always applied (no flag disables it).

Confirmation gate (optional, in the executor). ToolExecutor.__init__(registry, require_confirmation=True). In run(), before executing, if self._require_confirmation and tool.requires_confirmation:

It prints [Tool] name(args) (args preview capped at 120 chars),
then blocks on input(" Execute? (y/N): ").
Answer "y" → execute; anything else → returns ToolResult(success=False, error="User declined — tool not executed").
In practice only write_file has requires_confirmation=True, so it is the only tool that prompts. Git tools and read_file never prompt. doc_agent always constructs the executor with require_confirmation=True; the test suite disables it by setting _executor._require_confirmation = False.

Caveat: the confirmation uses a blocking input() on stdin. It works in the interactive docs flow in main.py, but would block in any non-interactive/headless deployment unless require_confirmation is disabled.

risk_level (none/low/medium/high) is metadata only — it drives the [risk] label in format_for_prompt() but is not itself a gate. The docstring in base.py defines high as "executes code or shell commands (run_python) — v3.0+", but no high-risk tool exists in the current code.

Error handling
Unknown tool: ToolExecutor.run returns ToolResult(success=False, error="Unknown tool: '<name>'. Available: [...]") — never raises. (Verified by test_executor_unknown_tool_returns_error_not_crash.)
Tool raises: ToolDefinition.execute catches PermissionError → "Permission denied: <e>", and any other Exception → str(e), both as ToolResult(success=False). (Verified by test_tool_exception_wrapped_not_propagated.)
Git failure: _run_git raises RuntimeError on non-zero exit; git_tags additionally catches RuntimeError and returns "(no tags found)". Other git tools let the error propagate to execute and become a ToolResult error. (Verified by test_git_diff_invalid_ref_returns_toolresult_error.)
Missing allowed file: read_file returns a placeholder string (success, not an error).
Truncation: both the executor (4096) and git tools (8000) cap output and append a truncation note.
Malformed tool-call text: parse silently drops unparseable blocks; has_calls keeps the loop going.
Max iterations: if the model never stops calling tools, the loop returns the iteration-limit message instead of looping forever. (Verified by test_max_iterations_ceiling_enforced.)
All failures are turned into <tool_result status="error"> blocks and fed back to the model, so the loop continues and the model can recover (e.g. test_unknown_tool_error_propagated_to_model shows the agent proceeds to a final answer after an unknown-tool error).

Future improvements
Derived from the code, its own comments, and verified gaps above:

Implement or remove append_file. app/agents/doc_agent.py's system prompt repeatedly instructs the model to call append_file ("Use append_file to add entries", "append_file → adds new content at end of existing file. Use this always.", workflow steps 9–10, task "3"), but no append_file function or ToolDefinition exists in file_tools.py. A model following the prompt will receive Unknown tool: 'append_file'. Either implement+register append_file (medium risk, requires confirmation) or rewrite the prompt to use the tools that actually exist.
Fix the parser's name-deduplication (or document it as intended). parse() collapses multiple same-name calls to the first, so a single response asking for git_show on many commits only runs one. The existing test test_100_tool_calls_parsed currently fails (expects 100, gets 1). Consider keying seen on (name, args) or executing all occurrences.
Align the system prompt with registered tools. Tasks "1" (changelog) and "2" (devlog) tell the model to "Write the complete updated file with the new entry prepended" (i.e. write_file overwrite), while the FILE WRITING RULES say "write_file → overwrites entire file. Never use on existing docs." and steer to append_file (which doesn't exist). The prompt is internally inconsistent.
Canonicalize paths instead of exact-match allowlists. The allowlist is an exact string compare; docs/./CHANGELOG.md or an absolute/normalized equivalent of an allowed file is rejected even though it resolves to an allowed target. Resolving paths against a configured root would be more robust and still safe. (The v3.0 comment in file_tools.py already anticipates "a proper permission system with user-configurable rules".)
Wire up native function calling (v3.0). ToolDefinition.to_openai_schema() and ToolRegistry.to_openai_schemas() already exist but are unused; moving to model.generate(tools=[...]) would only require changing the parse step in ToolExecutor, per the source comments.
Make confirmation non-blocking / pluggable. Replace the input() call with an injectable confirmation callback so the executor works headless and in tests without monkey-patching _require_confirmation.
Register git_status / git_branch or remove them. These functions exist in git_tools.py but are not in GIT_TOOLS, so they are unusable as tools (only directly callable from Python). Decide whether to expose them.
Surface error type to the model. Today PermissionError and generic errors are both ToolResult(success=False); only the "Permission denied:" prefix distinguishes them. A structured error_type could help the model respond appropriately.
AI Verification Status
AI Verified
app/tools/__init__.py is empty (no exports); callers import GIT_TOOLS/FILE_TOOLS from the submodules directly. (Read the file; it returned empty.)
The tool system is prompt-based: ToolExecutor parses <tool_call> tags; no native function calling is wired in. (executor.py, doc_agent.py.)
Exactly 7 tools are registered: git_log, git_diff_stat, git_diff_full, git_show, git_tags (git_tools.py) and read_file, write_file (file_tools.py). Confirmed by importing the modules and listing FILE_TOOLS/GIT_TOOLS. (GIT_TOOLS = ['git_log','git_diff_stat','git_diff_full','git_show','git_tags'], FILE_TOOLS = ['read_file','write_file'].)
write_file is the only tool with requires_confirmation=True (risk medium); all git tools are none and read_file is low, none require confirmation. (Confirmed by iterating the definitions.)
Registration happens only in DocumentationAgent.__init__ via register_many(GIT_TOOLS) + register_many(FILE_TOOLS) + ToolExecutor(..., require_confirmation=True). (doc_agent.py.)
ToolExecutor.MAX_OUTPUT_CHARS = 4096 and git_tools.DIFF_MAX_CHARS = 8000 cap outputs. (executor.py, git_tools.py.)
ToolDefinition.execute wraps exceptions: PermissionError → "Permission denied: ...", other Exception → str(e), success → ToolResult(success=True, output=str(result)). (base.py.)
Unknown tool → ToolResult(success=False, error="Unknown tool: ...") and never raises. (executor.py, confirmed by test_executor_unknown_tool_returns_error_not_crash.)
The agent loop returns early when has_calls is false; otherwise parses, appends the assistant message, runs each call, and injects all results as ONE user message; MAX_ITERATIONS = 12 caps the loop. (doc_agent.py, confirmed by test_immediate_response_no_tools, test_single_tool_use_then_done, test_multiple_tools_sequential, test_max_iterations_ceiling_enforced, test_tool_result_injected_into_messages.)
File handlers enforce exact-string allowlists ALLOWED_READ/ALLOWED_WRITE; non-members raise PermissionError; missing allowed files return a placeholder; write_file overwrites and creates parent dirs. (file_tools.py, confirmed by Security/Adversarial tests.)
Git tools use subprocess.run with a list (no shell=True) and only read-only subcommands. (git_tools.py.)
to_openai_schemas() / ToolRegistry.to_openai_schemas() are defined but not referenced anywhere in app/ (only in docstrings) — native calling is not active. (grep of app/.)
append_file does not exist in file_tools.py (confirmed by grep, by python import — hasattr(m,'append_file') is False — and by git showing neither the working tree nor HEAD contains it), yet doc_agent.py's system prompt instructs the model to call it.
git_status and git_branch are defined as functions in git_tools.py but are not in GIT_TOOLS (not registered). (Confirmed by import + list inspection.)
Parser deduplicates calls by name: 3 git_show calls in one response parsed to 1; the project test test_100_tool_calls_parsed fails (expected 100, actual 1). (Ran tests/stress_test.py: 45 passed, 1 failed.)
The on-disk file_tools.py differs from the committed version by two uncommitted additions to ALLOWED_READ (docs/CHANGELOG_recovered.md, docs/DEVLOG_recovered.md). (git status / git diff.)
AI Partially Verified
risk_level semantics. The base.py docstring classifies none/low/medium/high and notes high = "executes code or shell commands (run_python) — v3.0+". I verified the risk_level field and its use in format_for_prompt() (only none/low suppress the [risk] tag), but no high-risk tool exists in the code, so the high tier is unverifiable at runtime — only its documentation.
v3.0 native function calling. The comments in base.py/executor.py/doc_agent.py describe a future migration to model.generate(tools=[...]) using the already-present to_openai_schema(). The schema methods exist, but I could not verify they work end-to-end because no code path calls them and no test exercises them.
ALLOWED_READ contents. I verified the exact set as it exists on disk, but it is an uncommitted local modification vs HEAD (2 extra recovered-file entries). The "intended/canonical" allowlist therefore depends on whether those uncommitted lines will be kept — intent unverified.
Confirmation gate behavior in production. I verified the logic by reading executor.py and by the tests (which disable it). I could not exercise the actual input() prompt in a real interactive terminal during this task, so the live UX of the prompt is supported by code but not observed.
AI Unverified
Real LLM conformance. I did not run the agent against a live model, so I cannot verify that any actual model emits well-formed <tool_call> tags, follows the "one call per line / wait for results" instruction, or stops within MAX_ITERATIONS in practice. The parser's robustness against adversarially-formed JSON containing > (which could interact with the loose closing-tag regex) was not exercised beyond the project's own tests.
Author intent. Whether the missing append_file, the parser name-deduplication, and the prompt contradictions are deliberate known gaps or bugs could not be confirmed — I only verified the current code/prompt state, not the developers' intentions.
Runtime in a non-git or constrained environment. Git tools' behavior when run outside a repository in production (only the unit tests' env was exercised) was not verified here.
Performance/scaling. Behavior with very large repos, extremely large diffs, or many iterations under real load was not measured.
External systems. No external services (LLM servers, vector stores, etc.) were invoked or inspected; their interaction with the tool layer is out of scope of app/tools/.
Developer Verification
Status: ☐ Not Reviewed
Reviewer: 
# JARVIS Documentation Agent — Tool System (`app/tools/`)

> Source-verified documentation. Every claim below was checked against the code in
> `app/tools/` (`base.py`, `executor.py`, `file_tools.py`, `git_tools.py`, `__init__.py`)
> and the consuming code in `app/agents/doc_agent.py` and `app/main.py`, plus the
> project's own `tests/stress_test.py`. Verification details are in
> **AI Verification Status** at the end. Where the source contradicts itself, that is
> called out explicitly.

## Tool architecture

The tool system is a **prompt-based tool-calling framework** (not native model
function calling). The model emits `<tool_call>` tags in its text; the executor parses
and runs them. It is composed of four source files plus an empty package init:

- `base.py` — three building blocks: `ToolResult`, `ToolDefinition`, `ToolRegistry`.
- `executor.py` — `ToolExecutor`: parses `<tool_call>` tags out of model text and runs them.
- `file_tools.py` — file read/write handlers and the `FILE_TOOLS` list.
- `git_tools.py` — read-only git handlers and the `GIT_TOOLS` list.
- `__init__.py` — **empty**; it exports nothing. Callers import directly from the
  submodules (`from app.tools.file_tools import FILE_TOOLS`, etc.).

### Core data types (`base.py`)

`ToolResult` (dataclass) — the uniform return value of every tool.
- Fields: `success: bool`, `output: str`, `error: str = ""`.
- `__str__`: returns `output` on success, else `"Error: {error}"`.
- `__bool__`: returns `success` (a result is truthy iff it succeeded).

`ToolDefinition` (dataclass) — one tool's metadata + behavior.
- Fields: `name`, `description`, `parameters` (a JSON Schema `dict`), `handler: Callable`,
  plus `risk_level: str = "low"` and `requires_confirmation: bool = False`.
- `execute(**kwargs) -> ToolResult`: calls `handler`, wrapping any exception in a
  `ToolResult(success=False, ...)`. `PermissionError` becomes `"Permission denied: ..."`;
  any other `Exception` becomes `error=str(e)`. On success returns
  `ToolResult(success=True, output=str(result))`.
- `to_openai_schema() -> dict`: returns an OpenAI-style
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

### Registered tools (verified)

| Tool            | Source        | risk_level | requires_confirmation |
|-----------------|---------------|------------|-----------------------|
| `git_log`       | git_tools.py  | none       | no                    |
| `git_diff_stat` | git_tools.py  | none       | no                    |
| `git_diff_full` | git_tools.py  | none       | no                    |
| `git_show`      | git_tools.py  | none       | no                    |
| `git_tags`      | git_tools.py  | none       | no                    |
| `read_file`     | file_tools.py | low        | no                    |
| `write_file`    | file_tools.py | medium     | **yes**               |

So **7 tools** are registered: 5 git + 2 file.

## Tool registration

Registration is **hardcoded** and happens only in `DocumentationAgent.__init__`
(`app/agents/doc_agent.py`):

```python
self._registry# JARVIS Documentation Agent — Tool System (`app/tools/`)

> Source-verified documentation. Every claim below was checked against the code in
> `app/tools/` (`base.py`, `executor.py`, `file_tools.py`, `git_tools.py`, `__init__.py`)
> and the consuming code in `app/agents/doc_agent.py` and `app/main.py`, plus the
> project's own `tests/stress_test.py`. Verification details are in
> **AI Verification Status** at the end. Where the source contradicts itself, that is
> called out explicitly.

## Tool architecture

The tool system is a **prompt-based tool-calling framework** (not native model
function calling). The model emits `<tool_call>` tags in its text; the executor parses
and runs them. It is composed of four source files plus an empty package init:

- `base.py` — three building blocks: `ToolResult`, `ToolDefinition`, `ToolRegistry`.
- `executor.py` — `ToolExecutor`: parses `<tool_call>` tags out of model text and runs them.
- `file_tools.py` — file read/write handlers and the `FILE_TOOLS` list.
- `git_tools.py` — read-only git handlers and the `GIT_TOOLS` list.
- `__init__.py` — **empty**; it exports nothing. Callers import directly from the
  submodules (`from app.tools.file_tools import FILE_TOOLS`, etc.).

### Core data types (`base.py`)

`ToolResult` (dataclass) — the uniform return value of every tool.
- Fields: `success: bool`, `output: str`, `error: str = ""`.
- `__str__`: returns `output` on success, else `"Error: {error}"`.
- `__bool__`: returns `success` (a result is truthy iff it succeeded).

`ToolDefinition` (dataclass) — one tool's metadata + behavior.
- Fields: `name`, `description`, `parameters` (a JSON Schema `dict`), `handler: Callable`,
  plus `risk_level: str = "low"` and `requires_confirmation: bool = False`.
- `execute(**kwargs) -> ToolResult`: calls `handler`, wrapping any exception in a
  `ToolResult(success=False, ...)`. `PermissionError` becomes `"Permission denied: ..."`;
  any other `Exception` becomes `error=str(e)`. On success returns
  `ToolResult(success=True, output=str(result))`.
- `to_openai_schema() -> dict`: returns an OpenAI-style
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

### Registered tools (verified)

| Tool            | Source        | risk_level | requires_confirmation |
|-----------------|---------------|------------|-----------------------|
| `git_log`       | git_tools.py  | none       | no                    |
| `git_diff_stat` | git_tools.py  | none       | no                    |
| `git_diff_full` | git_tools.py  | none       | no                    |
| `git_show`      | git_tools.py  | none       | no                    |
| `git_tags`      | git_tools.py  | none       | no                    |
| `read_file`     | file_tools.py | low        | no                    |
| `write_file`    | file_tools.py | medium     | **yes**               |

So **7 tools** are registered: 5 git + 2 file.

## Tool registration

Registration is **hardcoded** and happens only in `DocumentationAgent.__init__`
(`app/agents/doc_agent.py`):

```python
self._registryDate: Notes:
