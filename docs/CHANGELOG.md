# Changelog

All notable changes to this project are documented in this file. Git tags are the source of version truth, and each entry summarizes the repository changes captured by the corresponding tag.

## [v2.5.0] - 2026-07-18
### Browser UI and safe state
This release moved JARVIS from a CLI-first tool toward a browser-backed experience while fixing silent failures and state corruption problems that made the system unreliable.

### Highlights
- Added browser-based UI and FastAPI backend with SSE chat and session management.
- Added attachment uploads and memory inspection so users can manage files and review stored state.
- Rewired backend discovery and model selection to support multiple local and cloud model backends.
- Fixed corrupt-memory failures and restored configuration-driven active profile loading.

### Added
- A web interface and FastAPI server so users can access JARVIS through the browser instead of only via CLI.
- Conversation management and file upload support so research files and chat sessions can be persisted across use.
- Memory inspection endpoints so users can see what the assistant has stored.

### Changed
- Reworked startup and backend discovery so model profiles load from configuration and the runtime can choose among multiple providers.
- Centralized logging, error handling, and generation routing to make failures visible instead of silent.

### Fixed
- Quarantined corrupt memory entries and skipped invalid records rather than allowing memory parsing to fail the entire session.
- Restored active profile loading from configuration and fixed issues in tool parsing and memory conversion.

### Internal
- Added git hooks, a version bump script, and regression tests covering memory, conversation, context, and routing behavior.

## [v2.4.2] - 2026-07-14
### Ollama Modelfile and configuration polish
This release tightened local model configuration and made release metadata explicit so runtime behavior could be driven from files instead of code.

### Highlights
- Added Ollama Modelfile support for local model definitions.
- Added explicit release metadata support via configuration.

### Added
- Explicit release metadata support so the application can surface version information at runtime.

### Changed
- Updated configuration handling and local Ollama setup so user-facing backend declarations are easier to manage.

## [v2.4.1] - 2026-07-14
### Architecture documentation support
This release focused on documenting the system shape so contributors could understand its evolving structure.

### Highlights
- Published architecture guides with diagrams covering agents, data flow, memory, and startup.
- Brought memory schema documentation in line with the current implementation.

### Added
- Published architecture documentation with visual guides for system topology and flow.

### Changed
- Updated memory schema documentation and repository documentation tooling to reflect the current system design.

## [v2.4.0] - 2026-07-14
### Backend routing and docs platform
This release expanded model support and formalized the repository’s documentation platform so future backends and features could be added with less friction.

### Highlights
- Added OpenRouter support and a runtime model switcher.
- Added a full documentation platform for API, configuration, memory, tools, and startup.
- Moved backend configuration toward a profile-driven model.

### Added
- OpenRouter backend support and a provider abstraction that lets local and cloud models coexist.
- Runtime profile switching so configured backends can be discovered and selected at startup.
- New documentation for API usage, configuration, database behavior, memory, tools, and startup flow.

### Changed
- Expanded backend configuration so model profiles are declared in configuration and used consistently.
- Updated startup orchestration and model factory logic to avoid hardcoded provider assumptions.

### Internal
- Added comprehensive project documentation to support contributors and future feature expansion.

## [v2.3.0] - 2026-07-14
### Agent-driven repository tooling
This release built the execution layer that lets the assistant act on files and repository state instead of only generating text.

### Highlights
- Added DocumentationAgent and a tool execution framework.
- Added file and git tools for repository-aware automation.
- Added stress-test coverage for the new agent flow.

### Added
- A tool execution framework that enables agent-driven operations over files and git state.
- File handling and git tools so the system can inspect and modify the repository directly.

### Changed
- Wired the main runtime to support agent and tool execution as part of the application flow.

### Internal
- Added stress-test harness coverage for the agent/tool pipeline.

## [v2.2.0] - 2026-07-05
### Semantic memory and retrieval
This release made past conversations and stored memory useful again by adding semantic search and hybrid retrieval.

### Highlights
- Added vector-based retrieval over conversations.
- Added hybrid memory search combining embeddings and keyword matching.
- Split memory processing into dedicated storage, retrieval, and ranking components.

### Added
- A conversation store and vector retrieval layer for semantically relevant memory recall.
- A hybrid retrieval pipeline that blends embedding search with keyword candidate matching.

