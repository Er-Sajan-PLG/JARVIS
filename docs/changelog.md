# v0.8.0

1. Added

* Structured dictionary-based memory
* Rule-based fact extraction
* rules.py
* Category/type/value memory format

2. Changed

* Updated fact_extractor.py
* Updated ollama_client.py
* Updated memory.py
* build_messages() now formats structured facts

3. Fixed

* Variable scope issues
* Missing RULES import
* Compatibility with new memory format

4. Verified

* Confirmed Ollama is stateless
* Verified complete memory pipeline
* Verified structured facts persist correctly

5. Known Issues

* Only one fact extracted per prompt
* No sentence splitting
* No duplicate detection



# v0.9.0

1. Added
-----
+ extract_facts()
+ Multi-fact extraction
+ Sentence splitting
+ Dictionary-based structured facts
+ Rule-driven extraction pipeline

2. Changed
-------
* Extractor now returns List[dict]
* main.py processes multiple facts
* Memory storage supports multiple structured facts
* Prompt builder uses structured memory

3. Fixed
-----
* Single-fact extraction limitation
* Nested list storage bug
* Dictionary/string incompatibility

4. Known Issues
------------
- Regex sentence splitter
- Duplicate memories
- Compound facts remain unparsed


# v1.0.0

1. Added

- Multiple fact extraction
- Sentence splitting
- Structured memory objects
- Behavior-based memory engine
- append behavior
- replace behavior
- ignore behavior framework
- Cleaner memory architecture

2. Changed

- MemoryManager no longer hardcodes replacement logic.
- Memory behavior is now controlled entirely by RULES.
- Fact extraction supports multiple sentences.

3. Fixed

- Nested fact list bug
- Conversation memory loading issues
- Behavior persistence
- Various extractor bugs


# v1.1


1. Added

- Multiple triggers per rule.
- Behavior field inside rules.
- Behavior propagation through extractor.
- MemoryManager behavior dispatcher.
- Pressure testing of extraction pipeline.

2. Improved

- Rule flexibility.
- Natural language coverage.
- Cleaner extractor architecture.

3. Fixed

- Trigger schema migration (`trigger` → `triggers`).
- Behavior persistence.
- Rule iteration logic.


# v2.0.0

Changelog
All notable changes to JARVIS are documented here.
Format: Keep a Changelog Versioning: Semantic Versioning

[Unreleased]
To Fix (v2.0.1)
    • _handle_replace calls self._store.save() but dirty flag was never set — silent no-op
    • touch() mutates memory fields directly without setting dirty flag — access stats not persisted
    • DEFAULT_MODEL = _DefaultModel() exports an object, not a string — breaks legacy imports

[2.0.0] — Architecture Release
Added
Memory System
    • MemoryStore — low-level CRUD and JSON persistence, dirty tracking, save_if_dirty() pattern
    • CandidateRetriever (Protocol) — interface for finding candidate memories; KeywordRetriever as default implementation
    • MemoryRanker — scores candidates using 5 weighted factors (relevance, importance, frequency, recency, confidence)
    • MemoryManager — high-level orchestrator; the only class external code should import
    • Two-stage retrieval pipeline: candidates → rank → update access stats
    • retrieve(prompt, limit) — returns only relevant memories, not all memories
    • store(fact), update(id, fields), replace(fact), delete(id), merge(id, data) — full CRUD surface
    • on_store, on_update, on_delete callbacks for memory lifecycle events
    • Candidate overshoot: fetches limit * 3 candidates before ranking, giving ranker more signal
Memory Schema
    • id — 8-char UUID fragment, stable identifier
    • created_at — immutable, set once at creation
    • updated_at — mutable, updated on field changes via mark_updated()
    • last_used — mutable, updated on every retrieval via touch()
    • access_count — incremented on every retrieval
    • source — "user", "system", or "inferred"
    • confidence — 0.0–1.0, reliability of this fact
    • importance — 0.0–1.0, significance weighting
    • IMPORTANCE_LOW/MEDIUM/HIGH/CRITICAL constants
