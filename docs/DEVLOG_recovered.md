## v0.1

Created JARVIS
-Learned about architecture, system design, future proof(upgradability, localized debug)
-created virtual environment, 
-created core files and folders
-written core code for main.py for running JARVIS, importing model, created client.py in model for ollama
-edited settings.py
-git setup and commited and pushed


## v0.2

Built CLI loop for Jarvis.

Key learning:
- while loops are better for open-ended interaction
- client should be created once, not inside loop
- input/output flow must be sequential (input → process → output)

Mistakes:
- initially tried mixing assignment inside while condition
- confused loop condition with loop body logic


## v0.3

Added:
- System prompt support.
- Jarvis identity layer.

Design decisions:
- Moved prompts into app/config/prompts.py.
- Kept settings.py for application configuration only.

Learned:
- System prompts influence model behavior.
- The model only follows the system prompt if it's included in the messages list.

Next:
- Session memory.



## v0.4 – Conversation Memory

Date: 2026-06-27

### Features
- Added conversation history to `OllamaClient`.
- Stored the system prompt during initialization.
- Appended each user message before sending a request to the LLM.
- Appended each assistant response after receiving it.
- Jarvis can now maintain context across multiple conversation turns.

### What I Learned
- Objects can own state (`self.conversation`).
- `__init__()` is used to initialize object attributes.
- Execution order matters: append → chat → append → return.
- The `messages` parameter belongs to the `chat()` function; `self.conversation` belongs to the object.
- `return` ends a function immediately, so any code after it won't execute.

### Notes
- Configured Git to ignore Python cache (`__pycache__`) files.


## v0.5 - Persistent Memory Core

🧠 Overview

In this version, Jarvis gained persistent conversational memory. The system now stores chat history on disk and reloads it on startup, allowing continuity across sessions and system restarts.

This moves Jarvis from a stateless LLM wrapper into a stateful conversational system.

⚙️ Major Features Added
💾 Persistent Memory System
Introduced MemoryManager
Stores conversation history in a JSON file
Loads previous conversation on startup
Saves updated conversation after every interaction
🔁 Conversation Continuity
Chat history is preserved across program restarts
Model receives full conversation context every request
Enables context-aware responses over time
🧩 Separation of Concerns (Architecture Refactor)

System now cleanly split into:

main.py → Orchestrates workflow
OllamaClient → Handles LLM interaction
MemoryManager → Handles persistence (load/save/clear)
🏗️ Architecture (v0.5)
User
 ↓
main.py
 ↓
MemoryManager → loads conversation.json
 ↓
OllamaClient → sends full conversation to model
 ↓
AI response
 ↓
MemoryManager → saves updated conversation.json
🧪 Behavior Changes
Before v0.5
Every run = fresh conversation
No memory between sessions
After v0.5
Jarvis remembers past messages
Identity and context persist
Conversations continue seamlessly after reboot
📂 Data Storage
Format: JSON
Structure: list of role-based messages
Location: app/memory/conversation.json

Example:

[
  {"role": "system", "content": "SYSTEM_PROMPT"},
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi!"}
]
🧠 Key Engineering Concepts Learned
State persistence in applications
Dependency injection (conversation passed into client)
Separation of concerns (memory vs model vs orchestration)
File-based storage using JSON
Lifecycle design: load → run → save loop
⚠️ Known Limitations
Memory grows indefinitely (no pruning yet)
No structured long-term memory (everything stored equally)
No recovery handling for corrupted JSON
No semantic memory (pure raw chat history only)
🚀 What v0.6 should focus on (suggested)
Memory trimming / summarization
Error handling for corrupted memory file
“Forget last N messages”
Structured memory (facts vs chat history)
Optional SQLite upgrade
Session tagging
🏁 Summary

v0.5 transforms Jarvis into a persistent conversational agent.

It now has:

continuity, identity, and memory across sessions.


## v0.06 - JARVIS Development

 🎯 Goal

Teach Jarvis to distinguish between conversation history and long-term facts.

 1. Features Added

* Implemented a rule-based fact extraction system.
* Added persistent fact storage alongside conversation history.
* Introduced `MemoryManager.add_fact()`.
* Updated memory format to store:

  * Conversation history
  * Long-term facts
* Added support for loading both the old conversation-only format and the new structured memory format.
* Successfully verified that facts persist after restarting Jarvis.

 2. Architecture Changes

```
User
  ↓
OllamaClient
  ↓
Conversation Memory
  ↓
Fact Extractor
  ↓
MemoryManager
  ↓
conversation.json
```

3. Memory now contains:

* Conversation (short-term context)
* Facts (long-term memory)

