
- **Model layer** — `ModelClient` Protocol with `LlamaCppClient` (local llama.cpp /
  OpenAI-compatible), `OllamaClient`, and `OpenRouterClient` (cloud)
- **Model routing** — `ModelRouter` with score-based routing to different `ModelClient`
  implementations based on `TaskType` (CODE, STEM, REASONING, GENERAL, DOCS)
- **Model switching** — `ModelSwitcher` for dynamic profile handling (local, cloud)
  and runtime model client instantiation via `ModelFactory`
- **Memory system** — `MemoryManager` orchestrates `MemoryStore` (JSON persistence),
  `CandidateRetriever` (Keyword & Vector via ChromaDB/OllamaEmbedding), and `MemoryRanker`
  (scores by relevance, importance, frequency, recency, confidence)
- **Context management** — `ContextWindowManager` fits messages into context window,
  trims in user/assistant pairs, `PromptBuilder` assembles full context
- **Tokenization** — `tiktoken`/`transformers` fallback chain for accurate token counting
- **Tool system** — `ToolRegistry` and `ToolExecutor` for prompt-based tool calling
  (e.g., `git_log`, `read_file`, `write_file`) with allowlists and confirmation gates
- **Documentation Agent** — `DocumentationAgent` as a mini-agentic loop using tools
  to generate `CHANGELOG` and `DEVLOG` entries


# Phase 0: Initial Project Structure (Pre-v0.1)

**Date:** 2026-06-27 (implied from v0.1 changelog entry)
**Objective:** Establish the foundational codebase and initial environment for JARVIS.
**Background:** The very first steps in creating the JARVIS project.
**Problem Statement:** No existing structure for an AI assistant.
**Investigation:** Researched basic architectural principles, system design, and future-proofing (upgradability, localized debugging).
**Alternative Designs Considered:** N/A (initial setup phase).
**Chosen Solution:**
- Created a virtual environment.
- Established core files and folders (e.g., `app/`, `main.py`).
- Basic `main.py` code for running JARVIS.
- `client.py` for model interaction (initially `OllamaClient`).
- Edited `settings.py` for initial configuration.
- Initialized Git repository, committed, and pushed.
**Implementation Details:** Standard Python project setup, basic Ollama client integration.
**Algorithms:** N/A.
**Files Introduced:**
- `.gitignore`
- `README.md`
- `requirements.txt`
- `app/__init__.py`
- `app/main.py`
- `app/config/settings.py`
- `app/models/ollama_client.py` (later renamed/refactored)
**Files Modified:** N/A (all new).
**Files Removed:** N/A.
**Architecture Discussion:** Laid the groundwork for a modular structure.
**Tradeoffs:** Simplicity over immediate complexity, focusing on getting a basic functional core.
**Known Bugs:** N/A.
**Future Improvements:** Implement CLI loop, add system prompts, introduce memory.
**Lessons Learned:** Importance of virtual environments, version control, and initial architectural planning.

# Phase 1: Foundation – Monolithic Memory & Single-Backend Prototype (v0.1 - v1.1)

This phase covers the initial iterations of JARVIS, focusing on establishing a conversational loop, introducing system prompts, and developing a foundational, albeit monolithic, memory system. The system evolves from stateless interactions to persistent, fact-based memory.

## v0.1: Initial Ollama Connection

**Date:** 2026-06-27
**Objective:** Connect JARVIS to the Ollama local LLM.
**Background:** Building the absolute minimum to get a response from an LLM.
**Problem Statement:** JARVIS needs to interact with an LLM.
**Investigation:** Explored methods to integrate with Ollama.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Created `ollama_client.py` to handle interactions with the Ollama server.
**Implementation Details:** Basic `OllamaClient` class.
**Algorithms:** N/A.
**Files Introduced:** (Covered in Phase 0 as initial structure)
**Files Modified:** `app/main.py`, `app/models/ollama_client.py` (for connection logic).
**Files Removed:** N/A.
**Architecture Discussion:** Established the concept of a `ModelClient`.
**Tradeoffs:** Very basic functionality, no conversation memory yet.
**Known Bugs:** N/A.
**Future Improvements:** Implement a CLI loop.
**Lessons Learned:** Successful connection to a local LLM is the first step.

## v0.2: CLI Chat Loop

**Date:** Unknown (relative order preserved)
**Objective:** Implement an interactive command-line interface (CLI) for JARVIS.
**Background:** JARVIS needs a way for users to interact with it repeatedly.
**Problem Statement:** Current setup only allows single-turn interactions.
**Investigation:** Explored different looping mechanisms for interactive CLI applications.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Implemented a `while` loop in `main.py` for continuous interaction.
**Implementation Details:**
- `while` loop for open-ended interaction.
- `OllamaClient` instantiated once outside the loop.
- Sequential input/output flow (input → process → output).
**Algorithms:** N/A.
**Files Introduced:** N/A.
**Files Modified:** `app/main.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Introduced the core conversational loop.
**Tradeoffs:** Still no memory, but provides continuous interaction.
**Known Bugs:**
- Initially tried mixing assignment inside `while` condition.
- Confused loop condition with loop body logic.
**Future Improvements:** Add system prompt support.
**Lessons Learned:** `while` loops are effective for open-ended interaction; client should be instantiated once.

## v0.3: System Prompt Support

**Date:** Unknown (relative order preserved)
**Objective:** Allow JARVIS to use system prompts to define its identity and behavior.
**Background:** LLMs perform better with clear system instructions.
**Problem Statement:** JARVIS lacks a defined identity or controlled behavior.
**Investigation:** Explored ways to integrate system prompts into the LLM interaction.
**Alternative Designs Considered:** Hardcoding prompts directly in `main.py`.
**Chosen Solution:** Moved system prompts into a dedicated `app/config/prompts.py` file.
**Implementation Details:**
- Added system prompt support to `OllamaClient`.
- System prompt is included in the messages list sent to the LLM.
**Algorithms:** N/A.
**Files Introduced:** `app/config/prompts.py`.
**Files Modified:** `app/models/ollama_client.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Separated prompt configuration from application settings.
**Tradeoffs:** Increased file count but improved organization.
**Known Bugs:** N/A.
**Future Improvements:** Implement session memory.
**Lessons Learned:** System prompts significantly influence model behavior; proper prompt placement is crucial.

## v0.4: Conversation Memory

