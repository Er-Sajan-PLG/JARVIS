# Repository Archaeology: Timeline & History

### [1] Commit `1999e53` `[INITIAL]` - Initial project structure
**Author:** Er Sajan PLG | **Date:** 2026-06-27 02:44:04 +0545

**Files Modified:** `.gitignore`, `README.md`, `app/__init__.py`, `app/main.py`, `requirements.txt`
**Architectural Insights:**
- *Scaffolding & Dependency Foundations*: Established the initial Python module root (`app/`), entrypoint stub (`app/main.py`), and dependency manifest (`requirements.txt`).
- *Tooling Stack*: Provisioned requirements for local LLMs (`ollama`), async web services (`fastapi`, `uvicorn`), vector search (`chromadb`), and deep learning utilities (`torch`, `transformers`).
- *Confidence Level*: `VERIFIED`


### [2] Commit `e13ee67` `[v0.1.0]` - Build Jarvis v0.1: Connect to Ollama
**Author:** Er Sajan PLG | **Date:** 2026-06-27 03:25:01 +0545

**Files Modified:** `app/models/ollama_client.py`, `app/main.py`
**Architectural Insights:**
- *Direct Local Model API Integration*: Introduced `OllamaClient` (`app/models/ollama_client.py`) connecting to local Ollama REST API (`http://localhost:11434/api/generate`).
- *Initial CLI Integration*: Connected `app/main.py` to `OllamaClient.ask()` for single-turn model execution.
- *Tag Boundary*: `v0.1.0` Release Boundary.
- *Confidence Level*: `VERIFIED`


### [3] Commit `ded44b9` `[v0.2.0]` - v0.2: working CLI chat loop with Ollama integration
**Author:** Er Sajan PLG | **Date:** 2026-06-27 04:59:01 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/main.py, docs/DEVLOG.md

### [4] Commit `163f8a1` `[v0.2.0]` - Add .gitignore for Python project
**Author:** Er Sajan PLG | **Date:** 2026-06-27 12:58:53 +0545

**Files Modified:** .gitignore

### [5] Commit `8b1d0cb` `[v0.3.0]` - Added Architecture and Roadmap in docs for what to do seamless development
**Author:** Er Sajan PLG | **Date:** 2026-06-27 13:05:30 +0545

**Files Modified:** docs/ARCHITECTURE.md, docs/ROADMAP.md

### [6] Commit `39b3d5b` `[v0.3.0]` - Making prompt
**Author:** Er Sajan PLG | **Date:** 2026-06-27 13:51:06 +0545

**Files Modified:** app/config/prompt.py, app/models/ollama_client.py

### [7] Commit `7491e9a` `[v0.3.0]` - prompt failure, prompts to prompt
**Author:** Er Sajan PLG | **Date:** 2026-06-27 14:03:01 +0545

**Files Modified:** app/models/__pycache__/ollama_client.cpython-314.pyc, app/models/ollama_client.py

### [8] Commit `e5c6fd6` `[v0.4.0]` - added SYSTEM_PROMPT in messege
**Author:** Er Sajan PLG | **Date:** 2026-06-27 14:10:19 +0545

**Files Modified:** app/models/__pycache__/ollama_client.cpython-314.pyc, app/models/ollama_client.py

### [9] Commit `94e1956` `[v0.4.0]` - Implement conversation history in OllamaClient
**Author:** Er Sajan PLG | **Date:** 2026-06-28 02:04:26 +0545

**Files Modified:** app/models/__pycache__/__init__.cpython-314.pyc, app/models/__pycache__/ollama_client.cpython-314.pyc, app/models/ollama_client.py

### [10] Commit `3cc9e4b` `[v0.4.0]` - change model from deepseek r1:32b to qwen3:8b for faster development
**Author:** Er Sajan PLG | **Date:** 2026-06-28 02:11:32 +0545

**Files Modified:** app/config/settings.py

### [11] Commit `4034bf7` `[v0.5.0]` - Persistent Memory Core
**Author:** Er Sajan PLG | **Date:** 2026-06-28 04:52:42 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/main.py, app/memory/conversation.json, app/memory/manager.py

