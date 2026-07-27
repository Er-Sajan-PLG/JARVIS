# Development Log

## v3.0.0 Refactored
- **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`ec0dc4e`) \| Tag Release Date: 2026-07-28*
- **Feature Commit Date**: 2026-07-28 (`c5a97b4` - `ec0dc4e`)
- **Tag Release Date**: 2026-07-28
### Why This Release Existed
JARVIS had accumulated architectural technical debt across multiple iterations: domain objects were coupled with database/web schemas, third-party libraries (ChromaDB, PaddleOCR) were directly invoked inside business logic, model routing lacked automated failover for rate limits (429) and provider outages (503), tool execution lacked safety policies for destructive filesystem/shell operations, and startup lacked a single dependency container.

### What Changed and Why
#### Pure Domain Layer (`app/domain/`)
Separated core entities (`ContentSource`, `MemoryRecord`, `ExecutionPlan`, `SessionState`, `SafetyTier`) into 100% pure Python 3.11+ dataclasses without framework, database, or vendor imports.

#### Composition Root (`app/bootstrap.py`)
Built `ApplicationContainer` dependency injection container to assemble all singletons, event buses, resource managers, and cognitive services in a single composition root.

#### Cognitive Brain Engine (`app/brain/`)
Modularized request processing into direct async execution loops: `IntentAnalyzer` (prompt classification), `TaskPlanner` (plan generation), `ExecutionRunner` (step execution with `@safety_gate` evaluation), and `ResponseSynthesizer` (output formatting).

#### Tiered Tool Safety Policy & Guardrails (`app/guardrails/`)
Built `ToolSafetyPolicy` and `@safety_gate` decorators categorizing operations into `SAFE` (auto-pass), `SENSITIVE` (policy-checked), and `DESTRUCTIVE` (mandatory Human-In-The-Loop approval gate).

#### Multi-Provider LLM Pool & Circuit Breaker (`app/models/` & `app/resources/`)
Built `ResourceManager` with `ProviderHealthMonitor` tracking RPM/TPM token budgets and 3-state circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`). Updated `ModelRouter` to automatically failover from failing providers to healthy fallback providers on 429/503 errors.

#### Memory Façade (`app/memory/`)
Built `MemoryService` as a domain-pure façade hiding ChromaDB vector and BM25 keyword search engines.

#### I/O Protocol Adapters (`app/adapters/`) & OSS Integrations (`app/integrations/`)
Created `app/adapters/` for REST HTTP routes, WebSocket / SSE streaming, and Bearer token API key security. Created `app/integrations/` to isolate ChromaDB vector stores and PaddleOCR backends.

### Key Architectural Decisions
- Decision: Use direct async interface calls for core cognitive orchestration loops while using `InMemoryAsyncBus` for passive telemetry logging.
  Why: Eliminates async event loop polling latency in linear request-reply execution chains while preserving clean telemetry decoupling.
- Decision: Enforce `@safety_gate` decorators with pause-and-resume `AWAITING_APPROVAL` states on all `DESTRUCTIVE` tools.
  Why: Prevents autonomous agent execution from performing unauthorized file deletions or system commands.

---

## v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`) \| Tag Release Date: 2026-07-26*
- **Feature Commit Dates**: 2026-07-19 (RAG Subsystem `e35d468`-`ba2026f`) | 2026-07-26 (Catalog Expansion `81e45f0`)
- **Tag Release Date**: 2026-07-26
### Why This Release Existed
JARVIS needed multi-provider scaling across cloud APIs (Google AI Studio, Groq, Cerebras, SambaNova, OpenRouter) and local runtimes, alongside a dedicated RAG / Knowledge retrieval subsystem for PDF research papers and OCR document ingestion.

### What Changed and Why
#### Live Provider Catalog
Added dynamic provider discovery and catalog management supporting cloud LLM providers alongside local Ollama/llama.cpp engines.

#### RAG & Knowledge Subsystem
Scaffolded PDF document extraction, text chunking, vector embedding, OCR service backends (PaddleOCR, UnlimitedOCR), and citation-grounded answer generation (`Steps 1-9`).

#### Web UI Enhancements
Added Research Papers tab, live catalog provider selection, and model status indicators in `frontend/`.

---

