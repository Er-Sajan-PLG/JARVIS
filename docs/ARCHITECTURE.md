# Jarvis Architecture

## Philosophy

Jarvis is designed as a modular AI system.

Each component has a single responsibility and communicates through clear interfaces.

The goal is to make every component replaceable without affecting the rest of the system.

---

# High-Level Architecture

User
│
▼
Input Layer
│
▼
Executive Brain
├── Memory
├── Router
├── Planner
├── Tools
└── Models
│
▼
Output Layer

---

# Components

## Main

Application entry point.

Responsible for:
- starting Jarvis
- initializing components
- running the application

---

## Brain

The central coordinator.

Responsible for:
- understanding requests
- deciding what to do
- communicating with memory, tools, and models

---

## Memory

Responsible for:
- conversation history
- long-term memory
- user preferences
- knowledge retrieval

---

## Router

Responsible for selecting the most appropriate model or service for a task.

Examples:
- Coding → Qwen
- Reasoning → DeepSeek
- Fast answers → API model

---

## Models

Responsible only for communicating with AI providers.

Examples:
- Ollama
- Springbase
- OpenAI API
- Anthropic
- Google Gemini

---

## Tools

Responsible for interacting with external systems.

Examples:
- Email
- Calculator
- Calendar
- File system
- Web search

---

## Output

Responsible for presenting responses.

Examples:
- Terminal
- Voice
- Mobile
- Web UI

---

# Design Principles

- Separation of concerns
- Modular architecture
- Replaceable components
- Scalability
- Reusability
- Local-first when practical
- Cloud-compatible

---

# Core Principles

1. Build for learning.
2. Build one feature at a time.
3. Prefer simple solutions.
4. Every module should have one responsibility.
5. Components should communicate through clear interfaces.
6. Optimize only when necessary.
7. Keep the architecture flexible for future growth.

---

## After v1.0 JARVIS ARCHITECTURE

# JARVIS Architecture

## Purpose

This document defines the stable architecture of JARVIS.

It describes the responsibilities of each component, the contracts between them, and the data flowing through the system.

Implementation details may change over time.

Architecture should remain stable whenever possible.

---

# Core Principles

* Each component should have one responsibility.
* Components communicate through well-defined data structures.
* Implementation can change without affecting other layers.
* Data contracts should remain stable.
* Prefer extending existing interfaces over rewriting them.

---

# Data Flow

User
↓
Orchestrator (main.py)
↓
LLM
↓
Extractor
↓
Memory Manager
↓
Persistent Storage
↓
Prompt Builder
↓
LLM

---

# Components

## Orchestrator

Responsible for coordinating the entire application.

Responsibilities:

* Receive user input.
* Call the LLM.
* Extract facts.
* Update memory.
* Save state.