4. Lessons Learned

* Conversation and knowledge are different kinds of memory.
* Persistent storage requires thinking about data structure evolution.
* Schema changes require migration or backward compatibility.
* Separating responsibilities (AI, memory, extraction) makes the system easier to extend.

5. Current Status

  Jarvis can:

* Hold conversations.
* Remember conversations across restarts.
* Extract simple facts from user input.
* Store long-term information independently of chat history.

6. Next Goal (v0.7)

Teach Jarvis to **use** remembered facts during conversation instead of only storing them.


## v0.7 - Context Builder & Long-Term Memory Integration


Date: 2026-06-28

🚀 Major Milestone

Jarvis no longer sends only the conversation to the LLM.

A dedicated Context Builder (build_messages()) now prepares the complete context for every request by combining:

System Prompt
Persistent Facts (Long-Term Memory)
Conversation History

before sending it to the model.

✅ Features
Context Builder
Added build_messages() to OllamaClient.
Centralized all prompt construction in one place.
Returns a complete messages list for the LLM.
Long-Term Memory
Persistent facts are now injected into every request.
Facts remain separate from conversation history.
Facts are formatted into a structured system message.
Cleaner Architecture

Responsibilities are now clearly separated:

MemoryManager
Load conversation
Save conversation
Store facts
Clear memory
OllamaClient
Build LLM context
Send requests
Update conversation
main.py
Coordinate communication between components
🧠 Architecture
User
 │
 ▼
main.py
 │
 ▼
MemoryManager
 │
 ├── Conversation
 └── Facts
 │
 ▼
OllamaClient
 │
 ├── build_messages()
 │      ├── System Prompt
 │      ├── Facts
 │      └── Conversation
 │
 ▼
chat()
 │
 ▼
Assistant Response
 │
 ▼
MemoryManager.save()
📚 Lessons Learned
Objects own state (self.conversation, self.facts).
Methods should use object state instead of passing everything as parameters.
Separate building context from sending requests.
Long-term memory and conversation history serve different purposes.
Designing architecture first makes implementation much easier.
🔜 Next (v0.8)
Intelligent memory retrieval.
Send only relevant facts instead of every stored fact.
Introduce memory categories (preferences, identity, projects, goals, etc.).
Begin trimming conversation while preserving important knowledge.
⭐ Personal Note

This version marks the point where Jarvis became more than a simple wrapper around an LLM. It now has its own memory layer, a context-building pipeline, and a clear separation of responsibilities between storage, orchestration, and inference.



## v0.8 - feat(v0.8): implement structured memory pipeline



1. Objective

The goal of v0.8.0 was to redesign Jarvis' memory architecture by replacing plain string facts with structured memory objects.

Previous versions stored facts as simple strings such as:

"user likes football"

This made searching, filtering, and extending memory difficult.

The objective was to move toward a scalable memory system.

---

2. Major Architectural Changes

a. Structured Memory

Changed fact storage from:

* string

to

* dictionary

Each memory now contains:

* category
* type
* value

Example:

{
"category": "preference",
"type": "like",
"value": "football"
}

This allows future querying and filtering of memories.

---

b. Rule-Based Extraction

Created a dedicated rules.py.

Instead of hardcoded if-statements, memory extraction now loops through a configurable list of rules.

Benefits:

* easier to extend
* easier to maintain
* central place for extraction rules

---

c. Updated Memory Pipeline

Updated:

* fact_extractor.py
* ollama_client.py
* memory.py

The complete memory flow is now:

User Prompt

↓

Rule Matching

↓

Fact Extraction

↓

Structured Dictionary

↓

Memory Storage

↓

Conversation JSON

↓

Message Builder

↓

LLM

---

3. Bugs Encountered

a. Variable Scope

Attempted to use "rule" before it existed.

Learned that variables created inside a loop only exist after the loop begins.

---

b. Missing Imports

Forgot to import RULES into fact_extractor.py.

Learned that every Python module has its own namespace.

---

c. Old Memory Format

v0.7 memories were stored as strings.

The new message builder expected dictionaries.

Result:

TypeError:
string indices must be integers

Solved by clearing the old facts and starting with the new format.

---

d. Memory Investigation

Suspected Ollama had persistent memory.

Performed an experiment.

Removed:

messages.extend(self.conversation)

Printed every message being sent.

Confirmed that Ollama only receives exactly what Jarvis sends.

Conclusion:

Ollama is stateless.

All memory comes from Jarvis' own architecture.

---

4. Current Limitations

Current extractor only extracts one fact from a message.

Example:

"I like football. I like music. I can code."

becomes

one large extracted fact.

