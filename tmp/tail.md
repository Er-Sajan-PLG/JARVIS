## 7. Prompt System Evolution (deep dive)

The prompt layer went from "one hardwired persona string inside the client" to "a stateless persona constant + a `PromptBuilder` that assembles dynamic context into a single system message." Two things are worth separating: **what the persona says** (`SYSTEM_PROMPT`, static) and **how dynamic memory/context gets injected** (`PromptBuilder`, per-turn).

### 7.1 The system prompt (`app/config/prompt.py`)

- **Current form:** a single module-level constant `SYSTEM_PROMPT` — *"You are Jarvis—a calm, sharp, and occasionally witty digital architect."* — followed by six numbered protocols: **(1) Core Identity**, **(2) STEM & Teaching**, **(3) Automation & Agents**, **(4) Daily Operations & Content**, **(5) Core Constraints**, **(6) Execution**.
- **It is static.** The string is hardcoded; it does **not** rewrite itself per turn, and there is no user-tunable persona in `config.yaml`/`settings.py`. Dynamic context (facts, past exchanges) arrives only via the `PromptBuilder`, never by mutating `SYSTEM_PROMPT`.
- **Evolution:** v0.1 carried the system prompt inline inside `OllamaClient`. v0.3 ("Making prompt" / `39b3d5b`) pulled it into a dedicated `app/config/prompts.py` file. The v2.0.0 overhaul (`8519f65`) renamed it to the current singular `app/config/prompt.py` and handed assembly to `PromptBuilder`.

### 7.2 Prompt assembly / building blocks (`app/prompt/builder.py`)

`PromptBuilder` exists to assemble the message list in a **fixed, correct order**:

1. **System content** = a single `role: "system"` message built by joining, in this order:
   - the `SYSTEM_PROMPT`,
   - `past_exchanges` formatted as a `## Relevant Past Exchanges` block (episodic context),
   - `memories` formatted as a `## Known User Facts` block (`- [category] memory_type: value`).
2. **Conversation history** (recent `user`/`assistant` turns).
3. **Current user prompt** (appended only if not already the last conversation message).

The docstring is explicit: *"Combines system prompt and memories into a SINGLE system message for maximum model compatibility."* `build_with_stats()` returns `(messages, stats_dict)` where the only token estimate is `len(self.system_prompt) // 4` (a rough proxy; it does **not** account for injected memory/exchange length).

### 7.3 Prompt conventions that stabilized

- **One system message.** System prompt + past exchanges + facts are concatenated into a single `system` role, not spread across `system`/`developer`/multiple roles — this is what keeps behavior consistent across `llama.cpp`, Ollama, and OpenRouter backends.
- **Episodic before semantic.** Injected `past_exchanges` appear *before* `Known User Facts` (v2.2.0 context-optimization change), so conversational recency is established ahead of long-term facts.
- **Tool-call protocol (agent).** The documentation agent emits `<tool_call>{"name": "...", "args": {...}}</tool_call>` tags; results are wrapped and injected as `<tool_result name="..." status="...">...</tool_result>` blocks (see §8).

### 7.4 What the prompt system *cannot* yet do (verified gaps)

- `SYSTEM_PROMPT` is a hardcoded constant — no per-turn self-rewrite, no config-driven persona, no "developer vs system" role separation.
- `PromptBuilder.build_with_stats()` only estimates system tokens from the persona string; it has **no budget awareness** of the memory/exchange blocks it injects (real context pressure is managed downstream by `ContextWindowManager`, not the builder).
- The agent's `_SYSTEM` instructs the model to use `append_file`, but `append_file` is **dead/unregistered** (§8.3) — the prompt tells the model to call a tool that does not exist in the registry.
- No prompt caching, no templated variable substitution beyond `{tools_section}` in the agent system prompt.

---

## 8. Tool System Evolution (deep dive)

### 8.1 Before tools: no external action

From v0.1 through v2.2.1 JARVIS could only *talk*: it read context, reasoned, and replied. It had no filesystem or git access from the model's side, and all project logging (CHANGELOG/DEVLOG) was done manually by the developer. The agentic tool system is entirely a v2.4.0 working-tree addition.

### 8.2 The framework (`app/tools/base.py`, `app/tools/executor.py`)

Three classes define the tool contract:

- **`ToolResult`** — every tool returns `success`/`output`/`error`; exceptions are caught and wrapped here so the agent loop never sees a raw exception.
- **`ToolDefinition`** — `name`, `description`, `parameters` (JSON Schema), `handler`, plus `risk_level` (`none`/`low`/`medium`/`high`) and `requires_confirmation`. `to_openai_schema()` already emits an OpenAI-compatible function schema, ready for the planned v3.0 native-calling migration.
- **`ToolRegistry`** — `register`/`register_many`/`get`/`all`; exposes `format_for_prompt()` (human-readable list injected into the agent system prompt) and `to_openai_schemas()` (for native calling).

`ToolExecutor` is the runtime engine:

- **Parsing:** three regexes — `_TOOL_CALL_RE` (JSON: `{"name":..,"args":..}`), `_HYBRID_CALL_RE` (`name({"ref":..})`), `_FUNC_CALL_RE` (positional: `read_file("path")`). `has_calls()` checks any of the three.
- **Dedup:** `parse()` tracks a `seen` set and collapses **by tool name**, so multiple same-named calls in one turn reduce to one.
- **Output cap:** `MAX_OUTPUT_CHARS = 4096` — tool output longer than this is truncated before injection (a huge `read_file` would otherwise blow the context).
- **Confirmation gate:** if `require_confirmation=True` *and* the tool's `requires_confirmation=True`, the executor blocks on an `input("  Execute? (y/N): ")` prompt.
- **Safety:** all tool failures become a `ToolResult(success=False)`, never an exception into the loop.

### 8.3 The tools themselves (verified)

Registered tools = **7** (the only ones in `GIT_TOOLS` + `FILE_TOOLS`):

| Tool | Source | risk | confirmation |
|---|---|---|---|
| `git_log` | git_tools | none | no |
| `git_diff_stat` | git_tools | none | no |
| `git_diff_full` | git_tools | none | no |
| `git_show` | git_tools | none | no |
| `git_tags` | git_tools | none | no |
| `read_file` | file_tools | low | no |
| `write_file` | file_tools | medium | **yes (the only one)** |

**Defined but NOT registered:**
- `git_status`, `git_branch` — full functions exist in `git_tools.py` but are **absent from the `GIT_TOOLS` list**, so the executor returns "Unknown tool" for them.
- `append_file` — implemented in `file_tools.py`, but its `ToolDefinition` is written *after a `return` statement* inside the `append_file()` function body, making it **dead code**; `FILE_TOOLS` also omits it.

**Referenced but absent:** the agent's `_SYSTEM` prompt tells the model to use `append_file` (dead) and mentions `git_diff` / `git_status` / `git_branch`, none of which are registered (only `git_diff_stat`/`git_diff_full` exist).

**Security model:** `file_tools.py` enforces everything through two allowlist sets — `ALLOWED_READ` (`docs/CHANGELOG.md`, `docs/DEVLOG.md`, `docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`, `docs/V3_ROADMAP.md`, `CHANGELOG.md`, `DEVLOG.md`, `README.md`, `config.yaml`) and `ALLOWED_WRITE` (`docs/CHANGELOG.md`, `docs/DEVLOG.md`, `CHANGELOG.md`, `DEVLOG.md`). The docstring states the design intent plainly: *"Blast radius is defined here, not enforced by the caller."* Git tools use `subprocess.run([...])` with an argument **list** (never `shell=True`), so they are shell-injection-safe. `DIFF_MAX_CHARS = 8000` caps diff output.

### 8.4 Execution flow (the mini-agentic loop)

The loop (driven by `DocumentationAgent.run`, §9) is: `generate` → `has_calls?` → `parse` → `run` each call → `format_result` → **inject all results as a single `user` message** → loop. The executor itself has no iteration ceiling; `MAX_ITERATIONS = 12` lives in the agent as a safety rail.

### 8.5 What the tool system *cannot* yet do (verified gaps)

- `parse()` dedups **by name**, so N parallel calls to the same tool in one response collapse to 1 (a stress test expecting 100 gets 1).
- `append_file` is dead → the agent cannot *append*; it must `write_file` (overwrite) despite being told to append.
- `git_status`/`git_branch` are unregistered despite existing implementations.
- Confirmation is a **blocking `input()`** — there is no headless/non-interactive approval path.
- Args are only JSON-parsed; there is no schema validation beyond what the handler itself does, and handler exceptions are silently folded into `ToolResult`.

---

## 9. Agent System Evolution (deep dive)

### 9.1 No agents (v0.1 – v2.2.1)

For the entire v0.x and v2.0.0–v2.2.1 history, "agency" meant the single `while` loop in `main.py` calling the model + memory. There was **no agent class, no orchestration layer** — `app/agents/` held only an empty `__init__.py`.

### 9.2 The first (and only) agent: `DocumentationAgent` (v2.2.1 committed; tool/agent code lives in the v2.4.0 working tree)

`app/agents/doc_agent.py` is the sole agent. Its job: read git history and existing docs, then generate `CHANGELOG`/`DEVLOG` entries that match the established format.

- Registers `GIT_TOOLS` + `FILE_TOOLS` into a `ToolRegistry`, wraps it in `ToolExecutor(require_confirmation=True)`.
- `MAX_ITERATIONS = 12` safety ceiling.
- `_SYSTEM` is a long, format-rich prompt: it injects `tools_section` (from `registry.format_for_prompt()`), defines the `<tool_call>` format, spells out CHANGELOG/DEVLOG entry rules, the full-history workflow (git_log → git_show per commit → read recovered/ current docs → append), and versioning notes (2-digit early, 3-digit from v2.0.0, the v1.x→v2.0.0 rewrite jump).

### 9.3 Why prompt-based (design rationale)

The docstring is explicit about *not* waiting for v3.0 native calling:
- Not all local models support `tool_calls` in responses.
- Prompt-based `<tool_call>` tags work on **any** instruction-following model.
- The tag format is unambiguous and easy to parse.
- The **same interface** is retained — when v3.0 ships native function calling, *only* `ModelClient.generate()` / `ToolExecutor.parse()` change; `ToolRegistry` and the loop stay.

### 9.4 Agent evolution — gaps and the v3.0 horizon (verified)

- **Prompt/registry mismatch:** `_SYSTEM` tells the model to use `append_file` (dead) and `git_diff`/`git_status`/`git_branch` (unregistered). A model that obeys the prompt literally calls missing tools and stalls.
- **Only one agent exists**; `app/agents/__init__.py` is still empty.
- The loop is generic — scoping to "documentation" is purely the `_SYSTEM` text + which tools are registered.
- v3.0 path is already paved: `ToolDefinition.to_openai_schema()` exists; `ToolExecutor.parse()` is the only piece that swaps from text tags to structured JSON.

---

## 10. Configuration Evolution (deep dive)

### 10.1 Hardcoded era (v0.1 – v1.1)

Configuration was inline constants — model names, paths, and behavior lived directly in `settings.py` / client modules. There was no external file and no override mechanism.

### 10.2 Centralized dataclass singleton (v2.0)

`app/config/settings.py` became a set of `@dataclass` containers — `ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, `PathsConfig` — composed under a master `Settings`. `get_settings()` is a **thread-safe singleton** using `threading.Lock` with double-checked locking; `reset_settings()` exists for tests; `get_default_model()` lazily reads `settings.default_model`.

### 10.3 External YAML + dynamic router (v2.1)

`Settings.load(path="config.yaml")` reads YAML and overrides the dataclass defaults; if the file is missing it returns `cls()` (hardcoded defaults). Models and the `ModelRouter` are built **dynamically from config** (`TaskType(role)` bridges YAML role strings to the enum). `.env` is loaded via `load_dotenv()`, and API keys are resolved as `env:VAR` strings inside `ModelFactory`.

### 10.4 What config *cannot* yet do (verified gaps)

These are coupled to the model layer (§6.4) and surface **only under the shipped Python defaults** (no `config.yaml`):

- Only the **`general`** model resolves (`llama-3.2-3b-instruct-q4_k_m.gguf` on llama.cpp). The `local` profile's `code`/`reasoning`/`docs`/`stem` keys point to model entries that **don't exist** in the default `models` dict, so they're skipped and every routed prompt falls back to `general`.
- The **`autocomplete`** client (`qwen2.5-1.5b` on port 8082) is instantiated but **never mapped** to a router/task type → dead under defaults.
- The **`cloud`** profile maps everything to a `"cloud"` key absent from defaults → an empty router with no default; `switcher.switch("cloud")` returns `True` but any `route()` would raise `ValueError`.
- A **dead fallback** in `main.py`: `if selected_model is None: selected_model = router.default_model` references an undefined `router` (the object is `switcher.router`) and would raise `NameError` if reached; it is currently unreachable because `route()` never returns `None`.

A real `config.yaml` is clearly expected (the switcher, router, and `NEW_DEVLOG.md` all assume the `code`/`reasoning`/`docs`/`stem`/`cloud` entries).

---

## 11. Directory Evolution

The package skeleton predates almost all of its contents. Every subdirectory was created as an **empty stub package** in the initial v0.1 commit (`e13ee67`), then filled in across later milestones:

- **v0.1 (`e13ee67`):** `app/` with `__init__.py`, `main.py`, `config/settings.py`, `models/ollama_client.py`, and empty stub packages `agents/`, `tools/`, `api/`, `brain/`, `memory/` (each just an `__init__.py`).
- **v2.0.0 (`8519f65`):** the modular rewrite added real subpackages — `prompt/` (`builder.py`), `context/` (`manager.py`), `conversation/` (`manager.py`) — plus `memory/`'s analytical modules (`retrieval.py`, `ranking.py`, `store.py`, `rules.py`, `schema.py`, `vector_retriever.py`, `hybrid_retriever.py`, `conversation_store.py`).
- **v2.2.1 → v2.4.0 working tree (`891fe4b` + staged):** `agents/doc_agent.py` and `tools/{base,executor,file_tools,git_tools}.py` were populated. `api/` and `brain/` **remain empty stubs** — `requirements.txt` lists `fastapi`/`uvicorn`/`starlette`, but no HTTP server exists; they are roadmap-only.

**Current layout (verified via `ls`):**

```
app/
  __init__.py, main.py
  agents/      __init__.py (empty), doc_agent.py
  api/         __init__.py (empty)
  brain/       __init__.py (empty)
  config/      __init__.py, prompt.py, settings.py, version.py
  context/     __init__.py, manager.py
  conversation/ __init__.py, manager.py
  memory/      __init__.py, conversation_store.py, fact_extractor.py,
               hybrid_retriever.py, manager.py, ranking.py, retrieval.py,
               rules.py, schema.py, store.py, vector_retriever.py
  models/      __init__.py, client.py, factory.py, llamacpp_client.py,
               ollama_client.py, openrouter_client.py, router.py, switcher.py
  prompt/      __init__.py, builder.py
  tools/       __init__.py, base.py, executor.py, file_tools.py, git_tools.py
  utils/       __init__.py, server_manager.py, tokenizer.py