Context Window
    • ContextWindowManager — fits messages into context window before every LLM call
    • Trims in user/assistant pairs, never breaks an exchange
    • _group_into_pairs() — groups conversation into logical exchanges
    • ContextStats dataclass — total_tokens, utilization, pairs_kept, pairs_trimmed, was_trimmed
    • get_stats() — returns stats from last fit() call
Token Counting (app/utils/tokenizer.py)
    • Fallback chain: tiktoken → transformers (offline) → word-based estimation
    • get_token_counter(model_name) — cached with @lru_cache, returns best available counter
    • get_tokenizer_info() — returns active method, availability flags, test count
    • HuggingFace forced offline (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1) — no surprise downloads
    • Word-based formula: int(words * 1.3) + 3 — conservative estimate
Conversation Manager
    • ConversationManager — manages conversation with dirty tracking
    • add_message(role, content) — adds message, marks dirty
    • get_recent(limit) / get_recent_formatted(limit) — windowed history retrieval
    • save_on_every_message config flag for eager persistence (useful for voice I/O later)
    • save_if_dirty() — only writes to disk if changes were made
Prompt Builder
    • PromptBuilder.build(memories, conversation, user_prompt) — assembles full message list
    • System prompt and memories merged into single role: system message for model compatibility
    • Memory block formatted as ## Known User Facts with category/type annotation
    • build_with_stats() — returns (messages, stats_dict) for debugging
Model Router
    • Score-based routing — all keyword categories scored independently, no order bias
    • Tie-breaking by specificity: CODE > STEM > REASONING > GENERAL
    • route(prompt) now returns (ModelClient, TaskType) tuple
    • register(task_type, client) — runtime model registration
    • Expanded keyword sets per task type (16 CODE keywords, 15 STEM, 14 REASONING)
Configuration
    • MemoryConfig.min_relevance_score — replaces broken retrieval_limit * 0.01
    • MemoryConfig.candidate_overshoot_factor — controls retrieval/ranking tradeoff
    • RankingConfig — individual weights for all 5 ranking factors
    • ConversationConfig.save_on_every_message — eager persistence toggle
    • ContextConfig.tokenizer_method — "auto", "tiktoken", "transformers", "word"
    • Thread-safe get_settings() singleton using threading.Lock
Fact Extractor
    • VALUE_BOUNDARIES — stops value extraction at conjunctions and clause boundaries
    • _extract_value(text, trigger) — cleaner extraction, strips artifacts ("that ", "to ")
    • Abbreviation handling in _split_into_sentences — mr., dr., prof. don't end sentences
    • Minimum value length check (len(value) >= 2) before storing
Main Loop
    • stats command — shows tokenizer info, memory count, conversation count, context utilization
    • _cleanup(memory, conversation) — graceful shutdown with save_if_dirty()
    • Fact extraction moved BEFORE retrieval — newly stated facts are available in the same turn
    • response.content no longer stored redundantly in conversation before extraction
Changed
    • Memory JSON format: v1 {category, type, value, behavior} → v2 full schema (auto-migrated on load)
    • Retrieval: v1 sent all memories → v2 retrieves only relevant memories
    • Context trimming: v1 trimmed individual oldest messages → v2 trims oldest pairs
    • Token counting: v1 len(text) // 4 → v2 tiktoken/transformers/word fallback chain
    • System prompt placement: v1 stored in conversation file → v2 injected fresh each turn
    • Model routing: v1 first-match keyword → v2 score-based with tie-breaking
Removed
    • MemoryManager.apply_behavior() — logic moved into MemoryManager.store()
    • LlamaCppClient.build_messages() — replaced by PromptBuilder
    • LlamaCppClient.conversation / LlamaCppClient.facts — moved to dedicated managers
    • MemoryManager.save(conversation, facts) — conversation no longer belongs to MemoryManager
    • _rules dead field in ModelRouter.__init__