### [12] Commit `7a840ee` `[v0.5.0]` - Save Fact based on preferences
**Author:** Er Sajan PLG | **Date:** 2026-06-28 05:16:44 +0545

**Files Modified:** app/main.py

### [13] Commit `b145614` `[v0.5.0]` - Fact Extraction
**Author:** Er Sajan PLG | **Date:** 2026-06-28 05:22:19 +0545

**Files Modified:** app/memory/manager.py

### [14] Commit `9aa2fb2` `[v0.5.0]` -  JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
**Author:** Er Sajan PLG | **Date:** 2026-06-28 16:23:10 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/main.py, app/memory/conversation.json, app/memory/fact_extractor.py, app/memory/manager.py

### [15] Commit `7803a93` `[v0.7.0]` - Context Builder & Long-Term Memory Integration
**Author:** Er Sajan PLG | **Date:** 2026-06-28 22:50:49 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/prompt.py, app/main.py

### [16] Commit `d43f6e9` `[v0.8.0]` - [200~feat(v0.8): implement structured memory pipeline~
**Author:** Er Sajan PLG | **Date:** 2026-06-29 03:50:36 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/version.py, app/main.py

### [17] Commit `2922129` `[v0.8.0]` - feat(memory): implement multi-fact extraction pipeline
**Author:** Er Sajan PLG | **Date:** 2026-06-29 07:02:35 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/main.py, app/memory/conversation.json

### [18] Commit `4f71baf` `[v0.8.0]` - feat(memory): implement behavior-driven memory engine and multi-fact extraction
**Author:** Er Sajan PLG | **Date:** 2026-06-29 08:56:24 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/main.py, app/memory/conversation.json

### [19] Commit `6316917` `[v1.0.0]` - feat(memory): implement multi-trigger extraction and behavior-based memory actions
**Author:** Er Sajan PLG | **Date:** 2026-06-29 12:13:20 +0545

**Files Modified:** app/memory/conversation.json, app/memory/fact_extractor.py, app/memory/rules.py

### [20] Commit `db51ccc` `[v1.0.0]` - feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
**Author:** Er Sajan PLG | **Date:** 2026-06-29 12:14:52 +0545

**Files Modified:** app/config/version.py, docs/ARCHITECTURE.md, docs/DEVLOG.md, docs/changelog.md

### [21] Commit `63addf6` `[v1.0.0]` - before big change in memory management
**Author:** Er Sajan PLG | **Date:** 2026-07-02 09:31:29 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/version.py, app/main.py

### [22] Commit `8519f65` `[v2.0.0]` - feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
**Author:** Er Sajan PLG | **Date:** 2026-07-03 23:31:02 +0545

**Files Modified:** app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/prompt.py, app/config/settings.py, app/config/version.py

### [23] Commit `5fccb37` `[v2.0.0]` - Bug fixes and added archiecture, dev log and changelog for v2.0.0
**Author:** Er Sajan PLG | **Date:** 2026-07-04 18:40:14 +0545

**Files Modified:** app/config/__pycache__/settings.cpython-314.pyc, app/config/settings.py, app/main.py, app/memory/manager.py, app/models/llamacpp_client.py

### [24] Commit `df45be2` `[v2.1.0]` - Multi-Backend + Streaming + External Config
**Author:** Er Sajan PLG | **Date:** 2026-07-05 07:23:59 +0545

**Files Modified:** .gitignore, app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/settings.py, app/config/version.py

### [25] Commit `b2c2211` `[v2.2.0]` - Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
**Author:** Er Sajan PLG | **Date:** 2026-07-05 22:01:06 +0545

**Files Modified:** app/__pycache__/__init__.cpython-314.pyc, app/__pycache__/main.cpython-314.pyc, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc, app/config/version.py

### [26] Commit `c84d53b` `[v2.3.0]` - feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
**Author:** Er Sajan PLG | **Date:** 2026-07-14 12:47:08 +0545

