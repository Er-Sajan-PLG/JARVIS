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
> **Scope.** Nineteen sections: (1) Overall Architecture Evolution, (2) Timeline,
> (3) Subsystem Evolution, (4) Memory System Evolution, (5) Conversation System
> Evolution, (6) Model System Evolution, (7) Prompt System Evolution, (8) Tool
> System Evolution, (9) Agent System Evolution, (10) Configuration Evolution,
> (11) Directory Evolution, (12) Major Refactors, (13) Current Design Philosophy,
> (14) Important Invariants, (15) Coding Standards, (16) Naming Conventions,
> (17) Architecture Patterns Known, (18) Technical Debt, (19) Future Direction. A
> short **Verification Notes** appendix records what was confirmed against source
> and the known gaps/discrepancies.

---

## How to read this document (sources & caveats)

**Authoritative sources used:**

- **Git history** — 38 commits in the repository; `HEAD = ba2026f` (short). The latest annotated tag is `v2.5.0` (commit f9fa0689bd3ee09a7daa01deef6cdfe2947d1230, tagged Sat Jul 18 2026 +0545). Git tags are treated as the canonical source for release versions in these docs.
- **Committed docs** — `docs/CHANGELOG.md` and `docs/DEVLOG.md` are taken from the committed tree and reconciled with git history.
- **Current source (working tree)** — the working tree may differ from the committed `HEAD`; `app/config/version.py` and other docstrings may contain version strings that do not match git tags. Prefer the git tag for canonical release identity and dates.

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

## 7. Prompt System Evolution (deep dive)

The prompt system is the glue that turns raw state (memories, conversation, past exchanges) into the ordered message list a model receives. Its evolution is the story of moving from ad-hoc string concatenation to a single, composable `PromptBuilder`.

### 7.1 From inline strings to a builder

v0.3–v0.6: the system prompt was concatenated inline at the call site; facts (once they appeared in v0.6) were appended as plain strings into the same growing prompt.

v0.7: `OllamaClient.build_messages()` centralized system + facts + history assembly so every request was constructed identically.

v2.0: `PromptBuilder.build()` took over. The system prompt and the retrieved memories are merged into one system message; the conversation history is appended as user/assistant turns; an optional current user prompt closes the list. `build_with_stats()` was added for debugging context fits.

### 7.2 Episodic-before-semantic ordering (v2.2)

`PromptBuilder.build()` gained a `past_exchanges` argument. The resulting ordering inside the single system message is base prompt → relevant past exchanges → retrieved memory facts — episodic context is placed before the semantic `## Known User Facts` block (a deliberate choice: recent conversational context primes the model before durable facts). This was part of the v2.2 response to the 97%-context incident (see §5.3): fewer memories, shorter exchanges, and a fixed `safety_margin`.

### 7.3 One system message, every backend

A core design principle (§1.3, principle 6) is to combine system prompt + memories into ONE system message for cross-backend compatibility — rather than relying on provider-specific system-role handling. The `ModelClient` Protocol contract expects a standard OpenAI-style messages list, so `PromptBuilder` emits exactly that.

### 7.4 The agent prompt path (v2.2.1+)

The documentation agent uses a separate prompt system from the main chat path. `DocumentationAgent` carries its own system prompt (`_SYSTEM`) that instructs the model on the available tools and the workflow for answering repo questions via `<tool_call>` loops. This prompt is independent of `PromptBuilder` and is tailored to tool-using behavior rather than conversational memory injection.

### 7.5 What the prompt system cannot yet do (verified gaps)

- The doc-agent system prompt (`_SYSTEM`) tells the model to use `append_file` and `git_diff`, both of which are not registered tools (see §8), so the agent is instructed toward calls it cannot execute.
- `build_with_stats()` exists but the main loop uses `build()` directly; the stats hook is diagnostic-only.
- No prompt templating/caching layer exists beyond `PromptBuilder`; system text is assembled per-turn.

## 8. Tool System Evolution (deep dive)

The tool system is the execution half of the agent layer: it turns a model-emitted `<tool_call>` into a real, sandboxed action against the repo. It is entirely prompt-based — the model is not given native function-calling schemas at runtime (§1.3, principle 7); `to_openai_schema()` helpers exist only for the planned v3.0 migration.

### 8.1 Origins in the agent scaffold (v2.2.1)

The agent/tool framework landed together in v2.2.1 as `app/tools/`: `ToolResult`, `ToolDefinition`, `ToolRegistry`, and `ToolExecutor`. The `docs` command routes to `DocumentationAgent`, which calls `ToolRegistry(GIT_TOOLS + FILE_TOOLS)` → `ToolExecutor` → `git_tools.py` / `file_tools.py`. Tools are allowlisted (exact-match `ALLOWED_READ` / `ALLOWED_WRITE` path sets), git operations are read-only, output is capped, and a confirmation gate protects destructive calls.

### 8.2 The registered tool set

Seven tools are registered: `git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags`, `read_file`, `write_file`. `write_file` is the only `requires_confirmation` tool. The git tools live in `GIT_TOOLS`; the file tools in `FILE_TOOLS` (`read_file` + `write_file`). `git_status` and `git_branch` are defined in `git_tools.py` but never registered, and `git_diff` is referenced by the doc-agent prompt but likewise absent.

### 8.3 Parsing and execution

`ToolExecutor` extracts `<tool_call>` tags via three regex formats, then deduplicates by tool name — so multiple same-name calls in a single turn collapse to one execution. Output from each tool is capped at `MAX_OUTPUT_CHARS = 4096`. The executor is fail-safe: unknown or malformed tool calls never raise; they return a `ToolResult` describing the failure, so a bad model emission cannot crash the agent loop.

### 8.4 Safety model

Safety is layered: (1) path allowlists restrict every file read/write to an exact set of approved paths; (2) git tools are read-only by construction; (3) output is truncated to `MAX_OUTPUT_CHARS`; (4) `write_file` requires interactive confirmation. There is no shell-execution tool and no arbitrary-command surface.