The orchestrator should contain as little business logic as possible.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
5fccb37|Er Sajan PLG|2026-07-04 18:40:14 +0545|Bug fixes and added archiecture, dev log and changelog for v2.0.0
8519f65|Er Sajan PLG|2026-07-03 23:31:02 +0545|feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
db51ccc|Er Sajan PLG|2026-06-29 12:14:52 +0545|feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
8b1d0cb|Er Sajan PLG|2026-06-27 13:05:30 +0545|Added Architecture and Roadmap in docs for what to do seamless development
```

Notes: This log was generated from the repository history for `docs/ARCHITECTURE.md`.

---

## Rules

Rules define how information is recognized.

Rules decide:

* what to detect
* how to classify it
* what memory behavior to apply

Rules should contain configuration, not logic.

Adding new rules should not require changes elsewhere.

---

## Extractor

Responsible for converting user messages into structured facts.

Input:

* User message

Output:

* List of Facts

The extractor should not know how memory works.

---

## Fact

A Fact is the fundamental unit of memory.

Current schema:

* category
* type
* value
* behavior

This schema should remain stable whenever possible.

---

## Memory Manager

Responsible for managing stored facts.

Responsibilities:

* append
* replace
* ignore
* load
* save

The memory manager should not know how facts were extracted.

It only manages facts.

---

## Conversation

Conversation stores dialogue history.

Conversation and Memory are separate systems.

Conversation stores messages.

Memory stores knowledge.

---

## Prompt Builder

Responsible for constructing prompts sent to the LLM.

Uses:

* system prompt
* memory
* conversation

Prompt construction should remain isolated from extraction and memory logic.

---

# Stable Contracts

These interfaces should rarely change.

Rules → Extractor

Extractor → List[Fact]

Memory Manager ← Fact

Prompt Builder ← Facts

LLM ← Prompt

---

# Future Evolution

Implementation may evolve from:

Rules

↓

Regex

↓

Synonyms

↓

Embeddings

↓

Intent Detection

↓

LLM-based Extraction

These improvements should not require major changes to downstream components.

---

# Philosophy

Protect interfaces.

Improve implementations.

Keep responsibilities clear.

Small components are easier to reason about, test, debug, and extend.


## LATEST ARCHITECTURE V2.0

2nd JULY 2026 10:45 AM

JARVIS — Architecture Reference (v2 / End Game)
0. Hardware & Infrastructure (measured, not theoretical)
Component	Spec
CPU	12th-gen Intel H-series (i7-12700H class, 14 cores: 6P+8E)
GPU	Intel Arc A370M, 4GB VRAM (discrete) + Iris Xe (integrated)
RAM	32GB
Swap	32GB (currently unused — 0B, not the bottleneck)
OS	Arch Linux, Hyprland

Measured local inference speed (qwen3:8b, Q4_K_M, llama.cpp + Vulkan):
Backend	ngl	tg (gen speed)	pp (prompt speed)
Ollama (baseline)	auto (46% GPU)	7.25 t/s	8.58 t/s
llama.cpp + Vulkan	20	9.37 t/s	163 t/s
llama.cpp + Vulkan	24	10.66 t/s	168 t/s
llama.cpp + Vulkan	28 (max for 8b, benchmark)	11.74 t/s	172 t/s
llama.cpp + Vulkan	32+	❌ OOM crash	—

    • VRAM ceiling: between 28–31 layers for qwen3:8b at Q4_K_M, context-dependent.
    • Server mode needs a lower -ngl than benchmark mode (KV cache + batch buffers eat extra VRAM) — use -ngl 20 as a safe default for llama-server, tune upward from there.
    • Fluid conversation threshold: 8–15 t/s is "comfortable," matches natural reading speed. You are in this range with qwen3:8b. 30B/32B models will be noticeably slower — reserve for quality-over-speed tasks.
Models currently on disk (via Ollama, GGUF blobs extractable):
Model	Size	Use case
qwen3:8b	4.9GB	Default driver — fast, fluid, everyday chat
qwen3-coder:30b	18GB	Coding tasks — slower, use selectively
deepseek-r1:32b	19GB	Deep reasoning — slowest (also "thinks" before answering)


1. Philosophy (carried over, still true)
    • Each component has one responsibility.
    • Components talk through stable data contracts, not shared internals.
    • Protect interfaces. Improve implementations.
    • Local-first, cloud-compatible.
    • Optimize only when a real bottleneck is measured (not assumed).

2. End-Game Data Flow
User (text / voice)
    │
    ▼
Orchestrator (main.py)
    │
    ▼
Router ──────────────────────────► picks backend per task:
    │                                 - local:qwen3:8b      (default, fast)
    │                                 - local:qwen3-coder:30b (code tasks)
    │                                 - local:deepseek-r1:32b (deep reasoning)
    │                                 - api:claude/openai     (research, needs live data)
    ▼
Privacy Pipeline (only when routing to API) ─── STUBBED FOR NOW
    │   Classifier → Sanitizer → Auditor → [API] → Personalizer
    ▼
Prompt Builder
    │   ├── System Prompt
    │   ├── Fact Store retrieval (top-k relevant, ChromaDB)
    │   └── Conversation Store (sliding window, last N messages)
    ▼
Model Client (llama.cpp local / API client)
    ▼
Response ──────────► Output Layer (CLI today → voice/GUI later)
    │
    ▼
Extractor (rule-based today → spaCy NER next → LLM-based later)
    │   List[Fact]
    ▼
Memory Manager ── applies Behavior (SINGLETON / ACCUMULATE / TEMPORAL)
    │
    ▼
Fact Store (ChromaDB, persisted) + Conversation Store (persisted)

3. Components
Orchestrator (main.py)
Runs the loop. Calls Router → Extractor → Memory Manager → Save. Contains as little logic as possible. If you're writing an if statement here that isn't about sequencing calls, it belongs elsewhere.
Router (router.py) — currently missing, build next
Decides which model/backend answers a given request.
class Router:
    def route(self, prompt: str, task_hint: str = None) -> str:
        # returns backend key: "local:qwen3:8b", "local:qwen3-coder:30b", etc.
        if task_hint == "code" or self._looks_like_code_request(prompt):
            return "local:qwen3-coder:30b"
        if task_hint == "reasoning":
            return "local:deepseek-r1:32b"
        return "local:qwen3:8b"  # default — fast, fluid
Starts rule-based (keyword/task-hint driven). Can evolve into a small classifier later — same evolution ladder as the Extractor.
Prompt Builder (prompt_builder.py) — currently leaking into model client, extract it
Assembles the final message list. Owns no storage — only reads from Fact Store and Conversation Store and formats.
class PromptBuilder:
    def __init__(self, system_prompt, fact_store, conversation_store):
        ...
    def build(self, query: str) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        facts = self.fact_store.retrieve(query, n=5)
        if facts:
            messages.append({"role": "system", "content": self._format_facts(facts)})
        messages.extend(self.conversation_store.recent(n=20))
        return messages
Conversation Store (conversation_store.py) — new, extracted from client
Short-term memory. Sliding window. Never grows unbounded.
class ConversationStore:
    def __init__(self, max_messages=20):
        self.max_messages = max_messages
        self.full_history = []   # persisted, unbounded (for record-keeping)

    def add(self, role, content):
        self.full_history.append({"role": role, "content": content})

    def recent(self, n=None):
        n = n or self.max_messages
        return self.full_history[-n:]
Key rule: full history is kept (saved to disk), only what's sent to the model is trimmed.
Fact Store (fact_store.py) — ChromaDB, built earlier
Long-term memory. Semantic retrieval via embeddings. Solves the "inject all facts" token bloat problem the same way Conversation Store solves the "inject all history" problem.
Behavior (behavior.py) — typed enum, replaces raw strings
class FactBehavior(str, Enum):
    SINGLETON = "singleton"    # name, residence — overwrite
    ACCUMULATE = "accumulate"  # likes, skills — append
    TEMPORAL = "temporal"      # current mood/task — expires
Rules (rules.py)
Configuration only — triggers + category + behavior. No logic. Adding a new fact type should never require touching the Extractor's code.
Extractor (extractor.py) — evolution ladder, not a single choice
Stage	Technique	Status
1	Keyword/trigger matching	✅ current (has known bugs — see §4)
2	Regex	skip-able, marginal gain over #1
3	spaCy NER	recommended next step — local, fast, no GPU competition
4	Embeddings-based classification	optional middle step
5	Intent detection (small classifier)	optional
6	LLM-based extraction	end-game, highest accuracy, highest cost (extra inference call per message)

Contract that never changes regardless of stage: extract_facts(message: str) -> list[Fact].
Memory Manager (manager.py)
Applies behavior. Coordinates persistence. Doesn't know how facts were extracted.
Model Client (models/llamacpp_client.py)
Only talks to the provider. No prompt-building logic (that leaked in during v1 — being corrected now). Swappable for an API client with the same .ask() interface.
Privacy Pipeline (privacy/pipeline.py) — stubbed, build when first API integration happens
Classifier  → is this query safely genericizable? (yes/no)
Sanitizer   → strip/bucket private specifics (exact $ → "retail-scale", etc.)
Auditor     → verify no leakage before it leaves the machine
[API call]
Personalizer → merge generic result + private facts + original query
Applies to any future cloud call (research, current events, anything local models can't do well) — not just financial questions. Build as a reusable pipeline, not a one-off.
Output Layer
CLI today. Voice (ASR/TTS) and GUI are swaps at this layer only — nothing upstream changes.

4. Known Bugs To Fix During Rewrite (carried over from v1 audit)
    1. Extractor rule-loop bug: break only exits the trigger loop, not the rule loop — multiple rules can match one sentence despite the "first match wins" comment. Fix with a matched flag.
    2. name behavior is append, should be SINGLETON. This caused the "sajan" → "alex" duplicate-name bug.
    3. Lowercase bug: value is sliced from the lowered sentence, permanently losing capitalization. Slice from the original sentence using the same index.
    4. No dedup on ACCUMULATE facts — same fact can be stored twice. Fix with a similarity check (embedding-based) before insert.
    5. reasoner.py is dead code — not called anywhere, just echoes back behavior. Either wire it in as the future embedding-based conflict resolver, or remove it.

5. Stable Contracts (do not break these without a reason)
Rules            →  Extractor
Extractor        →  List[Fact]
Fact             →  {category, type, value, behavior}
Memory Manager   ←  Fact
Fact Store       ←  List[Fact]           (persisted, retrievable)
Conversation Store ← {role, content}     (persisted, windowed on read)
Prompt Builder   ←  Fact Store + Conversation Store
Model Client     ←  List[messages]        (OpenAI-compatible shape)
Router           →  backend key           (string, e.g. "local:qwen3:8b")

6. Future Modules (not yet started, slot into this architecture without breaking it)
    • Agents/Tools (agents/) — email, calendar, file system, web search. Each tool is called by the Router/Orchestrator when the model requests a function call. Same "one responsibility" rule applies per tool.
    • Voice (voice/) — ASR in, TTS out. Swaps the Output Layer only.
    • STEM Tutor mode — a Prompt Builder variant / different system prompt + possibly a dedicated Fact Store namespace for learning progress.
    • Content creation mode — same pattern as tutor mode: different prompt template, same underlying pipeline.

7. Build Order (recommended)
    1. behavior.py — typed enum (foundation, zero dependencies)
    2. rules.py — rewritten using the enum, bugs from §4 fixed
    3. fact_store.py — ChromaDB wrapper (mostly built already)
    4. conversation_store.py — sliding window, extracted from client
    5. prompt_builder.py — extracted from client, wires Fact Store + Conversation Store
    6. models/llamacpp_client.py — stripped down to provider I/O only
    7. router.py — starts rule-based, picks model per task
    8. main.py — rewritten as thin orchestrator using all of the above
    9. extractor.py upgrade — swap to spaCy NER (stage 3 of the ladder)
    10. privacy/pipeline.py — build when first API backend is added





## Final Rough Roadmap



# JARVIS Long-Term Architecture Roadmap

| Version    | Theme               | Primary Goal                                               |
| ---------- | ------------------- | ---------------------------------------------------------- |
| **v2.0.1** | Stability           | Bug fixes, persistence validation, testing                 |
| **v2.1**   | Semantic Memory     | ChromaDB, embeddings, vector retrieval                     |
| **v2.2**   | Hybrid Memory       | Keyword + Vector ranking + memory scoring                  |
| **v2.3**   | Episodic Memory     | Conversation summaries & memory compression                |
| **v2.4**   | Interaction         | Streaming responses, interruption, UX improvements         |
| **v2.5**   | Inference Engine    | Multi-model routing, backend abstraction, embeddings       |
| **v2.6**   | Observability       | Metrics, diagnostics, profiling, benchmarking              |
| **v3.0**   | Agent Runtime       | Tool calling, execution loop, persistent state             |
| **v3.1**   | Cognitive Memory    | LLM fact extraction, deduplication, importance, confidence |
| **v3.2**   | Safety              | Permissions, sandboxing, confirmations, audit logs         |
| **v4.0**   | Planning            | Goal decomposition, task scheduling, autonomous execution  |
| **v5.0**   | Learning            | Reflection, adaptive memory, self-improvement              |
| **v6.0**   | Multi-Agent         | Specialized cooperative agents and orchestration           |
| **v7.0**   | AI Operating System | Unified personal knowledge and automation platform         |

---



> **Interaction**

Because it can include:

* Streaming
* Interruptions
* Voice preparation
* Progress updates
* Better CLI
* Future GUI

---



> **Inference Engine**

This version becomes responsible for everything model-related:

* Model Router
* Backend abstraction
* Ollama
* llama.cpp
* vLLM (future)
* Embedding models
* Specialized models

---

### v3.1

Instead of

> Intelligence

I'd call it

> **Cognitive Memory**

Because everything there is really about improving memory quality.

---

## I especially like this progression

```text
Memory