## v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`) \| Tag Release Date: 2026-07-18*
- **Feature Commit Date**: 2026-07-18 (`f9fa068`)
- **Tag Release Date**: 2026-07-18
### Why This Release Existed
The project had broadened its feature set but still relied on CLI-driven flows and brittle startup behavior. This release was a stabilization pivot: build a browser entrypoint, make model selection config-driven, and stop silent failures from corrupt memory and misconfigured backends.

### What Changed and Why
#### Web Interface
Added a FastAPI server and browser UI so chat, conversation management, attachment uploads, and memory inspection could be handled over HTTP. This separated UI concerns from the core pipeline and made state easier to inspect.

#### Model Routing
Centralized startup discovery and model profile loading so local Ollama, llama.cpp, Google, and OpenRouter options could be selected at runtime. The new approach replaces brittle hardcoded paths with configuration-driven backend choice.

#### Error and State Safety
Quarantined invalid memory records and improved error handling during generation and attachment operations. The goal was to preserve usable state rather than aborting on malformed storage.

#### Developer Tooling
Added git hooks, a version bump script, and regression tests around memory, conversation, context, and routing. This gives contributors a safer path for making changes to the core runtime.

### Architecture
The FastAPI backend now sits between the frontend and the existing runtime pipeline, turning UI requests into the same chat and memory operations the CLI previously drove. Startup now resolves backend profiles before the runtime begins model routing.

### Key Decisions
Decision: Treat corrupt memory files as quarantine candidates instead of fatal startup errors.
Why: Users should not lose the entire session because of one malformed record.
Trade-off: The app now needs explicit recovery behavior rather than assuming storage is always valid.

Decision: Expose model backend selection through configuration, not code.
Why: This makes adding or switching providers faster and safer for contributors.
Trade-off: Startup complexity increased because discovery must handle both local and cloud backend variants.

### What This Enables
This release makes it practical to continue adding UI-driven features, attachments, and new model providers without rewriting the runtime architecture.

## v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`) \| Tag Release Date: 2026-07-14*
- **Feature Commit Date**: 2026-07-14 (`6034224`)
- **Tag Release Date**: 2026-07-14
### Why This Release Existed
Local backend configuration was still awkward and opaque for users. The release was a small polish to make runtime model definitions easier to express and to expose release metadata in code.

### What Changed and Why
Added explicit release metadata support so the application can read version information at runtime. Added Ollama Modelfile support to let local model definitions live in a standard file instead of being configured implicitly.

### What This Enables
This work reduces friction for local Ollama setups and makes version tracking available to the application itself.

## v2.4.1
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`) \| Tag Release Date: 2026-07-14*
- **Feature Commit Date**: 2026-07-13 (`1cab1b1`)
- **Tag Release Date**: 2026-07-14
### Why This Release Existed
The system had grown enough that contributors needed clearer architecture documentation. This release was about making the existing design visible instead of changing behavior.

### What Changed and Why
Published architecture documentation with diagrams for agents, memory, model interactions, and startup flow. Updated memory schema documentation so the guide matched the implemented design.

### What This Enables
New contributors can understand the repository structure and system boundaries without reading the full codebase first.

## v2.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`) \| Tag Release Date: 2026-07-14*
- **Feature Commit Date**: 2026-07-11 (`6ea9796`)
- **Tag Release Date**: 2026-07-14
### Why This Release Existed
Model backend support was inconsistent and the documentation set did not map to the project’s platform aspirations. This release was about making backends pluggable and capturing project knowledge in docs.

### What Changed and Why
#### Model Routing
Added OpenRouter support and a provider abstraction so cloud and local backends could coexist behind a single runtime switcher. This avoids provider-specific startup hacks and keeps backend selection consistent.

#### Configuration
Moved backend definitions into `config.yaml` and made runtime profile switching the default. This separates deployment configuration from application code.

#### Documentation Platform
Published a broad set of docs for API, configuration, database, memory, tools, and startup flow. That work was meant to prevent future changes from being hidden in code alone.

### Architecture
A new backend router abstraction now mediates between configured profiles and live model clients. The runtime no longer assumes a single provider type at startup.

### Key Decisions
Decision: Use a router abstraction for model backends.
Why: It makes adding new providers easier and keeps runtime code consistent.
Trade-off: It adds an extra layer between model selection and model execution.

### What This Enables
The project can now add additional backends and deployment targets without changing the core chat flow.