Breaking Changes
    • Memory file format changed (v1 files are auto-migrated on first load, then written in v2 format)
    • MemoryManager.load() returns ([], facts) — conversation is now ConversationManager's job
    • ModelRouter.route() returns (ModelClient, TaskType), not just ModelClient
    • DEFAULT_MODEL is now a _DefaultModel object (bug — see Unreleased above)
Fixed
    • Context window overflow: ContextWindowManager.fit() now guarantees messages fit
    • "My name is X" fact stored but never actually replaced the old name — replace behavior now works
    • System prompt duplication: v1 stored the system prompt as first conversation message, then injected it again
    • Short-text token count returning 0: len(text) // 4 returned 0 for strings under 4 characters

[1.0.0] — Initial Release
    • LlamaCppClient with OpenAI-compatible API
    • MemoryManager with JSON persistence (load/save)
    • Rule-based extract_facts() with trigger matching
    • Single conversation file (system prompt + turns)
    • All memories sent to LLM on every turn (no retrieval)


## 2.0.0(forgot to change to v2.0.1) - Minor Bug fixes and added dev log, architect and changelog for v2.0.0

1. [2.0.1] — Stability

Five silent failures discovered through code review. None caused visible crashes.
All five caused data loss or dead behavior without any error message.

This release is about trust: after these fixes, what JARVIS stores stays stored,
what JARVIS routes gets routed, and if something goes wrong, the session survives.

---


2. **Bug 1 — Replaced memories didn't survive restarts**

`MemoryManager._handle_replace` modified `Memory` object fields directly, then
called `self._store.save()`. That save is gated on `_dirty`, which only gets set
when objects pass through the store's `add()` or `remove()` methods — not when
a memory's fields are mutated in-place. The flag was never set. The save was a
silent no-op.

Same issue in `retrieve()`: after `touch()` updated `last_used` and
`access_count`, `save_if_dirty()` did nothing because the store still thought
it was clean.

Fix: `force_save()` in both places, which bypasses the dirty check.

What this meant for JARVIS before the fix: if you said "My name is Robert" and
JARVIS already knew a name, the update appeared to work in that session.
On restart, JARVIS still called you by the old name. JARVIS looked like it was
learning while quietly forgetting.

3. **Bug 2 — DEFAULT_MODEL was an object, not a string**

`DEFAULT_MODEL = _DefaultModel()` was designed to defer `get_settings()` until
first access rather than at import time. The idea was right. The implementation
was wrong: `_DefaultModel()` is a truthy Python object. Any code doing
`model or DEFAULT_MODEL` would receive the object itself, not a string.
API calls passed `<_DefaultModel object at 0x...>` as the model name.

The wrong fix: `DEFAULT_MODEL = get_settings().default_model`
That evaluates at import time — the original problem, just moved.

The right fix: a function.
```python
def get_default_model() -> str:
    return get_settings().default_model
```
Functions are callable. There is no ambiguity between what `get_default_model`
is and what it returns. All callers updated accordingly.

4. **Bug 3 — ModelRouter was initialized but never called**

`main.py` created a `ModelRouter`, classified every prompt by task type, and
then immediately called `model.generate()` directly. The router did real work —
it just had no effect on anything.

```python
# Before: router existed, did nothing
response = model.generate(fitted_messages)

# After: router determines which model runs
selected_model, task_type = switcher.router.route(prompt)
response = selected_model.generate(fitted_messages)
```

At v2.0.1 with only one registered model, routing is transparent. The value
arrives in v2.5 when additional backends are added. Fixing this now means
v2.5 is a registration call, not an architecture change.

5. **Bug 4 — Full sessions lost on crash**

`save_on_every_message: bool = False` was the `ConversationConfig` default.
The intent was to reduce disk I/O by batching saves. The consequence: a crash,
power cut, or `kill -9` between turns discarded the entire session silently.