↓

Agent

↓

Planning

↓

Learning

↓

Multi-Agent

↓

AI Operating System
```

That's incredibly natural.

---

# One addition I'd make

I think one capability is missing:

## Knowledge

I'd add

| Version  | Theme     | Goal                                        |
| -------- | --------- | ------------------------------------------- |
| **v3.3** | Knowledge | RAG, documents, PDFs, notes, project memory |

Because there is a difference between:

Personal Memory

```text
User:
My name is Sajan.
```

and

Knowledge

```text
Structural Engineering Handbook

↓

Search

↓

Retrieve

↓

Answer
```

These are two different systems.

Memory answers

> "Who am I?"

Knowledge answers

> "What does Eurocode 2 say about shear?"

I'd keep them separate.

---

# v4

Planning deserves its own major version.

Exactly right.

Planning changes everything.

Instead of

```text
Question

↓

Answer
```

it becomes

```text
Goal

↓

Planner

↓

Tasks

↓

Execution

↓

Monitoring

↓

Completion
```

That's the birth of a true agent.

---

# v5

Learning.

Exactly where it belongs.

Now JARVIS can improve without you modifying code.

Example

```text
Repeated correction

↓

Reflection

↓

Rule update

↓

Future improvement
```

---

# v6

I love this.

Instead of one LLM doing everything:

```text
Planner