### 8.5 What the tool system cannot yet do (verified gaps)

- `append_file` is dead code — its `ToolDefinition` is defined after a `return` inside `append_file()`, so it can never be registered, yet `doc_agent._SYSTEM` instructs the model to use it.
- `git_diff`, `git_branch`, and `git_status` are referenced (in the doc-agent prompt or in `git_tools.py`) but not registered, so the model cannot call them.
- Name-based dedup collapses repeated same-name calls in one turn; this is why `tests/stress_test.py::test_100_tool_calls_parsed` fails (expected 100, got 1).
- Native function calling is not wired; only the `to_openai_schema()` serializer exists for future use.

## 9. Agent System Evolution (deep dive)

The agent layer is the youngest subsystem in JARVIS. It exists entirely to let the assistant act on its own repository (read files, inspect git history, regenerate docs) through a prompt-driven tool loop.

### 9.1 No agent, then one (v2.2.1)

Before v2.2.1 there was no agent layer at all — the system was a single conversational pipeline. v2.2.1 introduced `DocumentationAgent` alongside the `app/tools/` framework and a `TaskType.DOCS` routing enum, plus the `docs` CLI command that hands control to `run_interactive(doc_agent)`.

### 9.2 The single agent

`app/agents/` contains only an empty `__init__.py` and `doc_agent.py`; `DocumentationAgent` is the sole agent class. It runs a prompt-based tool loop: it emits `<tool_call>` tags, the `ToolExecutor` runs them, and results are fed back until the agent judges the question answered (capped at `MAX_ITERATIONS = 12`). It is re-created whenever the active model profile switches, and `ModelSwitcher.get_client()` supplies it a profile-appropriate docs client.

### 9.3 What the agent system cannot yet do (verified gaps)

- The doc-agent system prompt (`_SYSTEM`) references `append_file` and `git_diff`, both unregistered (see §8) — the agent is primed to emit calls it cannot execute.
- There is exactly one agent; no task-specialized or multi-agent orchestration exists beyond the scaffolding described in the working-tree reference docs.
- The agent loop is interactive/CLI-bound; it relies on the `ToolExecutor` confirmation gate (`input()`), so it is not headless-safe without that gate being injectable.

## 10. Configuration Evolution (deep dive)

Configuration is the face JARVIS presents to operators: which models exist, how they are routed, and how the memory/context subsystems tune themselves. Its evolution is a steady migration from hardcoded constants to a layered, overridable config stack.

### 10.1 From constants to dataclasses (v0.1 → v2.0)

v0.1–v0.5: the model name and system prompt were hardcoded; configuration was a single `settings.py` of module-level constants.

v0.6–v1.1: globals accumulated as features were added. The `get_default_model()` helper was introduced in v2.0.1 to replace a broken `_DefaultModel` object.

