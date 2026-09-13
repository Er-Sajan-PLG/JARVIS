# JARVIS Database

**Status**: ACTIVE
**Type**: reference
**Source**: `app/memory/` at HEAD
**Last Updated**: 2026-09-13

This document describes how JARVIS persists data. Every statement below was
checked against the source code at the time of writing. Files inspected:

- `app/config/settings.py` (paths + config defaults)
- `app/config/version.py` (derives `VERSION` from git tags at import; `_FALLBACK_VERSION = "v3.0.1"`)
- `app/memory/schema.py` (`Memory`, `MemoryResult`, constants)
- `app/memory/store.py` (`MemoryStore` — JSON CRUD + persistence)
- `app/memory/manager.py` (`MemoryManager` — orchestration)
- `app/memory/retrieval.py` (`CandidateRetriever`, `KeywordRetriever`)
- `app/memory/ranking.py` (`MemoryRanker`, `RankingWeights`)
- `app/memory/rules.py` (`RULES` triggers)
- `app/memory/fact_extractor.py` (`extract_facts`)
- `app/memory/vector_retriever.py` (`VectorRetriever` — ChromaDB)
- `app/memory/hybrid_retriever.py` (`HybridRetriever`)
- `app/memory/conversation_store.py` (`ConversationVectorStore` — ChromaDB)
- `app/conversation/manager.py` (`ConversationManager`, `Message`)
- `app/main.py` (wiring / startup)
- `requirements.txt` (chroma dependency)
- `.continue/agents/*.yaml` (inspected; see note in AI Unverified)

> Version note: `app/config/version.py` **derives** the version from git tags at
> import time (`git describe --tags --long`), so it reports the current tag (e.g.
> the current tag, e.g. `v3.3.1`), not a hardcoded string. `_FALLBACK_VERSION = "v3.0.1"` is used only
> when git is unavailable. Some module docstrings still carry older hand-written
> version strings ("v2.0", "v2.1") — those are cosmetic and are not the version.
> See `docs/VERSIONING.md`.

---

## Database Architecture

JARVIS uses a **dual-store, layered architecture**. There is no single
relational/NoSQL database; persistence is split across two engines:

1. **JSON file store** — the authoritative, human-readable record of facts
   (`memories.json`) and chat history (`conversations/default.json`).
   Handled by `MemoryStore` (`app/memory/store.py`) and
   `ConversationManager` (`app/conversation/manager.py`).
2. **ChromaDB vector store** — a semantic/embedding index for similarity
   search, persisted on disk under `data/chroma`. Handled by
   `VectorRetriever` (collection `jarvis-memories`) and
   `ConversationVectorStore` (collection `jarvis-conversations`).

The layering (verified in `manager.py`, `store.py`, `retrieval.py`,
`ranking.py`) is:

```
External callers
      │
      ▼
MemoryManager            (orchestration + behavior rules + lifecycle callbacks)
      ├── MemoryStore     (JSON CRUD + dirty-tracking persistence)
      ├── CandidateRetriever  (Protocol)
      │     ├── KeywordRetriever   (in-memory, derived from store)
      │     └── VectorRetriever    (ChromaDB collection "jarvis-memories")
      │        (wrapped by HybridRetriever at runtime)
      └── MemoryRanker    (scoring; no persistence)
```

Key architectural facts:

- **The JSON file is the source of truth for facts.** On every startup,
  `MemoryManager.__init__` calls `self._retriever.on_index_rebuilt(
  self._store.get_all())` (`manager.py`). For `VectorRetriever`,
  `on_index_rebuilt` **deletes every entry in the `jarvis-memories`
  collection and re-inserts all memories from the JSON store**
  (`vector_retriever.py`). So the vector collection is a *derived* index,
  not an independent source of truth.
- **The ChromaDB conversation collection is NOT rebuilt from the JSON
  conversation file on startup.** `main.py` only seeds it when
  `conv_store.count() == 0` via `index_history(conversation.get_all())`.
  Once populated it persists independently in `data/chroma`.