```

**Version file:** `app/config/version.py` currently reads `"v.2.4.0"` — note the **malformed extra dot** (should be `v2.4.0`); the last *committed* version is `891fe4b` = v2.2.1.

---

## 12. Major Refactors

- **v2.0.0 (`8519f65`) — the rewrite.** Monolith → Protocol-based modular subsystems. `MemoryManager` was split into `MemoryStore` (CRUD/JSON), `CandidateRetriever`, and `MemoryRanker`. New `ContextWindowManager` (pair-trim), `PromptBuilder` (single system message), `ModelRouter` (score-based), and the tokenizer fallback chain were introduced. The main loop was reordered to **extract/store facts before retrieval**. `typing.Protocol` was chosen over `ABC` for every boundary. A staging commit `63addf6` ("before big change in memory management") preceded it.
- **v2.1.0 (`df45be2`) — multi-backend + streaming + external config.** `ModelFactory`, callback-based `stream`/`on_token`, and `config.yaml` loading via `Settings.load()`; the router became config-driven.
- **v2.2.0 (`b2c2211`) — semantic memory.** ChromaDB `VectorRetriever`, `HybridRetriever` (keyword + vector), and `ConversationVectorStore` (episodic). `nomic-embed-text` via `OllamaEmbeddingFunction`.
- **v2.2.1 / v2.4.0 working tree (`891fe4b` + staged) — agentic tool system.** `ToolRegistry`/`ToolExecutor` and `DocumentationAgent`; `OpenRouterClient` + `ModelSwitcher` for runtime profile switching. (The committed `891fe4b` message is "Documentation agent wired, package structure fixed"; the substantive tool/agent modules are staged in the working tree under v2.4.0.)

---

## 13. Current Design Philosophy

These are the eight principles from §1.3 — *"stated explicitly in `docs/DEVLOG.md` (v2.0 session notes) and remain visible in code"* — restated here because every new subsystem (tools, agents, config) is expected to honor them:

1. **One clean interface per subsystem, implementation hidden.** `ModelClient` (Protocol), `CandidateRetriever` (Protocol), `MemoryStore`, `MemoryRanker`, `ContextWindowManager`, `PromptBuilder`, and now `ToolRegistry`/`ToolExecutor` are all swappable behind a narrow contract. This is *why* ChromaDB could drop in for keyword retrieval, or OpenRouter for llama.cpp, with no caller changes.
2. **Protocol, not ABC, for boundaries.** Structural subtyping (`typing.Protocol`) lets third-party classes satisfy an interface without inheriting — e.g. `OllamaClient` and `LlamaCppClient` satisfy `ModelClient` without a shared base class.
3. **Memory-first ordering in the main loop.** Facts are **extracted and stored before retrieval**, so a fact stated this turn is available to this turn's context.
4. **Hybrid retrieval.** Keyword catches exact matches; vector catches semantic ones. Neither alone is sufficient.
5. **Trim by user/assistant pairs, never individual messages**, so an exchange is never broken in half (`ContextWindowManager`).
6. **Combine system prompt + memories into ONE `system` message** for cross-backend compatibility.
7. **Prompt-based tool calling** (not native function calling yet) — `<tool_call>` tags parsed by an executor; `to_openai_schema()` already exists for the v3.0 migration.
8. **Centralized, overridable configuration.** `app/config/settings.py` dataclasses + optional `config.yaml` + `.env` (`load_dotenv`).

A ninth, tool-specific corollary is visible in `file_tools.py`: **the blast radius is defined by the allowlists, not by the caller** — security is enforced at the tool boundary, not hoped for upstream.

---

## 14. Important Invariants

These are load-bearing properties the architecture depends on. Each lists its current status (✅ upheld / ⚠️ currently violated) as verified against source.

1. **Single system message.** `PromptBuilder` concatenates persona + past exchanges + facts into exactly one `role: "system"` message. ✅ Upheld. Breaking it (splitting into multiple system/developer roles) risks divergent behavior across backends.
2. **Memory-first loop ordering.** Facts are stored *before* retrieval each turn. ✅ Upheld in `main.py`. Inverting it would make this-turn facts invisible to this-turn context (the original v2.0.0 bug).
3. **JSON is the source of truth for facts.** The `jarvis-memories` ChromaDB collection is **rebuilt from `memories.json` on startup**; ChromaDB vectors are a derived index, not authoritative. ✅ Upheld. Implication: deleting `memories.json` loses facts even if the vector store persists. ⚠️ Correlary currently violated: `MemoryManager._handle_replace`/`update` do **not** re-embed in ChromaDB, so edited facts are stale until restart.
4. **Pair-trimming unit.** `ContextWindowManager` trims in `(user, assistant)` pairs to preserve coherence. ✅ Upheld. Trimming single messages would fracture turns.
5. **Allowlists are the security boundary.** Write blast radius is defined by `ALLOWED_WRITE`, not by caller intent. ✅ Upheld for the doc agent. Any future tool that writes outside the allowlist bypasses the model's safety net.
6. **Tool output is capped before injection.** `MAX_OUTPUT_CHARS = 4096` (executor) and `DIFF_MAX_CHARS = 8000` (git) prevent context blow-up. ✅ Upheld. Removing the caps reintroduces the v2.2.0 "97% context → empty response" failure.
7. **Confirmation gate is non-negotiable for writes.** With `require_confirmation=True`, only `write_file` (`requires_confirmation=True`) prompts the user; read-only git tools are `risk_level="none"`. ✅ Upheld. The agent must never auto-execute a medium/high tool without confirmation.
8. **Every tool the prompt mentions must be registered.** The executor returns "Unknown tool" for unregistered names, which can stall the agent loop. ⚠️ **Currently violated:** `_SYSTEM` references `append_file` (dead/unregistered) and `git_diff`/`git_status`/`git_branch` (unregistered). `parse()` name-dedup (§8.5) is an additional loop hazard — parallel same-tool calls collapse to one.

---

## Verification Notes (consolidated — what was confirmed against source, and known discrepancies)

**Confirmed by reading source (`app/config/prompt.py`, `app/prompt/builder.py`, `app/agents/doc_agent.py`, `app/config/settings.py`, `app/tools/base.py`, `app/tools/executor.py`, `app/tools/file_tools.py`, `app/tools/git_tools.py`, plus `ls`/`git log`):**

- No HTTP/REST server exists; `app/api/` and `app/brain/` are empty packages; entry point is `python app/main.py`.
- `app/agents/` contains **only** `__init__.py` (empty) + `doc_agent.py` (the only agent class).
- `PromptBuilder` folds persona + past exchanges + facts into a **single** `system` message; `SYSTEM_PROMPT` is static and hardcoded.
- `ToolExecutor` parses `<tool_call>` tags (3 regex formats), dedups **by tool






## 7. Prompt System Evolution (deep dive)

The prompt system evolvedSTEM_PROMPT` is **static** — it does from "one hardwired persona string" not rewrite itself per turn; dynamic
 to a multi-source,
dynamically  memory context arrives only via the `## Known User Facts` block assembled, agent-aware prompt pipeline that `PromptBuilder`
  assembles. Its story is about *what goes
into the prompt*, *.in what order*, and *
- The doc-agent prompt is **internally inconsistent** with its tool sethow it is assembled* — and it splits into two
distinct prompt lineages after v (see §9.4): it
  instructs `append_file2.` (dead/unregistered), references `git2.1: the **chat** system prompt and the **agent**
system prompt._diff` (not registered),
 

### and forbids `write_file` on existing docs 7.1 The persona / system prompt while tasks 1/2 instruct a full-file itself

- **v0.3 (identity layer):** system-p
rompt support was introduced  overwrite.
- `tiktoken` is absent, and the identity
  string was moved so `build_with_stats`'s `system_tokens out of_estimate `main.py` into a dedicated `` is the crude
  `len(self.systemapp/config/prompts.py` file
  (per_prompt) // 4` heuristic, not a real `NEW_DEVLOG.md`: "Moved system token count.

---

## 8. Tool prompts into a dedicated `app/config/p System Evolution (deep dive)

The tool system is the newest subsystem (rompts.py`
  file"). This was the first separation of *prompt configurationcommitted v2.2.1, expanded through the* from *application
  code*. At this stage the system prompt was purely an identity v2.4.0
working tree). It is **prompt / behavior layer.
-based** (not native function calling): the model- **v0.4–v1.1:** the system prompt was emits
`<tool_call>` tags, stored on `OllamaClient` at init the executor parses and runs them. Its evolution is the story of
 and prepended
  to every request; its *content*how JARVIS learned to act on its* changed little, but it now rode along with environment* (filesystem + git).

 the
  growing client-owned conversation list.
-### 8.1 Before tools: no external **v2.0 (rename → `app/config/prompt.py`):** the module was consolidated action

- **v0.1–v2.2:** JARVIS could only read and generate text. It had to
  `app/config/prompt.py` exporting a no file or git access
  beyond what the core conversation pipeline touched single `SYSTEM_PROMPT` constant.. Documentation and changelogs were
 The current
  persona text — *  produced by hand. `app/tools/` did"You are Jarvis—a calm, sharp, and occasionally witty digital
  architect." not exist.

### 8.2 The framework* with six numbered protocols (Core Identity appears (v2.2.1 committed; `NEW; STEM & Teaching; Automation
 _DEVLOG.md` re-groups it under v2 & Agents; Daily Operations & Content;.4.0)

> ⚠️ **Version discrepancy.** Core Constraints; Execution) — is the The committed timeline (§2) and v2.0-era
  definition and remains the chat system prompt today.
- `AGENTS.md`/`TOOLS.md`
> attribute **v2.2.1 (second lineage):** a * the tool framework to **v2.2.1**separate* task-specific prompt appeared —
 (`891fe4b`). `NEW_DEVLOG.md` (working  `DocumentationAgent._SYSTEM` in `-tree
> notes) re-groups the same workapp/agents/doc_agent.py`. This is an instruction set
  (tool-list placeholder under **v2.4.0**. This history follows, `<tool_call>` format, entry-format rules the committed
> record (v2.2, file-writing rules,
  versioning notes), distinct from the chat.1 introduction) and notes the working-tree expansion.

- `SYSTEM_PROMPT`.

### 7.2 Prompt **`base.py`** — three assembly / building blocks: `ToolResult context building

-` ( **vuniform return value),
  `ToolDefinition` (metadata + `handler`0.7 (Context Builder):** `OllamaClient.build_messages()` centralized assembly + `risk_level`/`requires_confirm —
  system prompt + persistentation` facts + conversation history. This),
  `ToolRegistry` (dict was the first
  "context builder keyed by name).
- **`executor.py`," but it sent **all** facts every turn** — `ToolExecutor` parses `< (the unbounded-context
  problemtool_call>` tags that later forced the v2.0 rewrite).
 and runs them. Three
  regex formats: JSON- **v2.0 (`PromptBuilder`):** `app/p `{name, args}`, hybrid `name({json})`, positional `name("...")`.
rompt/builder.py` replaced the client-owned
  builder. `PromptBuilder  Calls **deduplicated by tool name**.build()` merges the system prompt (a `seen` set). `MAX_OUTPUT_CHARS **and retrieved memories
  into ONE `system` message** (OpenAI-compatible consistency), appends conversation
  history = 4096` caps
  injected output. `has_calls`/`parse`/`run`/`format, and optionally the current user_result` form the interface.
  `to prompt. `build_with_stats()` added for
  debugging. Facts are now_openai_schema()` helpers exist for the *retrieved*, not "all".
- ** planned v3.0 native-calling migration.
- **Design choice:** prompt-based overv2.2 (`past_exchanges`):** `build()` native function calling, explicitly to gained `past_exchanges`; ordering fixed as
  **base prompt → past exchanges → stay
  compatible with local models that don't emit `tool_calls`. The tag memory facts** (episodic before format is
  "unambiguous and easy semantic). Direct
  response to the to parse" (`NEW_DEVLOG.md` / `doc 97%-context incident (see §5.3).
_agent.py` docstring).

### 8.3- **v2.2.1 (agentic, code-generated prompt):** the doc agent builds its The tools themselves (verified)

Registration is **hardcoded** in system prompt
  at runtime — `Tool `DocumentationAgent.__init__` via
`register_many(GIT_TOOLS)` + `registerRegistry.format_for_prompt()` is injected into `_SYSTEM` via
  `str.format(t_many(FILE_TOOLS)`. There is **noools_section=...)` ( plugin
discovery**.

| Tool |see §9.2). The prompt Source | risk_level | confirm | Notes is now *partly generated from
 |
|---|---|---|---|---|
| `git  the registered tools* — a feedback loop between code and prompt text_log` | `git_tools.py` | none | no.

### 7.3 Prompt conventions that stabilized | read-only |
| `git_diff_stat`

- **Single `system` message** ( | `git_tools.py` | none | no | readnot separate system + memory messages-only |
| `git_diff_full` | `git_tools) — chosen in v2.0
  for cross-backend.py` | none | no | read-only; self-tr compatibility.
- **`## Known User Facts`** block (from `PromptBuilder._uncates `DIFF_MAX_CHARS=8000` |
|format_memories`) and
  **`## Relevant Past `git_show` | `git_tools.py` | none Exchanges`** block (from `_format_p | no | read-only; self-truncatesast_exchanges`) — fixed
  injections into |
