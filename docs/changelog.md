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