This will be redesigned in v0.9.

---

5. Lessons Learned

* Separate architecture from implementation.
* Verify assumptions with experiments instead of guessing.
* Print internal state when debugging.
* Memory and conversation serve different purposes.
* LLMs do not remember anything unless you provide context.

---

6. Result

v0.8.0 successfully introduced structured long-term memory and established the foundation for future intelligent memory extraction.


## v0.9 - Multi-Fact Memory Extraction


Version: v0.9.0
Date: 2026-06-29

Goal
----
The previous memory system could only extract a single fact from an entire user message.
If multiple facts were written together, only the first matching rule was saved.

Example:

"I like football. I can swim. I prefer tea."

Previous result:
✓ "I like football"

Lost:
✗ "I can swim"
✗ "I prefer tea"

The objective of this version was to redesign the extraction pipeline so one message could produce multiple structured memories.

Implementation
--------------
• Replaced extract_fact() with extract_facts().
• Extractor now returns List[dict] instead of a single dictionary.
• Added sentence splitting before extraction.
• Each sentence is checked independently against RULES.
• Matching sentences are converted into structured fact dictionaries.
• Multiple facts are returned together.
• main.py updated to iterate through extracted facts.
• Memory manager now stores each fact individually.
• ollama_client updated to build structured memory prompts from dictionaries instead of plain strings.

Architecture

User Message
      ↓
Sentence Splitter
      ↓
Sentence 1
Sentence 2
Sentence 3
      ↓
Rule Matching
      ↓
Fact Dictionaries
      ↓
Memory Storage
      ↓
Prompt Builder

Problems Encountered
--------------------
1.
The extractor initially returned a list while the rest of the pipeline still expected one dictionary.

This caused type errors.

2.
A nested list bug appeared because an entire list of facts was accidentally stored as a single fact.

Expected:

[
    fact,
    fact,
    fact
]

Actual:

[
    fact,
    [
        fact,
        fact
    ]
]

Debugging using pprint() and inspecting self.facts exposed the issue.

3.
Conversation history caused misleading memory tests.

Disabling conversation extension proved that the model itself has no persistent memory.

Only conversation history and extracted facts provide memory.

Lessons Learned
---------------
• Returning List[T] instead of T requires updating the entire pipeline.
• Debugging data structures is often easier than debugging code.
• Printing actual runtime objects is extremely valuable.
• Structured dictionaries are far easier to extend than plain strings.
• Sentence splitting should happen before semantic extraction.

Current Limitations
-------------------
• Sentence splitter still uses regex.
• Decimal numbers and abbreviations are not handled.
• Facts are not deduplicated.
• Compound sentences are not decomposed.
• Temporal information is not extracted.

Next Version (v0.10)
--------------------
• Duplicate detection.
• Better sentence parsing.
• Compound fact decomposition.
• Memory metadata.



##  v1.0 - Rule Based Memory Behavoir


1. Summary

Today JARVIS evolved from storing a single memory to extracting and managing multiple structured memories from one user message.

Major milestone:
- Introduced behavior-driven memory system.
- Memory logic is now controlled by RULES instead of hardcoded conditions.

---

2. Features Added

- Sentence splitter
- Multi-fact extraction
- Behavior field in rules
- append behavior
- replace behavior
- ignore behavior framework
- Cleaner MemoryManager architecture

---

3. Problems Encountered

- Nested list bug caused by passing the entire fact list into add_fact().
- Old memory format caused confusion during debugging.
- Mixed spelling of "behavior" and "behaviour".
- Forgot to restart Python after editing imported modules, causing old code to continue running.

---

4. Lessons Learned

- Follow the data, not assumptions.
- Print intermediate states when debugging.
- Python imports modules once per process.
- Small naming inconsistencies can waste hours.
- Behavior-driven architecture scales much better than hardcoded logic.

---

5. Current Status

v1.0 memory pipeline is operational.

User Message
      ↓
Sentence Splitter
      ↓
Fact Extractor
      ↓
Behavior Engine
      ↓
Memory Storage
      ↓
Prompt Builder
      ↓
LLM


## v1.1 - Recognize multiple natural language variation


1. Goal

Improve the rule system so one rule can recognize multiple natural language variations.

2. Changes

- Replaced `trigger` with `triggers`.
- Rules now support multiple phrases.
- Updated extractor to iterate over all triggers.
- Behavior is now stored inside rules and passed through extraction.
- Memory manager now follows the behavior specified by each extracted fact.

3. Discoveries

Pressure testing exposed architectural problems rather than programming bugs.

Examples:

- Current location vs permanent residence.
- Profession vs identity.
- Duplicate facts.
- Temporary vs permanent facts.
- Context-dependent facts.