| `git_tags` | `git_tools.py the system message.
- **`<tool_call>` tag protocol** for the agent (` | none | no | read-only |
| `readv2.2.1):
  `<tool_call>{"name":_file` | `file_tools.py` | low | no "...", "args": {...}}</tool_call | exact-match `ALLOWED_READ` |
|>`, one per line; results returned `write_file` | `file_tools.py` | medium
  as `<tool_result name="..." status | **yes** | exact-match `ALLOWED="...">`. A model-agnostic convention_WRITE`; overwrites chosen over
  native function calling ( |

So **7 tools**:deferred to v3.0) for local-model compatibility 5 read-only git + 1 read + 1 write..
- **Tool-list rendering** (`ToolRegistry.format_for_prompt()`): human-readable list Safety is layered:
- **Path allowlists** (`ALLOWED_READ`/`ALLOWED_WRITE;
  tools whose `risk_level` ∉ `{`) enforced *inside the handlers* —
  the primary blast-radius controlnone, (exact low}` get a ` [<risk> risk-string match, no `..` resolution).
]` suffix
  (`write_file` → `[medium risk]`).

### 7.4 What the prompt- **Read-only git** enforced by `subprocess.run([...])` with a list (no `shell=True`,
  no mutate sub system *cannot* yet do (verified gaps)

- The chat `SYSTEM_PROMPT` iscommands).
- **Output truncation** (executor 4096; git tools 800 **static** — it does not rewrite0).
- **Confirmation gate** (`require_confirm itself per turn; dynamic
  memory context arrives only via the `## Known User Factsation=True`): only `write_file` triggers a
  blocking `input(" Execute` block that `PromptBuilder`
  assembles.
? (y/N): ")`; git tools and `read_file- The doc-agent prompt is **internally inconsistent` never prompt.
- **No raw exceptions** with its tool set (see §9.4): escape**: `ToolDefinition.execute` wraps everything into it
  instructs `append_file` (dead/unregistered), references `git_diff` a
  `ToolResult (not registered),
  and forbids`.

### 8.4 Execution flow (the mini-agentic loop)

`DocumentationAgent `write_file` on existing docs while.run(task)`:
1. build system prompt from tasks 1/2 instruct a full-file
 `format_for_prompt()` injected into  overwrite.
- `tiktoken` is absent, so ` `_SYSTEM`;
2. `response = model.generatebuild_with(messages)` (non-streaming);
3._stats`'s `system_tokens if `not executor.has_calls(text)` →_estimate` is the crude
  `len(self.system return text (done);
4. else_prompt) // 4` heuristic, not a real `parse` → append assistant message → `run` each call → collect
   ` token count.

---

## 8. Tool System Evolution (deep dive)

Theformat_result` blocks → append **one tool system is the** `user` message with all results newest subsystem (committed v2. → loop2.1, expanded through the v2.4.;
5. `MAX_ITERATIONS = 12`0
working tree). It is **prompt-based** ( ceiling; if exceeded, returns the iteration-limit string.

Results are batnot native function calling): the model emits
`<ched intotool_call>` tags a single `user` message, the executor parses and runs them.; tool results use a `user` role ( Its evolution is the story of
*how JARVIS learned to act on its environment* (filesystem + git).

### 8.1 Beforenot a
native `tool` role) because this is prompt-based calling.

### 8.5 What the tool system *cannot* yet do (verified gaps)

- **No dynamic discovery.** Tools are tools: no external action

- **v0.1– added only by editing `GIT_TOOLS`v2.2:** JARVIS could only read and generate text./`FILE_TOOLS It had no file`
  and re-registering or git access
  beyond what the core conversation pipeline touched; `app/tools/__init__.py` is empty (no aggregator).
- **`append_file. Documentation and changelogs were
` is dead code.** Its `ToolDefinition`  produced by hand. `app/tools/` did not exist. is written *after a `

### 8.2 The framework appearsreturn`*
  inside `append_file()` in `file (v2.2.1 committed; `NEW_DEVLOG.md_tools.py`, so it is never in `FILE_TOOLS`. A model
  following the prompt` re-groups it under v2.4.0)

> ⚠️ **Version discrepancy.** The committed timeline emits `<tool_call>{"name":"append_file",... (§2) and `AGENTS}>` → `Unknown tool`.
  The.md`/`TOOLS.md only write`
> attribute the tool is `write_file` tool framework to **v2.2.1** (` (overwrites), contradicting "Never use write_file
  on existing docs."
891fe4b`). `NEW_DEVLOG.md` (working-tree
> notes) re-groups the same work under- **`git_diff` referenced but absent.** Task 1 says "Use git_log and git **v2.4.0**. This history follows the_diff" — only
  `git_diff_stat committed
`/`> record (v2.2.1 introductiongit_diff_full` exist.
- **`git_status) and notes the working-tree expansion.

- **`base.py`** — three building blocks`/`git_branch`** exist as functions but: `ToolResult` (uniform return value), are not in `GIT_TOOLS`.
- **Name-d
  `ToolDefinition` (metadata + `edup** in `parse()` collapses multiple same-name calls in onehandler` + `risk_level`/`requires_confirm turn;
  `test_100_tool_cation`),
  `ToolRegistry` (dictalls_parsed` fails (expects keyed by name).
- **`executor.py 100, gets 1).
- **Native calling ready but dormant.** `to_openai_schema`** — `ToolExecutor` parses `<tool_call>` tags and runs them. Three()`/`to_openai_schemas()` are
 
  regex formats: JSON `{name, args}`, defined but unused — the v3.0 migration hybrid `name({json})`, positional ` path.
- **Confirmation blocks stdin**name("...")`.
  Calls **deduplicated — fine in the interactive `docs` flow, would hang any
  headless deployment by tool name** (a `seen` set). `MAX_OUTPUT_CHARS = 4096` caps
 .

(See `docs/TOOLS.md` for the exhaustive source-verified account.)

---

## injected output. `has_calls`/`parse 9. Agent System Evolution (deep`/`run`/`format_result` form the dive)

JARVIS had no agent layer until interface.
  `to_openai_schema()` helpers exist for the planned the tool framework landed; the agent is the consumer
that v3 ties `ModelClient.0 native-calling migration.
- **Design choice:** prompt-based` + `ToolRegistry` + `ToolExecutor over native function calling, explicitly to stay
  compatible with local models` into a loop.

### 9.1 No agents ( that don't emit `tool_calls`. The tag format is
  "unambiguous andv0.1 – v2.2)

The entire system was a single REPL pipeline in `main easy to parse" (`NEW_DEVLOG.md`.py`. There was no
`app/agents/` package / `doc_agent.py` docstring).

, no agent class, no orchestration layer.### 8.3 The tools themselves (ver "Agency" meant the main
ified)

Registration is **hardcodedloop's extract → store → retrieve → generate cycle, not autonomous tool use** in `DocumentationAgent.__init__` via
.

###`register_many(GIT_TOOLS)` + 9.2 The first (and only) agent: `DocumentationAgent` (v2. `register_many(FILE_TOOLS)`. There is **no plugin
discovery**.

| Tool |2.1 committed)

- `app/agents/__ Source |init__.py` is empty; `app/agents/doc_agent.py` holds the sole
  `Documentation risk_level | confirm | Notes |
|---|---|---|---|---|
| `gitAgent` class + `run_interactive`.
_log` | `git_tools.py` | none | no- **No base `Agent` class, no registry, | read-only |
| `git_diff_stat` no multi-agent orchestrator** — ` | `git_tools.py` | none | no | readDocumentationAgent`
  is a concrete,-only |
| ` purpose-built documentation generatorgit_diff_full` | `git_tools, not a generic.py` | none | no agent runtime.
- ** | read-only; self-trArchitecture:** a mini agentic loop with prompt-based tooluncates `DIFF_MAX_CHARS=8000` |
| `git calling — exactly the
  shape the docstring_show` | `git_tools.py` | none says "v3.0's full agentic runtime" will generalize (no such
  runtime | no | read-only; self-truncates |
| `git_tags` | `git_tools.py` | none | no exists yet | read-only |
| `read_file; a forward-looking note).
- **Dependencies:** depends on the `ModelClient` Protocol (any
  `` | `file_tools.py` | low | no |generate(messages, stream=False, on_token=None, ** exact-match `ALLOWED_READ` |
| `kwargs) -> ModelResponse` object),
write_file` |  injected at construction `file_tools.py` | medium |. The agent calls the model **non **yes** | exact-match `ALLOWED_WRITE-streaming**.
- **Lifecycle:** constructed in `main.main()` from
  `switcher.get`; overwrites |

So **7 tools**:_client(profiles[active][" 5 read-only git + 1 read + 1 write. Safety is layered:
docs"])- **Path allow or switcher.router.default_model`;
 lists** **recreated** on a `model <name (`ALLOWED_READ`/`ALLOWED_WRITE`) enforced *>` switch (new client → new agentinside the handlers* —
  the primary blast-radius control (). Invoked only on the
  `docs` commandexact-string match, no `..` resolution).
 via `run_interactive`.
- **Tasks- **Read-only git** enforced by `subprocess:** `_.run([...])` withTASKS` predefine changelog a list (no `shell (1), devlog (2), both / full-history (=True`,
  no mutate subcommands3),
  custom (4), cancel (q). `).
- **Output truncation** (executor 4096; git tools 8000).
- **ConfirmationMAX_ITERATIONS = 12`.

### 9.3 Why prompt gate** (`require_confirmation=True`-based (design rationale): only `write_file` triggers a
 )

`doc_agent.py` docstring: not all local blocking `input(" Execute? (y/N): models support `tool_calls`; prompt-based works
on any instruction ")`; git tools and `read_file` never prompt-following model; `<tool_call>` is unambiguous.
- **No raw exceptions escape; the same interface
means v3.0**: `ToolDefinition.execute` wraps everything is "one method change in `Model into a
  `ToolResult`.

### 8Client`." This matches the tool framework.4 Execution flow (the mini-agentic loop)

`DocumentationAgent.run(task's
rationale (§8.2) and the v2.2)`:
1. build system prompt from.1 timeline entry.

### 9.4 Agent evolution `format_for_prompt()` injected into — gaps and the v3.0 horizon (verified `_SYSTEM`;
2. `response = model)

- **Prompt/tool mismatch** (see.generate(messages)` (non-streaming §8.5): `append_file` (dead), `git_diff`);
3. if `not executor.has_calls(text (absent),
  `git_status`/`)` → return text (done);
4. else `git_branch` (unregistered). The doc agentparse` → append assistant message → `run` each call → collect
  's instructions do not match
  its `format_result` blocks → append ** registered tools.
- **Model resolution under defaults is uncertain.**one** `user` message with all results → `profiles["local"][" loop;
5. `MAX_ITERATIONS = 12` ceiling; if exceeded, returns the iteration-ldocs"] = "docs"`
  but the default `models` dict only hasimit string.

Results are batched into `general`/`autocomplete`, so
  `get_client("docs")` is `None` and a single `user` message; tool results use the agent falls back to
  `switcher a `user` role (not a
native `tool.router.default_model` (the `general`` role) because this is prompt-based client). A real `config.yaml` is
 calling.

### 8.5 What the tool system  expected to define a `docs` model. *cannot* yet do (verified gaps)

 (`config- **No dynamic discovery.** Tools are.yaml` unreadable here — see caveats.)
- **Future (code comments added only by editing `GIT_TOOLS` / docstrings only, not implemented):** native function calling/`FILE_TOOLS`
  and re-registering
  (v3.; `app/tools/__init__.py` is empty0) using the existing `to_openai_schema()`; a "full agentic runtime (no aggregator).
- **`append_file" general` is dead codeizing
  this loop; a user-configurable permission system replacing hardcoded allowlists; a
  `risk_level=".** Its `ToolDefinition` is written *after a `return`*
  inside `append_file()` in `file_tools.py`, so it is never in `FILEhigh"` tier (`run_python` — v3._TOOLS`. A model
  following the prompt0+). `ARCHITECTURE.md` also lists emits `<tool_call>{"name":"append_file an
  "Agent Orchestration Layer"",...}>` → `Unknown tool`.
  The as a future improvement.

(See `docs/AGENTS.md` for the exhaustive only write tool is `write_file` (overwrites), contradicting "Never use source-verified account.)

---

## 10. Configuration Evolution (deep dive)

Configuration write_file
  on existing docs."
 evolved from hardcoded constants inside modules, to a centralized- **`git_diff` referenced but absent.**
dataclass singleton, to an overrid Task 1 says "Use git_log and gitable external YAML + `.env` system. Its story is
*where settings live*_diff" — only
  `git_diff_stat`/`git_diff_full` exist.
- **`git and *who can override them*.

###_status`/`git_branch`** exist as functions 10.1 Hardcoded era (v0.1 – v1.1 but are not in `GIT_TOOLS`.
- **Name-dedup** in `parse()` collapses)

- **v0.1–v0.5:** the model name multiple same-name calls in one turn;
  `test_100_tool_calls_parsed` fails (expects 100, gets 1).
 (`deepseek-r1:32b` → `qwen3`) and the system prompt were
  hardcoded; a single `settings.py` held constants- **Native calling ready but dormant.**.
- **v0.6–v1.1:** globals grew as `to_openai_schema()`/`to_openai subsystems were added; configuration was_schemas()` are
  defined but unused scattered
  across modules. `get_default_model()` did not yet exist ( — the v3.0 migration path.
- **Confirmation blocks stdin** — fine in the interactiveit arrived in v2.0.1 to
  replace the `docs` flow, would hang any
  headless broken `_DefaultModel` object).

 deployment.

(See `docs/TOOLS### 10.2 Centralized dataclass singleton.md` for the exhaustive source-ver (v2.0)

- **`Settings` dataclass**ified account.)

---

## 9. Agent System Evolution (deep dive)

JARVIS + nested config dataclasses: `ModelConfig had no agent layer until the tool`, `MemoryConfig`,
  `ContextConfig framework landed; the agent is the consumer`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`,
  `
that ties `ModelClient` + `ToolRegistry` + `ToolExecutor` into a loopPathsConfig`.
- **Thread-safe singleton** `get_settings()` (.

### 9double-checked locking.1 No agents (v0.1 – v2 with
  `.2)

The entire system was a single REthreading.Lock`).
- `PathsConfig` centralized filesystem pathsPL pipeline in `main.py`. There was no (`data_dir` plus `memories`,
  `conversations_dir`, `default_conversation