## v2.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`) \| Tag Release Date: 2026-07-14*
- **Feature Commit Date**: 2026-07-06 (`c84d53b`)
- **Tag Release Date**: 2026-07-14
### Why This Release Existed
The assistant could describe actions but not execute them reliably in the repository. This release created the bridge between generated instructions and actual file/git operations.

### What Changed and Why
#### Agent Loop
Added a DocumentationAgent and a tool execution framework so the agent can invoke concrete actions rather than only producing text output.

#### Tool Infrastructure
Added file and git tools to support repository-aware automation tasks. This makes document generation and repo changes reproducible.

#### Runtime Wiring
Updated the main runtime to integrate agent execution with the application flow, so the agent can participate in live operations.

### What This Enables
This release enables repository-aware automation and the ability to safely extend the system with action-capable agents.

## v2.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`) \| Tag Release Date: 2026-07-05*
- **Feature Commit Date**: 2026-07-05 (`b2c2211`)
- **Tag Release Date**: 2026-07-05
### Why This Release Existed
Keyword-based retrieval was not enough for long-term memory recall. The release was driven by the need to surface semantically related past exchanges in new conversations.

### What Changed and Why
#### Memory Layer
Added a conversation store, vector retriever, and hybrid retriever so the system can combine semantic search with keyword candidates. This avoids over-relying on exact text matches.

#### Prompt Pipeline
Integrated embedding-backed retrieval into the chat flow so each turn can use both recent context and semantically similar memory.

### Key Decisions
Decision: Blend embeddings with keyword retrieval.
Why: It improves recall while still preserving precise matches.
Trade-off: The retrieval path became more complex and required multiple memory components.

### What This Enables
The system can now use stored memory more intelligently, making past conversations relevant again.

## v2.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`) \| Tag Release Date: 2026-07-05*
- **Feature Commit Date**: 2026-07-04 (`5fccb37`) - 2026-07-05 (`df45be2`)
- **Tag Release Date**: 2026-07-05
### Why This Release Existed
The application was still tied to a narrow set of backend startup assumptions. This release externalized backend configuration and added runtime discovery so the system could operate in more deployment environments.

### What Changed and Why
#### Backend Configuration
Added a model factory and support for local/cloud backend instantiation from configuration. This separates backend creation from the core application logic.

#### Runtime Discovery
Added server management utilities to find live llama.cpp processes and expose them as available runtime options.

### What This Enables
The project can now support a wider range of local and cloud model setups without code changes.

## v2.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`) \| Tag Release Date: 2026-07-03*
- **Feature Commit Date**: 2026-07-02 (`63addf6`) - 2026-07-03 (`8519f65`)
- **Tag Release Date**: 2026-07-03
### Why This Release Existed
The codebase had become a monolithic prototype with tangled memory, context, and routing. This release was a deliberate rewrite to make behavior explicit and maintainable.

### What Changed and Why
#### Core Pipeline
Decomposed the main loop into extraction, storage, retrieval, ranking, and prompt assembly. This makes each stage easier to reason about and change independently.

#### Memory Design
Split memory responsibilities into store, retriever, and ranker components. Added immutable `created_at` and mutable `updated_at` metadata so records could be audited correctly.

#### Model Routing
Moved from first-match keyword routing to score-based classification to reduce bias and make backend selection more predictable.

#### Infrastructure
Added strict offline startup handling and real token counting to avoid runtime surprises from missing model resources.

### Architecture
The new flow now reads: extract facts, store them, retrieve candidates, rank them, build the prompt, then generate. That explicit pipeline replaced the older ad hoc state machine.

### Key Decisions
Decision: Enforce offline-safe startup.
Why: Network-dependent startup caused unpredictability during development.
Trade-off: Some remote model paths required explicit configuration.

Decision: Adopt immutable creation timestamps.
Why: It makes memory history reliable when facts are rewritten or updated.
Trade-off: The persistence format and migration path became more complex.

### What This Enables
The release set a foundation for later memory, retrieval, and multi-backend work by making the core runtime modular.

## v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`) \| Tag Release Date: 2026-06-29*
- **Feature Commit Date**: 2026-06-29 (`2922129` - `6316917`)
- **Tag Release Date**: 2026-06-29
### Why This Release Existed
The project needed a stable memory engine capable of recognizing multiple memory triggers and acting on them.

### What Changed and Why
Added multi-trigger memory extraction and behavior-based memory actions so the assistant could store facts from varied input and treat them differently based on intent.

### What This Enables
This work made the system’s memory behavior more flexible and paved the way for richer, long-term state tracking.