- **The keyword index is fully in-memory.** `KeywordRetriever` keeps a
  plain `list[Memory]` and rebuilds it from the JSON store on startup via
  `on_index_rebuilt`. It is never written to disk on its own.
- `MemoryManager` is the only class external code is expected to use
  (`manager.py` docstring + `main.py` wiring).

---

## Storage Engines

### 1. JSON file storage (filesystem)
- Engine: Python `json` module writing to plain text files (`store.py`,
  `conversation/manager.py`).
- Used for: the canonical fact list and the canonical conversation list.
- Default paths (from `settings.py` `PathsConfig`):
  - `data/memories.json` (`PathsConfig.memories`)
  - `data/conversations/default.json` (`PathsConfig.default_conversation`)
  - base dir `data/` (`PathsConfig.data_dir`)
- The `data/` directory is created lazily on save via
  `self.path.parent.mkdir(parents=True, exist_ok=True)`.

### 2. ChromaDB (embedded vector store)
- Engine: `chromadb.PersistentClient(path=...)` — an on-disk, embedded
  (DuckDB + SQLite + HNSW) vector database. Pinned dependency
  `chromadb==1.5.9` (`requirements.txt`).
- Persist directory: `data/chroma`. This is **hardcoded** in `main.py`
  (`MemoryManager`/`VectorRetriever` and `ConversationVectorStore`) and is
  also the default argument in `vector_retriever.py` /
  `conversation_store.py`. The two stores deliberately share one directory
  but use distinct collections.
- Embeddings are produced locally by Ollama via `OllamaEmbeddingFunction`
  (`chromadb.utils.embedding_functions`), pointed at
  `http://localhost:11434` with model `nomic-embed-text` (defaults in
  `vector_retriever.py` and `conversation_store.py`; `main.py` passes the
  URL but lets `embed_model` default).
- Similarity space: `"hnsw:space": "cosine"` set on collection creation.

### Engines NOT used
- No SQLite/shelve/Redis/etc. is used for app data. (ChromaDB internally
  uses SQLite/DuckDB for its own bookkeeping, but that is opaque to the
  application.)
- The `.continue/agents/*.yaml` files are Continue.dev extension config
  (model/prompt definitions), not JARVIS persistence. See AI Unverified.

---

## Data Models