`app/agents/` package, no agent` properties).
- Default `default_model class, no orchestration layer. "Agency" meant the main
loop's extract = "qwen3-8b.gguf"` (the v2.0-era default → store → retrieve → generate cycle,; the live working
  tree's default client not autonomous tool use.

### 9.2 The first (and only) agent: resolves to `llama-3.2-3b-instruct `DocumentationAgent` (v2.2.1 committed` via the `models` dict — see
  §)

- `app/agents/__init__.py` is empty6.4).

### 10.3 External YAML +; `app/agents/doc_agent.py` holds dynamic router (v2.1)

- `Settings.load the sole
  `DocumentationAgent`()` reads optional `config.yaml` ( class + `run_interactive`.
- **YAML, with comments, gitignored)No base `Agent` class, no registry, and
  overrides defaults; hard-coded fallback preserved if absent.
 no multi-agent orchestrator** — `- `MemoryConfig.min_relevance_scoreDocumentationAgent`
  is a concrete, purpose-built documentation generator, not`, `candidate_overshoot_factor`, ` a generic agent runtime.
RankingConfig`
  weights, `ContextConfig.tokenizer- **Architecture:** a mini agent_method` introduced.
ic loop with prompt-based tool calling — exactly the
  shape the docstring says "v3.0's full agentic runtime" will generalize (no such
  runtime exists yet; a forward-looking note).
- **Dependencies:** depends on the `ModelClient` Protocol (any
  `generate(messages, stream=False, on_token=None, **kwargs) -> ModelResponse` object),
  injected at construction. The agent calls the model **non-streaming**.
- **Lifecycle:** constructed in `main.main()` from
  `switcher.get_client(profiles[active]["docs"]) or switcher.router.default_model`;
  **recreated** on a `model <name>` switch (new client → new agent). Invoked only on the
  `docs` command via `run_interactive`.
- **Tasks:** `_TASKS` predefine changelog (1), devlog (2), both / full-history (3),
  custom (4), cancel (q). `MAX_ITERATIONS = 12`.

### 9.3 Why prompt-based (design rationale)

`doc_agent.py` docstring: not all local models support `tool_calls`; prompt-based works
on any instruction-following model; `<tool_call>` is unambiguous; the same interface
means v3.0 is "one method change in `ModelClient`." This matches the tool framework's
rationale (§8.2) and the v2.2.1 timeline entry.

### 9.4 Agent evolution — gaps and the v3.0 horizon (verified)

- **Prompt/tool mismatch** (see §8.5): `append_file` (dead), `git_diff` (absent),
  `git_status`/`git_branch` (unregistered). The doc agent's instructions do not match
  its registered tools.
- **Model resolution under defaults is uncertain.** `profiles["local"]["docs"] = "docs"`
  but the default `models` dict only has `general`/`autocomplete`, so
  `get_client("docs")` is `None` and the agent falls back to
  `switcher.router.default_model` (the `general` client). A real `config.yaml` is
  expected to define a `docs` model. (`config.yaml` unreadable here — see caveats.)
- **Future (code comments / docstrings only, not implemented):** native function calling
  (v3.0) using the existing `to_openai_schema()`; a "full agentic runtime" generalizing
  this loop; a user-configurable permission system replacing hardcoded allowlists; a
  `risk_level="high"` tier (`run_python` — v3.0+). `ARCHITECTURE.md` also lists an
  "Agent Orchestration Layer" as a future improvement.

(See `docs/AGENTS.md` for the exhaustive source-verified account.)

---

## 10. Configuration Evolution (deep dive)

Configuration evolved from hardcoded constants inside modules, to a centralized
dataclass singleton, to an overridable external YAML + `.env` system. Its story is
*where settings live* and *who can override them*.

### 10.1 Hardcoded era (v0.1 – v1.1)

- **v0.1–v0.5:** the model name (`deepseek-r1:32b` → `qwen3`) and the system prompt were
  hardcoded; a single `settings.py` held constants.
- **v0.6–v1.1:** globals grew as subsystems were added; configuration was scattered
  across modules. `get_default_model()` did not yet exist (it arrived in v2.0.1 to
  replace the broken `_DefaultModel` object).

### 10.2 Centralized dataclass singleton (v2.0)

- **`Settings` dataclass** + nested config dataclasses: `Model- **Bug:**Config`, `MemoryConfig`,
  `ContextConfig `Settings.load()` initially returned `cls()` (ignoring parsed config) — fixed
  in v2.1.1.
- Dynamic router built from config; `TaskType(role)` bridges YAML role strings to the
  enum.

### 10.4 Profiles, model registry, env vars (v2.4 working tree)

- `Settings` gains **`profiles`** (`local`, `cloud`), each mapping `TaskType` roles →
  model keys; an **`active_profile`** field; a broader **`models`** dict of
  `ModelConfig` instances.
- `reset_settings()` added (test helper) to clear the singleton.
- `dotenv.load_dotenv()` runs at `main.py` startup; `ModelConfig` API keys support
  `env:VAR` resolution in the factory (`_resolve_key`).
- Model-key resolution: profiles reference keys that must exist in `models`; under
  shipped Python defaults only `general`/`autocomplete` exist, so `code`/`reasoning`/
  `docs`/`stem`/`cloud` lookups are skipped (see §6.4).

### 10.5 Configuration fields — defined vs used (verified gap)

Many fields are declared but **not read** by the running system (carried from §3.1):

- `MemoryConfig`: ``, `ConversationConfig`, `Retriemax_memories`, `enable_ranking`, `min_confidence` (unused).
- `RetrievalConfig.method`, `keyword_min_overlap` (the keyword retriever hardcodes
  `min_keyword_overlap=1`; `method` is ignored).
- `RankingConfig` weights — `MemoryRanker` uses its own `DEFAULT_WEIGHTS`, not
  `settings.ranking`.
- `candidate_overshoot_factor` — `MemoryManager.retrieve()` hardcodes the 3× overshoot.
- `ContextConfig.compression_threshold`, `estimation_method` (unused).

### 10.6 What configuration *cannot* yet do (verified)

- **No runtime validation** — dataclasses + type hints only; a bad YAML type flows
  through to a downstream runtime error.
- **`config.yaml` is gitignored and unreadable in this audit** — all runtime wiring is
  inferred from `settings.py` defaults + `NEW_DEVLOG.md`.
- **No schema/version field** in `config.yaml`; loading is an untyped `yaml.safe_load`
  plus `ModelConfig(**data)`.
- `load_dotenv()` is invoked at startup but `settings.py` itself contains no
  `os.getenv()` overrides — env vars are only consumed by the model factory's `env:VAR`
  key resolution, not by the `Settings` dataclass.

---

## Verification Notes (what was confirmed against source, and known discrepancies)


# JARVIS — Project History

> **Purpose.** A single, comprehensive narrative of how JARVIS was built and how
> its architecture evolved — from a thin Ollama wrapper to a modular,
> multi-backend, memory-driven assistant with a prompt-based agent/tool layer.
>
> This document is meant to be read by both the original developer and by JARVIS
> itself (so it can understand its own lineage). It supersedes the fragmentary
> logs in `docs/CHANGELOG_recovered.md` and `docs/DEVLOG_recovered.md` while
> staying consistent with the committed `docs/CHANGELOG.md` and `docs/DEVLOG.md`
> and the source code.
>
> **Scope.** Six sections: (1) Overall Architecture Evolution, (2) Timeline,
> (3) Subsystem Evolution, (4) Memory System Evolution, (5) Conversation System
> Evolution, (6) Model System Evolution. A short **Verification Notes** appendix
> records what was confirmed against source and the known gaps/discrepancies.

---

## How to read this document (sources & caveats)

**Authoritative sources used:**

- **Git history** — 26 commits, `HEAD = 891fe4b` (titled `fix: v2.2.1 — Documentation agent wired, package structure fixed`). All version blocks v0.0.0 → v2.2.1 are committed.
- **Committed docs** — `docs/CHANGELOG.md` (Keep-a-Changelog, 17 version blocks) and `docs/DEVLOG.md`.
- **Current source** — the working tree (which is **staged but not yet committed**); its `app/config/version.py` reports `VERSION = "v.2.4.0"`. The architecture described below reflects this working-tree state.

**Caveats the reader must keep in mind:**

- ⚠️ **`config.yaml` is unreadable here** (security block; it is gitignored). Every claim about *which models/backends are actually wired at runtime* is therefore derived from the **hardcoded defaults in `app/config/settings.py`** (and `docs/NEW_DEVLOG.md` for intent), **not** from a deployed `config.yaml`. Under the shipped Python defaults only the `general` model resolves; the `cloud` profile and `autocomplete` client are effectively inert (see §6 and Verification Notes).
- ⚠️ **Working tree ≠ HEAD.** The code described as "current" is the **v2.4.0 staged working tree**. The committed `HEAD` is `v2.2.1`. Intermediate versions `v2.3.0` and `v2.4.0` exist only as uncommitted changes + `NEW_DEVLOG.md` notes, not as git commits.
- ⚠️ **Version string is malformed.** `version.py` says `"v.2.4.0"` (extra dot). Several other files carry stale version strings (`store.py` docstring "v2.0", `settings.py` docstring "v2.1", `STARTUP_FLOW.md` mentions `v.2.2.0`, `main.py` docstring "v2.1.0"). The canonical runtime banner is `v.2.4.0`.
- The "recovered" logs (`docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`) were reconstructed from session notes and may contain gaps/inconsistencies; this history prefers the git record and the committed changelog where they disagree.

---

## 1. Overall Architecture Evolution

### 1.1 The arc in one paragraph

JARVIS began (v0.1) as a **stateless Ollama chat wrapper**: one client, one system prompt, a `while` loop. It became **stateful** (v0.5) by persisting the raw conversation to JSON. It learned to **separate facts from chat** (v0.6) and to **inject those facts into every request** (v0.7). Facts became **structured dictionaries** (v0.8) and then a **behavior-driven memory engine** (v1.0–v1.1). The pivotal moment was **v2.0**, a full rewrite that decomposed the monolith into single-responsibility modules behind Python `Protocol` interfaces (memory store / retriever / ranker / context / prompt / model client), and switched from "send all memories" to "retrieve only what is relevant." From there it gained **streaming + multi-backend + external YAML config** (v2.1), **semantic (ChromaDB) memory + hybrid retrieval** (v2.2), and a **prompt-based agent/tool framework** (v2.2.1, expanded through the v2.3–v2.4 working tree) — all while keeping the same clean interfaces.

### 1.2 Current layered architecture (v2.4.0 working tree)

```
User (CLI: input("You: "))
        │
        ▼
   app/main.py  ── main() REPL ── _cleanup() on exit
        │  commands: quit · docs · memories · help · stats · model [<name>|list]
        ├──────────────┬───────────────┬────────────────┬─────────────────┐
        ▼              ▼               ▼                ▼                 ▼