**Date:** 2026-06-27
**Objective:** Enable JARVIS to remember previous conversation turns within a session.
**Background:** Stateless conversations limit usefulness and coherence.
**Problem Statement:** JARVIS forgets context after each turn.
**Investigation:** Explored how to store and pass conversation history to the LLM.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Added a `self.conversation` attribute to `OllamaClient` to store messages.
**Implementation Details:**
- `OllamaClient` stores the system prompt during initialization.
- Each user message is appended before sending.
- Each assistant response is appended after receiving.
- `messages` parameter in `chat()` function, `self.conversation` belongs to the object.
**Algorithms:** N/A.
**Files Introduced:** N/A.
**Files Modified:** `app/models/ollama_client.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Introduced statefulness to `OllamaClient`.
**Tradeoffs:** Memory grows indefinitely within a session (no pruning).
**Known Bugs:** N/A.
**Future Improvements:** Persistent memory, memory trimming.
**Lessons Learned:** Objects can own state; execution order (append → chat → append → return) is critical.

## v0.5: Persistent Memory Core

**Date:** Unknown (relative order preserved)
**Objective:** Make JARVIS's conversation memory persistent across sessions and restarts.
**Background:** Session-only memory prevents long-term continuity.
**Problem Statement:** JARVIS loses all context upon restart.
**Investigation:** Explored methods for storing and retrieving conversation history from disk.
**Alternative Designs Considered:** Directly handling JSON in `main.py`.
**Chosen Solution:** Introduced `MemoryManager` to handle persistence using a JSON file.
**Implementation Details:**
- `MemoryManager` stores conversation history in `app/memory/conversation.json`.
- Loads previous conversation on startup, saves updated conversation after every interaction.
- `main.py` orchestrates workflow, `OllamaClient` handles LLM, `MemoryManager` handles persistence.
**Algorithms:** N/A.
**Files Introduced:**
- `app/memory/manager.py`
- `app/memory/conversation.json`
**Files Modified:** `app/main.py`, `app/models/ollama_client.py` (implicitly to use new memory structure).
**Files Removed:** N/A.
**Architecture Discussion:** Cleanly separated concerns: orchestration, LLM interaction, and persistence.
**Tradeoffs:** Memory still grows indefinitely, no structured long-term memory.
**Known Bugs:** No recovery handling for corrupted JSON.
**Future Improvements:** Memory trimming, error handling, structured memory.
**Lessons Learned:** State persistence is crucial for a conversational system; separation of concerns improves extensibility.

## v0.06: Fact Extraction & Storage

**Date:** Unknown (relative order preserved)
**Objective:** Teach JARVIS to distinguish between conversation history and long-term facts, and store these facts persistently.
**Background:** Not all information in a conversation is equal; some are facts to be remembered.
**Problem Statement:** JARVIS treats all conversation content as undifferentiated memory.
**Investigation:** Explored rule-based methods for identifying and extracting facts.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Implemented a rule-based fact extraction system and persistent fact storage.
**Implementation Details:**
- Introduced `MemoryManager.add_fact()`.
- Updated memory format to store both conversation history and long-term facts.
**Algorithms:** Rule-based fact matching.
**Files Introduced:** `app/memory/fact_extractor.py`.
**Files Modified:** `app/memory/manager.py`, `app/models/ollama_client.py` (implicitly to use new memory structure).
**Files Removed:** N/A.
**Architecture Discussion:** Introduced a more granular memory structure.
**Tradeoffs:** Rule-based extraction can be limited and requires manual definition.
**Known Bugs:** N/A.
**Future Improvements:** Teach JARVIS to *use* remembered facts.
**Lessons Learned:** Conversation and knowledge are distinct memory types; persistent storage requires considering data structure evolution.

## v0.7: Context Builder & Long-Term Memory Integration

**Date:** 2026-06-28
**Objective:** Integrate extracted long-term facts into the LLM's context during conversation.
**Background:** JARVIS can store facts but doesn't actively use them in its responses.
**Problem Statement:** JARVIS's responses don't reflect its stored long-term knowledge.
**Investigation:** Explored a dedicated component to assemble the complete context for the LLM.
**Alternative Designs Considered:** Directly injecting facts in `OllamaClient`.
**Chosen Solution:** Created a `Context Builder` (`build_messages()` in `OllamaClient`) to combine system prompt, persistent facts, and conversation history.
**Implementation Details:**
- `build_messages()` centralizes all prompt construction.
- Persistent facts are injected into every request as a structured system message.
- Clear separation of responsibilities: `MemoryManager` (storage), `OllamaClient` (context building, requests), `main.py` (coordination).
**Algorithms:** N/A.
**Files Introduced:** N/A.
**Files Modified:** `app/models/ollama_client.py`, `app/main.py`, `app/memory/manager.py` (for loading facts).
**Files Removed:** N/A.
**Architecture Discussion:** Introduced a "Context Builder" pattern for dynamic prompt assembly.
**Tradeoffs:** Still sends *all* facts, potentially exceeding context window with many facts.
**Known Bugs:** N/A.
**Future Improvements:** Intelligent memory retrieval (send only relevant facts), memory categories, conversation trimming.
**Lessons Learned:** Designing architecture first simplifies implementation; methods should use object state; long-term and conversation memory serve different purposes.

## v0.8: Structured Memory Pipeline

**Date:** Unknown (relative order preserved)
**Objective:** Redesign JARVIS's memory architecture to use structured memory objects instead of plain strings.
**Background:** Plain string facts are difficult to search, filter, and extend.
**Problem Statement:** Inflexible memory format hinders advanced memory operations.
**Investigation:** Explored using dictionary structures for memory.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Changed fact storage from strings to dictionaries, each containing `category`, `type`, and `value`.
**Implementation Details:**
- Memory objects now have `category`, `type`, `value` fields.
- Created `rules.py` for configurable rule-based extraction.
- Updated `fact_extractor.py`, `ollama_client.py`, `memory.py` for the new structured flow.
**Algorithms:** Rule-matching based on `rules.py`.
**Files Introduced:** `app/memory/rules.py`.
**Files Modified:** `app/memory/fact_extractor.py`, `app/models/ollama_client.py`, `app/memory/manager.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Moved towards a scalable memory system; externalized extraction rules.
**Tradeoffs:** Required clearing old string-based facts; initial complexity increased.
**Known Bugs:**
- Variable scope issues (using "rule" before it existed).
- Missing imports (`RULES` in `fact_extractor.py`).
- Old memory format incompatibility (`TypeError: string indices must be integers`).
- Misconception that Ollama had persistent memory (disproved by experiment).
**Future Improvements:** Extract multiple facts per message, deduplication.
**Lessons Learned:** Separate architecture from implementation; verify assumptions with experiments; printing internal state is crucial for debugging; LLMs are stateless without explicit context.

## v0.9: Multi-Fact Memory Extraction

