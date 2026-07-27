# JARVIS Subsystem & Package Architecture Index

## Architecture Overview

JARVIS implements a **Pragmatic Hybrid Architecture**:
1. **Direct Async Interface Calls**: Orchestration loops (Cognitive Engine: `IntentAnalyzer` ➔ `TaskPlanner` ➔ `ExecutionRunner` ➔ `ResponseSynthesizer`).
2. **InMemoryAsyncBus**: Passive telemetry, metrics, event logging, background tasks, and streaming updates.
3. **Adapters & Integrations**:
   - `app/adapters/`: I/O protocol boundary (REST HTTP routes, WebSockets/SSE streaming, Bearer token security).
   - `app/integrations/`: Open-source third-party wrappers (PaddleOCR, PyMuPDF, ChromaDB vector store).

---

## Package Boundary Map

```
                     ┌────────────────────────────────┐
                     │    app/adapters/ (HTTP / WS)   │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │    app/bootstrap.py Container  │
                     └───────────────┬────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
          ▼                          ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│   app/brain/      │      │   app/context/    │      │  app/guardrails/  │
│ (Cognitive Engine)│      │(Context Builder)  │      │  (Safety Policy)  │
└─────────┬─────────┘      └─────────┬─────────┘      └─────────┬─────────┘
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │    app/domain/ (Pure Entities) │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │   app/integrations/ (OSS Wrappers)
                     └────────────────────────────────┘
```

---

## Subsystem Package Directory

| Subsystem Package | Location | Primary Responsibilities & Exported Interfaces |
| :--- | :--- | :--- |
| **Adapters** | `app/adapters/` | `http_router`, `ws_router`, `validate_api_key`. |
| **Integrations** | `app/integrations/` | `OCRService`, `get_ocr_service`, `ChromaVectorStore`. |
| **Composition Root** | `app/bootstrap.py` | `bootstrap_system()`, `ApplicationContainer`. |
| **Cognitive Brain** | `app/brain/` | `IntentAnalyzer`, `TaskPlanner`, `ExecutionRunner`, `ResponseSynthesizer`. |
| **Domain Layer** | `app/domain/` | Pure business entities (`ContentSource`, `MemoryRecord`, `ExecutionPlan`, `SessionState`, `SafetyTier`). |
| **Event System** | `app/events/` | `InMemoryAsyncBus`, `TelemetryEvent`, `StepExecutionEvent`, `HITLRequestEvent`, `TokenUsageEvent`. |
| **Guardrails** | `app/guardrails/` | `ToolSafetyPolicy`, `@safety_gate`, `HITLRequiredError`. |
| **Multi-Provider LLM** | `app/models/` | `BaseLLMProvider`, `LLMResponse`, `ModelRouter`, `TaskType`. |
| **Resource Manager** | `app/resources/` | `ResourceManager`, `TokenBudgetManager`, `RateLimitTracker`, `ProviderHealthMonitor`. |
| **Memory Façade** | `app/memory/` | `MemoryService` (vector + BM25 keyword search). |
| **Context Assembly** | `app/context/` | `ContextBuilder` (assembles system prompt, memories, sources within token budget). |
| **Session Persistence** | `app/session/` | `SessionManager`, `SessionPersistence` (asyncpg PostgreSQL + JSON fallback). |
| **Workspace Manager** | `app/workspace/` | `Project`, `FileWatcher`, `WorkspaceManager`. |
| **Artifact Manager** | `app/artifacts/` | `ArtifactManager` (disk spillover storage). |
| **Telemetry & Audit** | `app/telemetry/` | `EventLogger`, `Tracer`, `MetricsCollector`. |
