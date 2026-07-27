# Living Architecture & System Topology at HEAD

JARVIS is built on a **Pragmatic Hybrid Architecture** combining direct async interface execution loops for core cognitive orchestration with an `InMemoryAsyncBus` for passive telemetry, logging, metrics, streaming updates, and background jobs.

---

## 1. System Topology & Layering

```mermaid
graph TD
    Client[Web Client / REST API / WS] -->|HTTP / WS| Adapters[app/adapters/ Layer]
    Adapters -->|Token Auth & Forward| Bootstrap[app/bootstrap.py Composition Root]
    Bootstrap -->|Inject Dependencies| Brain[app/brain/ Cognitive Engine]

    subgraph "Cognitive Engine Loop (Direct await)"
        Brain --> Analyzer[IntentAnalyzer]
        Analyzer --> Planner[TaskPlanner]
        Planner --> Runner[ExecutionRunner]
        Runner --> Synthesizer[ResponseSynthesizer]
    end

    subgraph "Services & Subsystems"
        Runner -->|Evaluate Policy| Safety[app/guardrails/ Safety Policy]
        Brain -->|Assemble Context| Context[app/context/ ContextBuilder]
        Brain -->|Route LLM Calls| Models[app/models/ ModelRouter]
        Brain -->|Memory Queries| Memory[app/memory/ MemoryService]
        Brain -->|Session Lookup| Session[app/session/ SessionManager]
        Brain -->|Workspace Scan| Workspace[app/workspace/ WorkspaceManager]
    end

    subgraph "Pure Business Domain Layer"
        Context & Models & Memory & Session & Workspace --> Domain[app/domain/ Pure Dataclasses]
    end

    subgraph "Passive Event Telemetry"
        Runner & Models & Memory -->|Publish Events| Bus[app/events/ InMemoryAsyncBus]
        Bus -->|Subscribe| Telemetry[app/telemetry/ EventLogger & Metrics]
    end

    subgraph "Third-Party Integrations"
        Memory & Workspace -->|Wrapped Integration| OSS[app/integrations/ ChromaDB & OCR]
    end
```

---

## 2. Package Dependency & Boundary Rules

```mermaid
graph LR
    app_adapters[app/adapters] --> app_bootstrap[app/bootstrap]
    app_adapters --> app_brain[app/brain]
    app_bootstrap --> app_brain
    app_bootstrap --> app_models[app/models]
    app_bootstrap --> app_resources[app/resources]
    app_bootstrap --> app_memory[app/memory]
    app_bootstrap --> app_session[app/session]
    app_bootstrap --> app_workspace[app/workspace]
    app_brain --> app_domain[app/domain]
    app_brain --> app_events[app/events]
    app_brain --> app_guardrails[app/guardrails]
    app_models --> app_resources
    app_memory --> app_integrations[app/integrations]
    app_telemetry[app/telemetry] --> app_events
```

---

## 3. Data & Event Flow Architecture

1. **Incoming Request**: HTTP REST request or WebSocket message arrives at `app/adapters/`.
2. **Authentication**: `validate_api_key` verifies the Bearer token or `X-API-Key` header against `JARVIS_API_KEY`.
3. **Intent Analysis**: `IntentAnalyzer` categorizes prompt complexity (`DIRECT_CHAT`, `FILE_QUERY`, `TOOL_SEARCH`, `MULTI_STEP`).
4. **Plan Generation**: `TaskPlanner` synthesizes structured `ExecutionPlan` containing ordered `ExecutionStep` instances.
5. **Step Execution & Safety Gate**: `ExecutionRunner` executes steps. Each tool call triggers `@safety_gate`.
   - `SAFE` / `SENSITIVE`: Auto-approved or policy validated.
   - `DESTRUCTIVE`: Triggers `HITLRequestEvent` and pauses execution with `AWAITING_APPROVAL` status until explicitly confirmed.
6. **Provider Routing & Failover**: `ModelRouter` checks `ResourceManager` circuit breaker health status and routes to available LLM providers, failing over automatically on 429/503 errors.
7. **Response Synthesis & Telemetry**: `ResponseSynthesizer` outputs final response; `EventLogger` and `MetricsCollector` update passive telemetry metrics over `InMemoryAsyncBus`.