**Date:** 2026-06-29
**Objective:** Enable JARVIS to extract multiple structured facts from a single user message.
**Background:** Previous system could only extract one fact per message, losing information.
**Problem Statement:** JARVIS misses facts when multiple are expressed in one message.
**Investigation:** Explored sentence splitting and independent rule checking.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Replaced `extract_fact()` with `extract_facts()` to return a `List[dict]`.
**Implementation Details:**
- Added sentence splitting *before* extraction.
- Each sentence is checked independently against `RULES`.
- `main.py` updated to iterate through extracted facts.
- Memory manager stores each fact individually.
- `ollama_client` updated to build structured memory prompts from dictionaries.
**Algorithms:** Sentence splitting (regex-based), rule-matching per sentence.
**Files Introduced:** N/A.
**Files Modified:** `app/memory/fact_extractor.py`, `app/main.py`, `app/memory/manager.py`, `app/models/ollama_client.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Refined the extraction pipeline to be more comprehensive.
**Tradeoffs:** Increased complexity in parsing and data flow.
**Known Bugs:**
- Extractor returned a list when pipeline expected a single dictionary.
- Nested list bug during storage (entire list accidentally stored as one fact).
- Conversation history misleading memory tests (disproved Ollama's inherent memory).
**Future Improvements:** Duplicate detection, better sentence parsing, compound fact decomposition, memory metadata.
**Lessons Learned:** Returning `List[T]` instead of `T` requires pipeline updates; `pprint()` is useful for debugging data structures; sentence splitting should precede semantic extraction.

## v1.0: Rule Based Memory Behavior

**Date:** Unknown (relative order preserved)
**Objective:** Introduce a behavior-driven memory system, controlling memory logic via rules.
**Background:** Memory operations were still somewhat hardcoded or rigid.
**Problem Statement:** Lack of flexible control over how facts are stored and managed.
**Investigation:** Integrated behavior fields directly into rules.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Added a `behavior` field to rules, enabling `append`, `replace`, and `ignore` actions.
**Implementation Details:**
- Behavior field is now part of rule definition.
- `MemoryManager` follows the behavior specified by each extracted fact.
- Cleaner `MemoryManager` architecture.
**Algorithms:** Rule-matching with associated behaviors.
**Files Introduced:** N/A.
**Files Modified:** `app/memory/manager.py`, `app/memory/fact_extractor.py`, `app/memory/rules.py` (rules now include behavior).
**Files Removed:** N/A.
**Architecture Discussion:** Shifted to a behavior-driven memory engine for scalability.
**Tradeoffs:** Requires careful rule design to prevent unintended behavior.
**Known Bugs:**
- Nested list bug (re-emerged due to `add_fact()` usage).
- Old memory format confusion.
- Mixed spelling of "behavior"/"behaviour."
- Forgot to restart Python after module edits (old code running).
**Future Improvements:** Further refinement of behavior logic.
**Lessons Learned:** Follow the data, not assumptions; print intermediate states; Python imports modules once; behavior-driven architecture scales better.

## v1.1: Recognize Multiple Natural Language Variations

**Date:** Unknown (relative order preserved)
**Objective:** Improve the rule system to recognize multiple natural language variations for a single rule.
**Background:** Rules were too rigid, only matching one specific trigger phrase.
**Problem Statement:** Limited natural language understanding due to single-trigger rules.
**Investigation:** Replaced single `trigger` with a `triggers` list in rules.
**Alternative Designs Considered:** N/A.
**Chosen Solution:** Rules now support multiple phrases via a `triggers` list.
**Implementation Details:**
- Replaced `trigger` with `triggers` in rule definitions.
- Extractor iterates over all triggers.
- Behavior is propagated through extraction to `MemoryManager`.
**Algorithms:** Multiple string matching against a list of triggers.
**Files Introduced:** N/A.
**Files Modified:** `app/memory/rules.py`, `app/memory/fact_extractor.py`, `app/memory/manager.py`.
**Files Removed:** N/A.
**Architecture Discussion:** Enhanced rule flexibility without complicating extraction.
**Tradeoffs:** Increased rule definition complexity.
**Known Bugs:** N/A (pressure testing exposed architectural problems, not bugs).
**Future Improvements:** Memory should decide append/replace/ignore/merge, keeping extraction simple.
**Lessons Learned:** Simple extraction is best; memory should handle complex behavior decisions; separation of responsibilities eases future improvements.

# Phase 2: Architecture Rewrite – Modular Subsystem Era (v2.0.0)

This phase marks a complete architectural overhaul, moving away from the monolithic design of v1 to a modular, subsystem-based approach. The core problem addressed was the unbounded context window and tight coupling of components in v1. This rewrite introduced clear interfaces, separated responsibilities for memory management, and laid the foundation for intelligent context handling and model routing.

## v2.0.0: Complete Architectural Overhaul

**Date:** Unknown (relative order preserved)
**Objective:** Redesign JARVIS's core architecture to address context window limitations and component coupling, establishing a modular, scalable system.
**Background:** v1 suffered from sending every memory to the LLM on every turn, leading to rapid context window filling and lack of control over model knowledge. Tight coupling between `LlamaCppClient` and `MemoryManager` made changes difficult.
**Problem Statement:** JARVIS v1 was not scalable due to context window issues and high component coupling.
**Investigation:** Extensive architectural review, focusing on separation of concerns and interface definitions.
**Alternative Designs Considered:** Incremental fixes to v1 (rejected in favor of a full rewrite for long-term stability).
**Chosen Solution:** A full architectural redesign, defining clear Protocol classes for every subsystem boundary.

### Defining Interfaces (Session 1)
**Implementation Details:**
- Defined `Protocol` classes: `CandidateRetriever`, `MemoryRanker`, `MemoryStore`, `ModelClient`, `ContextWindowManager`.
- Chose Python's `Protocol` (PEP 544) over `ABC` for structural subtyping, enabling easier testing and third-party compatibility.
**Files Introduced:**
- `app/memory/retrieval.py` (for `CandidateRetriever` protocol)
- `app/memory/ranking.py` (for `MemoryRanker` protocol)
- `app/memory/store.py` (for `MemoryStore` protocol)
- `app/models/client.py` (for `ModelClient` protocol)
- `app/context/manager.py` (for `ContextWindowManager`)
**Architecture Discussion:** Every subsystem exposes one clean interface, hiding implementation details to allow swapping components without touching `MemoryManager` or `main.py`.
**Lessons Learned:** Protocol classes enforce clean boundaries and enable modularity.

### Memory Redesign (Session 2)
**Implementation Details:**
- Separated `MemoryManager` (orchestration, behavior rules) into `MemoryStore` (CRUD, JSON persistence), `CandidateRetriever` (finds candidates), and `MemoryRanker` (scores/ranks).
- `MemoryManager` is the sole public interface for memory operations.
- Changed main loop order: **extract and store facts BEFORE retrieval**, so newly introduced facts are immediately available.
- Introduced a rich memory schema: `id`, `created_at`, `updated_at`, `last_used`, `access_count`, `source`, `confidence`, `importance`.
- Used separate `created_at` (immutable) and `updated_at` (mutable) timestamps.
**Files Introduced:**
- `app/memory/store.py` (concrete implementation for JSON persistence)
- `app/memory/retrieval.py` (concrete `KeywordRetriever`)
- `app/memory/ranking.py` (concrete `MemoryRanker`)
**Files Modified:** `app/memory/manager.py` (refactored), `app/main.py` (loop order).
**Architecture Discussion:** Decoupled memory responsibilities; designed rich schema for future ranking and analysis; optimized loop for immediate fact availability.
**Lessons Learned:** Clean separation of concerns within memory; meticulous schema design prevents future migrations; retrieve before store is a crucial ordering.

### Ranking System (Session 3)
**Implementation Details:**
- Implemented two-stage retrieval: cheap `CandidateRetriever` finds candidates, expensive `MemoryRanker` scores them.
- `MemoryManager` fetches an "overshoot factor" (3x default) of candidates for the `Ranker`.
- Used log scale for frequency scoring (`log(1+count) / log(1+scale)`) to prevent early advantage.
- Defined default ranking weights: Relevance (0.35), Importance (0.25), Frequency (0.15), Recency (0.15), Confidence (0.10).
**Files Modified:** `app/memory/ranking.py`, `app/memory/manager.py`.
**Architecture Discussion:** Pattern adopted from information retrieval for efficient and precise memory ranking.
**Tradeoffs:** Added complexity in retrieval pipeline for improved context relevance.
**Lessons Learned:** Two-stage retrieval is effective; log scaling prevents bias in frequency metrics.

### Context Window (Session 4)
**Implementation Details:**
- Implemented `ContextWindowManager` to fit messages into the context window.
- **Trimmed messages in user/assistant pairs** (as a unit) to preserve conversational coherence, rather than oldest individual messages.
- Introduced a robust tokenization fallback chain:
    1. `tiktoken` (most accurate for OpenAI-compatible)
    2. `transformers` (for local Llama models, forced offline)
    3. Word-based estimation (`int(words * 1.3) + 3`).
- `get_token_counter()` result cached with `@lru_cache`.
**Files Introduced:**
- `app/context/manager.py`
- `app/utils/tokenizer.py`
**Files Modified:** `app/main.py`, `app/prompt/builder.py` (to integrate context fitting).
**Architecture Discussion:** Solved context overflow and incoherent trimming; implemented accurate token counting.
**Tradeoffs:** Required careful implementation of token counting and message grouping.
**Lessons Learned:** Trimming in pairs is essential for conversational coherence; accurate token counting is non-trivial.

### Model Layer (Session 5)
**Implementation Details:**
- Implemented **score-based model routing** in `ModelRouter`:
    - Scores each category (CODE, STEM, REASONING, GENERAL) independently.
    - Breaks ties by a preference order (CODE > STEM > REASONING > GENERAL).
    - `route()` returns `(ModelClient, TaskType)`.
- Combined base system prompt and retrieved memories into a **single `role: system` message** for consistent behavior across backends.
**Files Introduced:** `app/models/router.py`.
**Files Modified:** `app/main.py`, `app/prompt/builder.py`, `app/models/client.py`.
**Architecture Discussion:** Eliminated order bias in routing; ensured consistent system prompt handling.
**Tradeoffs:** Increased complexity in routing logic.
**Lessons Learned:** Score-based routing is superior to first-match; single system message improves model compatibility.

### Persistence & Dirty Tracking (Session 6)
**Implementation Details:**
- Implemented dirty tracking on `MemoryStore` and `ConversationManager` to prevent wasteful disk writes.
- `save_if_dirty()` called on exit via `_cleanup`.
- Added `save_on_every_message` config flag for eager saving (useful for voice I/O in future).
**Files Modified:** `app/memory/store.py`, `app/conversation/manager.py`, `app/main.py`.
**Architecture Discussion:** Optimized disk I/O; improved data integrity on unexpected shutdowns.
**Tradeoffs:** Added flags and logic for managing dirty state.
**Lessons Learned:** Batching saves improves performance; eager saving is important for robustness.

**Overall Tradeoffs (v2.0.0):** Significant increase in architectural complexity for greatly improved scalability, modularity, and control. Initial development time was high for the redesign, but future feature additions are now simpler.
**Known Bugs (v2.0.0):**
1. Dirty flag not set on direct memory mutation in `_handle_replace` and `touch()` — caused silent data loss on restart.
2. `DEFAULT_MODEL` was an object (`_DefaultModel()`) instead of a string, breaking legacy imports and API calls.
3. `ModelRouter` was initialized but `main.py` called `model.generate()` directly, bypassing routing logic.
4. `save_on_every_message` defaulted to `False`, leading to full session loss on crashes.
5. Model unavailability killed the process before `_cleanup()`, losing session data.
(These bugs were identified and fixed in v2.0.1).

**Future Improvements (v2.0.0):** Address identified bugs (v2.0.1); implement multi-backend support, streaming, external config (v2.1.0); semantic memory (v2.2.0); agentic tool system.
**Lessons Learned (v2.0.0):** Protocol interfaces are powerful; comprehensive schema design is critical; subtle bugs in core architecture can cause silent data loss; architecture reviews are as important as coding.

# Phase 3: Stability Hardening (v2.0.1)

This phase focused on addressing the silent failures and architectural inconsistencies identified immediately after the v2.0.0 rewrite. The goal was to ensure data integrity and establish a more reliable foundation for future features.

## v2.0.1: Stability and Bug Fixes

**Date:** Unknown (relative order preserved)
**Objective:** Resolve critical silent failures in v2.0.0 and improve system robustness.
**Background:** Post-release review of v2.0.0 revealed five critical issues that caused data loss or incorrect behavior without raising errors.
**Problem Statement:** v2.0.0 had multiple silent points of failure impacting data integrity and reliability.
**Investigation:** Code review and targeted testing of memory persistence, model default handling, and routing logic.
**Alternative Designs Considered:** N/A (focus on direct fixes).
**Chosen Solution:** Implemented five targeted fixes to address discovered bugs.

### Fix 1: Memory Persistence (Dirty Flag)
**Implementation Details:**
- Replaced `self._store.save()` with `self._store.force_save()` in `MemoryManager._handle_replace` and `retrieve()`.
- `force_save()` bypasses the dirty check, ensuring in-place mutations (like `touch()`) are persisted.
**Files Modified:** `app/memory/store.py`, `app/memory/manager.py`.
**Architecture Discussion:** Corrected a flaw where direct object mutation bypassed the store's dirty tracking.
**Lessons Learned:** Be wary of in-place mutations when using dirty tracking; explicit saving is sometimes necessary.

### Fix 2: Model Default Handling
**Implementation Details:**
- Replaced the `_DefaultModel` object with a simple `get_default_model()` function.
- `get_default_model()` calls `get_settings().default_model` on each access, ensuring lazy loading without returning a truthy object.
**Files Modified:** `app/config/settings.py`, `app/models/llamacpp_client.py`, `app/main.py`.
**Architecture Discussion:** Replaced an "overly clever" lazy loading pattern with a simpler, more robust function call.
**Lessons Learned:** Simplicity often beats cleverness in foundational logic.

### Fix 3: Active Routing
**Implementation Details:**
- Updated `main.py` to correctly use `ModelRouter.route(prompt)` to determine the model for each turn.
**Files Modified:** `app/main.py`.
**Architecture Discussion:** Properly connected the already-implemented router to the main conversational loop.
**Lessons Learned:** Wiring is as important as implementation.

### Fix 4: Crash Resilience (Eager Saving)
**Implementation Details:**
- Changed the default of `ConversationConfig.save_on_every_message` from `False` to `True`.
**Files Modified:** `app/config/settings.py`.
**Architecture Discussion:** Prioritized data integrity (session persistence) over minimal disk I/O.
**Lessons Learned:** For conversational systems, losing a session is worse than slightly increased I/O.

### Fix 5: Graceful Error Handling
**Implementation Details:**
- Wrapped `model.generate()` in `main.py` with `try/except`.
- Added logic to print a diagnostic, remove the triggering user message, and continue the loop on failure.
- Ensured `_cleanup()` (and thus saving) always runs on exit.
**Files Modified:** `app/main.py`.
**Architecture Discussion:** Improved system resilience to external failures (e.g., offline LLM server).
**Lessons Learned:** Always plan for component failure; maintain consistent internal state even when external calls fail.

**Overall Tradeoffs (v2.0.1):** Slightly increased disk I/O and slightly more complex error handling for significantly improved data trust and system stability.
**Lessons Learned (v2.0.1):** Data loss is a critical failure even if silent; simple patterns are often more reliable than complex ones.

# Phase 4: Multi-Backend & Streaming & External Config (v2.1.0)

This phase expanded JARVIS's capabilities by introducing support for multiple LLM backends (starting with Ollama), token-by-token streaming responses, and an externalized configuration system. The goal was to move beyond the single-backend limitation of v2.0 and provide a more flexible and interactive user experience.

## v2.1.0: Flexibility and Interactivity

**Date:** Unknown (relative order preserved)
**Objective:** Implement multi-backend support, streaming responses, and externalized configuration for improved flexibility and user experience.
**Background:** v2.0 could only use `llama.cpp`. The router was implemented but had only one model to route to. Responses appeared all at once, leading to a static feel. Settings were hardcoded.
**Problem Statement:** Single-backend limitation, lack of streaming, and hardcoded settings restricted JARVIS's flexibility and interactivity.
**Investigation:** Researched factory patterns for backend management, callback mechanisms for streaming, and YAML for structured configuration.
**Alternative Designs Considered:**
- Scattered `if/else` for backends (rejected in favor of a Factory).
- Generators for streaming (rejected in favor of callbacks for better composition with the sync loop).
- JSON for config (rejected in favor of YAML for readability and comments).
**Chosen Solution:** Implemented a Model Factory, callback-based streaming, and a YAML-based configuration system.

### Model Factory (Session 1 & 2)
**Implementation Details:**
- Introduced `app/models/factory.py` with a `create_client(config)` function.
- `main.py` now calls the factory and receives a `ModelClient` Protocol instance, decoupled from specific backend knowledge.
- Implemented `OllamaClient` using the `ollama` Python package, satisfying the `ModelClient` Protocol.
**Files Introduced:**
- `app/models/factory.py`
- `app/models/ollama_client.py`
**Architecture Discussion:** The `ModelClient` Protocol paid off, allowing multiple backends to be swapped seamlessly.
**Lessons Learned:** Factory pattern effectively decouples orchestration from backend implementation details.

### Streaming (Session 3)
**Implementation Details:**
- Added `stream: bool` and `on_token: Callable` to `ModelClient.generate()`.
- Implemented callback-based streaming in both `LlamaCppClient` and `OllamaClient`.
- Provided a `print` callback from `main.py` for real-time console output.
**Files Modified:** `app/models/client.py`, `app/models/llamacpp_client.py`, `app/models/ollama_client.py`, `app/main.py`.
**Architecture Discussion:** Named parameters (`stream`, `on_token`) prevent leakage into underlying API `**kwargs`. Callbacks were chosen for easier integration with the existing loop.
**Lessons Learned:** Streaming significantly improves perceived responsiveness; callbacks compose well with synchronous loops.

### External Config (Session 4)
**Implementation Details:**
- Implemented `config.yaml` support in `Settings.load()`.
- Used YAML for structured, readable configuration with comments.
- Settings are deserialized into dataclasses with hardcoded fallbacks if `config.yaml` is missing.
- Implemented dynamic router initialization from the loaded configuration.
**Files Introduced:** `config.yaml` (root).
**Files Modified:** `app/config/settings.py`, `app/main.py`.
**Architecture Discussion:** Moved configuration from code to data; enabled environment-specific model choices via `gitignore`.
**Tradeoffs:** Added a YAML dependency.
**Lessons Learned:** External configuration is essential for flexibility; YAML is an excellent choice for structured config.

**Overall Tradeoffs (v2.1.0):** Increased complexity in the model layer and added a new configuration format for greatly improved backend flexibility and user interactivity.
**Known Bugs (v2.1.0):**
1. `Settings.load()` returned `cls()` instead of the parsed `settings` object — config was ignored.
2. `LlamaCppClient` streaming code was unreachable (placed after a `return` statement).
3. `router.route()` returned a tuple, but `main.py` treated it as a client — caused a crash.
4. `on_token` kwarg leaked into the OpenAI API call in some paths, causing errors.
(These bugs were identified and fixed in v2.1.1).

**Future Improvements (v2.1.0):** Address identified bugs (v2.1.1); semantic memory (v2.2.0); agentic tool system.
**Lessons Learned (v2.1.0):** Watch for unreachable code during restructures; verify tuple unpacking; ensure internal parameters are consumed and not forwarded to external APIs.

# Phase 5: Semantic Memory (v2.2.0)

This phase introduced semantic memory capabilities, enabling JARVIS to retrieve relevant memories and past conversation exchanges based on semantic similarity rather than just keyword matching. The goal was to provide a more intuitive and context-aware memory system.

## v2.2.0: Semantic and Hybrid Retrieval

**Date:** 2026-07-05
**Objective:** Implement semantic memory using vector embeddings and integrate it with the existing keyword-based retrieval.
**Background:** Keyword-based retrieval is limited to exact matches. Semantic retrieval allows JARVIS to find conceptually related information (e.g., matching "what do I enjoy?" with "I like coding").
**Problem Statement:** Purely keyword-based retrieval is brittle and misses semantically related context.
**Investigation:** Researched vector databases (ChromaDB), embedding models (`nomic-embed-text`), and hybrid retrieval strategies.
**Alternative Designs Considered:**
- Custom embedding function using `requests` to Ollama (rejected due to ChromaDB's complex internal protocol requirements).
- Purely semantic retrieval (rejected; keyword matching is still superior for exact names/terms).
**Chosen Solution:** Implemented `VectorRetriever` (ChromaDB), `HybridRetriever` (Keyword + Vector), and `ConversationVectorStore`.

### Vector and Hybrid Retrieval (Session 1 & 2)
**Implementation Details:**
- Implemented `VectorRetriever` satisfying the `CandidateRetriever` Protocol.
- Used ChromaDB as the persistent vector database.
- Integrated `OllamaEmbeddingFunction` (using the `ollama` Python package) for local embedding generation via `nomic-embed-text`.
- Embedded text format: `"{category} {memory_type}: {value}"` for richer context.
- Implemented `HybridRetriever` to run both keyword and vector retrieval in parallel and deduplicate results.
**Files Introduced:**
- `app/memory/vector_retriever.py`
- `app/memory/hybrid_retriever.py`
**Architecture Discussion:** Hybrid retrieval provides the best of both worlds: precision of keyword matching and the broad conceptual reach of semantic search.
**Tradeoffs:** Added `ollama` package as a dependency specifically for embeddings; increased memory and processing requirements for vector operations.
**Lessons Learned:** Use established libraries (like `ollama` package) for complex integrations; hybrid retrieval is more robust than either method alone; deduplicate by stable IDs, not mutable objects.

### Conversation Vector Store (Session 3)
**Implementation Details:**
- Implemented `ConversationVectorStore` using a separate ChromaDB collection (`jarvis-conversations`).
- Stores and semantically searches complete user/assistant exchanges.
- Added one-time indexing of historical conversation on first startup.
**Files Introduced:** `app/memory/conversation_store.py`.
**Architecture Discussion:** Introduced episodic semantic memory alongside fact-based semantic memory.
**Tradeoffs:** Increased storage footprint; retrieval limits must be conservative (2 exchanges default) to preserve context window.
**Lessons Learned:** Episodic memory provides valuable conversational context; managing the context budget is critical when adding rich episodic data.

### Context Optimization (Session 4)
**Implementation Details:**
- Discovered that aggressive retrieval (20 memories + 5 exchanges) could consume 97% of context, leading to empty responses.
- Reduced `retrieval_limit` from 20 to 8 and past exchange limit to 2.
- Increased `safety_margin` from 150 to 300 tokens.
- Updated `PromptBuilder.build()` to inject `past_exchanges` into the system prompt (episodic context before semantic facts).
**Files Modified:** `app/prompt/builder.py`, `app/main.py`.
**Architecture Discussion:** Context budget is a finite and precious resource; retrieval limits must be carefully tuned.
**Tradeoffs:** Less context retrieved for improved model response quality and stability.
**Lessons Learned:** Monitor context utilization during stress tests; retrieval limits directly impact model output.

**Overall Tradeoffs (v2.2.0):** Increased architectural complexity and system requirements (ChromaDB, embeddings) for vastly improved context awareness and more human-like memory retrieval.
**Known Bugs (v2.2.0):**
1. `HybridRetriever` used `set(memories)` for deduplication, failing on unhashable mutable `Memory` objects. Fixed by deduplicating by ID.
2. ChromaDB metadata rejected nested dicts in `Memory.to_dict()`. Fixed by flattening/omitting metadata during store and restoring on load.
3. Collection conflicts in ChromaDB when changing embedding configurations required manual data deletion.
**Future Improvements (v2.2.0):** Memory deduplication, conversation summarization, agentic tool system.
**Lessons Learned (v2.2.0):** Vector databases bring new schema and configuration challenges; hybrid retrieval requires careful tuning; context window management is an ongoing balancing act.

# Phase 6: Agentic Tool System & Documentation Agent (v2.3.0 - v2.4.0)

This phase introduced agentic capabilities to JARVIS, enabling it to perform autonomous tasks using tools. The primary focus was the development of a `DocumentationAgent` capable of analyzing project history and generating documentation. This required building a robust tool execution framework and integrating it with the existing model architecture.

## v2.4.0: Agentic Foundations and Model Switching

**Date:** 2026-07-06 (inferred from recent activity)
**Objective:** Implement a tool execution framework, develop an autonomous Documentation Agent, and introduce mid-session model profile switching.
**Background:** Documentation and project logging were manual tasks. JARVIS lacked the ability to interact with the external world (filesystem, Git). Configuration was limited to a single active profile.
**Problem Statement:** Manual project logging is tedious and error-prone. JARVIS cannot autonomously analyze or modify its own state or surroundings.
**Investigation:** Researched prompt-based tool calling, Git automation, and dynamic model client management.
**Alternative Designs Considered:**
- Native LLM function calling (rejected for v2.4.0 to maintain compatibility with local models that don't support it; planned for v3.0).
- Static documentation generation scripts (rejected in favor of a flexible, autonomous agent).
**Chosen Solution:** Implemented `ToolRegistry`/`ToolExecutor`, `DocumentationAgent`, and `ModelSwitcher`.

### Tool Execution Framework (Session 1)
**Implementation Details:**
- Implemented `ToolRegistry` and `ToolExecutor` in `app/tools/`.
- Prompt-based tool calling using `<tool_call>` tags, unambiguous and compatible with any instruction-following model.
- Implemented three parsing formats: JSON, hybrid (function name with JSON), and positional function calls.
- Enforced deduplication by tool name in `ToolExecutor.parse()`.
- Implemented `MAX_OUTPUT_CHARS = 4096` and `DIFF_MAX_CHARS = 8000` for output truncation.
**Files Introduced:**
- `app/tools/base.py`
- `app/tools/executor.py`
**Architecture Discussion:** Establishes a standard interface for extending JARVIS's capabilities through tools. Prompt-based approach ensures maximum model compatibility.
**Tradeoffs:** Model must follow instructions for tool-call formatting; prompt-based parsing is less robust than native function calling.
**Lessons Learned:** Clear tag-based protocols are easier for models and parsers to handle; truncation is essential when injecting tool output into context.

### File and Git Tools (Session 2)
**Implementation Details:**
- Implemented read-only Git tools (`git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags`) using `subprocess`.
- Implemented file tools (`read_file`, `write_file`) with explicit allowlists (`ALLOWED_READ`, `ALLOWED_WRITE`).
- `write_file` requires explicit user confirmation via an `input()` prompt.
**Files Introduced:**
- `app/tools/file_tools.py`
- `app/tools/git_tools.py`
**Architecture Discussion:** Enforced security via strict allowlists and confirmation gates for risky operations. Read-only Git access prevents accidental repo corruption.
**Tradeoffs:** Confirmation prompt is blocking and requires a terminal; allowlists must be manually updated.
**Lessons Learned:** Multi-layered security (allowlists + confirmation) is effective for agentic tools; Git read access is a powerful signal for documentation agents.

### Documentation Agent (Session 3)
**Implementation Details:**
- Implemented `DocumentationAgent` as a "mini agentic loop" with a `MAX_ITERATIONS = 12` ceiling.
- Agent loop: generate response → parse calls → execute → inject results → loop.
- Predefined tasks for generating `CHANGELOG` and `DEVLOG` entries by analyzing Git history.
- Integrated `run_interactive()` menu for user control.
**Files Introduced:** `app/agents/doc_agent.py`.
**Architecture Discussion:** Demonstrated the power of the modular architecture by building an agent that reuses model clients and tools.
**Tradeoffs:** CONTRAST: System prompt instructs using `append_file` which is currently unregistered/dead code, forcing the agent to use `write_file` (overwrite) despite instructions.
**Known Bugs:**
1. `append_file` in `file_tools.py` is dead code (placed after a `return`) and not registered.
2. `git_diff` referenced in prompt but not registered (available as `git_diff_stat`/`git_diff_full`).
3. `git_status`/`git_branch` unregistered.
4. `parse()` dedups by name, preventing multiple calls to the same tool in one turn.
**Lessons Learned:** System prompt must be strictly aligned with registered tools; autonomous loops require robust iteration ceilings.

### Model Switching and Profile Management (Session 4)
**Implementation Details:**
- Implemented `ModelSwitcher` to manage model profiles (local, cloud) and build routers on demand.
- Implemented `OpenRouterClient` for cloud model access via the OpenAI-compatible API.
- Refactored `main.py` to use `ModelSwitcher` and added the `model` command for runtime profile switching.
- Integrated environment variable resolution for API keys (e.g., `env:XAI_API_KEY`).
**Files Introduced:**
- `app/models/switcher.py`
- `app/models/openrouter_client.py`
**Files Modified:** `app/main.py`, `app/models/factory.py`, `app/models/llamacpp_client.py`.
**Architecture Discussion:** Enabled JARVIS to switch between local and cloud backends without restarting, improving flexibility for different tasks.
**Tradeoffs:** Increased complexity in initialization and profile management.
**Lessons Learned:** Runtime switching requires careful resource management (building clients once); environment variable mapping is essential for secure API key handling.

**Overall Tradeoffs (v2.4.0):** Significant expansion of JARVIS's capabilities into autonomous agency and multi-profile cloud access, at the cost of increased complexity in tool management and security.
**Lessons Learned (v2.4.0):** Agentic systems require multi-layered security; the gap between agent instructions and registered tools is a common failure point; runtime model switching greatly enhances the platform's versatility.

---

# Current State & Outstanding Work (v2.4.0+)

The JARVIS project is now a modular, multi-backend AI assistant with semantic memory and an initial agentic tool system. The foundational architecture (v2.0.0+) has proven stable and extensible, allowing for the rapid integration of new backends (OpenRouter) and capabilities (DocumentationAgent).

**Verified Working Features:**
- CLI conversation loop with Fact Extraction and Memory retrieval.
- Hybrid memory retrieval (Keyword + Semantic via ChromaDB).
- Token-accurate context window fitting and pair-wise message trimming.
- Streaming responses from multiple local (llama.cpp, Ollama) and cloud (OpenRouter) backends.
- Runtime profile switching (local vs. cloud).
- Documentation Agent with 7 tools (read-only Git + limited File access).
- Secure API key handling via `.env` file mapping.

**Immediate Priorities (Outstanding Work):**
1. **Fix Agent-Tool Discrepancies:**
    - Correct the `append_file` implementation and registration in `file_tools.py`.
    - Align `doc_agent.py` system prompt with actual tool names (`git_diff_full` vs. `git_diff`).
    - Register `git_status` and `git_branch` to the agent.
    - Fix parser name-deduplication to allow multiple calls to the same tool in one response.
2. **Implement Memory Deduplication:** Prevent multiple facts for the same entity (e.g., duplicate names) from accumulating.
3. **Episodic Summarization:** Use the `_summary` field in `ConversationManager` to compress trimmed conversation pairs rather than discarding them.
4. **Native Function Calling (v3.0):** Transition to structured tool calls for models that support it, using the already-defined schema methods.
5. **Enhanced Permissions:** Move from hardcoded allowlists to a user-configurable permission system.

The engineering history recorded in this document serves as the canonical record of JARVIS's development, preserving the technical reasoning for every major architectural milestone.


# v2.4.0 Documentation Addition for each document having its own identity of why it exists.

## docs/ROADMAP.md
- What: A comprehensive project roadmap, now incorporating explicit sections for purpose, project vision, current development stage, completed milestones, work in progress, planned work, dependencies, known limitations, risks, future vision, and a detailed "AI Verification Status" with verified, partially verified, and unverified statements.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: The previous ROADMAP.md was more of a high-level plan. This new version aims to be a living, verifiable document that pulls information directly from the project's code, git history, and existing documentation. The primary motivation is to ensure transparency and accuracy by explicitly stating the source of verification for each claim. This helps both developers and JARVIS itself to understand the project's true state and direction without speculation.
- What it does/says: It provides a structured narrative of JARVIS's development, emphasizing the current transition towards dynamic model switching and expanded API support. The document details the architectural evolution, key features implemented, and upcoming work. The "AI Verification Status" is crucial, serving as a meta-document that clarifies the certainty of information presented, distinguishing between directly verifiable facts and planned work or historical reconstruction.
- Good to know: The inclusion of the "AI Verification Status" is a significant design decision, reflecting a commitment to evidence-based documentation. It acknowledges the challenges of reconstructing historical context and clearly delineates what is confirmed by the system's own introspection from what is based on existing plans. This makes the roadmap a more reliable and trustworthy source of information.

## docs/MEMORY.md
- What: A single verified map of the JARVIS memory layer — every module in app/memory/ documented from the code, not guessed.
- When: 2026/07/11 · v2.4.0 working tree
- Why: To give the developer one authoritative, source-checked document describing the memory architecture and data flow, replacing the need to read the modules individually. Every statement was cross-checked against schema.py, store.py, manager.py, retrieval.py, ranking.py, fact_extractor.py, rules.py, vector_retriever.py, hybrid_retriever.py, and conversation_store.py.
- What it does/says: Records the layered memory design, the full memory lifecycle (store/retrieve/update/delete), JSON + ChromaDB persistence formats, the hybrid keyword+vector retrieval pipeline, the weighted ranker, rule-based fact extraction, and the separate conversation vector store.
- Good to know: This is documentation-only (no code feature) — but it is genuinely useful because it was built by tracing the actual code path end-to-end and everything was verified against source rather than assumed, so the doc reflects real behavior (including the hybrid retriever, the 5-factor weighted ranking, and the two distinct ChromaDB collections).

## docs/CONFIG.md
- What: A single reference doc describing how JARVIS configuration works — architecture,
config files, environment variables, defaults, validation, runtime overrides, and
lifecycle — derived from app/config/settings.py.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: To give the developer (and JARVIS reading its own setup) one authoritative doc
for the config system, since the logic lived only in source and the protected config.yaml
could not be inspected directly.
- What it does/says: Records that config is centralized in a thread-safe Settings
singleton loaded from config.yaml with hardcoded dataclass fallbacks, lists every
default value, notes there is no explicit validation, and explains how get_settings()/
reset_settings() govern the lifecycle. (No new code feature; documentation-only.)

## docs/STARTUP_FLOW.md
- What: A single doc recording how JARVIS boots: from the `if __name__ ==
"__main__"` guard in app/main.py, through settings loading and subsystem
construction (MemoryManager, ConversationManager, PromptBuilder,
ConversationVectorStore, ContextWindowManager, ModelSwitcher,
DocumentationAgent), into the main interactive loop, and out via _cleanup.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: To give the developer (and JARVIS itself) one authoritative, source-checked
record of the startup path so boot behavior and dependency order are clear
without re-deriving them from code.
- What it does/says: Lays out entry point, startup sequence, initialization
order, objects created, configuration loading, dependency graph, event loop,
and shutdown sequence; each statement is tied back to the actual source
(main.py, config/settings.py, config/prompt.py, config/version.py).
- Good to know: Documentation-only — no code feature or behavior change. It was
written under a strict "verify against source, do not guess" rule, so it's a
honest boot map rather than speculative; uncertainties are called out inline.

## docs/ARCHITECTURE.md
- What: A single architecture document that explains JARVIS's structure, startup sequence, and runtime behavior, traced directly from source rather than guessed.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: To consolidate the system's design into one readable reference so new developers don't have to read every module to understand the flow, and to record verified facts about what is and isn't implemented.
- What it does/says: Maps folders to purposes, draws a layer diagram of component dependencies, walks the initialization in main(), describes the dependency-injection pattern used by MemoryManager/HybridRetriever/DocumentationAgent, details the while-loop lifecycle, and explicitly lists uncertainties (empty app/api and app/brain, commented-out server auto-start, pycache-only tools not in source).
- Good to know: The "Uncertainties / Unimplemented" section is the genuinely useful part — it honestly calls out empty folders, disabled features, and orphaned pycache files so the doc stays factual instead of speculative. (No new code feature; documentation-only.)

## docs/DATABASE.md 
- What: A single source-checked reference for how JARVIS stores and retrieves data — from a thin JSON-file fact store plus an embedded ChromaDB vector index, to the full write/read/update/delete lifecycle and the indexing layers on top.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: To give the developer one authoritative document that supersedes the fragmentary memory docs, and to close the gap that the persistence layer (engines, JSON-vs-vector split, verification status) was never written down against the actual code.
- What it does/says: Records the dual-store architecture, the data models, the persistence lifecycle for facts and conversations, the keyword/vector/hybrid indexes, the ChromaDB collections and embedding setup, the JSON storage format, and a future-improvements list; the appendix maps each section to a source check and lists what could not be verified.
- Good to know: The AI Verification Status appendix is the genuinely useful part — every claim is checked against source and unwired config / runtime-unverifiable items are called out honestly, so the doc stays truthful instead of speculative. (No new code feature; this is documentation-only.)

## docs/PROJECT_HISTORY.md (augmented)
- What: A single comprehensive history of how JARVIS was built and how its architecture
  evolved — from a thin Ollama wrapper to the current modular, multi-backend,
  memory-driven assistant. Now 19 sections plus a Verification Notes appendix.
- When: 2026/07/11 · working tree v2.4.0 (uncommitted)
- Why: To give the developer (and JARVIS reading its own lineage) one authoritative
  document that supersedes the fragmentary logs, and to close gaps the file had —
  §7–§10 had no source confirmations, and the engineering back-matter (§11–§19) was missing.
- What it does/says: Records the architecture arc, design philosophy, invariants, coding
  and naming standards, known patterns, technical debt, and future direction; the appendix
  maps each section to a source check and lists known discrepancies.
- Good to know: The Verification Notes appendix is the genuinely useful part — every claim
  is checked against source and known gaps/debt are called out, so the doc stays honest
  instead of speculative. (No new code feature; this is documentation-only.)



# V2.4.0 (2026-07-11)

# v2.4.0 — Model router crash: "No model for task type: TaskType.GENERAL" 

## Problem
On first prompt (`Hello Jarvis.`) the app died with
`ValueError: No model for task type: TaskType.GENERAL`, raised from
`ModelRouter.select()`. The router for the active `local` profile contained zero
models and had no default, so any task type — even `GENERAL` — failed to resolve.

## Options considered
1. Blame the missing API keys — the console showed 13 warnings
   (`grok_*`, `openrouter_*`, `google_*`, `cerebras_general`) because `.env` keys
   were commented out. Easy to assume, but wrong: those cloud models are not
   referenced by the `local` profile at all.
2. Make `select()`/`route()` never raise — fall back to a registered model or
   default instead of crashing the whole process.
3. Fix the actual wiring: load `profiles` from `config.yaml` so the `local`
   profile maps to `local_general`/`local_code`/etc., which need no API key.

## Decision
Do both (2) **and** (3). The profile-mapping bug was the true root cause, so (3)
is the real fix. (2) is defensive hardening so a future missing mapping degrades
to a default response instead of killing the CLI. We rejected (1): even with every
API key valid, the crash reproduced identically, because `local` still pointed at
non-existent keys.

## Why the hypothesis was wrong (verification)
`Settings.load()` handles `default_model`, `models`, `memory`, `context`,
`conversation`, `retrieval`, `ranking` — but has **no `if "profiles" in data:`**
branch. So `settings.profiles` kept the hardcoded default whose `local` map uses
keys `general`/`code`/`reasoning`/`docs`. `config.yaml`'s real models are
`local_general`, `local_code`, `local_reasoning`, `local_docs`, `grok_*`,
`openrouter_*`, `google_*`, `cerebras_general`. The 4 `local_*` models load fine
(no key) and produce no warning; the 13 cloud/cerebras models warn only because
their `env:` keys are unset. None of the warned models are in the `local` profile,
so the warnings and the crash are independent. Proof: warning count = 4 grok + 4
openrouter + 4 google + 1 cerebras = 13, exactly matching the log, while no
`general`/`autocomplete` warning appears.

## Trade-off accepted
Loading `profiles` directly from YAML means `config.yaml` is now the single source
of truth for profile→model mapping; the hardcoded `profiles` default in
`settings.py` becomes dead fallback. That's acceptable — it removes the silent
divergence that caused this bug. The router still raises only in the truly empty
case (no models and no default), which should never happen post-fix.



# Interactive Local/API + per-model cloud picker

## Problem
Users wanted to choose, mid-chat, between local and cloud execution, and — within a cloud provider — a specific model (e.g. OpenRouter's llama-3.3-70b vs qwen3-30b). The existing `model` command only switched whole profiles by name; a profile collapsed every role onto one fixed model, so there was no way to pick an individual model without hand-editing `config.yaml`.

## Options considered
1. One profile per model (e.g. `openrouter_llama`, `openrouter_qwen`) and just list profiles. Simple, but bloats `profiles:` and still requires editing YAML to add a model; doesn't give a clean Local/API split.
2. Keep profiles, but add a sub-menu that, after choosing API + provider, lists the cloud model entries and builds a single-model router on the fly. No YAML churn; model choice is data-driven from `settings.models`.
3. Auto-prompt provider before every message. Rejected as noisy/annoying UX.

## Decision
Option 2. Added `ModelSwitcher.switch_to_model(model_key)` which constructs a `ModelRouter` mapping all `TaskType`s to one client and sets it active under a synthetic `model:<key>` profile. `main.py` got three helpers: `_categorize_profiles` (local vs api), `_categorize_cloud_models` (groups model keys by `base_url` host), and `_interactive_model_select` (the menu). `model` (no arg) now launches the menu; `model list` / `model <name>` still work.

## Trade-off accepted
Single-model selection intentionally bypasses the `profiles:` role-differentiation system — a chosen model serves every task type. That's the desired behavior for "use this exact model," while `profiles` remains for users who want different models per task. Google models are currently excluded from cloud grouping because their `base_url` is hardcoded to `localhost` for the Python block; that's a pre-existing config quirk, noted as a Known Issue rather than worked around here.