## v0.8.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`) \| Tag Release Date: 2026-06-29*
- **Feature Commit Date**: 2026-06-29 (`d43f6e9`)
- **Tag Release Date**: 2026-06-29
### Why This Release Existed
The early memory flow was too ad hoc and needed a consistent processing pipeline.

### What Changed and Why
Introduced a structured memory pipeline so facts could move through a repeatable, predictable lifecycle.

### What This Enables
This created a stable foundation for later retrieval and ranking improvements.

## v0.7.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`) \| Tag Release Date: 2026-06-28*
- **Feature Commit Date**: 2026-06-28 (`7a840ee` - `7803a93`)
- **Tag Release Date**: 2026-06-28
### Why This Release Existed
The assistant needed better context assembly from prior conversations.

### What Changed and Why
Added a context builder and long-term memory integration so the prompt construction could include earlier relevant information more reliably.

### What This Enables
This made conversation state more coherent across turns.

## v0.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`) \| Tag Release Date: 2026-06-28*
- **Feature Commit Date**: 2026-06-28 (`94e1956` - `4034bf7`)
- **Tag Release Date**: 2026-06-28
### Why This Release Existed
The system needed to keep memory and conversations across sessions.

### What Changed and Why
Added persistent memory core and conversation storage so state could survive restarts.

### What This Enables
This enabled session persistence and longer-running assistant usage.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
c84d53b|Er Sajan PLG|2026-07-06 06:13:31 +0545|feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
b2c2211|Er Sajan PLG|2026-07-05 22:01:06 +0545|Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
df45be2|Er Sajan PLG|2026-07-05 07:23:59 +0545|Multi-Backend + Streaming + External Config
5fccb37|Er Sajan PLG|2026-07-04 18:40:14 +0545|Bug fixes and added archiecture, dev log and changelog for v2.0.0
db51ccc|Er Sajan PLG|2026-06-29 12:14:52 +0545|feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
4f71baf|Er Sajan PLG|2026-06-29 08:56:24 +0545|feat(memory): implement behavior-driven memory engine and multi-fact extraction
2922129|Er Sajan PLG|2026-06-29 07:02:35 +0545|feat(memory): implement multi-fact extraction pipeline
d43f6e9|Er Sajan PLG|2026-06-29 03:50:36 +0545|feat(v0.8): implement structured memory pipeline
7803a93|Er Sajan PLG|2026-06-28 22:50:49 +0545|Context Builder & Long-Term Memory Integration
9aa2fb2|Er Sajan PLG|2026-06-28 16:23:10 +0545|JARVIS MEMORY SEPARATION FROM CONVERSATION ANDFACTS
4034bf7|Er Sajan PLG|2026-06-28 04:52:42 +0545|Persistent Memory Core
ded44b9|Er Sajan PLG|2026-06-27 04:59:01 +0545|v0.2: working CLI chat loop with Ollama integration
e13ee67|Er Sajan PLG|2026-06-27 03:25:01 +0545|Build Jarvis v0.1: Connect to Ollama
1999e53|Er Sajan PLG|2026-06-27 02:44:04 +0545|Initial project structure
```

Notes: This log was generated from the repository history for `docs/DEVLOG.md`.

## v0.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`) \| Tag Release Date: 2026-06-27*
- **Feature Commit Date**: 2026-06-27 (`39b3d5b` - `e5c6fd6`)
- **Tag Release Date**: 2026-06-27
### Why This Release Existed
Assistant behavior was inconsistent because system prompts were not managed explicitly.

### What Changed and Why
Added system prompt architecture to make the assistant’s base behavior more explicit in the message flow.

### What This Enables
This improved consistency across generated responses.

## v0.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`) \| Tag Release Date: 2026-06-27*
- **Feature Commit Date**: 2026-06-27 (`163f8a1` - `8b1d0cb`)
- **Tag Release Date**: 2026-06-27
### Why This Release Existed
The project needed an explicit direction before more features were added.

### What Changed and Why
Added architecture and roadmap documentation to clarify what the project should do next and how its components fit together.

### What This Enables
This guided future development and aligned contributors on the overall design.

## v0.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`) \| Tag Release Date: 2026-06-27*
- **Feature Commit Date**: 2026-06-27 (`ded44b9`)
- **Tag Release Date**: 2026-06-27
### Why This Release Existed
The earliest prototype needed a working interactive interface.