Changed default to `True`. Saving a few kilobytes of JSON after each completed
turn is not a performance bottleneck for a conversational loop. Losing a session
is not acceptable.

6. **Bug 5 — Model unavailability killed the process before cleanup**

If `llama-server` was offline, `model.generate()` raised a `ConnectionError`
that propagated through `main()` and bypassed `_cleanup()`. Memories and
conversation turns from that session were lost.

Wrapped in try/except. On failure: print a diagnostic, remove the user message
that triggered the failed call (to keep conversation state consistent), and
continue the loop. `_cleanup()` now always runs on exit regardless of how the
model responds.

---

7. Changed

- `DEFAULT_MODEL` removed; replaced with `get_default_model() -> str`
- `ConversationConfig.save_on_every_message` default: `False` → `True`
- `main.py` model calls now route through `ModelRouter`

This file records every significant change to JARVIS, in order.
It is written for two readers: the developer who built this system,
and JARVIS itself — so that JARVIS can understand its own history,
what it could and couldn't do at each stage, and why it became what it is.


# 2.1.0 — Multi-Backend + Streaming + External Config

JARVIS can now run models from two backends simultaneously — llama.cpp and Ollama
— with each backend routed automatically based on task type. Configuration moved
from hardcoded Python to an external config.yaml, so the model setup can change
without touching source code. Responses now stream token by token instead of
appearing all at once.



1. OllamaClient (app/models/ollama_client.py)

New model backend using the ollama Python package. Satisfies the same
ModelClient Protocol as LlamaCppClient — main.py sees no difference
between the two. Handles both blocking and streaming modes natively:

pythonclient = OllamaClient(model="deepseek-r1:32b", role="reasoning")
response = client.generate(messages, stream=True, on_token=print)

The import is optional — if ollama is not installed, JARVIS loads without it
and only crashes if an Ollama model is actually requested. This prevents the
package from becoming a hard dependency for users running llama.cpp only.

Factory (app/models/factory.py)

Single function that reads a ModelConfig and returns the correct client
instance. main.py no longer knows what backends exist.

python# Before (main.py knew about backends):
client = LlamaCppClient(model=cfg.name, base_url=cfg.base_url)

After (main.py knows nothing):
client = create_client(cfg)

Adding a new backend in the future (OpenAI API, LM Studio, etc.) requires
a new client class and one elif in the factory. Nothing else changes.

2. Streaming

Both clients now accept stream: bool and on_token: Callable[[str], None]
as named parameters. The caller (main.py) provides the callback; the client
owns the loop. Voice output in v3.1 will replace the print callback with a
speech synthesis call — no client code changes required.

stream and on_token are explicit named parameters, not **kwargs. This
prevents them from leaking into the underlying API call (see Bug 4 below).

3. External config (config.yaml)

All model and memory configuration moved to a YAML file at the project root.
Settings.load() reads it on first call and falls back to hardcoded defaults
if the file doesn't exist — no breaking change for existing setups.

The full model lineup as of v2.1:

RoleModelBackendgeneralllama-3.2-3b-instructllamacppcodeqwen3:8bollamareasoningdeepseek-r1:32bollamaautocompleteqwen2.5-coder:1.5bollama

4. Dynamic router initialization

main.py now builds the router from config at startup rather than hardcoding
registrations. Each model entry in config.yaml maps its role string to a
TaskType enum value (TaskType("code") → TaskType.CODE). Failed model
loads print a warning and continue — one unavailable model doesn't prevent
the rest from loading.

ModelConfig.backend field

New field on ModelConfig ("llamacpp" or "ollama"). The factory reads
this to determine which client class to instantiate.


5. Changed


LlamaCppClient.__init__ now uses get_default_model() instead of the
removed _DefaultModel object (v2.0.1 fix carried through)
main.py model initialization: hardcoded LlamaCppClient instantiation
→ dynamic create_client(cfg) calls via factory
main.py main loop: model.generate(messages) → model.generate(messages, stream=True, on_token=lambda t: print(t, end="", flush=True))
 