The extractor performed well.

Most remaining issues are rule design problems rather than implementation bugs.

4. Lesson Learned

Extraction should remain simple.

Memory should become responsible for deciding whether facts are:

- appended
- replaced
- ignored
- merged

This keeps responsibilities separated and makes future improvements easier.


## v2.0.0 -

┌─────────────────────────────────────────────────────────────────────┐
│                           MAIN LOOP                                 │
│                                                                      │
│  1. add_message()                                                    │
│  2. extract_facts() ──────────────────────┐                         │
│  3. memory.store()  ◄─────────────────────┘                         │
│  4. memory.retrieve()                                                   │
│  5. prompt_builder.build()                                             │
│  6. context_manager.fit()                                              │
│  7. model.generate()                                                  │
│  8. add_message()                                                     │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MemoryManager                                 │
│                    (Orchestration Layer)                             │
│                                                                      │
│  • Behavior logic (append/replace/ignore/delete)                     │
│  • Coordinates Store + Retriever + Ranker                            │
│  • Callbacks                                                         │
└──────┬──────────────────┬──────────────────┬────────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ MemoryStore │   │  Retriever  │   │   Ranker    │
│             │   │             │   │             │
│ • CRUD      │   │ • Keywords  │   │ • Relevance │
│ • Persist   │   │ • Find      │   │ • Importance│
│ • Dirty     │   │ • Candidates│   │ • Frequency │
└─────────────┘   └─────────────┘   │ • Recency   │
                                     │ • Confidence│
                                     └─────────────┘


                                     JARVIS Development Log


The Problem With v1
v1 worked. But it had one structural flaw that made everything else worse: it sent every memory to the LLM on every turn. That meant the context window filled up fast, older conversation was trimmed silently, and you had no control over what the model actually "knew" in a given turn. Every new feature you could have added — ranking, confidence, importance — was blocked by this single design flaw. Retrieving before sending fixed all of those downstream.
The other issue was coupling. LlamaCppClient knew about facts. MemoryManager knew about conversation. There was no clear owner for anything. Fixing one thing broke another.
v2 was a full architectural redesign, not a feature release.

Session 1 — Defining the Interfaces
Decision made: Protocol classes for every subsystem boundary.
Before writing any implementation, we wrote the interfaces:
    • CandidateRetriever — finds memory candidates, no scoring
    • MemoryRanker — scores candidates, no retrieval
    • MemoryStore — persistence, no business logic
    • ModelClient — generates responses, no prompt assembly
    • ContextWindowManager — fits messages, no LLM knowledge
The guiding rule: every subsystem should expose one clean interface while hiding its implementation. This means you can swap KeywordRetriever for VectorRetriever without touching MemoryManager. You can swap the JSON store for SQLite without touching anything outside MemoryStore.
Decision made: Protocol, not ABC.
Python's Protocol (PEP 544) was chosen over ABC for the retriever and store interfaces. The reason: Protocol gives you structural subtyping — a class satisfies a protocol just by having the right methods, without inheriting anything. This makes testing with mocks trivially easy and means third-party classes (e.g., a ChromaDB wrapper) don't need to know about JARVIS's internal ABC hierarchy to be compatible.

Session 2 — Memory Redesign
Decision made: Separate MemoryStore, CandidateRetriever, MemoryRanker.
The v1 MemoryManager did everything: CRUD, persistence, retrieval, behavior logic. In v2, three separate classes own those responsibilities:
MemoryManager        — orchestrates, applies behavior rules
├── MemoryStore      — CRUD + JSON persistence
├── CandidateRetriever — finds candidate memories by keyword
└── MemoryRanker     — scores and ranks candidates
MemoryManager is the only class external code should import. The internals can be completely replaced.
Decision made: Retrieve BEFORE store, store BEFORE retrieve in main loop.
This was a subtle ordering bug in the initial v2 plan. The original flow was:
    1. Add user message
    2. Retrieve memories
    3. Extract and store facts
    4. Build prompt
This meant if you said "My name is Sajan," the fact was stored after the retrieval step. The model wouldn't know your name in the same turn you told it.
The fix — extract and store before retrieval — means newly introduced facts are immediately available for the current turn's context.
Decision made: Rich memory schema from day one.
v1 schema: {category, type, value, behavior}
v2 schema adds: id, created_at, updated_at, last_used, access_count, source, confidence, importance
The extra fields cost nothing now and enable memory ranking later. The schema is the contract between all subsystems. Changing it in v3 would require a migration. Better to design it right once.
Decision made: Separate created_at and updated_at timestamps.
A single timestamp field (v1 style) loses information the moment you update a memory. You can't tell "when did I first learn this" vs "when was this last corrected." v2 uses three timestamp fields:
    • created_at — immutable, set once
    • updated_at — mutable, set on every modification
    • last_used — mutable, set on retrieval