**Files Modified:** app/__pycache__/__init__.cpython-314.pyc, app/__pycache__/main.cpython-314.pyc, app/agents/doc_agent.py, app/config/__pycache__/__init__.cpython-314.pyc, app/config/__pycache__/settings.cpython-314.pyc

### [27] Commit `6ea9796` `[v2.4.0]` - feat(platform): expand model backends and configuration system
**Author:** Er Sajan PLG | **Date:** 2026-07-14 12:47:54 +0545

**Files Modified:** NEW_CHANGELOG.md, app/agents/doc_agent.py, app/config/settings.py, app/config/version.py, app/main.py

### [28] Commit `1cab1b1` `[v2.4.1]` - mermaid added in docs/architecture and mermaid dependencies
**Author:** Er Sajan PLG | **Date:** 2026-07-14 12:48:42 +0545

**Files Modified:** .gitignore, app/memory/schema.py, docs/architecture/agents.md, docs/architecture/architecture.md, docs/architecture/data-flow.md

### [29] Commit `6034224` `[v2.4.2]` - chore: update configuration and add Ollama Modelfile
**Author:** Er Sajan PLG | **Date:** 2026-07-14 12:48:42 +0545

**Files Modified:** .gitignore, Modelfile, config/version.py

### [30] Commit `f9fa068` `[v2.5.0]` - feat: add web UI, FastAPI server, and fix batch of issues
**Author:** Er Sajan PLG | **Date:** 2026-07-18 18:10:01 +0545

**Files Modified:** app/agents/doc_agent.py, app/api/__init__.py, app/api/server.py, app/attachments/store.py, app/config/settings.py

### [31] Commit `e5875fa` `[v2.5.0]` - chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
**Author:** Er Sajan PLG | **Date:** 2026-07-19 10:16:49 +0545

**Files Modified:** home/sajan/JARVIS/tests/test_issue9.py, tmp/tail.md

### [32] Commit `e35d468` `[v2.5.0]` - feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
**Author:** Er Sajan PLG | **Date:** 2026-07-19 13:53:07 +0545

**Files Modified:** app/config/settings.py, app/knowledge/__init__.py, app/knowledge/chunk.py, app/knowledge/extract.py, requirements.txt

### [33] Commit `4b93857` `[v2.5.0]` - feat(knowledge): add PaperStore ChromaDB layer (Step 4)
**Author:** Er Sajan PLG | **Date:** 2026-07-19 13:59:54 +0545

**Files Modified:** app/knowledge/store.py, tests/test_store.py

### [34] Commit `7be0863` `[v2.5.0]` - feat(knowledge): add RAG answer() with grounded citations (Step 5)
**Author:** Er Sajan PLG | **Date:** 2026-07-19 14:19:27 +0545

**Files Modified:** app/knowledge/rag.py, tests/test_rag.py

### [35] Commit `5e7937b` `[v2.5.0]` - feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
**Author:** Er Sajan PLG | **Date:** 2026-07-19 14:31:40 +0545

**Files Modified:** app/knowledge/findings.py, app/memory/manager.py, tests/test_findings.py

### [36] Commit `3c80fe7` `[v2.5.0]` - Step 7: RAG papers API + folder-scoped retrieval
**Author:** Er Sajan PLG | **Date:** 2026-07-19 15:36:23 +0545

**Files Modified:** app/api/server.py, app/attachments/store.py, app/knowledge/__init__.py, app/knowledge/ingest.py, app/knowledge/rag.py

### [37] Commit `6e1b09a` `[v2.5.0]` - Step 8: Research Papers web UI
**Author:** Er Sajan PLG | **Date:** 2026-07-19 15:40:44 +0545

**Files Modified:** frontend/app.js, frontend/index.html, frontend/styles.css

### [38] Commit `ba2026f` `[v2.5.0]` - Step 9: KNOWLEDGE.md + consolidated knowledge tests
**Author:** Er Sajan PLG | **Date:** 2026-07-19 15:49:02 +0545

**Files Modified:** app/knowledge/chunk.py, docs/KNOWLEDGE.md, tests/test_knowledge.py

