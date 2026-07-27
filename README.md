# JARVIS: Personal AI Platform

JARVIS is a modular, hosted-ready personal AI platform for single-tenant deployment featuring a pragmatic hybrid architecture:
1. **Direct Async Interface Calls**: Core orchestration (Cognitive Engine: Analyzer ➔ Planner ➔ Runner ➔ Synthesizer) uses direct `async` interface calls (`await`).
2. **InMemoryAsyncBus**: Passive telemetry, metrics, event logging, background jobs, SSE streaming events, and scheduler notifications.

---

## Coding Standards & Conventions

1. **Python 3.11+ Modern Syntax**:
   - Native generic types: `list[str]`, `dict[str, Any]`, `str | None`.
   - Tooling stack: **Ruff** for linting/formatting, **Pyright** for static type checking (`strict` on `app/domain/`), and **pytest** for testing.

2. **Naming & Type Annotations**:
   - Variables & functions: `snake_case`.
   - Classes & domain entities: `PascalCase`.
   - Constants: `UPPER_SNAKE_CASE`.
   - Type annotations: 100% explicit typing on all public APIs, arguments, and return values.

3. **Domain Purity**:
   - `app/domain/` contains pure business entities only (`dataclass` / Pydantic models). Zero infrastructure, database, or web framework imports.

4. **Documentation Philosophy**:
   - Document intent and non-obvious contracts using Google-style docstrings (`Args:`, `Returns:`, `Raises:`).

---

## Subsystem & Module Index

| Subsystem Package | Path | Primary Exports & Responsibilities |
| :--- | :--- | :--- |
| **Domain Layer** | `app/domain/` | Pure business domain entities (`ContentSource`, `ArtifactHandle`, `DocumentReference`, `Role`, `MessageAttachment`, `Message`, `ConversationState`, `MemoryType`, `MemoryRecord`, `FactExtractionResult`, `SafetyTier`, `StepStatus`, `ToolCall`, `ExecutionStep`, `ExecutionPlan`, `UserPreferences`, `SessionState`). |
| **Event System** | `app/events/` | Passive event bus & contracts (`InMemoryAsyncBus`, `Event`, `TelemetryEvent`, `StepExecutionEvent`, `HITLRequestEvent`, `TokenUsageEvent`, `NotificationEvent`). |
| **Guardrails & Safety** | `app/guardrails/` | Tiered tool safety policy engine & decorator (`ToolSafetyPolicy`, `@safety_gate`, `HITLRequiredError`, `PolicyViolationError`). |
| **Artifact Manager** | `app/artifacts/` | Disk spillover storage & binary artifact handles (`ArtifactManager`). |
| **Session Persistence** | `app/session/` | PostgreSQL (`asyncpg`) & fallback persistence (`SessionManager`, `SessionPersistence`). |
| **Workspace Manager** | `app/workspace/` | Project workspace management & file watcher (`Project`, `FileWatcher`, `WorkspaceManager`). |
| **Multi-Provider LLM** | `app/models/` | Unified provider interface (`BaseLLMProvider`, `LLMResponse`), router & failover pool (`ModelRouter`, `TaskType`). |
| **Resource Manager** | `app/resources/` | Token budget tracking, provider rate limits, circuit breaker (`ResourceManager`, `TokenBudgetManager`, `RateLimitTracker`, `ProviderHealthMonitor`, `CircuitState`). |
| **Memory Façade** | `app/memory/` | Persistent memory façade (`MemoryService`), pgvector hybrid search & BM25 retrieval. |
| **Context Assembly** | `app/context/` | Dynamic prompt context assembly (`ContextBuilder`). |
| **Cognitive Brain** | `app/brain/` | Fast intent classifier (`IntentAnalyzer`), slow-path planner (`TaskPlanner`), step runner (`ExecutionRunner`), synthesizer (`ResponseSynthesizer`). |
| **Prompts Engine** | `prompts/` | Externalized Jinja2 markdown templates (`system_base.md`, `planner.md`, `synthesizer.md`) & mtime-cached `PromptLoader`. |
| **Telemetry & Audit** | `app/telemetry/` | Observability, event logging, tracing, metrics (`EventLogger`, `Tracer`, `MetricsCollector`, `AggregatedMetrics`). |
| **Composition Root** | `app/bootstrap.py` | Single-tenant dependency injection container (`bootstrap_system`, `ApplicationContainer`). |

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

4. Run automated test suite:
   ```bash
   .venv/bin/python -m pytest tests/unit/
   ```