Session 3 — Ranking System
Decision made: Two-stage retrieval (candidates → rank).
The retriever's job is to find candidates cheaply (keyword overlap — O(n) scan). The ranker's job is to score candidates expensively using all available signals. The manager controls how many candidates to fetch (overshoot factor: 3x by default) so the ranker has enough to work with.
This pattern comes from information retrieval systems. The retriever is like a search index — fast but rough. The ranker is the reranker — slower but precise.
Decision made: Log scale for frequency scoring.
Linear frequency scoring would unfairly advantage memories that were retrieved many times early on. A memory accessed 100 times shouldn't score 10x higher than one accessed 10 times. Log scale (log(1+count) / log(1+scale)) keeps frequency relevant but bounded.
Ranking weights (v2.0 defaults): | Factor     | Weight | Rationale                              | |------------|--------|----------------------------------------| | Relevance  | 0.35   | Most important — is this about the topic? | | Importance | 0.25   | User-set or inferred significance       | | Confidence | 0.10   | How reliable is this fact?              | | Frequency  | 0.15   | Has this been useful before?            | | Recency    | 0.15   | Has this been accessed recently?        |
These are starting defaults. v2.x will expose them as config.

Session 4 — Context Window
Decision made: Trim in user/assistant PAIRS, not individual messages.
v1 trimmed the oldest individual messages. This could cut off a user message while keeping the assistant response that followed it, creating orphaned context that made no sense to the model.
v2 groups messages into logical pairs before trimming:
[user: "what's 2+2?", assistant: "4"] ← kept or dropped as a unit
This preserves conversational coherence. The model always sees complete exchanges.
Decision made: Real tokenizer with fallback chain.
Token counting via len(text) // 4 (v1) is wrong in two ways:
    1. Integer division gives 0 for short strings (4 chars or fewer)
    2. The ratio is inconsistent across languages, code, and special tokens
v2 token counting priority:
    1. tiktoken — most accurate for OpenAI-compatible models
    2. transformers — good for local Llama models (forced offline)
    3. Word-based estimation — int(words * 1.3) + 3
The get_token_counter() result is cached with @lru_cache so the tokenizer is loaded once per process.

Session 5 — Model Layer
Decision made: Score-based routing, not first-match.
v1 router checked keywords in order: if any code keyword was found, return CODE. This meant the routing result depended on which category was checked first — order bias.
v2 scores each category independently, then picks the highest. Ties are broken by a preference order (CODE > STEM > REASONING > GENERAL). The router also returns (ModelClient, TaskType) instead of just ModelClient so callers know which route was taken.
Decision made: Combine system prompt and memories into ONE system message.
Some local models handle multiple system messages inconsistently. By combining the base system prompt and the retrieved memory block into a single role: system message, we get consistent behavior across all backends.


session6 — Persistence & Dirty Tracking
Decision made: Dirty tracking on both MemoryStore and ConversationManager.
Writing to disk on every single operation is wasteful when batching is possible. Both storage components now track whether they have unsaved changes and expose save_if_dirty(). The main loop calls this on exit via _cleanup.
Decision made: save_on_every_message config flag.
When voice I/O is added (v3.1), the process might be interrupted mid-session by the OS or a crash. The save_on_every_message config flag lets users opt into eager saving at the cost of more I/O.

Known Issues / v2.0.1 Targets
Two bugs were found in the final v2.0 code that don't cause crashes but will cause incorrect behavior under specific conditions:
1. Dirty flag not set on direct memory mutation.
_handle_replace modifies a Memory object's fields directly (bypassing MemoryStore's CRUD methods) then calls self._store.save(). But save() is gated on _dirty, which was never set to True. The save silently skips.
touch() has the same issue — it modifies last_used and access_count directly, the store never knows.
Fix: add force_save() calls, or route mutations through the store, or add a mark_dirty() method and call it whenever a Memory object is mutated outside of store CRUD.
# In _handle_replace, replace:
self._store.save()
# With:
self._store.force_save()

# In retrieve(), after touch():
self._store.force_save()
2. DEFAULT_MODEL is an object, not a string.
# Current (wrong):
DEFAULT_MODEL = _DefaultModel()  # truthy object, not a string