Conversation   FactExtractor    MemoryManager      PromptBuilder     ContextWindowManager
Manager        (rules.py)      (orchestrator)     (system+mem+      (pair-trim to fit)
(conversation  extract_facts()  ├ MemoryStore      history→messages)  ├ tokenizer (tiktoken→
.json +        → memory.store   │  (JSON CRUD)     │                                   transformers→word)
Conversation-  (behavior)       ├ HybridRetriever  │                 └ get_token_counter
VectorStore    │                │  ├ KeywordRetriever
(semories)     │                │  └ VectorRetriever (ChromaDB jarvis-memories)
        │       │                └ MemoryRanker (5 weighted factors)        │
        ▼       ▼                          │                                 │
        │   retrieve(prompt) ◀─────────────┘                                 │
        │   conv_store.search(prompt,2) ── ConversationVectorStore ──────────┘
        │        (ChromaDB jarvis-conversations)
        ▼
   ModelSwitcher(settings)
        ├ builds ModelRouter per profile (local / cloud)
        ├ create_client() → LlamaCppClient | OllamaClient | OpenRouterClient
        └ route(prompt) → (ModelClient, TaskType)
        │
        ▼  selected_model.generate(fitted_messages, stream=True, on_token=print)
   LLM backends:
        • llama.cpp  (OpenAI-compatible, http://localhost:8080/v1, default)
        • Ollama     (ollama package, http://localhost:11434)
        • OpenRouter (cloud, https://openrouter.ai/api/v1)   [working-tree addition]
   Embeddings: OllamaEmbeddingFunction → nomic-embed-text (local)

   Separate path: the `docs` command → DocumentationAgent (prompt-based
   tool loop) → ToolRegistry(GIT_TOOLS + FILE_TOOLS) → ToolExecutor
   → git_tools.py / file_tools.py (allowlisted, read-only git, capped output)
```

### 1.3 Design principles that survived every rewrite

These were stated explicitly in `docs/DEVLOG.md` (v2.0 session notes) and remain visible in code:

1. **One clean interface per subsystem, implementation hidden.** `ModelClient` (Protocol), `CandidateRetriever` (Protocol), `MemoryStore`, `MemoryRanker`, `ContextWindowManager`, `PromptBuilder` are all swappable behind a narrow contract. This is *why* ChromaDB could be dropped in for keyword retrieval, or OpenRouter for llama.cpp, with no caller changes.
2. **Protocol, not ABC, for boundaries.** Structural subtyping (`typing.Protocol`) lets third-party classes satisfy an interface without inheriting — e.g. `OllamaClient` and `LlamaCppClient` satisfy `ModelClient` without sharing a base class.
3. **Memory-first ordering in the main loop.** Facts are **extracted and stored before retrieval**, so a fact stated this turn is available to this turn's context (a bug in the original v2.0 plan was fixed by reordering).
4. **Hybrid retrieval.** Keyword catches exact matches ("what's my name?" → `name: Sajan`); vector catches semantic ones ("what do I enjoy?" → "I like coding"). Neither alone is sufficient.
5. **Trim by user/assistant pairs, never individual messages**, so an exchange is never broken in half (ContextWindowManager).
6. **Combine system prompt + memories into ONE `system` message** for cross-backend compatibility.
7. **Prompt-based tool calling** (not native function calling yet). The model emits `<tool_call>` tags; an executor parses and runs them. OpenAI-schema helpers (`to_openai_schema()`) already exist for the planned v3.0 migration.
8. **Centralized, overridable configuration.** `app/config/settings.py` dataclasses + optional `config.yaml` + `.env` (`load_dotenv`).

### 1.4 Placeholders and stubs (honest inventory)

- `app/api/` and `app/brain/` contain **only empty `__init__.py`** files. `requirements.txt` lists `fastapi`/`uvicorn`/`starlette`, but **no HTTP server exists** — the only entry point is `python app/main.py`. Web/GUI/voice are roadmap-only (doc-only, unverified in code).
- `app/utils/server_manager.py` (`is_port_open`, `ensure_server_running`) exists but its call site in `main.py` is **commented out**, so LLM servers are not auto-started.
- Conversation **summarization** (`ConversationManager.set_summary`/`get_summary`, `ConversationConfig.enable_summarization`) is present but **dormant**.
- The **Google/Gemini provider** is a fully-written but **commented-out** block inside `LlamaCppClient.generate()` (dead code).

---

## 2. Timeline

Dates are from git author timestamps for committed versions; v2.3.0/v2.4.0 are working-tree states (no commits) dated by `NEW_DEVLOG.md`/file mtimes.

| Version | Date | Commit(s) | Headline | Key capabilities added |
|---|---|---|---|---|
| **v0.0.0** | 2026-06-27 | `1999e53`, `163f8a1`, `8b1d0cb` | Foundation | Project skeleton, `requirements.txt`, `.gitignore`, architecture & roadmap docs |
| **v0.1.0** | 2026-06-27 | `e13ee67` | First chat | `OllamaClient` + `app/config/prompt.py` (`SYSTEM_PROMPT`), single-turn CLI |
| **v0.2.0** | 2026-06-27 | `ded44b9` | Loop | `while` REPL + `quit` |
| **v0.3.0** | 2026-06-27 | `39b3d5b`, `7491e9a`, `e5c6fd6` | Persona | System prompt support + identity layer; injection/import fixes |
| **v0.4.0** | 2026-06-28 | `94e1956`, `3cc9e4b` | Memoryful chat | Client-owned `conversation` history; deepseek-r1:32b → qwen3 |
| **v0.5.0** | 2026-06-28 | `4034bf7` | Persistence | `MemoryManager` persists `conversation.json`; reload on startup |
| **v0.6.0** | 2026-06-28 | `7a840ee`, `b145614`, `9aa2fb2` | Facts | Rule-based fact extraction; facts separated from chat history |
| **v0.7.0** | 2026-06-28 | `7803a93` | Context builder | `build_messages()` combines system + facts + history |
| **v0.8.0** | 2026-06-29 | `d43f6e9` | Structured memory | `category/type/value` dict facts; `rules.py` |
| **v0.9.0** | 2026-06-29 | `2922129` | Multi-fact | `extract_facts()` + sentence splitting (one message → many facts) |
| **v1.0.0** | 2026-06-29 | `4f71baf` | Behavior engine | append/replace/ignore behaviors driven by `RULES` |
| **v1.1.0** | 2026-06-29 | `6316917`, `db51ccc`, `63addf6` | Rich rules | Multiple triggers per rule; `behavior` inside rules; debug cleanup |
| **v2.0.0** | 2026-07-03 | `8519f65` | Architecture rewrite | Protocol-based modular redesign; retrieve-only-relevant; `MemoryManager`/`Store`/`HybridRetriever`/`Ranker`; `ContextWindowManager` (pair trim); `PromptBuilder`; score-based `ModelRouter`; tokenizer chain |
| **v2.0.1** | 2026-07-04 | `5fccb37` | Stability | `force_save()` fixes; `get_default_model()`; router actually used; `save_on_every_message=True`; model-failure recovery; ARCHITECTURE/DEVLOG/CHANGELOG docs |
| **v2.1.0** | 2026-07-05 | `df45be2` | Multi-backend | `OllamaClient`; `factory.create_client`; `stream`/`on_token` callbacks; `config.yaml`; dynamic router from config; fixes (Settings.load return, streaming reachability, tuple unpacking, kwarg leak) |
| **v2.2.0** | 2026-07-05 | `b2c2211` | Semantic memory | `VectorRetriever` (ChromaDB + `nomic-embed-text` cosine); `HybridRetriever`; `ConversationVectorStore`; `past_exchanges` in prompt; retrieval-limit tuning after 97%-context incident |
| **v2.2.1** | 2026-07-06 | `891fe4b` | Agent scaffold | `DocumentationAgent` + prompt-based `app/tools/` framework (`ToolResult`/`ToolDefinition`/`ToolRegistry`/`ToolExecutor`); `TaskType.DOCS`; `docs` command; package `__init__.py` fixes |
| **v2.3.0** | *uncommitted* | — (working tree) | Autocomplete & hardening | Continue.dev autocomplete agent (`qwen2.5-coder:1.5b`); search/indexing; resilience hardening; search command *(per `NEW_DEVLOG.md`; not committed)* |
| **v2.4.0** | *uncommitted* | — (working tree, `version.py="v.2.4.0"`) | Agent/tool era | `ModelSwitcher` (profiles: local/cloud); `OpenRouterClient`; `TaskType` extended; reference docs (`API`/`TOOLS`/`AGENTS`/`DATABASE`/`LLM`/`CONFIG`/`STARTUP_FLOW`/`MEMORY`/`ARCHITECTURE`); multi-agent scaffolding *(current staged tree)* |

### 2.1 Phases

- **Foundations (v0.0 – v0.9):** learn to talk, then to remember, then to extract structure.
- **Behavior Engine (v1.0 – v1.1):** memory gains intent (append/replace/ignore) and richer rule coverage.
- **Architecture Rewrite (v2.0 – v2.0.1):** the monolith becomes modular; retrieval stops being "send everything."
- **Multi-Backend & Config (v2.1):** the router finally has somewhere to route; config leaves Python.
- **Semantic Memory (v2.2):** keyword retrieval is augmented with vector similarity + episodic conversation search.
- **Agent Era (v2.2.1 → v2.4 working tree):** JARVIS can act on its own repo via prompt-based tools; multi-profile model switching; cloud backends.

---

## 3. Subsystem Evolution

Each subsystem below is traced from its first form to the current (v2.4.0 working-tree) implementation, with the file(s) that own it.

### 3.1 Configuration (`app/config/`)
- **v0.1–v0.5:** model name + system prompt hardcoded; a single `settings.py` with constants.
- **v0.6–v1.1:** growing globals; `get_default_model()` helper introduced in v2.0.1 to replace the broken `_DefaultModel` object.
- **v2.0:** `Settings` dataclass + nested config dataclasses (`ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, `PathsConfig`); thread-safe `get_settings()` singleton (`threading.Lock`).
- **v2.1:** `Settings.load()` reads optional `config.yaml` (YAML, with comments, gitignored) and overrides defaults; hard-coded fallback preserved. `MemoryConfig.min_relevance_score`, `candidate_overshoot_factor`, `RankingConfig` weights, `ContextConfig.tokenizer_method` all introduced.
- **v2.4 (working tree):** `Settings` gains `profiles` (`local`, `cloud`) mapping roles → model keys, a `default_model` field, and a broader `models` dict. `reset_settings()` added for tests. `dotenv.load_dotenv()` runs at `main.py` startup.
- **Caveat:** many `MemoryConfig`/`RetrievalConfig`/`RankingConfig` fields are defined but **not read** by the memory subsystem (see Verification Notes).

### 3.2 Memory (`app/memory/`)
See §4 for the deep dive.

### 3.3 Conversation (`app/conversation/`)
See §5 for the deep dive.

### 3.4 Context window (`app/context/manager.py`)
- **v0.4–v1.1:** no real management; the full (growing) conversation was sent every turn; trimming, if any, removed the oldest *individual* messages.
- **v2.0:** `ContextWindowManager.fit()` introduced; **trims in user/assistant pairs**; counts tokens via `app/utils/tokenizer.py` (tiktoken → transformers → word fallback); returns `ContextStats` (`pairs_kept`/`pairs_trimmed`/`utilization`).
- **v2.4:** unchanged in logic; `estimation_method` parameter accepted but **unused** (counter chosen by `get_token_counter(model_name)`).

### 3.5 Prompt assembly (`app/prompt/builder.py`)
- **v0.3–v0.6:** system prompt concatenated inline.
- **v0.7:** `OllamaClient.build_messages()` centralized system + facts + history.
- **v2.0:** `PromptBuilder.build()` — system prompt and retrieved memories merged into **one `system` message**; conversation history appended; optional current user prompt. `build_with_stats()` added for debugging.
- **v2.2:** `build()` gains `past_exchanges`; ordering is **base prompt → past exchanges → memory facts** (episodic before semantic).

### 3.6 Models (`app/models/`)
See §6 for the deep dive. Summary of the wrapping layers:
- **`ModelClient` (Protocol)** — the polymorphism boundary (`generate`, `model_name`, `role`).
- **`ModelRouter`** — score-based task classification → `(ModelClient, TaskType)`.
- **`ModelSwitcher`** (v2.4) — builds one `ModelRouter` per profile from `Settings.profiles` × `Settings.models`; runtime `switch()`; `get_client()` for the doc agent.
- **`create_client` (factory)** — dispatches by `ModelConfig.backend` (`llamacpp`/`ollama`/`openrouter`); resolves `env:VAR` API keys.

### 3.7 Agents & Tools (`app/agents/`, `app/tools/`)
- **Before v2.2.1:** no agent layer at all.
- **v2.2.1:** `DocumentationAgent` + `app/tools/` (prompt-based `<tool_call>` execution). 7 registered tools (`git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags`, `read_file`, `write_file`). Safety via path allowlists + read-only git + output caps + confirmation gate.
- **v2.4 (working tree):** extended tool/agent reference docs; `ModelSwitcher` feeds the agent a profile-appropriate `docs` client; the agent is re-created on `model` switches. `app/agents/__init__.py` stays empty; `doc_agent.py` is the only agent class.

### 3.8 Retrieval & Ranking (`app/memory/retrieval.py`, `vector_retriever.py`, `hybrid_retriever.py`, `ranking.py`)
- **v0.5–v1.1:** every stored memory sent to the model each turn (no retrieval).
- **v2.0:** `KeywordRetriever` (in-memory, stop-word filtered overlap) finds candidates; `MemoryRanker` scores 5 weighted factors; `MemoryManager.retrieve()` overshoots (`limit × 3`) then ranks.
- **v2.2:** `VectorRetriever` (ChromaDB cosine) added; `HybridRetriever` runs both and **deduplicates by `memory.id`** (mutable dataclasses are unhashable, so `set()` would raise); `MemoryRanker` weights hardcoded as `DEFAULT_WEIGHTS` (relevance 0.35, importance 0.25, frequency 0.15, recency 0.15, confidence 0.10).

### 3.9 Persistence (`app/memory/store.py`, `conversation/manager.py`, `data/chroma`)
- **v0.5:** single `conversation.json` (list of role messages) — facts and chat intertwined.
- **v0.6:** `conversation.json` gains a `facts` list alongside `conversation`.
- **v2.0:** split into `data/memories.json` (`{"version":"2.0","memories":[...]}`) and `data/conversations/default.json` (`{"version":"2.0","summary":"","messages":[...]}`); both use dirty-tracking (`save_if_dirty()` / `force_save()`); v1 formats auto-migrated on load.
- **v2.2:** **dual-store** — JSON remains the authoritative fact record; ChromaDB (`data/chroma`) holds two derived collections (`jarvis-memories` rebuilt from JSON every startup; `jarvis-conversations` seeded once when empty). See §4.4.

### 3.10 Main pipeline & CLI (`app/main.py`)
- **v0.1:** `client.chat(prompt)`.
- **v0.5:** `MemoryManager.load → chat → MemoryManager.save`.
- **v2.0:** explicit pipeline `add_message → extract_facts → store → retrieve → build → fit → generate → add_message`; `stats`/`help`/`memories` commands; `_cleanup()`.
- **v2.1:** `generate(..., stream=True, on_token=print)`; model calls routed via `switcher.router.route()`.
- **v2.2:** `conv_store.search` + `add_exchange`; `model` command for profiles (v2.4).
- **v2.2.1:** `docs` command → `run_interactive(doc_agent)`.
- **Resilience:** model failure is caught; the just-added **user** message is popped (`pop_last_message()`) and the loop continues. (Stored facts from the failed turn are *not* rolled back — a known asymmetry.)

### 3.11 Errors & resilience
- **v0.1–v2.0:** a model/connection error typically crashed the process (bypassing cleanup).
- **v2.0.1:** `try/except` around generation; diagnostic printed; user message removed; `_cleanup()` guaranteed on exit (`EOFError`/`KeyboardInterrupt` handled).
- **v2.1+:** per-client `ImportError` guards; `ModelSwitcher` catches individual client load failures and continues; `ToolExecutor` never raises on unknown/broken tool calls (returns `ToolResult`).

---

## 4. Memory System Evolution (deep dive)

The memory subsystem is the oldest and most-rewritten part of JARVIS. Its evolution is the story of three questions: *what to store*, *how to store it*, and *what to retrieve*.

### 4.1 Storage format migration

| Era | Format | Problem it solved |
|---|---|---|
| v0.5 | `conversation.json`: list of `{role, content}` (system + turns) | Persistence across restarts |
| v0.6 | same file, plus a `facts` list | Separate long-term facts from chat |
| v0.7 | facts still strings (`"user likes football"`) | — (extraction only) |
| v0.8 | facts as `{category, type, value}` dicts | Queryable/structured memory |
| v1.0–v1.1 | dicts + `behavior` field | Intent-aware storage |
| v2.0 | full `Memory` schema (see below), `memories.json` `{"version":"2.0",...}` | Rich ranking signals; v1 auto-migrated |

`Memory` dataclass (`app/memory/schema.py`) — the v2.0 contract:
`id` (8-char uuid prefix), `category`, `memory_type`, `value`, `behavior` (`append`/`replace`/`ignore`/`delete`), `created_at` (immutable), `updated_at` (mutable), `last_used` (mutable, set on retrieval via `touch()`), `source` (`user`/`system`/`inferred`), `confidence` (0–1), `importance` (0–1), `access_count`, `metadata`. `to_dict()`/`from_dict()` handle v1→v2 migration (v1 `timestamp` → `created_at`/`updated_at`).

### 4.2 Fact extraction (`app/memory/fact_extractor.py` + `rules.py`)

- **v0.6:** single fact per message; hardcoded `if` checks.
- **v0.8:** `rules.py` introduced (declarative trigger → category/type).
- **v0.9:** `extract_facts()` returns a **list**; sentence splitting before matching; multiple facts per message.
- **v1.0:** behavior engine wired (append/replace/ignore).
- **v1.1:** multiple `triggers` per rule; behavior travels through extraction into storage.
- **v2.0:** `VALUE_BOUNDARIES` stop value extraction at conjunctions/clause boundaries; `_extract_value()` strips artifacts (`"that "`, `"to "`); abbreviation-aware sentence splitter (`mr.`, `dr.`); minimum value length `>= 2`; confidence `1.0`.
- **Current:** purely **rule-based** over ~130 trigger phrases across 8 categories (identity, preference, skills, goals, plans, tasks, location, profession). The interface is explicitly designed to be swappable for **LLM-based extraction** later (`fact_extractor.py` docstring: "Interface is stable - can swap to LLM extraction later"). No deduplication of facts is implemented (noted as a known gap since v0.9).

### 4.3 Behavior engine (`MemoryManager.store`)

- **v1.0:** `store()` dispatches on `fact["behavior"]`: `ignore` → return `None`; `delete` → `delete_by_type`; `replace` → `_handle_replace` (first matching category+type is mutated, else append); `append` (default) → `_handle_append` (new `Memory`). Behavior is driven entirely by `RULES`, not hardcoded branches.
- **Known gap:** `_handle_replace()` and `update()` mutate fields **without** calling `retriever.on_memory_added`, so the ChromaDB embedding goes **stale until the next startup rebuild** (verified in source).

### 4.4 Retrieval & persistence (dual-store)

Three candidate indexes, all fed by the `CandidateRetriever` Protocol callbacks (`on_memory_added`/`on_memory_removed`/`on_index_rebuilt`):

1. **Keyword index** (`KeywordRetriever`) — in-memory `list[Memory]`, rebuilt from JSON on startup. Stop-word filtered overlap; `min_keyword_overlap=1`.
2. **Vector index** (`VectorRetriever`) — ChromaDB collection `jarvis-memories`, cosine HNSW, embeddings via local `OllamaEmbeddingFunction` (`nomic-embed-text`). Document embedded = `f"{category} {memory_type}: {value}"`. **Rebuilt from JSON every startup** (`on_index_rebuilt` deletes all ids then re-upserts) — so JSON is the **source of truth** for facts; the vector store is a *derived* index.
3. **Hybrid** (`HybridRetriever`) — runs keyword + vector, concatenates, **dedups by `memory.id`**, returns `combined[:limit]`. This is what `main.py` wires.

Ranking (`MemoryRanker.rank`): overshoot candidates (`limit × 3`, hardcoded — `candidate_overshoot_factor` config is ignored), then score = weighted sum of relevance (Jaccard + category/type boosts), importance, frequency (`log(1+count)/log(1+scale)`, `scale=10`), recency (exp decay, half-life 7 days), confidence. Scores below `MemoryConfig.min_relevance_score` dropped. Returned memories are `touch()`-ed and `force_save()`-ed to persist access stats.

**Conversation vector store** (`ConversationVectorStore`, collection `jarvis-conversations`): stores complete `User:/Assistant:` exchanges (metadata capped at 1000 chars/user+assistant; `pair_id = md5(ts + user_msg[:20])[:8]`). Seeded from `conversation.get_all()` **only when empty** (`conv_store.count() == 0`); afterward append-only and persists independently (can drift from the JSON conversation — a known risk).

**Persistence format notes:** `memories.json` `version` is the literal string `"2.0"` (independent of app version `v.2.4.0`). ChromaDB metadata must be flat, so `Memory.to_dict()`'s nested `metadata` field is **omitted** in `_to_chroma_meta()` and defaulted to `{}` on load. `chromadb` is a pinned dependency (`chromadb==1.5.9`).

### 4.5 What memory *cannot* yet do (verified gaps)
- No fact **deduplication** (duplicate `name` entries accumulate — observed in v2.2 stress test).
- `replace`/`update` do not refresh the vector embedding in-session.
- Several `MemoryConfig`/`RetrievalConfig`/`RankingConfig` fields are defined but unused (`max_memories`, `enable_ranking`, `min_confidence`, `candidate_overshoot_factor`, `RetrievalConfig.method`, `RankingConfig` weights — `MemoryRanker` uses its own `DEFAULT_WEIGHTS`).
- `VectorRetriever` contains a **dead nested method** `_memory_to_text` (defined inside `on_index_rebuilt`, never called; the inline f-string is used instead).

---

## 5. Conversation System Evolution (deep dive)

The conversation system evolved from "a list the client happens to keep" to "a managed, persisted, retrievable context source."

### 5.1 From client-owned list to a dedicated manager

- **v0.4:** conversation history was a plain `self.conversation` list **inside `OllamaClient`**; the client appended user/assistant messages and sent the whole list each turn. This coupled transport with state.
- **v0.5:** `MemoryManager` took over persistence (`conversation.json`); the client still held the in-memory list.
- **v2.0:** state moved entirely out of the client into **`ConversationManager`** (`app/conversation/manager.py`). The client became a pure transport (`generate()`). `ConversationManager` owns a `Message` dataclass (`role`, `content`, `timestamp`, `metadata`), dirty-tracking, `add_message`/`get_recent`/`get_recent_formatted` (OpenAI format)/`get_all`/`count`/`clear`/`pop_last_message`/`save_if_dirty`, and loads v2/v1 formats.

### 5.2 Persistence & safety

- **v2.0.1:** `ConversationConfig.save_on_every_message` default flipped `False → True` after the discovery that a crash between turns silently discarded entire sessions. Eager save is now the default (the doc note frames this as insurance for future voice I/O).
- **v2.0+:** `add_message()` saves immediately when `save_on_every_message` is set; `_cleanup()` calls `conversation.save_if_dirty()` on exit.

### 5.3 Semantic conversation history (v2.2)

Raw chat history and extracted facts serve different purposes, so v2.2 added a **second** memory: `ConversationVectorStore`. Instead of re-sending raw history, the pipeline now **semantically searches** past exchanges (`conv_store.search(prompt, limit=2)`) and injects the top-2 as `## Relevant Past Exchanges` into the system prompt (before the `## Known User Facts` block). This was a direct response to the **97%-context incident** (stress test): sending 20 memories + 5 exchanges + a long input left ~123 tokens for the answer → empty response. Limits were cut to `retrieval_limit ≈ 5–8` and `past_exchanges = 2`, `safety_margin` raised to ~300.

### 5.4 Trimming & coherence

Because the conversation can grow without bound, `ContextWindowManager.fit()` trims **oldest user/assistant pairs first** (never a lone message). `ConversationManager` also reserves a `summary` field + `set_summary`/`get_summary`, and `ConversationConfig.enable_summarization` exists — but **summarization is not yet enacted** (the field defaults to `False`; no caller performs it). The roadmap (v2.3.0+) intends to compress trimmed pairs into a summary rather than discard them.

### 5.5 Current flow (working tree)

```
user input
  → conversation.add_message("user", prompt)        # persisted if save_on_every_message
  → extract_facts(prompt) → memory.store(fact) ×N   # visible to this turn's retrieval
  → relevant_memories = memory.retrieve(prompt)
  → past_exchanges   = conv_store.search(prompt, 2)
  → messages = prompt_builder.build(memories, conversation.get_recent_formatted(), past_exchanges)
  → fitted  = context_manager.fit(messages)         # pair-trim if needed
  → selected_model, task_type = switcher.router.route(prompt)
  → response = selected_model.generate(fitted, stream=True, on_token=print)
  → conversation.add_message("assistant", response.content)
  → conv_store.add_exchange(prompt, response.content)
```

---

## 6. Model System Evolution (deep dive)

The model layer evolved from "one hardwired client" to "a polymorphic, profile-switchable, multi-backend router."

### 6.1 The clients

- **v0.1 (OllamaClient, original):** talked to `deepseek-r1:32b` via the `ollama` package; owned the conversation list and the system prompt. Single backend, single model.
- **v0.4:** switched default model deepseek-r1:32b → **qwen3**; an `autocomplete` model (`qwen2.5-coder:1.5b`) appears in config intent.
- **v2.0 (LlamaCppClient):** rewritten to use the **OpenAI-compatible** API of a local `llama-server` (`openai.OpenAI(base_url="http://localhost:8080/v1")`). The `OllamaClient` was retained but the primary path became llama.cpp. `ModelClient` Protocol + `ModelResponse` dataclass defined.
- **v2.1 (OllamaClient revived):** `ollama` package used again, this time via `ollama.Client(host=...)`; both clients implement `generate(messages, stream, on_token, **kwargs)` identically. Import is optional (`try/except ImportError`) so llama.cpp-only users don't need it.
- **v2.4 (working tree, OpenRouterClient):** new `openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)` client for 200+ cloud models (gemini/grok/claude/etc. by model name). `factory.create_client` dispatches to it when `backend=="openrouter"`.
- **Dead provider:** a complete **Google/Gemini** block exists inside `LlamaCppClient.generate()` but is **commented out** — not a wired backend.

### 6.2 Routing

- **v0.1–v1.1:** no routing; one model.
- **v2.0 (ModelRouter):** score-based classification. Every keyword category is scored independently (no order bias); ties broken by specificity `CODE > STEM > REASONING > GENERAL`. `route()` returns `(ModelClient, TaskType)`. Initially the router was built but **never called** (v2.0.1 bug 3) — fixed so `main.py` actually uses `selected_model, task_type = switcher.router.route(prompt)`.
- **v2.1:** router built **dynamically from config**; `TaskType(role)` bridges YAML role strings to the enum; failed model loads warn-and-continue.
- **v2.2.1:** `TaskType.DOCS` added for the documentation agent.
- **v2.4 (ModelSwitcher):** introduces **profiles** (`local`, `cloud`). `ModelSwitcher(settings)` instantiates every client in `Settings.models` via the factory, then builds one `ModelRouter` per profile (`role → model key`). `switch(profile)` flips the active profile at runtime; `get_client(key)` feeds the doc agent. `router.route()` is provider-agnostic.

`TaskType` enum (current): `AUTOCOMPLETE, CODE, REASONING, STEM, GENERAL, DOCS`. Keyword classification (`ModelRouter.KEYWORDS`) defines lists **only for CODE/STEM/REASONING**; `AUTOCOMPLETE`/`GENERAL`/`DOCS` are reachable only via explicit `select()`, never by auto-classification.

### 6.3 Streaming & tokens

- **v2.0:** `generate()` non-streaming; `tokens_used`/`finish_reason` populated.
- **v2.1:** `stream` + `on_token` added as **named parameters** (not `**kwargs`) so they are consumed by the client and never leak into the provider API call (a v2.1 bug: `on_token` in `**kwargs` caused an API error). `main.py` prints tokens as they arrive. On the streaming path `tokens_used`/`finish_reason` are `None`.

### 6.4 What the model layer *cannot* do yet (verified gaps)

Under the **shipped Python defaults** (`settings.py`, since `config.yaml` is unreadable):
- Only the **`general`** model resolves (llama-3.2-3b-instruct on llama.cpp). The `local` profile's `code`/`reasoning`/`docs`/`stem` keys point to model entries that **don't exist** in the default `models` dict, so they're skipped and every routed prompt falls back to `general`.
- The **`autocomplete`** client (qwen2.5-1.5b on port 8082) is instantiated but **never mapped to a router/task type** → dead under defaults.
- The **`cloud`** profile maps everything to a `"cloud"` key absent from defaults → an empty router with no default; `switcher.switch("cloud")` returns `True` but any `route()` would raise `ValueError`.
- A **dead fallback** in `main.py`: `if selected_model is None: selected_model = router.default_model` references an undefined `router` (the object is `switcher.router`) and would raise `NameError` if reached; it is currently unreachable because `route()` never returns `None`.

A real `config.yaml` is clearly expected to define the `code`/`reasoning`/`docs`/`stem`/`cloud` entries (the switcher, router, and `NEW_DEVLOG.md` all assume them). `NEW_DEVLOG.md` describes the intended lineup as **local llama models + cloud (OpenRouter) + Grok/Google** models, with `local` (privacy-first) and `cloud` (capability) profiles switchable live.

---

## Verification Notes (what was confirmed against source, and known discrepancies)

**Confirmed by reading source:**
- No HTTP/REST server exists; `app/api/` and `app/brain/` are empty packages; entry point is `python app/main.py`.
- `app/agents/` contains **only** `__init__.py` (empty) + `doc_agent.py` (the only agent class). (`AGENTS.md` is accurate; my earlier assumption of extra agent files was wrong.)
- `ToolExecutor` parses `<tool_call>` tags (3 regex formats), dedups **by tool name** (so multiple same-name calls in one turn collapse — `tests/stress_test.py::test_100_tool_calls_parsed` fails: expected 100, got 1).
- Registered tools = 7 (`git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags`, `read_file`, `write_file`). `write_file` is the only `requires_confirmation` tool. `append_file` is **dead code** (defined after a `return` inside `append_file()`), yet `doc_agent._SYSTEM` tells the model to use it; `git_diff`/`git_branch`/`git_status` are referenced but not registered.
- `MemoryManager._handle_replace`/`update` do **not** re-embed in ChromaDB (stale until restart).
- JSON is authoritative for facts; `jarvis-memories` is rebuilt from JSON on startup; `jarvis-conversations` is seeded once.
- `tiktoken` is **not** in `requirements.txt`, so the live tokenizer is transformers/word, not tiktoken.
- `server_manager.ensure_server_running` is commented out in `main.py`.
- Git: 26 commits, `HEAD = 891fe4b` (v2.2.1); working tree is **staged but uncommitted**, `version.py = "v.2.4.0"`.

**Could not verify:**
- `config.yaml` contents (security block). Runtime model/backend wiring is inferred from `settings.py` defaults + `NEW_DEVLOG.md`.
- Actual ChromaDB/embeddings at runtime (no `data/` present; Ollama server not reachable here).
- Real LLM conformance to the `<tool_call>` format under load.

**Authoritative version map (committed):**
v0.0.0 (`1999e53`,`163f8a1`,`8b1d0cb`) · v0.1.0 (`e13ee67`) · v0.2.0 (`ded44b9`) · v0.3.0 (`39b3d5b`,`7491e9a`,`e5c6fd6`) · v0.4.0 (`94e1956`,`3cc9e4b`) · v0.5.0 (`4034bf7`) · v0.6.0 (`7a840ee`,`b145614`,`9aa2fb2`) · v0.7.0 (`7803a93`) · v0.8.0 (`d43f6e9`) · v0.9.0 (`2922129`) · v1.0.0 (`4f71baf`) · v1.1.0 (`6316917`,`db51ccc`,`63addf6`) · v2.0.0 (`8519f65`) · v2.0.1 (`5fccb37`) · v2.1.0 (`df45be2`) · v2.2.0 (`b2c2211`) · v2.2.1 (`891fe4b`). Working tree adds v2.3.0 (uncommitted) and v2.4.0 (uncommitted, `version.py`).



### 7.4 Whatdocs/PROJECT_HISTORY.md
## Verification Notes (what was confirmed the prompt system *cannot* yet do (verified gaps)

- The chat `SY against source, and known discrepancies)

## 7. Prompt System Evolution (deep dive)

The prompt system evolvedSTEM_PROMPT` is **static** — it does from "one hardwired persona string" not rewrite itself per turn; dynamic
 to a multi-source,
dynamically  memory context arrives only via the `## Known User Facts` block assembled, agent-aware prompt pipeline that `PromptBuilder`
  assembles. Its story is about *what goes
into the prompt*, *.in what order*, and *
- The doc-agent prompt is **internally inconsistent** with its tool sethow it is assembled* — and it splits into two
distinct prompt lineages after v (see §9.4): it
  instructs `append_file2.` (dead/unregistered), references `git2.1: the **chat** system prompt and the **agent**
system prompt._diff` (not registered),
 

### and forbids `write_file` on existing docs 7.1 The persona / system prompt while tasks 1/2 instruct a full-file itself

- **v0.3 (identity layer):** system-p
rompt support was introduced  overwrite.
- `tiktoken` is absent, and the identity
  string was moved so `build_with_stats`'s `system_tokens out of_estimate `main.py` into a dedicated `` is the crude
  `len(self.systemapp/config/prompts.py` file
  (per_prompt) // 4` heuristic, not a real `NEW_DEVLOG.md`: "Moved system token count.

---

## 8. Tool prompts into a dedicated `app/config/p System Evolution (deep dive)

The tool system is the newest subsystem (rompts.py`
  file"). This was the first separation of *prompt configurationcommitted v2.2.1, expanded through the* from *application
  code*. At this stage the system prompt was purely an identity v2.4.0
working tree). It is **prompt / behavior layer.
-based** (not native function calling): the model- **v0.4–v1.1:** the system prompt was emits
`<tool_call>` tags, stored on `OllamaClient` at init the executor parses and runs them. Its evolution is the story of
 and prepended
  to every request; its *content*how JARVIS learned to act on its* changed little, but it now rode along with environment* (filesystem + git).

 the
  growing client-owned conversation list.
-### 8.1 Before tools: no external **v2.0 (rename → `app/config/prompt.py`):** the module was consolidated action

- **v0.1–v2.2:** JARVIS could only read and generate text. It had to
  `app/config/prompt.py` exporting a no file or git access
  beyond what the core conversation pipeline touched single `SYSTEM_PROMPT` constant.. Documentation and changelogs were
 The current
  persona text — *  produced by hand. `app/tools/` did"You are Jarvis—a calm, sharp, and occasionally witty digital
  architect." not exist.

### 8.2 The framework* with six numbered protocols (Core Identity appears (v2.2.1 committed; `NEW; STEM & Teaching; Automation
 _DEVLOG.md` re-groups it under v2 & Agents; Daily Operations & Content;.4.0)

> ⚠️ **Version discrepancy.** Core Constraints; Execution) — is the The committed timeline (§2) and v2.0-era
  definition and remains the chat system prompt today.
- `AGENTS.md`/`TOOLS.md`
> attribute **v2.2.1 (second lineage):** a * the tool framework to **v2.2.1**separate* task-specific prompt appeared —
 (`891fe4b`). `NEW_DEVLOG.md` (working  `DocumentationAgent._SYSTEM` in `-tree
> notes) re-groups the same workapp/agents/doc_agent.py`. This is an instruction set
  (tool-list placeholder under **v2.4.0**. This history follows, `<tool_call>` format, entry-format rules the committed
> record (v2.2, file-writing rules,
  versioning notes), distinct from the chat.1 introduction) and notes the working-tree expansion.

- `SYSTEM_PROMPT`.

### 7.2 Prompt **`base.py`** — three assembly / building blocks: `ToolResult context building

-` ( **vuniform return value),
  `ToolDefinition` (metadata + `handler`0.7 (Context Builder):** `OllamaClient.build_messages()` centralized assembly + `risk_level`/`requires_confirm —
  system prompt + persistentation` facts + conversation history. This),
  `ToolRegistry` (dict was the first
  "context builder keyed by name).
- **`executor.py`," but it sent **all** facts every turn** — `ToolExecutor` parses `< (the unbounded-context
  problemtool_call>` tags that later forced the v2.0 rewrite).
 and runs them. Three
  regex formats: JSON- **v2.0 (`PromptBuilder`):** `app/p `{name, args}`, hybrid `name({json})`, positional `name("...")`.
rompt/builder.py` replaced the client-owned
  builder. `PromptBuilder  Calls **deduplicated by tool name**.build()` merges the system prompt (a `seen` set). `MAX_OUTPUT_CHARS **and retrieved memories
  into ONE `system` message** (OpenAI-compatible consistency), appends conversation
  history = 4096` caps
  injected output. `has_calls`/`parse`/`run`/`format, and optionally the current user_result` form the interface.
  `to prompt. `build_with_stats()` added for
  debugging. Facts are now_openai_schema()` helpers exist for the *retrieved*, not "all".
- ** planned v3.0 native-calling migration.
- **Design choice:** prompt-based overv2.2 (`past_exchanges`):** `build()` native function calling, explicitly to gained `past_exchanges`; ordering fixed as
  **base prompt → past exchanges → stay
  compatible with local models that don't emit `tool_calls`. The tag memory facts** (episodic before format is
  "unambiguous and easy semantic). Direct
  response to the to parse" (`NEW_DEVLOG.md` / `doc 97%-context incident (see §5.3).
_agent.py` docstring).

### 8.3- **v2.2.1 (agentic, code-generated prompt):** the doc agent builds its The tools themselves (verified)

Registration is **hardcoded** in system prompt
  at runtime — `Tool `DocumentationAgent.__init__` via
`register_many(GIT_TOOLS)` + `registerRegistry.format_for_prompt()` is injected into `_SYSTEM` via
  `str.format(t_many(FILE_TOOLS)`. There is **noools_section=...)` ( plugin
discovery**.

| Tool |see §9.2). The prompt Source | risk_level | confirm | Notes is now *partly generated from
 |
|---|---|---|---|---|
| `git  the registered tools* — a feedback loop between code and prompt text_log` | `git_tools.py` | none | no.

### 7.3 Prompt conventions that stabilized | read-only |
| `git_diff_stat`

- **Single `system` message** ( | `git_tools.py` | none | no | readnot separate system + memory messages-only |
| `git_diff_full` | `git_tools) — chosen in v2.0
  for cross-backend.py` | none | no | read-only; self-tr compatibility.
- **`## Known User Facts`** block (from `PromptBuilder._uncates `DIFF_MAX_CHARS=8000` |
|format_memories`) and
  **`## Relevant Past `git_show` | `git_tools.py` | none Exchanges`** block (from `_format_p | no | read-only; self-truncatesast_exchanges`) — fixed
  injections into |
| `git_tags` | `git_tools.py the system message.
- **`<tool_call>` tag protocol** for the agent (` | none | no | read-only |
| `readv2.2.1):
  `<tool_call>{"name":_file` | `file_tools.py` | low | no "...", "args": {...}}</tool_call | exact-match `ALLOWED_READ` |
|>`, one per line; results returned `write_file` | `file_tools.py` | medium
  as `<tool_result name="..." status | **yes** | exact-match `ALLOWED="...">`. A model-agnostic convention_WRITE`; overwrites chosen over
  native function calling ( |

So **7 tools**:deferred to v3.0) for local-model compatibility 5 read-only git + 1 read + 1 write..
- **Tool-list rendering** (`ToolRegistry.format_for_prompt()`): human-readable list Safety is layered:
- **Path allowlists** (`ALLOWED_READ`/`ALLOWED_WRITE;
  tools whose `risk_level` ∉ `{`) enforced *inside the handlers* —
  the primary blast-radius controlnone, (exact low}` get a ` [<risk> risk-string match, no `..` resolution).
]` suffix
  (`write_file` → `[medium risk]`).

### 7.4 What the prompt- **Read-only git** enforced by `subprocess.run([...])` with a list (no `shell=True`,
  no mutate sub system *cannot* yet do (verified gaps)

- The chat `SYSTEM_PROMPT` iscommands).
- **Output truncation** (executor 4096; git tools 800 **static** — it does not rewrite0).
- **Confirmation gate** (`require_confirm itself per turn; dynamic
  memory context arrives only via the `## Known User Factsation=True`): only `write_file` triggers a
  blocking `input(" Execute` block that `PromptBuilder`
  assembles.
? (y/N): ")`; git tools and `read_file- The doc-agent prompt is **internally inconsistent` never prompt.
- **No raw exceptions** with its tool set (see §9.4): escape**: `ToolDefinition.execute` wraps everything into it
  instructs `append_file` (dead/unregistered), references `git_diff` a
  `ToolResult (not registered),
  and forbids`.

### 8.4 Execution flow (the mini-agentic loop)

`DocumentationAgent `write_file` on existing docs while.run(task)`:
1. build system prompt from tasks 1/2 instruct a full-file
 `format_for_prompt()` injected into  overwrite.
- `tiktoken` is absent, so ` `_SYSTEM`;
2. `response = model.generatebuild_with(messages)` (non-streaming);
3._stats`'s `system_tokens if `not executor.has_calls(text)` →_estimate` is the crude
  `len(self.system return text (done);
4. else_prompt) // 4` heuristic, not a real `parse` → append assistant message → `run` each call → collect
   ` token count.

---

## 8. Tool System Evolution (deep dive)

Theformat_result` blocks → append **one tool system is the** `user` message with all results newest subsystem (committed v2. → loop2.1, expanded through the v2.4.;
5. `MAX_ITERATIONS = 12`0
working tree). It is **prompt-based** ( ceiling; if exceeded, returns the iteration-limit string.

Results are batnot native function calling): the model emits
`<ched intotool_call>` tags a single `user` message, the executor parses and runs them.; tool results use a `user` role ( Its evolution is the story of
*how JARVIS learned to act on its environment* (filesystem + git).

### 8.1 Beforenot a
native `tool` role) because this is prompt-based calling.

### 8.5 What the tool system *cannot* yet do (verified gaps)

- **No dynamic discovery.** Tools are tools: no external action

- **v0.1– added only by editing `GIT_TOOLS`v2.2:** JARVIS could only read and generate text./`FILE_TOOLS It had no file`
  and re-registering or git access
  beyond what the core conversation pipeline touched; `app/tools/__init__.py` is empty (no aggregator).
- **`append_file. Documentation and changelogs were
` is dead code.** Its `ToolDefinition`  produced by hand. `app/tools/` did not exist. is written *after a `

### 8.2 The framework appearsreturn`*
  inside `append_file()` in `file (v2.2.1 committed; `NEW_DEVLOG.md_tools.py`, so it is never in `FILE_TOOLS`. A model
  following the prompt` re-groups it under v2.4.0)

> ⚠️ **Version discrepancy.** The committed timeline emits `<tool_call>{"name":"append_file",... (§2) and `AGENTS}>` → `Unknown tool`.
  The.md`/`TOOLS.md only write`
> attribute the tool is `write_file` tool framework to **v2.2.1** (` (overwrites), contradicting "Never use write_file
  on existing docs."
891fe4b`). `NEW_DEVLOG.md` (working-tree
> notes) re-groups the same work under- **`git_diff` referenced but absent.** Task 1 says "Use git_log and git **v2.4.0**. This history follows the_diff" — only
  `git_diff_stat committed
`/`> record (v2.2.1 introductiongit_diff_full` exist.
- **`git_status) and notes the working-tree expansion.

- **`base.py`** — three building blocks`/`git_branch`** exist as functions but: `ToolResult` (uniform return value), are not in `GIT_TOOLS`.
- **Name-d
  `ToolDefinition` (metadata + `edup** in `parse()` collapses multiple same-name calls in onehandler` + `risk_level`/`requires_confirm turn;
  `test_100_tool_cation`),
  `ToolRegistry` (dictalls_parsed` fails (expects keyed by name).
- **`executor.py 100, gets 1).
- **Native calling ready but dormant.** `to_openai_schema`** — `ToolExecutor` parses `<tool_call>` tags and runs them. Three()`/`to_openai_schemas()` are
 
  regex formats: JSON `{name, args}`, defined but unused — the v3.0 migration hybrid `name({json})`, positional ` path.
- **Confirmation blocks stdin**name("...")`.
  Calls **deduplicated — fine in the interactive `docs` flow, would hang any
  headless deployment by tool name** (a `seen` set). `MAX_OUTPUT_CHARS = 4096` caps
 .

(See `docs/TOOLS.md` for the exhaustive source-verified account.)

---

## injected output. `has_calls`/`parse 9. Agent System Evolution (deep`/`run`/`format_result` form the dive)

JARVIS had no agent layer until interface.
  `to_openai_schema()` helpers exist for the planned the tool framework landed; the agent is the consumer
that v3 ties `ModelClient.0 native-calling migration.
- **Design choice:** prompt-based` + `ToolRegistry` + `ToolExecutor over native function calling, explicitly to stay
  compatible with local models` into a loop.

### 9.1 No agents ( that don't emit `tool_calls`. The tag format is
  "unambiguous andv0.1 – v2.2)

The entire system was a single REPL pipeline in `main easy to parse" (`NEW_DEVLOG.md`.py`. There was no
`app/agents/` package / `doc_agent.py` docstring).

, no agent class, no orchestration layer.### 8.3 The tools themselves (ver "Agency" meant the main
ified)

Registration is **hardcodedloop's extract → store → retrieve → generate cycle, not autonomous tool use** in `DocumentationAgent.__init__` via
.

###`register_many(GIT_TOOLS)` + 9.2 The first (and only) agent: `DocumentationAgent` (v2. `register_many(FILE_TOOLS)`. There is **no plugin
discovery**.

| Tool |2.1 committed)

- `app/agents/__ Source |init__.py` is empty; `app/agents/doc_agent.py` holds the sole
  `Documentation risk_level | confirm | Notes |
|---|---|---|---|---|
| `gitAgent` class + `run_interactive`.
_log` | `git_tools.py` | none | no- **No base `Agent` class, no registry, | read-only |
| `git_diff_stat` no multi-agent orchestrator** — ` | `git_tools.py` | none | no | readDocumentationAgent`
  is a concrete,-only |
| ` purpose-built documentation generatorgit_diff_full` | `git_tools, not a generic.py` | none | no agent runtime.
- ** | read-only; self-trArchitecture:** a mini agentic loop with prompt-based tooluncates `DIFF_MAX_CHARS=8000` |
| `git calling — exactly the
  shape the docstring_show` | `git_tools.py` | none says "v3.0's full agentic runtime" will generalize (no such
  runtime | no | read-only; self-truncates |
| `git_tags` | `git_tools.py` | none | no exists yet | read-only |
| `read_file; a forward-looking note).
- **Dependencies:** depends on the `ModelClient` Protocol (any
  `` | `file_tools.py` | low | no |generate(messages, stream=False, on_token=None, ** exact-match `ALLOWED_READ` |
| `kwargs) -> ModelResponse` object),
write_file` |  injected at construction `file_tools.py` | medium |. The agent calls the model **non **yes** | exact-match `ALLOWED_WRITE-streaming**.
- **Lifecycle:** constructed in `main.main()` from
  `switcher.get`; overwrites |

So **7 tools**:_client(profiles[active][" 5 read-only git + 1 read + 1 write. Safety is layered:
docs"])- **Path allow or switcher.router.default_model`;
 lists** **recreated** on a `model <name (`ALLOWED_READ`/`ALLOWED_WRITE`) enforced *>` switch (new client → new agentinside the handlers* —
  the primary blast-radius control (). Invoked only on the
  `docs` commandexact-string match, no `..` resolution).
 via `run_interactive`.
- **Tasks- **Read-only git** enforced by `subprocess:** `_.run([...])` withTASKS` predefine changelog a list (no `shell (1), devlog (2), both / full-history (=True`,
  no mutate subcommands3),
  custom (4), cancel (q). `).
- **Output truncation** (executor 4096; git tools 8000).
- **ConfirmationMAX_ITERATIONS = 12`.

### 9.3 Why prompt gate** (`require_confirmation=True`-based (design rationale): only `write_file` triggers a
 )