6. Bugs 
Encountered bugs and fixed in same version
Bug 1 — Settings.load() returns cls() instead of settings (critical)

The entire YAML parsing block builds a settings object that is never returned.
The method returns cls() — fresh defaults — regardless of what's in config.yaml.
JARVIS silently ignores all configuration.

python# Wrong (current):
return cls()

Fix:
return settings

Bug 2 — LlamaCppClient streaming code is unreachable (critical)

The streaming logic was appended after the return ModelResponse(...) statement
in the non-streaming path. Python never executes code after a return.
Calling generate(stream=True) on a LlamaCppClient returns a complete
non-streamed response. No tokens are emitted to on_token.

Fix: restructure generate() to match OllamaClient's pattern:

pythondef generate(self, messages, stream=False, on_token=None, **kwargs):
    if not stream:
        # existing non-streaming path
        ...
        return ModelResponse(...)
    # streaming path (currently unreachable)
    ...

Bug 3 — router.route() returns a tuple; main.py treats it as a client (crash)

router.route() was updated in v2.0.1 to return (ModelClient, TaskType).
v2.1's main.py assigns the result to model and immediately calls
model.generate(). This crashes with:
AttributeError: 'tuple' object has no attribute 'generate'

python# Wrong (current):
model = switcher.router.route(prompt)

Fix:
model, task_type = switcher.router.route(prompt)

Bug 4 — on_token leaks into the OpenAI API call (API error)

Before restructuring for Bug 2: generate(self, messages, **kwargs) receives
on_token in **kwargs, then passes all of **kwargs to
self._client.chat.completions.create(...). The OpenAI SDK rejects unknown
keyword arguments. This error fires before the unreachable streaming code is
ever reached, making Bugs 2 and 4 appear as one symptom.

Fix is the same as Bug 2: make stream and on_token named parameters so
they are consumed by generate() and never forwarded to the API.



# 2.2.0 - — Semantic Memory

All notable changes to JARVIS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

1. Added
- `VectorRetriever` — ChromaDB-backed semantic memory retrieval using
  cosine similarity. Satisfies `CandidateRetriever` Protocol, drop-in
  for `KeywordRetriever`
- `HybridRetriever` — runs keyword and vector retrieval in parallel,
  deduplicates by memory ID, passes union to `MemoryRanker`
- `ConversationVectorStore` — separate ChromaDB collection for storing
  and semantically searching complete conversation exchanges
- One-time indexing of historical conversation on first startup
- `past_exchanges` parameter in `PromptBuilder.build()` — injects
  semantically relevant historical conversations into system prompt
- Local embedding generation via `nomic-embed-text` through Ollama
- `ollama` Python package installed for ChromaDB embedding integration
  (distinct use from chat — embeddings require the package,
  generation does not)

2. Changed
- `PromptBuilder` system message now ordered: base prompt →
  past exchanges → memory facts (episodic before semantic)
- `retrieval_limit` reduced from 20 to 8 — 20 memories consumed
  ~300 tokens before generation, causing empty responses at 97% context
- Past exchange retrieval limited to 2 per turn (each exchange ~200 tokens)
- `safety_margin` increased from 150 to 300 tokens

3. Fixed
- `HybridRetriever` used `set(memories)` for deduplication —
  `Memory` is a mutable dataclass, Python sets `__hash__ = None`
  automatically, causing `TypeError: unhashable type: 'Memory'`
  at runtime. Fixed: deduplicate by `memory.id` string instead
- ChromaDB metadata nested dict rejection — `Memory.to_dict()` includes
  `metadata: {}` (nested dict), rejected by ChromaDB which requires
  flat `str | int | float | bool` values. Fixed: omit `metadata`
  field in `_to_chroma_meta()`; `Memory.from_dict()` defaults to `{}`

---