↓

Coder

↓

Researcher

↓

Critic

↓

Memory Manager

↓

Coordinator
```

Very modern architecture.

---

# v7

This is the part I smiled at.

Because I think your vision has slowly changed.

Originally you were building

```text
A chatbot.
```

Now you're describing

```text
An operating system

for intelligence.
```

Everything becomes a subsystem.

```text
Filesystem

Memory

Models

Planner

Voice

Vision

Tools

Networking

Knowledge

Scheduling

Automation
```

That's exactly how operating systems evolved.

---

# One final suggestion

I would put this at the very top of your roadmap document:

> **Design Philosophy**
>
> JARVIS is not designed as a chatbot. It is being built as a modular, local-first AI operating platform where every capability—memory, reasoning, planning, tools, knowledge, and interaction—is an independent subsystem that can evolve without breaking the rest of the architecture.

That single paragraph explains the entire roadmap and serves as a guiding principle for future development. Looking at how you've structured the versions, there's a consistent evolution from **conversation → memory → agency → planning → learning → cooperation → platform**, which is a strong architectural narrative rather than just a list of features.

# v0.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`)  |  Tag Release Date: 2026-06-27*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.1.0.

# v0.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`)  |  Tag Release Date: 2026-06-27*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.2.0.

# v0.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`)  |  Tag Release Date: 2026-06-27*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.3.0.