# Used like:
model = DEFAULT_MODEL or "fallback"  # returns _DefaultModel, not string
LlamaCppClient(model=DEFAULT_MODEL)  # passes object to API
The _DefaultModel lazy accessor pattern is unnecessarily clever for a value that doesn't need to be lazy. main.py already does get_settings() at startup. The legacy compat property is the only thing that actually uses this, and it would be broken.
Fix: revert to DEFAULT_MODEL = get_settings().default_model (a plain string). Lazy settings loading is already handled by get_settings().

v1.0.0 — Initial Release
First working JARVIS: llama.cpp client, simple memory storage, rule-based fact extraction, single conversation file. Functional but context window was unbounded and all memories were sent on every turn.



## v2.1.0 - Multi-Backend + Streaming + External Config


1. The Problem With One Backend

v2.0 could only talk to llama.cpp. The model router was wired up but had nothing
to route to — every prompt went to the same model regardless of task type. The
router was doing real classification work (scoring keywords, breaking ties) and
producing results that were immediately discarded.

v2.1 gives the router something to actually do.


Decision: Factory Pattern for Model Instantiation

2. The naive approach: if backend == "ollama" scattered through main.py. The
problem: main.py would need to import both client classes, know their constructor
signatures, and handle ImportErrors for optional dependencies. Every new backend
adds more conditionals to a file that should only care about the conversation loop.

The factory moves all of that knowledge into one place:

pythondef create_client(config: ModelConfig) -> ModelClient:
    if config.backend == "ollama":
        return OllamaClient(...)
    return LlamaCppClient(...)

main.py calls create_client(cfg) and gets back a ModelClient. It has no
idea whether it's talking to llama.cpp or Ollama or anything else. When a third
backend is added, the factory gets one elif. Nothing else changes anywhere.

This is the ModelClient Protocol paying off for the first time. The Protocol
was defined in v2.0 without anything to demonstrate its value — now two different
implementations satisfy it and the rest of the system is blind to the difference.


Decision: stream and on_token as Named Parameters, Not **kwargs

The first instinct is to let streaming fall through **kwargs:

python# Tempting but wrong:
def generate(self, messages, **kwargs):
    self._client.chat.completions.create(model=self._model, messages=messages, **kwargs)

This breaks immediately: on_token is a JARVIS-internal callback. The OpenAI SDK
and Ollama SDK have never heard of it. Passing it through **kwargs causes an
API error before any streaming happens.

The fix is to make JARVIS-internal parameters explicit:

pythondef generate(self, messages, stream=False, on_token=None, **kwargs):
    # stream and on_token consumed here — never reach the API
    # **kwargs only carries legitimate API params: temperature, max_tokens, etc.

This pattern — separate your interface parameters from your passthrough parameters
— applies to every wrapper layer in this codebase. The context manager, the prompt
builder, the memory manager: each one has its own parameters and passes only what
its downstream dependency understands.


Decision: Callback over Generator for Streaming

Two architectural choices for streaming:

Callback: on_token(delta) called for each chunk. Caller provides the function.
Generator: yield delta from generate(). Caller iterates.

v2.1 chose callbacks. The reason: callbacks compose better with the existing
synchronous main loop. The caller doesn't need to restructure its control flow —
it just passes a function.