### What Changed and Why
Delivered a CLI chat loop with Ollama integration so the assistant became usable in practice.

### What This Enables
This turned the project from an idea into a working conversational system.

## v0.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`) \| Tag Release Date: 2026-06-27*
- **Feature Commit Date**: 2026-06-27 (`1999e53` - `e13ee67`)
- **Tag Release Date**: 2026-06-27
### Why This Release Existed
The first step was to connect the assistant to a model backend.

### What Changed and Why
Built the initial Ollama-backed foundation and project scaffolding.

### What This Enables
This provided the minimal runtime for future development.

# v0.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`) \| Tag Release Date: 2026-06-27*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `1999e53` Implementation Details
```text
Initial project structure
```
#### `e13ee67` Implementation Details
```text
Build Jarvis v0.1: Connect to Ollama
```
#### `e13ee67` Implementation Details
```text
Build Jarvis v0.1: Connect to Ollama
```

# v0.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`) \| Tag Release Date: 2026-06-27*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `ded44b9` Implementation Details
```text
v0.2: working CLI chat loop with Ollama integration
```
#### `ded44b9` Implementation Details
```text
v0.2: working CLI chat loop with Ollama integration
```

# v0.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`) \| Tag Release Date: 2026-06-27*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `163f8a1` Implementation Details
```text
Add .gitignore for Python project
```
#### `163f8a1` Implementation Details
```text
Add .gitignore for Python project
```
#### `8b1d0cb` Implementation Details
```text
Added Architecture and Roadmap in docs for what to do seamless development
```
#### `8b1d0cb` Implementation Details
```text
Added Architecture and Roadmap in docs for what to do seamless development
```

# v0.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`) \| Tag Release Date: 2026-06-27*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `39b3d5b` Implementation Details
```text
Making prompt
```
#### `39b3d5b` Implementation Details
```text
Making prompt
```
#### `7491e9a` Implementation Details
```text
prompt failure, prompts to prompt
```
#### `7491e9a` Implementation Details
```text
prompt failure, prompts to prompt
```
#### `e5c6fd6` Implementation Details
```text
added SYSTEM_PROMPT in messege
```
#### `e5c6fd6` Implementation Details
```text
added SYSTEM_PROMPT in messege
```

# v0.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`) \| Tag Release Date: 2026-06-28*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `94e1956` Implementation Details
```text
Implement conversation history in OllamaClient
```
#### `94e1956` Implementation Details
```text
Implement conversation history in OllamaClient
```
#### `3cc9e4b` Implementation Details
```text
change model from deepseek r1:32b to qwen3:8b for faster development
```
#### `3cc9e4b` Implementation Details
```text
change model from deepseek r1:32b to qwen3:8b for faster development
```
#### `4034bf7` Implementation Details
```text
Persistent Memory Core
```
#### `4034bf7` Implementation Details
```text
Persistent Memory Core
```

# v0.7.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`) \| Tag Release Date: 2026-06-28*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `7a840ee` Implementation Details
```text
Save Fact based on preferences
```
#### `7a840ee` Implementation Details
```text
Save Fact based on preferences
```
#### `b145614` Implementation Details
```text
Fact Extraction
```
#### `b145614` Implementation Details
```text
Fact Extraction
```
#### `9aa2fb2` Implementation Details
```text
 JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
```
#### `9aa2fb2` Implementation Details
```text
 JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
```
#### `7803a93` Implementation Details
```text
Context Builder & Long-Term Memory Integration
```
#### `7803a93` Implementation Details
```text
Context Builder & Long-Term Memory Integration
```

# v0.8.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`) \| Tag Release Date: 2026-06-29*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `d43f6e9` Implementation Details
```text
[200~feat(v0.8): implement structured memory pipeline~
```
#### `d43f6e9` Implementation Details
```text
[200~feat(v0.8): implement structured memory pipeline~
```

# v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`) \| Tag Release Date: 2026-06-29*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `2922129` Implementation Details
```text
feat(memory): implement multi-fact extraction pipeline
```
#### `2922129` Implementation Details
```text
feat(memory): implement multi-fact extraction pipeline
```
#### `4f71baf` Implementation Details
```text
feat(memory): implement behavior-driven memory engine and multi-fact extraction
```
#### `4f71baf` Implementation Details
```text
feat(memory): implement behavior-driven memory engine and multi-fact extraction
```
#### `6316917` Implementation Details
```text
feat(memory): implement multi-trigger extraction and behavior-based memory actions
```
#### `6316917` Implementation Details
```text
feat(memory): implement multi-trigger extraction and behavior-based memory actions
```

