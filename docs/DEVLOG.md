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