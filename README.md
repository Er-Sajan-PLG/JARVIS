# JARVIS: Personal AI Platform

JARVIS is a modular, hosted-ready personal AI platform for single-tenant deployment featuring a pragmatic hybrid architecture:
1. **Direct Async Interface Calls**: Core orchestration (Cognitive Engine: Analyzer ➔ Planner ➔ Runner ➔ Synthesizer) uses direct `async` interface calls (`await`).
2. **InMemoryAsyncBus**: Passive telemetry, metrics, event logging, background jobs, SSE streaming events, and scheduler notifications.

---

## Coding Standards & Conventions

1. **Python 3.11+ Modern Syntax**:
   - Use native generic types: `list[str]`, `dict[str, Any]`, `str | None`.
   - Tooling stack: **Ruff** for linting/formatting, **Pyright** for static type checking (`strict` on `app/domain/`), and **pytest** for testing.

2. **Naming & Type Annotations**:
   - Variables & functions: `snake_case`.
   - Classes & domain entities: `PascalCase`.
   - Constants: `UPPER_SNAKE_CASE`.
   - Type annotations: 100% explicit typing on all public APIs, arguments, and return values.

3. **Domain Purity**:
   - `app/domain/` contains pure business entities only (dataclasses/Pydantic models). Zero infrastructure, database, or web framework imports.

4. **Documentation Philosophy**:
   - Document intent and non-obvious contracts using Google-style docstrings (`Args:`, `Returns:`, `Raises:`).

---

## Subsystem & Module Index

| Subsystem Package | Path | Description & Primary Exports |
| :--- | :--- | :--- |
| **Domain Entities** | `app/domain/` | Pure business entities (`ContentSource`, `ArtifactHandle`, `Message`, `ConversationState`, `MemoryRecord`, `ExecutionPlan`, `ExecutionStep`, `SessionState`). |
| **Event System** | `app/events/` | Passive event bus (`InMemoryAsyncBus`) and event contracts (`TelemetryEvent`, `StepExecutionEvent`, `HITLRequestEvent`, `TokenUsageEvent`). |
| **Guardrails & Safety** | `app/guardrails/` | Tiered tool safety policy (`ToolSafetyPolicy`, `@safety_gate`, `HITLRequiredError`). |
| **Artifact Manager** | `app/artifacts/` | Disk spillover storage & binary artifact handles (`ArtifactManager`). |
| **Session Persistence** | `app/session/` | PostgreSQL (`asyncpg`) & fallback file persistence (`SessionManager`, `SessionPersistence`). |
| **Cognitive Brain** | `app/brain/` | Intent analyzer (`IntentAnalyzer`), dynamic planner (`TaskPlanner`), step runner (`ExecutionRunner`), synthesizer (`ResponseSynthesizer`). |
| **Prompts Engine** | `prompts/` | Externalized Jinja2 markdown prompt templates & mtime-cached `PromptLoader`. |
| **Workspace Manager** | `app/workspace/` | Project workspace management & filesystem watcher (`WorkspaceManager`). |
| **Multi-Provider LLM** | `app/models/` | Unified provider interface (`BaseLLMProvider`), router & failover pool (`ModelRouter`). |
| **Memory Façade** | `app/memory/` | Persistent memory façade (`MemoryService`), pgvector hybrid search & BM25 retrieval. |
| **Resource Manager** | `app/resources/` | Token budget tracking, provider rate limits (`ResourceManager`). |

---

## Local Development & Service Setup

1. Create and activate virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Run local PostgreSQL database with `pgvector`:
   ```bash
   docker compose up -d
   ```

3. Run FastAPI web server:
   ```bash
   .venv/bin/python -m app.api.server
   ```