### `Memory` (`app/memory/schema.py`)
A `@dataclass` representing one stored fact. Fields (verified from the
dataclass + `to_dict`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | Default `str(uuid.uuid4())[:8]` (8-char prefix). |
| `category` | `str` | e.g. `"identity"`, `"preference"`, `"skills"`, `"goals"`, `"plans"`, `"tasks"`, `"location"`, `"profession"`. |
| `memory_type` | `str` | e.g. `"name"`, `"like"`, `"ability"`. Set from rule `"type"`. |
| `value` | `str` | The actual content. |
| `behavior` | `str` | `"append"` (default), `"replace"`, `"ignore"`, `"delete"`. |
| `created_at` | `float` | Immutable (`time.time()` at creation). |
| `updated_at` | `float` | Mutable; set by `mark_updated()`. |
| `last_used` | `float` | Mutable; set by `touch()` on retrieval. |
| `source` | `str` | `"user"` (default), `"system"`, `"inferred"`. |
| `confidence` | `float` | 0.0–1.0 (default 1.0). |
| `importance` | `float` | 0.0–1.0 (default 0.5). |
| `access_count` | `int` | Incremented by `touch()`. |
| `metadata` | `dict` | Free-form. **Note:** included in `to_dict()` but **omitted** from ChromaDB metadata (see Vector database). |

Serialization: `to_dict()` keys use `"type"` for `memory_type`;
`from_dict()` reads `"type"` and falls back to v1 `"timestamp"` if
`created_at`/`updated_at` are absent. Constants
`BEHAVIOR_*` / `SOURCE_*` / `IMPORTANCE_*` are defined in `schema.py`.

### `Message` (`app/conversation/manager.py`)
A `@dataclass` for one chat turn: `role` (`"user"`/`"assistant"`/`"system"`),
`content`, `timestamp` (default `time.time()`), `metadata` (dict).
Serialized via `to_dict()`/`from_dict()`; `to_openai_format()` returns
`{"role", "content"}`.

### `MemoryResult` (`app/memory/schema.py`)
`{"memory": Memory, "score": float}` — output of ranking.

### `RankingWeights` (`app/memory/ranking.py`)
`@dataclass` with `relevance=0.35`, `importance=0.25`, `frequency=0.15`,
`recency=0.15`, `confidence=0.10`. **Note:** `MemoryRanker` uses its own
hardcoded `DEFAULT_WEIGHTS`; config `RankingConfig` is not passed in
(`manager.py` instantiates `MemoryRanker(weights=ranking_weights)` where
`ranking_weights` defaults to `None` → `DEFAULT_WEIGHTS`). See AI Partially
Verified.

### Extracted fact `dict`
Produced by `extract_facts` (`fact_extractor.py`): keys `category`,
`type`, `value`, `behavior`, `source` (default `"user"`), `confidence`
(`1.0`). These are the input to `MemoryManager.store()`.

---

## Persistence Lifecycle

All persistence is **explicit and dirty-flag gated**. Both `MemoryStore`
and `ConversationManager` track `_dirty` and skip writing when not dirty.

### Facts (Memories)

**Create / Store** — `MemoryManager.store(fact)` (`manager.py`):
1. Reads `fact["behavior"]`.
2. `ignore` → returns `None` (nothing stored).
3. `delete` → `delete_by_type(category, type)`.
4. `replace` → `_handle_replace()`.
5. `append` (default) → `_handle_append()`:
   - Builds a `Memory` with new `id`, timestamps, `source`, `confidence`,
     `importance`.
   - `MemoryStore.add()` appends to the in-memory list, sets `_dirty`.
   - `retriever.on_memory_added(memory)` updates keyword + vector indexes.
   - `MemoryStore.save()` writes JSON **only if dirty** (it is).

**Replace** — `_handle_replace()` (`manager.py`): finds memories matching
`category`+`type`. If found, mutates the first match's `value`/`source` in
place and calls `force_save()`. If none found, falls back to append.
> Caveat verified in code: `_handle_replace` does **not** call
> `on_memory_added`, so the ChromaDB embedding for that memory is **not**
> updated in-session. It is corrected only on the next startup rebuild.
> (Same caveat applies to `MemoryManager.update()`.)

**Retrieve** — `MemoryManager.retrieve(prompt, limit)` (`manager.py`):
1. `candidate_limit = min(limit * 3, store.count() or 50)` (overshoot;
   hardcoded ×3, not from `candidate_overshoot_factor`).
2. `retriever.find_candidates()` → hybrid keyword + vector.
3. `MemoryRanker.rank(...)` filtered by `config.min_relevance_score`.
4. For each returned `Memory`, `touch()` updates `last_used` + increments
   `access_count`, then `MemoryStore.force_save()` persists access stats.

**Update** — `MemoryManager.update(memory_id, updates)` (`manager.py`):
`MemoryStore.update_fields()` uses `setattr` for each key, calls
`mark_updated()`, then `save_if_dirty()`. An optional `_on_update` callback
fires. **Does not** notify the retriever → vector index stale until
rebuild. `merge()` extends `update()` by prepending existing value with
`"; "`.

**Delete** — `MemoryManager.delete(id)` / `delete_by_type(cat, type)`
(`manager.py`): removes from store, calls `retriever.on_memory_removed(id)`
(so the keyword list and ChromaDB entry are both removed), fires optional
`_on_delete` callback, then `save()`.

**Clear** — `MemoryManager.clear()` (`manager.py`): `MemoryStore.clear()`
(empties list + `save()`) and `retriever.clear()` (keyword list +
ChromaDB `delete` of all ids).

**Startup load** — `MemoryStore._load()` reads the JSON file. It handles:
- v2 dict with `"version"` → `memories` list.
- v1 dict with `"facts"` → treated as memories.
- v1 bare list → ignored (no facts).
Malformed JSON / IO errors are swallowed and treated as empty.

### Conversation

**Append** — `ConversationManager.add_message()` (`conversation/manager.py`):
appends a `Message`, sets `_dirty`, and saves immediately iff
`config.save_on_every_message` (default `True`).

**Load** — `ConversationManager._load()` handles v2 dict (`"version"` with
`summary` + `messages`), v1 bare list, and v1 dict with `"conversation"`
key. Malformed data is swallowed.

**Other** — `clear()`, `pop_last_message()` (error recovery),
`set_summary()`/`get_summary()`, all dirty-gated and saved.

**Shutdown** — `main.py` `_cleanup()` calls `memory.save_if_dirty()` and
`conversation.save_if_dirty()`.

---

## Indexing

There are two parallel candidate indexes, both fed by
`CandidateRetriever.on_memory_added/removed/index_rebuilt` (Protocol in
`retrieval.py`):

### Keyword index (`KeywordRetriever`, `retrieval.py`)
- **In-memory only** (`self._memories: list[Memory]`). No disk file.
- Keywords extracted by lowercasing, stripping punctuation, splitting, and
  removing a ~130-word English stop-word set. Memory keywords are built from
  `f"{value} {category} {memory_type}"`.
- `find_candidates()` returns memories with `>= min_keyword_overlap`
  (default 1) keyword intersection with the query.
- `on_index_rebuilt()` simply replaces the in-memory list with the loaded
  memories (so it is re-derived from JSON every startup).

### Vector index (`VectorRetriever`, `vector_retriever.py`)
- ChromaDB collection `jarvis-memories`; see Vector database below.
- `on_index_rebuilt()` deletes all existing ids then re-upserts every
  memory (one embedding call per memory).

### Hybrid (`HybridRetriever`, `hybrid_retriever.py`)
- Runs keyword + vector `find_candidates` and concatenates, **deduplicating
  by `memory.id`** (Memory is unhashable, so a `set` cannot be used — code
  comment confirms this). Returns `combined[:limit]`.
- This is the retriever actually wired in `main.py`.

### Ranking (`MemoryRanker`, `ranking.py`)
Not an index but the next stage. Combines five weighted scores:
relevance (Jaccard keyword overlap + category/type boosts),
importance, frequency (log scale, `frequency_scale=10` → 1.0),
recency (exponential decay, half-life `7.0` days), confidence. Scores
below `min_relevance_score` are dropped; results sorted descending and
trimmed to `limit`.

---

## Vector Database

### Collections
Both use `chromadb.PersistentClient(path="data/chroma")` and HNSW cosine
space, sharing one directory:

| Store | Collection | `ids` | `documents` (embedded text) | `metadatas` |
|-------|-----------|-------|------------------------------|-------------|
| `VectorRetriever` (`vector_retriever.py`) | `jarvis-memories` | `memory.id` | `f"{category} {memory_type}: {value}"` | flat Memory dict **without** nested `metadata` (keys: id, category, type, value, behavior, created_at, updated_at, last_used, source, confidence, importance, access_count) |
| `ConversationVectorStore` (`conversation_store.py`) | `jarvis-conversations` | md5 of `f"{ts}{user_msg[:20]}"`[:8] | `f"User: {user_msg}\nAssistant: {assistant_msg}"` | `user` (≤1000 chars), `assistant` (≤1000 chars), `timestamp` |

### Why `metadata` is dropped for memories
`Memory.to_dict()` includes `metadata: {}` (a nested dict), which ChromaDB
rejects (it requires flat `str|int|float|bool` values). `_to_chroma_meta()`
therefore omits it; `Memory.from_dict()` defaults `metadata` to `{}` on
reconstruction. This matches the change noted in `docs/changelog.md`.

### Embeddings
- Provider: `OllamaEmbeddingFunction` from `chromadb.utils.embedding_functions`.
- Endpoint: `http://localhost:11434` (Ollama). Model: `nomic-embed-text`.
- Embeddings are generated locally; the same Ollama server is used for
  chat generation but via a different client.

### Query path
- `VectorRetriever.find_candidates(query, limit)`: if collection `count()==0`
  returns `[]`; else `collection.query(query_texts=[query],
  n_results=min(limit, count))` and rebuilds `Memory` objects from metadata
  (wrapped in try/except, dropping any that fail).
- `ConversationVectorStore.search(query, limit=2)`: same shape; returns
  `[{"user", "assistant"}]` built from metadata.

### Lifecycle notes (verified)
- Memory collection is **fully rebuilt from JSON on every startup**
  (`on_index_rebuilt`). It is a derived index.
- Conversation collection is seeded **only if empty** on startup
  (`main.py`); afterward it is append-only via `add_exchange()` and
  persists independently.
- `add_exchange()` computes its `pair_id` from the same md5 formula as
  `_extract_pairs()`, so a historical pair and a live pair can collide on
  id if they share timestamp + first 20 chars (upsert would overwrite).
- Dead code: in `vector_retriever.py`, `_memory_to_text()` is defined
  **nested inside** `on_index_rebuilt` (indentation bug) and is never
  called; the embedded document is built inline instead.

---

## JSON Storage

### `data/memories.json`
Top-level object:
```json
{
  "version": "2.0",
  "memories": [ { ...Memory.to_dict()... } ]
}
```
Written by `MemoryStore.save()` as `json.dump(data, f, indent=2)` when
dirty. `version` string is `"2.0"` (hardcoded in `store.py`, independent of
the git-derived app version). Loader accepts v1 shapes for backward
compatibility.

### `data/conversations/default.json`
```json
{
  "version": "2.0",
  "summary": "",
  "messages": [ { "role", "content", "timestamp", "metadata" } ]
}
```
Written by `ConversationManager.save()` (`json.dump`, indent=2) when dirty.
`summary` is reserved for a future summarization feature
(`enable_summarization` defaults to `False` in `settings.py`; not enacted
in the conversation code inspected).

### Dirty-tracking contract (verified)
- `MemoryStore.save()` and `ConversationManager.save()` early-return when
  not dirty.
- Public `save_if_dirty()` is the normal hook; `force_save()` flips dirty
  true then saves (used after `retrieve()` touches memories).
- `clear()` on both calls `save()` directly.

---

## Future Improvements

Items below are grounded in code comments, structural observations, or
missing wiring found during inspection — not speculation about features:

1. **Re-embed on `replace`/`update`.** `_handle_replace()` and
   `update()` mutate `value`/`category`/`type` but never call
   `on_memory_added`, so the ChromaDB embedding goes stale until the next
   startup rebuild. A targeted re-upsert (or `on_index_rebuilt`) would fix
   in-session staleness.
2. **Wire up unused config.** `MemoryConfig.max_memories`, `enable_ranking`,
   `min_confidence`, `candidate_overshoot_factor`, `RetrievalConfig.method`,
   and `RankingConfig` weights are defined in `settings.py` but not
   referenced by the memory subsystem code inspected. Either enforce them
   or remove them to avoid confusion (see AI Partially Verified).
3. **Make `candidate_overshoot_factor` effective.** `retrieve()` hardcodes
   `limit * 3`; the config field is ignored.
4. **LLM-based fact extraction.** `fact_extractor.py` comment: "Interface
   is stable - can swap to LLM extraction later." Currently rule-based via
   `RULES`.
5. **Smarter merges.** `MemoryManager.merge()` concatenates with `"; "`.
6. **Adaptive ranking / forgetting.** `RankingWeights` and half-life are
   static; no explicit forgetting/consolidation exists.
7. **Conversation vector/JSON drift.** Conversation vector store is seeded
   only when empty and never re-synced from `default.json`; a re-index
   path or startup reconciliation would prevent divergence.
8. **Remove dead code.** `_memory_to_text()` nested in
   `VectorRetriever.on_index_rebuilt`.
9. **Robust load error reporting.** Both loaders swallow
   `json.JSONDecodeError`/`IOError` silently; a corrupt file yields an empty
   store with no warning.
10. **Single source for storage paths.** `memories.json` and
    `conversations/default.json` come from `settings.paths`, but the
    ChromaDB `data/chroma` path is hardcoded in three places; centralizing
    it would honor `PathsConfig` consistently.

---

## AI Verification Status

### AI Verified
The following statements were directly confirmed by reading the cited
source during this task:

- JARVIS persists data to JSON files (`memories.json`,
  `conversations/default.json`) and a ChromaDB directory (`data/chroma`).
  (`store.py`, `conversation/manager.py`, `main.py`, `vector_retriever.py`,
  `conversation_store.py`)
- Default paths: `data/memories.json`, `data/conversations/default.json`,
  base `data/`; `PathsConfig` in `settings.py`.
- ChromaDB persist dir `data/chroma` is hardcoded in `main.py` and is the
  default in `vector_retriever.py`/`conversation_store.py`.
- Two ChromaDB collections exist: `jarvis-memories`
  (`VectorRetriever`) and `jarvis-conversations` (`ConversationVectorStore`).
- Embeddings use `OllamaEmbeddingFunction` at `http://localhost:11434`,
  model `nomic-embed-text`, cosine HNSW space. (`vector_retriever.py`,
  `conversation_store.py`)
- `MemoryStore.save()` and `ConversationManager.save()` are dirty-gated and
  write `json.dump(..., indent=2)`; memory JSON has `version: "2.0"` and a
  `memories` list. (`store.py`, `conversation/manager.py`)
- `Memory` dataclass fields and `to_dict`/`from_dict` (including `"type"`
  mapping and v1 `timestamp` fallback) match the table above. (`schema.py`)
- `MemoryManager.store()` implements append/replace/ignore/delete via
  `_handle_append`/`_handle_replace`/`delete_by_type`. (`manager.py`)
- On startup, `MemoryManager.__init__` calls
  `retriever.on_index_rebuilt(store.get_all())`;
  `VectorRetriever.on_index_rebuilt` deletes all ids then re-upserts from
  the JSON store. (`manager.py`, `vector_retriever.py`) → JSON is
  authoritative for memories; vector store is derived.
- `ConversationVectorStore` is seeded from `conversation.get_all()` only
  when `conv_store.count() == 0` (`main.py`); otherwise persists
  independently.
- `KeywordRetriever` is in-memory only and is rebuilt from the store via
  `on_index_rebuilt`. (`retrieval.py`)
- `HybridRetriever` dedupes candidates by `memory.id`. (`hybrid_retriever.py`)
- `retrieve()` touches returned memories and calls `force_save()`; candidate
  overshoot is hardcoded `limit * 3`. (`manager.py`)
- `_handle_replace()` and `update()` do **not** call `on_memory_added`, so
  the vector embedding is not refreshed in-session. (`manager.py`)
- `MemoryRanker` default weights are `DEFAULT_WEIGHTS` in `ranking.py`
  (relevance 0.35, importance 0.25, frequency 0.15, recency 0.15,
  confidence 0.10); `min_relevance_score` from `MemoryConfig` is applied in
  `retrieve()`. (`ranking.py`, `manager.py`, `settings.py`)
- `_to_chroma_meta()` omits the nested `metadata` field; `from_dict`
  defaults it to `{}`. (`vector_retriever.py`, `schema.py`)
- `ConversationVectorStore` caps `user`/`assistant` metadata at 1000 chars
  and derives `pair_id` via md5 of timestamp + first 20 chars.
  (`conversation_store.py`)
- `chromadb==1.5.9` is a pinned dependency. (`requirements.txt`)
- Runtime `VERSION` is derived from git tags at import (`config/version.py`);
  see `docs/VERSIONING.md`.
- `_memory_to_text()` is defined nested inside
  `VectorRetriever.on_index_rebuilt` and is never called. (`vector_retriever.py`)

### AI Partially Verified
Statements supported by evidence but not fully confirmed:

- **Several `MemoryConfig`/`RetrievalConfig`/`RankingConfig` fields appear
  unused.** `max_memories`, `enable_ranking`, `min_confidence`,
  `candidate_overshoot_factor`, `RetrievalConfig.method`, and
  `RankingConfig` weights are defined in `settings.py` and documented in
  `docs/CONFIG.md`, but a search of `app/memory/` found no code that reads
  them. I verified the memory subsystem files I was directed to; I did not
  exhaustively read every module in the repo (e.g., `app/brain/`,
  `app/agents/`, `app/models/`, `app/context/`, `app/prompt/`), so a usage
  could exist elsewhere that I did not inspect.
- **`conversation.enable_summarization` / `set_summary()` is a future
  feature.** The field defaults to `False` and `ConversationManager` has
  `set_summary`/`get_summary`, but no caller performs summarization in the
  files inspected. I could not confirm whether `main.py` or another module
  invokes summarization.
- **Conversation vector store vs JSON drift risk.** I verified the
  "seed only if empty" behavior in `main.py`; I could not fully trace every
  code path that might call `index_history` again, so I cannot guarantee
  there is no other re-sync.
- **`OllamaEmbeddingFunction` availability at runtime.** The import is
  present in source, but I could not execute the code or confirm the Ollama
  server / `nomic-embed-text` model is actually installed/running, so I
  cannot verify embeddings are produced successfully at runtime.

### AI Unverified
Items the AI could not verify — files, runtime, permissions, or external
systems were unavailable. No guesses were made:

- **`config.yaml` contents.** Reading `config.yaml` is blocked by a
  security restriction in this environment, so I could not confirm whether
  deployed paths, `retrieval_limit`, or other settings override the
  `settings.py` defaults. All path/config statements above describe the
  code defaults, not necessarily the deployed configuration.
- **Runtime behavior / actual disk state.** No ChromaDB directory,
  `memories.json`, or `conversations/default.json` exists in the workspace
  (no `data/` directory present), so I could not inspect real persisted
  data, collection counts, or embedding dimensions.
- **Ollama server availability.** `http://localhost:11434` and the
  `nomic-embed-text` model were not reachable/verifiable here.
- **`.continue/agents/*.yaml` (new-config*.yaml).** These are Continue.dev
  extension config files (model/prompt definitions). I opened
  `new-config.yaml` and it is an example Continue configuration, unrelated
  to JARVIS app persistence. I did not read the other three
  (`new-config-1..4.yaml`) in detail; they are not part of the app's
  persistence layer as far as the code shows, but I cannot fully rule out a
  connection without reading each.
- **Behavior of uninpspected modules.** Anything persistence-related that
  might live outside `app/memory/` and `app/conversation/` (e.g.,
  `app/brain/`, `app/agents/doc_agent.py`, `app/models/`, tests) was not
  fully read, so I cannot confirm there are no additional writers to the
  same data files.

---
## Developer Verification
Status: ☐ Not Reviewed
Reviewer:
Date:
Notes:

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
6ea9796|Er Sajan PLG|2026-07-11 22:42:47 +0545|feat(platform): expand model backends and configuration system
```

Notes: This log was generated from the repository history for `docs/DATABASE.md`.