The trade-off: callbacks make it harder to stop generation mid-stream, buffer
output for processing, or pipe tokens into multiple destinations simultaneously.
When voice output arrives in v3.1, the callback will need to buffer tokens into
sentences before speaking them (you don't speak individual tokens). A generator
would make that buffering cleaner.

This is a future refactor, not a current problem. Document it here so the decision
to switch isn't a surprise.


Decision: YAML Config with Hardcoded Fallback

3. Three options for external configuration:


Environment variables — good for secrets, bad for structured model configs
JSON — no comments, hard to read
YAML — readable, supports comments, handles nested structure cleanly


YAML was chosen. config.yaml lives at the project root. Settings.load() reads
it if it exists; if not, hardcoded Python defaults apply. This means:


Existing setups with no config.yaml continue to work unchanged
New setups can configure everything without touching Python
config.yaml can be gitignored so personal model choices aren't in the repo


The ModelConfig(**mdata) pattern for loading each model deserializes YAML
dictionaries directly into dataclasses. Adding a new field to ModelConfig
requires adding it to the YAML schema — but existing config files without
the new field still load cleanly because Python uses the dataclass default.


Decision: Dynamic Router Initialization

4. v2.0's router had registrations hardcoded in main.py. Adding a new model meant
editing two files: config.yaml and main.py. This is a configuration problem
masquerading as a code problem.

v2.1 builds the router entirely from config:

pythonfor key, model_cfg in settings.models.items():
    client = create_client(model_cfg)
    task_type = TaskType(model_cfg.role)  # "code" → TaskType.CODE
    router.register(task_type, client)

TaskType(model_cfg.role) is the bridge between the human-readable YAML string
("code") and the type-safe enum (TaskType.CODE). If someone puts an invalid
role in config.yaml, this line raises a ValueError at startup — visible
immediately, not silently ignored.

Failed model loads (server offline, package not installed) are caught and logged
as warnings. One unavailable model doesn't prevent the others from loading.
JARVIS degrades gracefully instead of refusing to start.


5. Bugs Introduced in This Release

Four bugs were introduced and will be fixed in v2.1.1.

The common thread: all four come from the same root cause — code was written in
the correct shape but placed or connected incorrectly. The logic was right; the
wiring was wrong.

Settings.load() built the correct settings object but returned cls()
(fresh defaults) on the last line instead of settings. One word, total
information loss. JARVIS ran with hardcoded defaults throughout v2.1 regardless
of what config.yaml said.

LlamaCppClient streaming was written as an append to the existing
non-streaming method rather than a restructure. The new code landed after the
return statement. Python stops executing a function at return. The streaming
path was completely unreachable.

main.py router.route() unpacking was a regression from the v2.0.1 fix that
changed route() to return (ModelClient, TaskType). The new main.py assigned
the tuple to model and called model.generate(). Crash.

on_token kwarg leak was a consequence of the streaming restructure not
happening: with streaming code unreachable, on_token stayed in **kwargs and
was forwarded to the OpenAI SDK, which rejected it. Bugs 2 and 4 appeared as one
symptom — calling generate(stream=True) would hit an API error before ever
reaching the unreachable streaming code.


## v.2.2.0 - — Semantic Memory


Architecture Decision: ollama Package Scope

The ollama Python package was initially avoided entirely — Ollama speaks
OpenAI protocol for chat, making the package redundant for generation.

For embeddings the situation is different. ChromaDB's OllamaEmbeddingFunction
requires the ollama package internally. An attempt was made to replace it
with a custom _OllamaEmbeddings class using requests directly, which hit
three successive ChromaDB interface requirements:


name() method required on the embedding function object
embed_query() method required during collection query
Likely more undocumented requirements beyond those


ChromaDB's embedding interface is an internal protocol that changes between
versions. Chasing it with a custom class creates a maintenance liability.

Final decision: install ollama package for embeddings only.

Chat/generation  →  openai package  →  LlamaCppClient  →  llama-server + Ollama
Embeddings       →  ollama package  →  OllamaEmbeddingFunction  →  ChromaDB

Two packages, each doing what they were designed for. No overlap.

The Memory dataclass is mutable. Python sets __hash__ = None on mutable
dataclasses automatically. An early HybridRetriever implementation used
set(memories) for deduplication — this raises TypeError: unhashable type
at runtime. Fixed by deduplicating on memory.id (a plain string) instead.

ChromaDB Integration

ChromaDB selected as the persistent vector database.

Key configuration:


PersistentClient — vectors survive restarts, no manual save needed
hnsw:space: cosine — cosine distance (0.0 = identical, 2.0 = opposite)
is more appropriate for semantic similarity than default L2 distance
data/chroma/ persist directory — consistent with data/memories.json
convention, relative to project root


Metadata limitation discovered: ChromaDB metadata values must be
str | int | float | bool. Memory.to_dict() includes a metadata: {} field
which is a nested dict — ChromaDB rejects it silently or raises on insert.
Fixed by omitting the metadata field in _to_chroma_meta().
Memory.from_dict() defaults it to {} when missing, so reconstruction is lossless.

Collection conflicts: stale ChromaDB data from earlier failed experiments
conflicted with new collection configurations. Required rm -rf data/chroma
to reset. ChromaDB does not allow changing embedding function configuration
on an existing collection.

VectorRetriever

Implements CandidateRetriever Protocol. Drop-in replacement for
KeywordRetriever — one line change in MemoryManager.__init__.

The text embedded per memory is:

"{category} {memory_type}: {value}"

Richer than just the value alone — gives the embedding model category context
that improves similarity matching.

HybridRetriever

Combines KeywordRetriever and VectorRetriever. Runs both, deduplicates
by memory ID, passes union to MemoryRanker. Neither retriever alone is
sufficient:


Keyword: catches "what's my name?" → name: Sajan (exact match)
Vector: catches "what do I enjoy?" → I like coding (no keyword overlap)


ConversationVectorStore

Separate ChromaDB collection (jarvis-conversations) distinct from
jarvis-memories. Stores complete user/assistant exchanges rather than
extracted facts.

On first startup with existing conversation history: indexes all historical
exchanges. Subsequent startups: collection already populated, no re-indexing.

Retrieval limit: 2 exchanges per turn (conservative — each exchange can be
200+ tokens, rapidly consuming context budget).

Context Window Discovery

Stress testing with a long paragraph input revealed a critical interaction:


retrieval_limit: 20 memories × ~15 tokens each = ~300 tokens
5 past exchanges × ~200 tokens each = ~1000 tokens
System prompt + long user input consumed the remainder


Result: 97% context used before generation. Model received ~123 tokens for
its response — insufficient to produce anything. Response was empty string.

Fixed: retrieval_limit reduced to 5–8. Past exchange limit reduced to 2.
safety_margin increased from 150 to 300 tokens.

Prompt Builder Extension

PromptBuilder.build() extended with past_exchanges parameter.
Retrieved conversation history injected into system message before fact memory:

[system prompt]

## Relevant Past Exchanges
[semantically similar historical conversations]

## Known User Facts
[retrieved memory facts]

The ordering is intentional: episodic context (what we discussed) before
semantic facts (what is true about the user).


Agent Automation Experiment (Reverted)

Goal

Experiment with an internal development agent capable of:


Generating development logs and changelogs
Summarizing Git history
Analyzing project architecture
Reviewing code changes


Result

Reverted before completion.

Why It Failed

Core was not stable. The execution pipeline was still actively changing.
Adding an autonomous layer that operated on an unstable foundation created
circular debugging — it was unclear whether failures were in the agent, the
pipeline, or the tools.

Responsibilities merged incorrectly. The prototype mixed conversation logic,
routing, Git utilities, and agent orchestration in ways that blurred module
boundaries and increased coupling between components that should be independent.

No stable interface to automate. The agent was expected to generate
documentation for an architecture that was still being defined in the same
development cycle. The automation had no reliable target.

Multiple simultaneous failure points. Routing, model loading, Git tooling,
memory retrieval, and agent logic could all fail independently. Debugging
became exponentially harder with each new component added.


Stress Test Results

Input: long paragraph containing ~15 extractable facts.

[Memory] Stored: state → a civil engineering student at pokhara university in nepal
[Memory] Stored: name → sajan acharya
[Memory] Stored: job_title → civil engineering student at pokhara university in nepal
[Memory] Stored: state → currently running an intel i7 12th gen h processor
[Memory] Stored: state → facing right now is getting the intel arc gpu to accelerate
[Memory] Stored: like → first-principles explanations over surface-level tutorials
[Context] Retrieved 20 relevant memories
[History] Retrieved 5 relevant past exchange(s)
[Context] Trimmed 1 pairs (97% used)

Findings:


Fact extraction working correctly
Vector retrieval working (semantic matches found)
Conversation history indexed and retrieved
Context overflow caused empty response — retrieval limits too aggressive
Duplicate name fact stored (sajan acharya alongside existing sajan) —
deduplication not yet implemented


After reducing limits:

You: Hello JARVIS. What platform do I create content for? What GPU do I have?
     What were we debugging last time?
[Context] Retrieved 5 relevant memories
[History] Retrieved 2 relevant past exchange(s)

Jarvis: Platform: LearningHubSTEM — YouTube and Instagram education content
        for physics, chemistry, and mathematics students...
        GPU: Intel Arc A370M...
        Last debugging: GPU acceleration via SYCL/Vulkan on Arch Linux...

Semantic retrieval confirmed working. History retrieval confirmed working.


Lessons Learned


Stabilize core architecture before adding autonomous agents
Separate infrastructure from orchestration
Introduce one subsystem at a time and verify end-to-end before expanding
ChromaDB embedding function must be a class instance, not a plain callable
Mutable dataclasses are not hashable — never use set(dataclass_list)
Context budget is a finite resource — retrieval limits directly affect
whether the model has room to respond
The ollama package and OpenAI-compatible API serve different purposes;
using each for what it was designed for is cleaner than forcing one to do both



Current State

JARVIS v2.2.0 includes:


Hybrid memory retrieval (keyword + vector)
Semantic vector memory via ChromaDB
Local embedding generation via nomic-embed-text
Semantic conversation history storage and retrieval
ChromaDB persistence across restarts
Multi-model routing via ModelRouter (llama-server + Ollama)
Streaming responses
VS Code autocomplete via Continue.dev + qwen2.5-coder:1.5b


Next Milestone

Complete the memory deduplication system so duplicate facts (e.g., multiple
name entries) are consolidated rather than accumulated. Then proceed to v2.3.0
conversation summarization — wiring up the existing _summary field in
ConversationManager so trimmed conversation pairs are compressed rather than
permanently discarded.