# v2.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`) \| Tag Release Date: 2026-07-03*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `db51ccc` Implementation Details
```text
feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
```
#### `db51ccc` Implementation Details
```text
feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
```
#### `63addf6` Implementation Details
```text
before big change in memory management
```
#### `63addf6` Implementation Details
```text
before big change in memory management
```
#### `8519f65` Implementation Details
```text
feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
```
#### `8519f65` Implementation Details
```text
feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
```

# v2.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`) \| Tag Release Date: 2026-07-05*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `5fccb37` Implementation Details
```text
Bug fixes and added archiecture, dev log and changelog for v2.0.0
```
#### `5fccb37` Implementation Details
```text
Bug fixes and added archiecture, dev log and changelog for v2.0.0
```
#### `df45be2` Implementation Details
```text
Multi-Backend + Streaming + External Config
```
#### `df45be2` Implementation Details
```text
Multi-Backend + Streaming + External Config
```

# v2.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`) \| Tag Release Date: 2026-07-05*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `b2c2211` Implementation Details
```text
Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
```
#### `b2c2211` Implementation Details
```text
Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
```

# v2.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`) \| Tag Release Date: 2026-07-14*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `c84d53b` Implementation Details
```text
feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
```
#### `c84d53b` Implementation Details
```text
feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
```

# v2.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`) \| Tag Release Date: 2026-07-14*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `6ea9796` Implementation Details
```text
feat(platform): expand model backends and configuration system
```
#### `6ea9796` Implementation Details
```text
feat(platform): expand model backends and configuration system
```

# v2.4.1
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`) \| Tag Release Date: 2026-07-14*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `1cab1b1` Implementation Details
```text
mermaid added in docs/architecture and mermaid dependencies
```
#### `1cab1b1` Implementation Details
```text
mermaid added in docs/architecture and mermaid dependencies
```

# v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`) \| Tag Release Date: 2026-07-14*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `6034224` Implementation Details
```text
chore: update configuration and add Ollama Modelfile
```
#### `6034224` Implementation Details
```text
chore: update configuration and add Ollama Modelfile
```

# v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`) \| Tag Release Date: 2026-07-18*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `f9fa068` Implementation Details
```text
feat: add web UI, FastAPI server, and fix batch of issues
```
#### `f9fa068` Implementation Details
```text
feat: add web UI, FastAPI server, and fix batch of issues
```

# v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`) \| Tag Release Date: 2026-07-26*
## Developer Code Shift & Architecture Synthesis
### Release Features & Technical Notes
#### `e5875fa` Implementation Details
```text
chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
```
#### `e5875fa` Implementation Details
```text
chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
```
#### `e35d468` Implementation Details
```text
feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
```
#### `e35d468` Implementation Details
```text
feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
```
#### `4b93857` Implementation Details
```text
feat(knowledge): add PaperStore ChromaDB layer (Step 4)
```
#### `4b93857` Implementation Details
```text
feat(knowledge): add PaperStore ChromaDB layer (Step 4)
```
#### `7be0863` Implementation Details
```text
feat(knowledge): add RAG answer() with grounded citations (Step 5)
```
#### `7be0863` Implementation Details
```text
feat(knowledge): add RAG answer() with grounded citations (Step 5)
```
#### `5e7937b` Implementation Details
```text
feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
```
#### `5e7937b` Implementation Details
```text
feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
```
#### `3c80fe7` Implementation Details
```text
Step 7: RAG papers API + folder-scoped retrieval
```
#### `3c80fe7` Implementation Details
```text
Step 7: RAG papers API + folder-scoped retrieval
```
#### `6e1b09a` Implementation Details
```text
Step 8: Research Papers web UI
```
#### `6e1b09a` Implementation Details
```text
Step 8: Research Papers web UI
```
#### `ba2026f` Implementation Details
```text
Step 9: KNOWLEDGE.md + consolidated knowledge tests
```
#### `ba2026f` Implementation Details
```text
Step 9: KNOWLEDGE.md + consolidated knowledge tests
```
#### `81e45f0` Implementation Details
```text
feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
```
#### `81e45f0` Implementation Details
```text
feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
```