### Changed
- Integrated embedding-backed retrieval into the chat pipeline so each turn can leverage both recent and semantically related memories.

## [v2.1.0] - 2026-07-05
### Multi-backend runtime support
This release moved model backend selection out of hardcoded startup logic and into configuration, making the project easier to deploy with different providers.

### Highlights
- Added support for local and cloud models through a model factory.
- Added live backend discovery for llama.cpp.
- Externalized runtime settings to configuration.

### Added
- A model factory and cloud/local backend support so clients can be instantiated from configuration.
- Server management utilities to detect live llama.cpp processes and expose them at runtime.

### Changed
- Streamlined startup so model clients are built from configuration and discovery rather than hardcoded defaults.

## [v2.0.0] - 2026-07-03
### Modular architecture and pipeline rewrite
This release restructured JARVIS from a monolithic prototype into a layered assistant with explicit context, memory, and retrieval boundaries.

### Highlights
- Replaced ad hoc state with structured context, conversation, and memory modules.
- Added dedicated memory ranking, retrieval, schema, and storage components.
- Introduced score-based model routing and offline-safe startup behavior.

### Added
- Explicit context and conversation management modules.
- Dedicated memory store, retriever, ranking, and schema components.
- A model router abstraction with score-based classification.

### Changed
- Reworked the main application flow to build chat turns from structured context, memory retrieval, and managed conversation state.
- Updated memory and conversation persistence formats and trimming behavior for coherent replay.

### Internal
- Enforced strict offline mode and real token counting to make startup and generation behavior more predictable.

## [v1.0.0] - 2026-06-29
### Mature memory engine
This release refined memory extraction and introduced behavior-driven memory actions to make stored facts more useful.

### Highlights
- Added multi-trigger memory extraction.
- Added behavior-based memory actions.

### Added
- Memory extraction that supports multiple triggers and action-based memory handling.

## [v0.8.0] - 2026-06-29
### Structured memory pipeline
This release introduced a more disciplined memory pipeline so facts could be processed consistently.

### Highlights
- Added structured memory pipeline support.

### Added
- A structured memory pipeline to make memory processing more systematic.

## [v0.7.0] - 2026-06-28
### Context builder and long-term memory
This release connected long-term memory with prompt construction so conversations could refer to earlier content more effectively.

### Highlights
- Added context builder logic.
- Added long-term memory integration.

### Changed
- Added long-term memory support to the prompt construction flow.

## [v0.5.0] - 2026-06-28
### Persistent memory core
This release established persistent storage for conversation and memory state.

### Highlights
- Added persistent memory and conversation storage.

### Added
- Persistent memory core and conversation storage foundation.

## [v0.4.0] - 2026-06-27
### System prompt architecture
This release introduced structured system prompt handling to improve assistant consistency.

### Highlights
- Added system prompt handling to the message flow.

### Changed
- Added system prompt architecture so assistant behavior could be managed more explicitly.

## [v0.3.0] - 2026-06-27
### Architecture and roadmap foundation
This release documented the project’s direction so future development could stay aligned.

### Highlights
- Added architecture and roadmap documentation.

### Added
- Architecture and roadmap documentation to clarify project direction and system design.

## [v0.2.0] - 2026-06-27
### Working CLI chat loop
This release delivered the first interactive CLI experience for the assistant.

### Highlights
- Added a working CLI chat loop with Ollama integration.

### Changed
- Implemented the CLI chat loop so JARVIS could operate as an interactive assistant.

## [v0.1.0] - 2026-06-27
### First Ollama integration
This release created the initial Ollama-backed foundation for the project.

### Highlights
- Added the first working Ollama integration.

### Added
- Initial Ollama-backed project scaffolding and integration.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
f9fa068|Er Sajan PLG|2026-07-18 18:05:40 +0545|feat: add web UI, FastAPI server, and fix batch of issues
6ea9796|Er Sajan PLG|2026-07-11 22:42:47 +0545|feat(platform): expand model backends and configuration system
c84d53b|Er Sajan PLG|2026-07-06 06:13:31 +0545|feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
```

Notes: This log was generated from the repository history for `docs/CHANGELOG.md`.