v2.0: configuration was formalized as a `Settings` dataclass plus nested config dataclasses — `ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, `PathsConfig` — behind a thread-safe `get_settings()` singleton (`threading.Lock`).

### 10.2 External YAML and layered overrides (v2.1)

`Settings.load()` gained the ability to read an optional `config.yaml` (YAML, with comments, gitignored) and override the Python defaults, while preserving the hardcoded fallback if the file is absent. This version also introduced `MemoryConfig.min_relevance_score`, `candidate_overshoot_factor`, `RankingConfig` weights, and `ContextConfig.tokenizer_method`.

### 10.3 Profiles and multi-backend wiring (v2.4, working tree)

`Settings` grew a `profiles` map (`local`, `cloud`) associating roles with model keys, a top-level `default_model` field, and a broader `models` dict. `reset_settings()` was added for tests, and `dotenv.load_dotenv()` runs at `main.py` startup so `env:VAR` API-key references (used by the openrouter backend) resolve. `factory.create_client` resolves `env:VAR` strings into real keys.

### 10.4 What configuration cannot yet do (verified gaps)

- `config.yaml` is gitignored and unreadable in this audit; every claim about runtime model/backend wiring is therefore inferred from the hardcoded `app/config/settings.py` defaults, not a deployed file.
- Those shipped defaults resolve only the `general` model (llama-3.2-3b-instruct on llama.cpp, port 8080). The `local` profile's `code`/`reasoning`/`docs`/`stem` role keys point at model entries absent from the default `models` dict, and the `cloud` profile references a `"cloud"` key that does not exist — so the cloud profile and the autocomplete client (qwen2.5-1.5b, port 8082) are effectively inert under defaults.
- Many `MemoryConfig`/`RetrievalConfig`/`RankingConfig` fields (`max_memories`, `enable_ranking`, `min_confidence`, `candidate_overshoot_factor`, `RetrievalConfig.method`, the `RankingConfig` weights) are defined but not read by the memory subsystem, which uses its own hardcoded constants instead.

---

## 11. Directory Evolution (deep dive)

The repository layout tracks the architecture's journey from a single-file script to a package hierarchy. The tree below is the **current v2.4.0 working-tree state**, verified by listing `app/` and the repo root.

### 11.1 Current layout (v2.4.0 working tree)

```
JARVIS/
├── app/
│   ├── main.py                 # REPL entry point
│   ├── config/
│   │   ├── prompt.py           # SYSTEM_PROMPT
│   │   ├── settings.py         # Settings dataclasses + get_settings()
│   │   └── version.py          # VERSION = "v.2.4.0"
│   ├── memory/
│   │   ├── schema.py           # Memory dataclass
│   │   ├── store.py            # MemoryStore (JSON CRUD)
│   │   ├── manager.py          # MemoryManager (orchestrator)
│   │   ├── fact_extractor.py   # rule-based extraction
│   │   ├── rules.py            # trigger → category/type
│   │   ├── retrieval.py        # CandidateRetriever Protocol
│   │   ├── hybrid_retriever.py # keyword + vector merge
│   │   ├── vector_retriever.py # ChromaDB cosine
│   │   ├── ranking.py          # MemoryRanker (5 weighted factors)
│   │   └── conversation_store.py  # ConversationVectorStore
│   ├── conversation/
│   │   └── manager.py          # ConversationManager
│   ├── context/
│   │   └── manager.py          # ContextWindowManager (pair-trim)
│   ├── prompt/
│   │   └── builder.py          # PromptBuilder
│   ├── models/
│   │   ├── client.py           # ModelClient Protocol + ModelResponse
│   │   ├── factory.py          # create_client (backend dispatch)
│   │   ├── router.py           # ModelRouter (score-based)
│   │   ├── switcher.py         # ModelSwitcher (profiles)
│   │   ├── llamacpp_client.py  # LlamaCppClient
│   │   ├── ollama_client.py    # OllamaClient
│   │   └── openrouter_client.py# OpenRouterClient (working tree)
│   ├── agents/
│   │   ├── __init__.py         # empty
│   │   └── doc_agent.py        # DocumentationAgent (sole agent)
│   ├── tools/
│   │   ├── base.py             # ToolResult/ToolDefinition/ToolRegistry
│   │   ├── executor.py         # ToolExecutor (<tool_call> parser)
│   │   ├── git_tools.py        # GIT_TOOLS (read-only)
│   │   └── file_tools.py       # FILE_TOOLS (allowlisted)
│   ├── utils/
│   │   ├── tokenizer.py        # get_token_counter chain
│   │   └── server_manager.py   # ensure_server_running (unused)
│   ├── api/                    # empty __init__.py (stub)
│   └── brain/                  # empty __init__.py (stub)
├── config.yaml                 # gitignored, optional overrides (unreadable here)
├── data/                       # runtime-only: memories.json, conversations/, chroma/ (gitignored)
├── docs/                       # CHANGELOG/DEVLOG + reference docs (API/TOOLS/AGENTS/DATABASE/LLM/CONFIG/…)
├── tests/                      # stress_test.py
├── .continue/                  # Continue.dev autocomplete agent config (v2.3.0 intent)
├── knowledge/                  # present on disk, undocumented
├── scripts/                    # present on disk, undocumented
├── tmp/                        # scratch (e.g. tail.md), undocumented
├── hello.py                    # stray script at root, undocumented
├── requirements.txt
└── README.md
```

### 11.2 How the tree grew

- **v0.0.0–v0.5:** a flatter tree. The client (`OllamaClient`) owned both transport and the `conversation` list; `app/config/prompt.py` held `SYSTEM_PROMPT`; persistence was a single `conversation.json`. No dedicated `memory/`, `conversation/`, `context/`, `prompt/`, `models/`, `agents/`, or `tools/` packages existed yet.
- **v1.0–v1.1:** rules and a `Memory`-like fact record began to separate from the client, but the layout was still monolithic (facts + chat interleaved in one file).
- **v2.0 (the big split):** the rewrite created the package hierarchy — `config/`, `memory/`, `conversation/`, `context/`, `prompt/`, `models/` — each owning one responsibility behind a `Protocol`. Conversation state moved out of the client into `conversation/manager.py`; the client became a pure `generate()` transport. `utils/tokenizer.py` and `utils/server_manager.py` appeared.
- **v2.2:** the dual-store arrived — `data/` (with `memories.json`, `conversations/`, and `chroma/`) became the persistence layer beside JSON; `memory/vector_retriever.py` and `memory/conversation_store.py` were added.
- **v2.2.1:** the agent/tool layer landed as `agents/` (just `doc_agent.py`) and `tools/` (`base.py`, `executor.py`, `git_tools.py`, `file_tools.py`).
- **v2.3.0 (working tree):** `.continue/` was added for the Continue.dev autocomplete agent; `scripts/`/`knowledge/`/`tmp/`/`hello.py` also appear on disk but are not described by any committed doc (honest gap).
- **v2.4.0 (working tree):** `models/` gained `switcher.py`, `openrouter_client.py`, and `factory.py`; `api/` and `brain/` were added as **empty stub packages** (no HTTP server implemented). `config.yaml` sits at the repo root, gitignored.

### 11.3 Empty / stub packages (honest inventory)

`app/api/` and `app/brain/` contain only `__init__.py`. `requirements.txt` lists `fastapi`/`uvicorn`/`starlette`, but no server code exists; the sole entry point remains `python app/main.py`. Web/GUI/voice remain roadmap-only (see §1.4). The root `knowledge/`, `scripts/`, `tmp/`, and `hello.py` are present but undocumented — likely scratch/experiment artifacts.

## 12. Major Refactors (deep dive)

This isolates the turning points where the code was **rewritten** (not merely extended). The full timeline is §2; here we name the refactors that changed the *shape* of the system.

### 12.1 v2.0 — the architecture rewrite (the only true "rewrite")

The monolithic client was decomposed into single-responsibility modules behind `Protocol` boundaries: `MemoryStore` / `CandidateRetriever` / `MemoryRanker` / `ContextWindowManager` / `PromptBuilder` / `ModelClient`. Two consequences reshaped everything downstream: (1) retrieval became "retrieve only what's relevant" instead of "send all memories"; (2) conversation state moved out of the client. The `ModelRouter` was introduced but, famously, **built but never called** until v2.0.1 (bug 3 — §6.2).

### 12.2 v0.8 / v1.0 — memory becomes structured, then intentional

- **v0.8:** facts became `{category, type, value}` dicts (queryable/structured).
- **v1.0:** the behavior engine (`append`/`replace`/`ignore`) added *intent*, driven entirely by `RULES`. This was a refactor of what memory *meant*, not just how it was stored.

### 12.3 v2.2 — dual-store semantic memory

A refactor of the persistence/retrieval layer: ChromaDB (`jarvis-memories`, `jarvis-conversations`) was added as a **derived** index rebuilt from JSON every startup. Introduced invariant: JSON is source of truth; vectors are disposable. `HybridRetriever` merged keyword + vector and deduped by `memory.id`.

### 12.4 v2.2.1 — prompt-based agent/tool framework

A structural *addition* that changed control flow: the `docs` command now hands control to `DocumentationAgent` → `ToolExecutor`. The model emits `<tool_call>` tags; an executor parses and runs them. `to_openai_schema()` helpers were added for the future v3.0 native-function-calling migration but left **unwired**.

### 12.5 v2.4 — multi-profile model switching

`ModelSwitcher` refactored model wiring from a single router to **one `ModelRouter` per profile** (`local`/`cloud`), built from `Settings.profiles` × `Settings.models`. `factory.create_client` centralizes backend dispatch and `env:VAR` API-key resolution. The dead `router.default_model` fallback in `main.py` (§6.4) is a vestige of this transition.

### 12.6 Cross-cutting refactors

- **Tokenizer chain (v2.0):** `get_token_counter()` tries tiktoken → transformers → word, so context counting never hard-fails. (tiktoken is *not* a dependency — the live path is transformers/word.)
- **Streaming signature (v2.1):** `stream`/`on_token` became named params so they don't leak into provider APIs (a `**kwargs` leak had caused an API error).
- **Settings → dataclasses + config.yaml (v2.0 → v2.1 → v2.4):** module constants became nested dataclasses, then gained an external YAML override and profile maps.

## 13. Current Design Philosophy (deep dive)

The principles below are observed in code and stated in `docs/DEVLOG.md` (v2.0 notes). They are the "why" behind every refactor in §12 (and restate/extend the §1.3 principles).

### 13.1 Interface-first, implementation-hidden

One clean `Protocol` per subsystem (`ModelClient`, `CandidateRetriever`, `MemoryStore`, `MemoryRanker`, `ContextWindowManager`, `PromptBuilder`). New backends (ChromaDB, OpenRouter) dropped in with zero caller changes. Prefer `Protocol` over `ABC` so third-party classes satisfy interfaces structurally.

### 13.2 Memory-first, retrieve-only-relevant

Facts are **extracted and stored before retrieval** in the main loop, so a fact stated this turn is available this turn. Retrieval returns only the top-k relevant memories (overshoot then rank), never the whole store.

### 13.3 Hybrid retrieval by necessity

Keyword catches exact matches; vector catches semantic ones. `HybridRetriever` runs both and dedups by `memory.id`. Neither alone is sufficient.

### 13.4 Coherence-preserving context trim

Trim by user/assistant **pairs**, never lone messages, so an exchange is never bisected. Count tokens via a resilient chain (tiktoken → transformers → word).

### 13.5 One message list, every backend

System prompt + memories + past exchanges collapse into a **single `system` message** + OpenAI-style turns. This keeps the `ModelClient` contract backend-agnostic.

### 13.6 Prompt-based tools now, native later

Tool calling is prompt-driven (`<tool_call>` tags + regex parser), fail-safe by design (bad calls return a `ToolResult`, never raise). `to_openai_schema()` exists for the v3.0 migration to native function calling.

### 13.7 Safer-by-default agent surface

Tools are allowlisted to exact paths, git is read-only, output is capped (`MAX_OUTPUT_CHARS = 4096`), and the single destructive tool (`write_file`) requires confirmation. No shell-exec surface.

### 13.8 Centralized, overridable, layered config

Python dataclass defaults are the fallback; an optional gitignored `config.yaml` overrides them; `.env` (`load_dotenv`) supplies secrets via `env:VAR`. The system runs with zero config (defaults) or full config (YAML).

### 13.9 Honest about gaps

Stubs (`app/api/`, `app/brain/`), dormant features (summarization, autocomplete under defaults), and dead code (Gemini block, `_memory_to_text`, the `router.default_model` fallback) are called out rather than hidden.

## 14. Important Invariants (deep dive)

Properties the system relies on and that any future change must preserve (or deliberately break *with* a doc update). File references are given so they can be re-checked.

### 14.1 Data-flow invariants

- **Memory-first ordering.** In `app/main.py`, `extract_facts() → memory.store()` runs *before* `memory.retrieve()`. A fact stated this turn is retrievable this turn (§5.5).
- **JSON is the source of truth for facts.** `memories.json` (`{"version":"2.0",...}`) is authoritative; `jarvis-memories` is rebuilt from it every startup. Never trust the vector store as the record.
- **Conversation vector store is seeded once.** `ConversationVectorStore` upserts from `conversation.get_all()` only when `count() == 0`; afterward it is append-only and can drift from the JSON conversation.
- **Hybrid dedup by `memory.id`.** `HybridRetriever` dedups candidates by `memory.id` because `Memory` dataclasses are mutable/unhashable (`set()` would raise). Changing the key risks duplicate injections.

### 14.2 Context & prompt invariants

- **Pair-trim only.** `ContextWindowManager.fit()` removes oldest *pairs*; callers must not trim individual messages.
- **Single system message.** `PromptBuilder.build()` emits exactly one `system` role containing base → past_exchanges → memory facts, then OpenAI-style turns. Backends assume one system message.
- **Episodic-before-semantic.** Within that system message, past exchanges precede memory facts (deliberate ordering from the 97%-context incident, §5.3).

### 14.3 Tool & agent invariants

- **Fail-safe execution.** `ToolExecutor` never raises on unknown/malformed `<tool_call>`; it returns a `ToolResult`. A bad model emission must not crash the agent loop.
- **Allowlist enforcement.** Every file read/write must resolve to an exact entry in `ALLOWED_READ`/`ALLOWED_WRITE`; git tools are read-only by construction. Any new tool must preserve this.
- **Prompt-only tool invocation.** The runtime does not pass OpenAI schemas to the model; `to_openai_schema()` is unused. Removing the `<tool_call>` parser without adding native calling breaks the agent.

### 14.4 Model & config invariants

- **`route()` never returns `None`.** `ModelRouter.route()` raises `ValueError` on an empty/undeterminable router rather than returning `None`; the `if selected_model is None` guard in `main.py` is therefore unreachable (and references the wrong variable — §6.4).
- **Defaults are runnable.** With no `config.yaml`, `settings.py` defaults must still boot: under them only `general` resolves; `cloud` and `autocomplete` are intentionally inert. A config change should not *break* the default boot.
- **Secrets via `env:VAR`.** API keys are referenced as `env:VAR` in config and resolved in `factory.create_client`; they are never hardcoded.
- **`config.yaml` is gitignored and optional.** The system must function on Python defaults alone; YAML is an override layer, not a requirement.

### 14.5 Persistence invariants

- **Dirty-tracking.** `MemoryStore`/`ConversationManager` persist via `save_if_dirty()`/`force_save()`; v1 formats auto-migrate on load. `force_save()` is also called after `touch()` so access stats survive.
- **`memories.json` version is the literal `"2.0"`** independent of the app `v.2.4.0` banner — do not couple them.

---

## 15. Coding Standards (deep dive)

Observed conventions in `app/` (de-facto; no linter/CI config in the tree enforces them).

### 15.1 Typing is pervasive
Every boundary is typed: `from typing import Protocol, Optional, Callable`; dataclasses carry type hints; module functions annotate return types (`-> ModelResponse`, `-> Settings`); `Optional[...]`/`Callable[[str], None]` are used. `Protocol` is preferred over `ABC` for interfaces (§13.1).

### 15.2 Data containers are `@dataclass`
All config blocks (`ModelConfig`, `MemoryConfig`, `ContextConfig`, …) and tool metadata (`ToolResult`, `ToolDefinition`) are `@dataclass`. Construction is declarative; behavior lives in methods.

### 15.3 Fail-safe by default
Tools never raise to their caller — `ToolDefinition.execute()` wraps any exception in a `ToolResult(success=False, …)`; `ToolExecutor` returns an "Unknown tool" result instead of raising, so the agent loop is exception-isolated. The factory is the exception: it raises `ImportError`/`ValueError` on a missing backend package or unset `env:VAR` (fail-loud at wiring time). `Settings.load()` is silent (returns defaults if the file is absent).

### 15.4 Singletons via double-checked locking
`get_settings()` uses a module-level `_settings` + `threading.Lock` with double-checked locking; `reset_settings()` exists for tests. (The `@lru_cache` alternative was not used — explicit locking was chosen for clarity.)

### 15.5 Graceful optional dependencies
Heavy/optional backends are imported under `try/except ImportError` with `AVAILABLE` flags (`OLLAMA_AVAILABLE`, `OPENROUTER_AVAILABLE` in `factory.py`); the system degrades to the `llamacpp` default. Lazy `import os`/`import sys` inside helper functions keeps startup light when the dep is unused.

### 15.6 Constants and imports
Module-level constants are `UPPER_SNAKE` (`MAX_OUTPUT_CHARS`, `DIFF_MAX_CHARS`, `DEFAULT_WEIGHTS`); regexes use a `_NAME_RE` convention. Import order is stdlib → third-party → local (`app.*`). Docstrings sit at module, class, and method level and explain *why* (e.g., the `ToolResult` docstring documents the fail-safe contract).

### 15.7 What is *not* standardized (verified gaps)
- No formatter/linter config (`pyproject.toml`/`ruff.toml`/`setup.cfg`) is present — these are conventions, not enforced rules.
- Interactive surfaces use `print()`/`input()` directly (agent prompts), not `logging`.
- No in-tree unit tests for `app/`; only `tests/stress_test.py` exercises the tool parser end-to-end.

---

## 16. Naming Conventions (deep dive)

### 16.1 Packages & modules
All `snake_case`: `memory/`, `models/`, `tools/`, `prompt/`, `context/`, `conversation/`, `config/`, `utils/`, `agents/`, `brain/`, `api/`. Files are `snake_case.py` (`fact_extractor.py`, `vector_retriever.py`, `hybrid_retriever.py`, `ranking.py`, `executor.py`, `base.py`, `git_tools.py`, `file_tools.py`, `doc_agent.py`, `switcher.py`, `factory.py`, `client.py`, `router.py`, `builder.py`, `tokenizer.py`). Tests are `test_*.py` (`stress_test.py`).

### 16.2 Classes, functions, constants
- **Classes / Protocols / Type aliases:** `PascalCase` (`MemoryManager`, `ModelRouter`, `ToolExecutor`, `PromptBuilder`, `ToolRegistry`, `ToolDefinition`, `ToolResult`, `ModelResponse`, `Settings`, `ModelClient`).
- **Functions / methods:** `snake_case` (`get_settings`, `reset_settings`, `create_client`, `to_openai_schema`, `format_for_prompt`, `has_calls`, `build_with_stats`).
- **Constants:** `UPPER_SNAKE` (`MAX_OUTPUT_CHARS`, `DIFF_MAX_CHARS`, `DEFAULT_WEIGHTS`, `MAX_ITERATIONS`, `KEYWORDS`).
- **Private / internal:** leading underscore (`_resolve_key`, `_settings`, `_lock`, `_tools`, `_TOOL_CALL_RE`, `_FUNC_CALL_RE`, `_HYBRID_CALL_RE`). Regexes use the `_NAME_RE` suffix.

### 16.3 Data & stores
JSON stores are `snake_case.json` (`memories.json`, `default.json`); ChromaDB collections are `kebab-case` (`jarvis-memories`, `jarvis-conversations`). `risk_level` is a lowercase string enum (`"none"`/`"low"`/`"medium"`/`"high"`). Task types are `UPPER_SNAKE` enum members (`CODE`, `STEM`, `REASONING`, …).

### 16.4 Inconsistencies to watch (verified)
- `version.py` is malformed (`"v.2.4.0"` with a stray dot) while docstrings elsewhere say `v2.0`/`v2.1`/`v2.1.0` — version strings are not centralized.
- Some names predate refactors (e.g., `MemoryManager`/`MemoryStore` in docs vs the actual `store.py`/`manager.py` split) — see §3.1/§4.

---

## 17. Architecture Patterns Known (deep dive)

Patterns observable in the working tree, grouped by intent. "Intended" marks cases where the code *states* the pattern but only partially implements it.

### 17.1 Protocol / structural typing (interface-first)
`ModelClient(Protocol)` defines the backend contract; third-party clients satisfy it structurally. §13.1 states the same `Protocol`-per-subsystem intent for `CandidateRetriever`/`MemoryStore`/`MemoryRanker`/`ContextWindowManager`/`PromptBuilder`, but in practice only `ModelClient` is a `Protocol` — the others are concrete classes. *Pattern: Intended → partially realized.*

### 17.2 Singleton (thread-safe)
`get_settings()` returns a process-wide `Settings` via double-checked `threading.Lock`. *Pattern: Singleton.*

### 17.3 Factory + Strategy (backend dispatch)
`create_client(config)` is an abstract-factory/strategy: it branches on `config.backend` (`"llamacpp"`/`"ollama"`/`"openrouter"`), resolves `env:VAR` keys, and returns the matching adapter. Optional backends are gated by `try/except ImportError` availability flags. *Pattern: Factory + Strategy + optional-dependency degradation.*

### 17.4 Registry
`ToolRegistry` holds `ToolDefinition`s keyed by name and exposes two views — `to_openai_schemas()` (native calling, v3.0) and `format_for_prompt()` (prompt-based, current). Module-level lists (`GIT_TOOLS`, `FILE_TOOLS`) are lightweight registries. *Pattern: Registry.*

### 17.5 Builder + Pipeline
`PromptBuilder.build()` assembles the single system message (builder); `main.py` chains extract → store → retrieve → build → fit → route → generate (pipeline / template-method orchestration). *Pattern: Builder + Pipeline.*

### 17.6 Adapter / Wrapper
`LlamaCppClient`/`OllamaClient`/`OpenRouterClient` adapt heterogeneous backends to the one `ModelClient` interface. `ToolDefinition.execute()` wraps handler exceptions into `ToolResult` (fail-safe adapter). *Pattern: Adapter + fail-safe wrapper.*

### 17.7 Composite / Hybrid + Fallback chain
`HybridRetriever` composes keyword + vector retrievers and dedups by `memory.id` (composite). The tokenizer selects `tiktoken → transformers → word` (chain-of-responsibility / fallback). *Pattern: Composite + Chain-of-responsibility.*

### 17.8 Dependency injection + dirty-tracking persistence
Clients/router/models are built from a single `Settings` object (config-driven DI). `MemoryStore`/`ConversationManager` persist via `save_if_dirty()`/`force_save()` (dirty-tracking). *Pattern: Dependency Injection + Unit-of-work/dirty-tracking.*

### 17.9 Not yet present (per roadmap)
Native function-calling dispatch, a centralized memory-lifecycle manager, and multi-agent orchestration are planned (§19) but not yet implemented as patterns in `app/`.

---

## 18. Technical Debt (deep dive)

A candid inventory of known issues, each tied to a file so it can be re-checked. Severity is the author's read, not a formal triage.

### 18.1 Dead / disabled code
- **`append_file` is unreachable.** In `app/tools/file_tools.py`, `append_file()` defines its `ToolDefinition` *after* a `return`, so the tool never registers; yet `doc_agent._SYSTEM` instructs the model to call `append_file` (§8/§9). Misleading contract.
- **Unregistered-but-referenced tools.** `git_diff`, `git_branch`, `git_status` appear in prompts/notes; `git_status`/`git_branch` are defined in `git_tools.py` but excluded from `GIT_TOOLS`. Only 7 tools actually register.
- **Gemini block requires manual unhashing.** `openrouter_client.py` (per `docs/ROADMAP.md`) contains a Google integration that must be manually uncommented; its production readiness is unverified.
- **Dead helpers & stubs.** `vector_retriever._memory_to_text` is unreachable; `app/api/` and `app/brain/` are empty `__init__.py` packages; `server_manager.ensure_server_running` is commented out in `main.py`.

### 18.2 Correctness bugs (verified)
- **Parser collapses repeated same-name calls.** `ToolExecutor.parse()` dedups by tool *name* (`seen` set), so 100 distinct `read_file` calls in one turn become 1 — `tests/stress_test.py::test_100_tool_calls_parsed` fails (expected 100, got 1).
- **Stale vector embeddings on replace/update.** `MemoryManager._handle_replace`/`update` mutate `Memory` fields in place without calling `retriever.on_memory_added`; ChromaDB vectors are stale until restart (§4.4).
- **Unreachable + wrong-variable fallback.** In `main.py`, `if selected_model is None: selected_model = switcher.router.default_model` is dead (`route()` raises `ValueError`, never returns `None`) and references `switcher.router` rather than a bare `router` (§6.4/§14.4).
- **Rule-based extractor.** Fact extraction is keyword/first-match-wins; `docs/ROADMAP.md` flags it as limited and needing LLM-based extraction.

### 18.3 Config drift
- **Unread config fields.** `MemoryConfig`/`RetrievalConfig`/`RankingConfig` declare fields (`max_memories`, `enable_ranking`, `min_confidence`, `candidate_overshoot_factor`, `RetrievalConfig.method`, ranking weights) that the memory subsystem ignores in favor of hardcoded `DEFAULT_WEIGHTS` and `limit × 3` overshoot.
- **Doc vs code numbers.** `CHANGELOG`/`NEW_DEVLOG`/`MEMORY`/`DATABASE` claim `safety_margin` 150→300 and `retrieval_limit` 20→8; `settings.py` ships `100`/`20`. The docs only match a (unreadable) `config.yaml`.
- **Tokenizer claim.** `tiktoken` is documented as the primary tokenizer but is absent from `requirements.txt`; live path is transformers→word (§10.4).

### 18.4 Documentation debt
- **Divergent duplicate.** `tmp/tail.md` is a ~36K-token copy of this history with its *own* §11–§14 wording — a single-source-of-truth risk; it should be deleted or reconciled.
- **Internal duplication & wrong claims.** `TOOLS.md` repeats its body and asserts `append_file` "does not exist" (the function exists, only its registration is dead).
- **Duplicate logs/roadmaps.** `CHANGELOG.md` vs `changelog.md`; multiple recovered logs. `STARTUP_FLOW.md` shows `v.2.2.0`; `main.py` docstring says `v2.1.0`; `settings.py`/`store.py` docstrings say `v2.1`/`v2.0`; `version.py` is malformed (`v.2.4.0`).
- **Undocumented root artifacts.** `knowledge/`, `scripts/`, `tmp/`, `hello.py` are not described anywhere.

### 18.5 Headless-safety gap
`ToolExecutor`'s confirmation gate calls blocking `input()`; `DocumentationAgent` depends on it, so the agent is CLI-bound and not headless-safe without an injectable gate (§9).

---

## 19. Future Direction (deep dive)

Drawn from `docs/ROADMAP.md` ("Planned Work"), the v3.0 hints baked into `app/tools/base.py`/`executor.py`, and `docs/NEW_DEVLOG.md`. Timelines are unverified (ROADMAP itself marks future goals "AI partially verified").

### 19.1 v3.0 — native function calling
`ToolDefinition.to_openai_schema()` and `ToolRegistry.to_openai_schemas()` already emit OpenAI-compatible schemas; the plan is to replace prompt-based `<tool_call>` parsing with `model.generate(tools=[...])`. `ToolExecutor`'s *interface* is deliberately designed to stay the same — only the `parse()` step changes. This also retires the three regex formats and the name-dedup bug (§18.2).

### 19.2 Memory lifecycle centralization
ROADMAP calls for a redesign that unifies Store/Update/Replace/Delete/Merge/Retrieve behind one manager — directly addressing the `_handle_replace` staleness debt (§18.2) — plus targeted `retrieve(prompt)` via ChromaDB and tuned hybrid thresholds.

### 19.3 Episodic & cognitive memory
Conversation summarization/compression (`ConversationConfig.enable_summarization=False` today) and LLM-based fact extraction with importance/confidence ranking (replacing the rule-based extractor). Would wire the currently-ignored `RankingConfig` weights and `min_confidence` (§18.3).

### 19.4 Agent runtime & multi-agent
Richer tool-calling loops and *specialized cooperative agents* beyond the lone `DocumentationAgent`. Requires a configurable permission system and an injectable (non-blocking) confirmation callback to become headless-safe (§18.5).

### 19.5 Model & profile expansion
Broaden profiles (`openrouter`, `grok`, `google`) via `config.yaml`; the Google path currently needs manual code uncommenting. `ModelSwitcher` already supports per-profile routers (§6.4).

### 19.6 Planning & long-term vision
Goal decomposition / task scheduling; long-term a "unified personal knowledge & automation platform (AI OS)" with adaptive (reflective) memory and eventual robotics/hardware integration (per `docs/ROADMAP.md` Future Vision).

### 19.7 What would close the loop
- Delete/reconcile `tmp/tail.md`; de-duplicate `TOOLS.md` and the changelog/roadmap files.
- Centralize the version string; fix the stale docstrings/banner.
- Wire the unread config fields or remove them.
- Either implement `append_file`/`git_status`/`git_branch` or stop advertising them.
- Land native function calling and the centralized memory manager to retire the largest correctness debts.

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

- **Prompt system (§7):** `PromptBuilder.build()` emits a single system message ordered **base prompt → past exchanges → memory facts** (episodic-before-semantic), confirmed in `app/prompt/builder.py`. `build_with_stats()` exists but the main loop calls `build()` directly, so its stats hook is diagnostic-only. No prompt templating/caching layer exists beyond `PromptBuilder` (system text assembled per turn). The doc agent uses a separate `doc_agent._SYSTEM` prompt that drives `<tool_call>` repo work and points the model at `append_file`/`git_diff` (unregistered — see §8/§9).
- **Tool safety (§8):** file access is constrained to exact-match `ALLOWED_READ`/`ALLOWED_WRITE` path sets; git tools are read-only by construction; tool output is capped at `MAX_OUTPUT_CHARS = 4096`; only `write_file` triggers the interactive confirmation gate. `ToolDefinition.to_openai_schema()` exists for the planned v3.0 native-function-calling migration but is **not** wired into the runtime (the system remains prompt-based).
- **Agent system (§9):** `DocumentationAgent` is the sole agent; its tool loop is capped at `MAX_ITERATIONS = 12`. It is re-created on model/profile switches and fed a docs client via `ModelSwitcher.get_client()`. The loop is interactive/CLI-bound and depends on the `ToolExecutor` confirmation gate's blocking `input()`, so it is **not headless-safe** without an injectable gate.
- **Configuration (§10):** `Settings.load()` reads the optional `config.yaml`; `dotenv.load_dotenv()` runs at `main.py` startup and `factory.create_client` resolves `env:VAR` API-key references. Many `MemoryConfig`/`RetrievalConfig`/`RankingConfig` fields (`max_memories`, `enable_ranking`, `min_confidence`, `candidate_overshoot_factor`, `RetrievalConfig.method`, the `RankingConfig` weights) are **defined but not read** by the memory subsystem, which uses its own hardcoded constants instead (e.g. `MemoryRanker.DEFAULT_WEIGHTS`, overshoot `limit × 3`). `reset_settings()` exists for tests.

- **Directory layout (§11):** current `app/` tree confirmed by listing — `main.py` + packages `config/`, `memory/`, `conversation/`, `context/`, `prompt/`, `models/`, `agents/`, `tools/`, `utils/`, plus empty stubs `api/` and `brain/`. `models/` contains `switcher.py`, `openrouter_client.py`, `factory.py`; `agents/` contains only `__init__.py` + `doc_agent.py`; `tools/` contains `base.py`, `executor.py`, `git_tools.py`, `file_tools.py`; `memory/` contains `conversation_store.py` (the `ConversationVectorStore`). Root also has `config.yaml` (gitignored), `data/` (runtime, gitignored), `docs/`, `tests/`, `.continue/`, and undocumented `knowledge/`, `scripts/`, `tmp/`, `hello.py`.
- **Major refactors (§12):** the v2.0 split (Protocol modules + retrieve-only-relevant + state out of client), v1.0 behavior engine, v2.2 dual-store, v2.2.1 prompt-based agent/tool layer, and v2.4 per-profile `ModelSwitcher` are the structural pivots; the v2.0 `ModelRouter` was built-but-never-called until v2.0.1; the tokenizer chain and the `stream`/`on_token` named-param signature are the key cross-cutting refactors.
- **Design philosophy (§13):** the eight §1.3 principles hold, extended by a safer-by-default agent surface (allowlists / read-only git / `MAX_OUTPUT_CHARS` cap / `write_file` confirmation) and layered overridable config (Python defaults → `config.yaml` → `env:VAR`); gaps (stubs, dormant features, dead code) are documented rather than hidden.
- **Important invariants (§14):** confirmed — memory-first ordering in `main.py`; JSON authoritative for facts with `jarvis-memories` rebuilt each startup; `jarvis-conversations` seeded once; hybrid dedup by `memory.id`; pair-trim only; single system message (base → past_exchanges → memory facts); fail-safe `ToolExecutor`; `route()` raises instead of returning `None`; defaults boot with only `general` resolving; `env:VAR` secrets; gitignored optional `config.yaml`; dirty-tracking persistence; and `memories.json` version pinned to the literal `"2.0"`.

- **Coding standards (§15):** confirmed — pervasive `typing` (`Protocol`, `Optional`, `Callable`) and `@dataclass` containers; fail-safe tool contract (`ToolDefinition.execute()` wraps exceptions in `ToolResult`); thread-safe singleton `get_settings()` via `threading.Lock` double-checked locking; optional backends imported under `try/except ImportError` with `AVAILABLE` flags (`factory.py`); `UPPER_SNAKE` constants and `_NAME_RE` regex convention; no in-tree linter/CI config and no `app/` unit tests (only `tests/stress_test.py`).
- **Naming conventions (§16):** confirmed — `snake_case` modules/packages (`memory/`, `tools/`, `prompt/`, …) and `test_*.py`; `PascalCase` classes/Protocols (`MemoryManager`, `ModelClient`, `ToolResult`); `snake_case` functions; `UPPER_SNAKE` constants (`MAX_OUTPUT_CHARS`, `DEFAULT_WEIGHTS`, `MAX_ITERATIONS`); leading-underscore privates (`_resolve_key`, `_settings`, `_TOOL_CALL_RE`); `snake_case.json` data files and `kebab-case` ChromaDB collections (`jarvis-memories`/`jarvis-conversations`); lowercase `risk_level` strings.
- **Architecture patterns (§17):** confirmed — `Protocol` interface (`ModelClient`) + structural typing; thread-safe singleton (`get_settings`); factory/strategy (`create_client` by `backend`, `env:VAR` resolution, optional-dep degradation); registry (`ToolRegistry` with `to_openai_schemas()`/`format_for_prompt()`); builder (`PromptBuilder.build()`) + pipeline (`main.py` extract→store→retrieve→build→fit→route→generate); adapter clients; composite `HybridRetriever`; tokenizer fallback chain (tiktoken→transformers→word); config-driven DI + dirty-tracking persistence. Note: only `ModelClient` is a true `Protocol`; the other "Protocol-per-subsystem" intent (§13.1) is not yet realized in code.
- **Technical debt (§18):** confirmed — `append_file` is dead (defined after `return`) yet advertised by `doc_agent._SYSTEM`; `git_status`/`git_branch` defined but unregistered; parser collapses repeated same-name calls (`stress_test` fails 100→1); `_handle_replace`/`update` skip `retriever.on_memory_added` (stale vectors); unreachable + wrong-variable `selected_model is None` guard in `main.py`; many `MemoryConfig`/`RankingConfig`/`RetrievalConfig` fields unread; `tiktoken` not in `requirements.txt`; divergent `tmp/tail.md`; duplicated `TOOLS.md`/changelog/roadmap; stale version strings (`version.py` `v.2.4.0`, `main.py` `v2.1.0`, `STARTUP_FLOW.md` `v.2.2.0`); undocumented `knowledge/`/`scripts/`/`tmp/`/`hello.py`; blocking `input()` confirmation gate (not headless-safe).
- **Future direction (§19):** confirmed against `docs/ROADMAP.md` + `app/tools/base.py`/`executor.py` v3.0 hints — native function calling via existing `to_openai_schema()`/`to_openai_schemas()`; centralized memory-lifecycle manager; episodic/cognitive memory (summarization + LLM extraction) wiring the currently-ignored `RankingConfig`; multi-agent orchestration; expanded profiles (`openrouter`/`grok`/`google`, Google needs manual uncomment); planning + long-term "AI OS" vision. ROADMAP marks future timelines as AI-partially-verified.

**Could not verify:**
- `config.yaml` contents (security block). Runtime model/backend wiring is inferred from `settings.py` defaults + `NEW_DEVLOG.md`.
- Actual ChromaDB/embeddings at runtime (no `data/` present; Ollama server not reachable here).
- Real LLM conformance to the `<tool_call>` format under load.

**Authoritative version map (committed):**
v0.0.0 (`1999e53`,`163f8a1`,`8b1d0cb`) · v0.1.0 (`e13ee67`) · v0.2.0 (`ded44b9`) · v0.3.0 (`39b3d5b`,`7491e9a`,`e5c6fd6`) · v0.4.0 (`94e1956`,`3cc9e4b`) · v0.5.0 (`4034bf7`) · v0.6.0 (`7a840ee`,`b145614`,`9aa2fb2`) · v0.7.0 (`7803a93`) · v0.8.0 (`d43f6e9`) · v0.9.0 (`2922129`) · v1.0.0 (`4f71baf`) · v1.1.0 (`6316917`,`db51ccc`,`63addf6`) · v2.0.0 (`8519f65`) · v2.0.1 (`5fccb37`) · v2.1.0 (`df45be2`) · v2.2.0 (`b2c2211`) · v2.2.1 (`891fe4b`). Working tree adds v2.3.0 (uncommitted) and v2.4.0 (uncommitted, `version.py`).