`doc_agent.py` docstring: not all local blocking `input(" Execute? (y/N): models support `tool_calls`; prompt-based works
on any instruction ")`; git tools and `read_file` never prompt-following model; `<tool_call>` is unambiguous.
- **No raw exceptions escape; the same interface
means v3.0**: `ToolDefinition.execute` wraps everything is "one method change in `Model into a
  `ToolResult`.

### 8Client`." This matches the tool framework.4 Execution flow (the mini-agentic loop)

`DocumentationAgent.run(task's
rationale (§8.2) and the v2.2)`:
1. build system prompt from.1 timeline entry.

### 9.4 Agent evolution `format_for_prompt()` injected into — gaps and the v3.0 horizon (verified `_SYSTEM`;
2. `response = model)

- **Prompt/tool mismatch** (see.generate(messages)` (non-streaming §8.5): `append_file` (dead), `git_diff`);
3. if `not executor.has_calls(text (absent),
  `git_status`/`)` → return text (done);
4. else `git_branch` (unregistered). The doc agentparse` → append assistant message → `run` each call → collect
  's instructions do not match
  its `format_result` blocks → append ** registered tools.
- **Model resolution under defaults is uncertain.**one** `user` message with all results → `profiles["local"][" loop;
5. `MAX_ITERATIONS = 12` ceiling; if exceeded, returns the iteration-ldocs"] = "docs"`
  but the default `models` dict only hasimit string.

