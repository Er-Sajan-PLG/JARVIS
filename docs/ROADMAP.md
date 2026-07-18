# Purpose
The JARVIS project is an AI-powered personal assistant platform designed for learning, engineering, research, and automation. This document outlines the project's evolution, current development, and future objectives based on existing project documentation.

# Project Vision
JARVIS is designed as a modular, local-first AI operating platform. The long-term vision is to create a system where every capability—memory, reasoning, planning, tools, knowledge, and interaction—is an independent subsystem, allowing for seamless evolution without architectural instability. It aims to support local models, cloud APIs, persistent memory, and multi-agent orchestration.

# Current Development Stage
The project is currently in the transition from **v2 (Stable Architecture)** to incorporating more robust model switching and API integration.
- **Current Focus:** Refactoring the `main.py` entry point to utilize a `ModelSwitcher` and expanding model support (OpenRouter, Google Gemini, Grok).
- **Recent Work:** Implementation of `ModelSwitcher`, externalizing configurations for profiles (local, cloud, openrouter, grok, google), and updating documentation agents.

# Completed Milestones
- Core architecture overhaul (v2.0.0).
- Ollama/LLM integration.
- Initial CLI conversation loop.
- Structured memory pipeline (fact extraction, behavior-based management).
- Semantic Memory system with ChromaDB.
- Multi-backend support (llamacpp, ollama, openrouter, gemini).
- Documentation agent for automated project logging.

# Work In Progress
- Implementation of `ModelSwitcher` for dynamic profile handling.
- Refinement of `doc_agent.py` for comprehensive history documentation.
- Integration of environment variable management for API keys (`python-dotenv`).
- Support for `openrouter` and `google` backends.

# Planned Work
*Based on `ARCHITECTURE.md` and project documentation:*
- **Memory Retrieval:** Transition to targeted `retrieve(prompt)` using ChromaDB.
- **Memory Manager Redesign:** Centralizing the memory lifecycle (Store, Update, Replace, Delete, Merge, Retrieve).
- **Hybrid Memory:** Integrating keyword and semantic ranking.
- **Episodic Memory:** Implementing conversation summarization and compression.
- **Agent Runtime:** Introducing tool calling capabilities and an execution loop.
- **Cognitive Memory:** LLM fact extraction, importance/confidence ranking.
- **Planning:** Goal decomposition, task scheduling.
- **Multi-Agent:** Specialized cooperative agent orchestration.

# Dependencies and Prerequisites
1. **Infrastructure:** Python environment with `requirements.txt` dependencies.
2. **Backends:** Ollama service for local models; API keys for external models (OpenRouter, Grok, Google).
3. **Memory:** ChromaDB installation for vector storage.

# Known Limitations
- **Extractor Logic:** Currently rule-based and prone to the "first-match-wins" limitation; needs LLM-based extraction.
- **Configuration:** While improving, some configuration settings are still maturing.
- **Memory:** ChromaDB vector index requires manual cleanup after heavy usage.
- **Hybrid Retriever:** Keyword overlap threshold requires tuning.

# Risks
- **Architectural Integrity:** Potential component leakage during rapid refactoring of the Router/Switcher/Client architecture.
- **Dependency Stability:** Reliance on external APIs and local backends (Ollama/llama.cpp) creates potential points of failure if interfaces or environments change.

# Future Vision
- Unified personal knowledge and automation platform (AI OS).
- Adaptive memory updates through reflection.
- Robotics and hardware integration.

# Uncertainties
- **Early History:** Full details on v0.1 to v0.8 are reliant on recovered logs (`docs/CHANGELOG_recovered.md`), which may contain gaps.
- **Google Integration:** Resolved — Google Gemini is now a first-class `GoogleClient` (`app/models/google_client.py`), selected via `backend: "google"` in `config.yaml` (no source editing required).

---

## AI Verification Status

### AI Verified
- Project architecture overhaul (v2.0.0).
- Memory system (ChromaDB, fact extraction).
- Multi-backend support (llamacpp, ollama, openrouter).
- Documentation agent existence.
- Current development focus on `ModelSwitcher` and profile configurations.

### AI Partially Verified
- Future goals (v3.0 - v7.0) are extracted from project documentation, but the exact timeline is subject to development velocity.
- Early project history (v0.1 - v0.8) is reconstructed from recovered logs.

### AI Unverified
- Specific performance metrics of the hybrid retriever or extraction accuracy in production environments.

---

## Developer Verification
Status: ☐ Not Reviewed
Reviewer:
Date:
Notes:
-
-