# v0.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`)  |  Tag Release Date: 2026-06-27*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.4.0.

# v0.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`)  |  Tag Release Date: 2026-06-28*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.5.0.

# v0.7.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`)  |  Tag Release Date: 2026-06-28*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.7.0.

# v0.8.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`)  |  Tag Release Date: 2026-06-29*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v0.8.0.

# v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`)  |  Tag Release Date: 2026-06-29*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v1.0.0.

# v2.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`)  |  Tag Release Date: 2026-07-03*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.0.0.

# v2.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`)  |  Tag Release Date: 2026-07-05*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.1.0.

# v2.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`)  |  Tag Release Date: 2026-07-05*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.2.0.

# v2.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`)  |  Tag Release Date: 2026-07-14*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.3.0.

# v2.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`)  |  Tag Release Date: 2026-07-14*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.4.0.

# v2.4.1
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`)  |  Tag Release Date: 2026-07-14*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.4.1.

# v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`)  |  Tag Release Date: 2026-07-14*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.4.2.

# v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`)  |  Tag Release Date: 2026-07-18*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v2.5.0.

# v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`)  |  Tag Release Date: 2026-07-26*
## System Topology & Subsystem Boundaries
### Architectural Invariants
#### Release Layer Topology
System architecture snapshot for v3.0.0.