Results are batched into `general`/`autocomplete`, so
  `get_client("docs")` is `None` and a single `user` message; tool results use the agent falls back to
  `switcher a `user` role (not a
native `tool.router.default_model` (the `general`` role) because this is prompt-based client). A real `config.yaml` is
 calling.

### 8.5 What the tool system  expected to define a `docs` model. *cannot* yet do (verified gaps)

 (`config- **No dynamic discovery.** Tools are.yaml` unreadable here — see caveats.)
- **Future (code comments added only by editing `GIT_TOOLS` / docstrings only, not implemented):** native function calling/`FILE_TOOLS`
  and re-registering
  (v3.; `app/tools/__init__.py` is empty0) using the existing `to_openai_schema()`; a "full agentic runtime (no aggregator).
- **`append_file" general` is dead codeizing
  this loop; a user-configurable permission system replacing hardcoded allowlists; a
  `risk_level=".** Its `ToolDefinition` is written *after a `return`*
  inside `append_file()` in `file_tools.py`, so it is never in `FILEhigh"` tier (`run_python` — v3._TOOLS`. A model
  following the prompt0+). `ARCHITECTURE.md` also lists emits `<tool_call>{"name":"append_file an
  "Agent Orchestration Layer"",...}>` → `Unknown tool`.
  The as a future improvement.