### [39] Commit `81e45f0` `[v3.0.0]` - feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
**Author:** Er Sajan PLG | **Date:** 2026-07-26 01:40:15 +0545

**Files Modified:** NEW_CHANGELOG.md, README.md, app/api/ocr/routes.py, app/api/server.py, app/config/settings.py

### [40] Commit `2c855c7` `[v3.0.0]` - Merge feature/unlimited-ocr-integration into main: v3.0.0 Provider Expansion, Live Catalog, Security & Polish + RAG/Knowledge subsystem (Steps 1-9)
**Author:** Er Sajan PLG | **Date:** 2026-07-26 10:03:25 +0545

**Files Modified:** NEW_CHANGELOG.md, README.md, app/api/ocr/routes.py, app/api/server.py, app/attachments/store.py

### [41] Commit `d23f5a0` `[v3.0.0]` - docs: v3.0.0 release notes
**Author:** Er Sajan PLG | **Date:** 2026-07-26 10:09:49 +0545

**Files Modified:** CHANGELOG_v3.0.0.md, DEVLOG_v3.0.0.md

### [42] Commit `41f93b9` `[v3.0.0]` - refactor: remove Attachments Library and Research Papers subsystems
**Author:** Er Sajan PLG | **Date:** 2026-07-27 19:03:54 +0545

**Files Modified:** app/api/server.py, app/attachments/store.py, app/config/settings.py, app/knowledge/__init__.py, app/knowledge/chunk.py

### [43] Commit `d86e203` `[v3.0.0]` - refactor(frontend): modularize web interface into ES modules and component stylesheets
**Author:** Er Sajan PLG | **Date:** 2026-07-27 21:10:43 +0545

**Files Modified:** frontend/app.js, frontend/css/base.css, frontend/css/components/chat.css, frontend/css/components/modals.css, frontend/css/components/sidebar.css

### [44] Commit `c5a97b4` `[v3.0.0]` - feat(pre-phase-0): implement pure domain models, prompt engine & event contracts
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:01:15 +0545

**Files Modified:** .gitignore, README.md, app/artifacts/__init__.py, app/artifacts/manager.py, app/brain/__init__.py

### [45] Commit `930fa7e` `[v3.0.0]` - feat(phase-1): build workspace manager, project watcher & session persistence
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:03:17 +0545

**Files Modified:** app/workspace/__init__.py, app/workspace/manager.py, app/workspace/project.py, app/workspace/watcher.py, tests/unit/test_phase1.py

### [46] Commit `bb7e20b` `[v3.0.0]` - feat(phase-2): build BaseLLMProvider interface, resource manager & failover ModelRouter
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:05:35 +0545

**Files Modified:** .gitignore, app/models/__init__.py, app/models/anthropic_client.py, app/models/cerebras_client.py, app/models/cloudflare_ai_client.py

### [47] Commit `8a34243` `[v3.0.0]` - feat(phase-3): build MemoryService facade & ContextBuilder prompt assembler
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:07:35 +0545

**Files Modified:** app/context/__init__.py, app/context/builder.py, app/memory/__init__.py, app/memory/service.py, app/utils/tokenizer.py

### [48] Commit `f4d5e01` `[v3.0.0]` - feat(phase-4): build Cognitive Brain engine & wrap tools with tiered safety policy
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:10:02 +0545

**Files Modified:** app/brain/runner.py, app/tools/__init__.py, app/tools/file_tools.py, tests/unit/test_phase4.py

### [49] Commit `fef3297` `[v3.0.0]` - feat(phase-5): implement telemetry observability, composition root & complete subsystem index
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:11:41 +0545

**Files Modified:** README.md, app/bootstrap.py, app/telemetry/__init__.py, app/telemetry/logger.py, app/telemetry/metrics.py

### [50] Commit `ec0dc4e` `[v3.0.0]` - refactor: post-refactor cleanup, boundary isolation & dead-code elimination
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:28:43 +0545

**Files Modified:** app/adapters/__init__.py, app/adapters/http/router.py, app/adapters/websocket/stream.py, app/api/ocr/routes.py, app/integrations/__init__.py