(See `docs/AGENTS.md` for the exhaustive only write tool is `write_file` (overwrites), contradicting "Never use source-verified account.)

---

## 10. Configuration Evolution (deep dive)

Configuration write_file
  on existing docs."
 evolved from hardcoded constants inside modules, to a centralized- **`git_diff` referenced but absent.**
dataclass singleton, to an overrid Task 1 says "Use git_log and gitable external YAML + `.env` system. Its story is
*where settings live*_diff" — only
  `git_diff_stat`/`git_diff_full` exist.
- **`git and *who can override them*.

###_status`/`git_branch`** exist as functions 10.1 Hardcoded era (v0.1 – v1.1 but are not in `GIT_TOOLS`.
- **Name-dedup** in `parse()` collapses)

- **v0.1–v0.5:** the model name multiple same-name calls in one turn;
  `test_100_tool_calls_parsed` fails (expects 100, gets 1).
 (`deepseek-r1:32b` → `qwen3`) and the system prompt were
  hardcoded; a single `settings.py` held constants- **Native calling ready but dormant.**.
- **v0.6–v1.1:** globals grew as `to_openai_schema()`/`to_openai subsystems were added; configuration was_schemas()` are
  defined but unused scattered
  across modules. `get_default_model()` did not yet exist ( — the v3.0 migration path.
- **Confirmation blocks stdin** — fine in the interactiveit arrived in v2.0.1 to
  replace the `docs` flow, would hang any
  headless broken `_DefaultModel` object).

 deployment.

(See `docs/TOOLS### 10.2 Centralized dataclass singleton.md` for the exhaustive source-ver (v2.0)

- **`Settings` dataclass**ified account.)

---

## 9. Agent System Evolution (deep dive)

JARVIS + nested config dataclasses: `ModelConfig had no agent layer until the tool`, `MemoryConfig`,
  `ContextConfig framework landed; the agent is the consumer`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`,
  `
that ties `ModelClient` + `ToolRegistry` + `ToolExecutor` into a loopPathsConfig`.
- **Thread-safe singleton** `get_settings()` (.

### 9double-checked locking.1 No agents (v0.1 – v2 with
  `.2)

The entire system was a single REthreading.Lock`).
- `PathsConfig` centralized filesystem pathsPL pipeline in `main.py`. There was no (`data_dir` plus `memories`,
  `conversations_dir`, `default_conversation
`app/agents/` package, no agent` properties).
- Default `default_model class, no orchestration layer. "Agency" meant the main
loop's extract = "qwen3-8b.gguf"` (the v2.0-era default → store → retrieve → generate cycle,; the live working
  tree's default client not autonomous tool use.

### 9.2 The first (and only) agent: resolves to `llama-3.2-3b-instruct `DocumentationAgent` (v2.2.1 committed` via the `models` dict — see
  §)

- `app/agents/__init__.py` is empty6.4).

### 10.3 External YAML +; `app/agents/doc_agent.py` holds dynamic router (v2.1)

- `Settings.load the sole
  `DocumentationAgent`()` reads optional `config.yaml` ( class + `run_interactive`.
- **YAML, with comments, gitignored)No base `Agent` class, no registry, and
  overrides defaults; hard-coded fallback preserved if absent.
 no multi-agent orchestrator** — `- `MemoryConfig.min_relevance_scoreDocumentationAgent`
  is a concrete, purpose-built documentation generator, not`, `candidate_overshoot_factor`, ` a generic agent runtime.
RankingConfig`
  weights, `ContextConfig.tokenizer- **Architecture:** a mini agent_method` introduced.
ic loop with prompt-based tool calling — exactly the
  shape the docstring says "v3.0's full agentic runtime" will generalize (no such
  runtime exists yet; a forward-looking note).
- **Dependencies:** depends on the `ModelClient` Protocol (any
  `generate(messages, stream=False, on_token=None, **kwargs) -> ModelResponse` object),
  injected at construction. The agent calls the model **non-streaming**.
- **Lifecycle:** constructed in `main.main()` from
  `switcher.get_client(profiles[active]["docs"]) or switcher.router.default_model`;
  **recreated** on a `model <name>` switch (new client → new agent). Invoked only on the
  `docs` command via `run_interactive`.
- **Tasks:** `_TASKS` predefine changelog (1), devlog (2), both / full-history (3),
  custom (4), cancel (q). `MAX_ITERATIONS = 12`.

### 9.3 Why prompt-based (design rationale)

`doc_agent.py` docstring: not all local models support `tool_calls`; prompt-based works
on any instruction-following model; `<tool_call>` is unambiguous; the same interface
means v3.0 is "one method change in `ModelClient`." This matches the tool framework's
rationale (§8.2) and the v2.2.1 timeline entry.

### 9.4 Agent evolution — gaps and the v3.0 horizon (verified)

- **Prompt/tool mismatch** (see §8.5): `append_file` (dead), `git_diff` (absent),
  `git_status`/`git_branch` (unregistered). The doc agent's instructions do not match
  its registered tools.
- **Model resolution under defaults is uncertain.** `profiles["local"]["docs"] = "docs"`
  but the default `models` dict only has `general`/`autocomplete`, so
  `get_client("docs")` is `None` and the agent falls back to
  `switcher.router.default_model` (the `general` client). A real `config.yaml` is
  expected to define a `docs` model. (`config.yaml` unreadable here — see caveats.)
- **Future (code comments / docstrings only, not implemented):** native function calling
  (v3.0) using the existing `to_openai_schema()`; a "full agentic runtime" generalizing
  this loop; a user-configurable permission system replacing hardcoded allowlists; a
  `risk_level="high"` tier (`run_python` — v3.0+). `ARCHITECTURE.md` also lists an
  "Agent Orchestration Layer" as a future improvement.

(See `docs/AGENTS.md` for the exhaustive source-verified account.)

---

## 10. Configuration Evolution (deep dive)

Configuration evolved from hardcoded constants inside modules, to a centralized
dataclass singleton, to an overridable external YAML + `.env` system. Its story is
*where settings live* and *who can override them*.

### 10.1 Hardcoded era (v0.1 – v1.1)

- **v0.1–v0.5:** the model name (`deepseek-r1:32b` → `qwen3`) and the system prompt were
  hardcoded; a single `settings.py` held constants.
- **v0.6–v1.1:** globals grew as subsystems were added; configuration was scattered
  across modules. `get_default_model()` did not yet exist (it arrived in v2.0.1 to
  replace the broken `_DefaultModel` object).

### 10.2 Centralized dataclass singleton (v2.0)

- **`Settings` dataclass** + nested config dataclasses: `Model- **Bug:**Config`, `MemoryConfig`,
  `ContextConfig `Settings.load()` initially returned `cls()` (ignoring parsed config) — fixed
  in v2.1.1.
- Dynamic router built from config; `TaskType(role)` bridges YAML role strings to the
  enum.

### 10.4 Profiles, model registry, env vars (v2.4 working tree)

- `Settings` gains **`profiles`** (`local`, `cloud`), each mapping `TaskType` roles →
  model keys; an **`active_profile`** field; a broader **`models`** dict of
  `ModelConfig` instances.
- `reset_settings()` added (test helper) to clear the singleton.
- `dotenv.load_dotenv()` runs at `main.py` startup; `ModelConfig` API keys support
  `env:VAR` resolution in the factory (`_resolve_key`).
- Model-key resolution: profiles reference keys that must exist in `models`; under
  shipped Python defaults only `general`/`autocomplete` exist, so `code`/`reasoning`/
  `docs`/`stem`/`cloud` lookups are skipped (see §6.4).

### 10.5 Configuration fields — defined vs used (verified gap)

Many fields are declared but **not read** by the running system (carried from §3.1):

- `MemoryConfig`: ``, `ConversationConfig`, `Retriemax_memories`, `enable_ranking`, `min_confidence` (unused).
- `RetrievalConfig.method`, `keyword_min_overlap` (the keyword retriever hardcodes
  `min_keyword_overlap=1`; `method` is ignored).
- `RankingConfig` weights — `MemoryRanker` uses its own `DEFAULT_WEIGHTS`, not
  `settings.ranking`.
- `candidate_overshoot_factor` — `MemoryManager.retrieve()` hardcodes the 3× overshoot.
- `ContextConfig.compression_threshold`, `estimation_method` (unused).

### 10.6 What configuration *cannot* yet do (verified)

- **No runtime validation** — dataclasses + type hints only; a bad YAML type flows
  through to a downstream runtime error.
- **`config.yaml` is gitignored and unreadable in this audit** — all runtime wiring is
  inferred from `settings.py` defaults + `NEW_DEVLOG.md`.
- **No schema/version field** in `config.yaml`; loading is an untyped `yaml.safe_load`
  plus `ModelConfig(**data)`.
- `load_dotenv()` is invoked at startup but `settings.py` itself contains no
  `os.getenv()` overrides — env vars are only consumed by the model factory's `env:VAR`
  key resolution, not by the `Settings` dataclass.

---

## Verification Notes (what was confirmed against source, and known discrepancies)