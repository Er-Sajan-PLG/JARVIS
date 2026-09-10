# JARVIS Architecture — Living Document v3.0.0

**Status**: IMPLEMENTED (forensic-verified)
**Source of Truth**: `/home/sajan/Projects/JARVIS` @ `e8bef8f`
**Last Updated**: 2026-09-10
**Workflow Orchestration**: n8n (external)

---

## 1. System Overview

JARVIS is a **single-tenant personal AI platform** built on a **Pragmatic Hybrid Architecture**:

- **Direct Async Execution Loops** — Core cognitive orchestration (Intent → Plan → Execute → Synthesize) uses direct `async/await` interface calls for minimum latency
- **InMemoryAsyncBus** — Passive event bus for telemetry, token metrics, step execution logs, background job notifications (never the data path for state)
- **External Workflow Orchestration** — n8n handles all workflow automation, scheduling, and integration flows (not embedded)

---

## 2. System Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JARVIS RUNTIME                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌────────────────────────────────────────────────┐  │
│  │   CLIENTS    │────▶│          app/main.py (FastAPI)                 │  │
│  │  HTTP / WS   │     │  ├─ CORSMiddleware (configurable origins)      │  │
│  └──────────────┘     │  ├─ StaticFiles → /frontend                    │  │
│                       │  ├─ http_router (REST + Bearer Auth)           │  │
│                       │  └─ ws_router (WS + SSE, auth REQUIRED)        │  │
│                       └────────────────┬───────────────────────────────┘  │
│                                        │ bootstrap_system()                │
│                                        ▼                                  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │              app/bootstrap.py — Composition Root                   │  │
│  │  ApplicationContainer {                                            │  │
│  │    brain: IntentAnalyzer, TaskPlanner, ExecutionRunner,            │  │
│  │           ResponseSynthesizer         ← Cognitive Engine Loop      │  │
│  │    events: InMemoryAsyncBus                                     ←  │  │
│  │    models: ModelRouter + ResourceManager (circuit breakers)      ←  │  │
│  │    memory: MemoryService (ChromaDB + BM25 hybrid)                ←  │  │
│  │    guardrails: ToolSafetyPolicy @safety_gate (SAFE/SENSITIVE/      │  │
│  │                DESTRUCTIVE)                                      ←  │  │
│  │    prompt: PromptLoader (Jinja2, mtime-cached)                   ←  │  │
│  │    session: SessionManager + SessionPersistence                  ←  │  │
│  │    workspace: WorkspaceManager                                    ←  │  │
│  │    telemetry: EventLogger, MetricsCollector, Tracer              ←  │  │
│  │    artifacts: ArtifactManager                                     ←  │  │
│  │  }                                                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    EXTERNAL ORCHESTRATION (n8n)                    │  │
│  │  • Workflow automation & scheduling                                │  │
│  │  • Integration flows (webhooks, APIs, triggers)                  │  │
│  │  • Human-in-the-loop approval gates                               │  │
│  │  • Communicates with JARVIS via REST API (/api/v1/*)             │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Topology (rendered)

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

### Package boundaries (rendered)

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

## 3. Cognitive Engine Loop (Direct Async)

```
User Request
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  app/brain/IntentAnalyzer.analyze(prompt)                    │
│  → IntentAnalysis { complexity: DIRECT_CHAT | FILE_QUERY |   │
│       TOOL_SEARCH | MULTI_STEP, requires_tools, safety_flags }│
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  app/brain/TaskPlanner.create_plan(prompt, analysis)         │
│  → ExecutionPlan { plan_id, steps: [ExecutionStep], status } │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  app/brain/ExecutionRunner.execute_plan(plan, hitl_approvals)│
│  → For each step:                                            │
│     1. @safety_gate evaluates tier (SAFE/SENSITIVE/DESTRUCTIVE)│
│     2. DESTRUCTIVE → HITLRequestEvent → PAUSE (AWAITING_APPROVAL)│
│     3. Execute tool via registered handler                    │
│     4. Publish StepExecutionEvent to InMemoryAsyncBus        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  app/brain/ResponseSynthesizer.synthesize(plan)              │
│  → Formatted response with provenance                         │
└──────────────────────────────────────────────────────────────┘
```

**Key Invariant**: No event bus in the data path. Events are **telemetry only**.

---

## 4. Package Boundary Rules (Enforced by Architecture)

```
app/adapters      → app/bootstrap, app/brain
app/bootstrap     → app/brain, app/models, app/resources, app.memory,
                    app.session, app.workspace, app.prompt, app.telemetry
app/brain         → app.domain, app.events, app.guardrails
app.models        → app.resources
app.memory        → app.integrations (ChromaDB, OCR)
app.telemetry     → app.events
app.guardrails    → (standalone, no deps)
```

**Rule**: No reverse dependencies. No circular imports. Violations = build failure.

---

## 5. Security Model

| Layer | Mechanism | Enforcement |
|-------|-----------|-------------|
| **Transport** | TLS termination at edge (Cloudflare) | Required for production |
| **API Auth** | Bearer Token (`JARVIS_API_KEY`) + X-API-Key header | `app/adapters/http/router.py:validate_api_key` |
| **WS Auth** | Same Bearer + X-API-Key on upgrade | **MUST BE ADDED** to `ws_router` |
| **Tool Safety** | `@safety_gate(tier)` decorator | Runtime wrapper — blocks DESTRUCTIVE without HITL |
| **Secrets** | `.env` only, never committed | `.gitignore` enforced |
| **n8n → JARVIS** | API key rotation, scoped credentials | n8n stores JARVIS_API_KEY in encrypted credentials |

---

## 6. Data Flow Architecture

```
Request (HTTP/WS)
     │
     ▼
validate_api_key (Bearer/X-API-Key)
     │
     ▼
http_router.chat_completions / ws_router.websocket_endpoint
     │
     ▼
bootstrap_system() → ApplicationContainer (singleton)
     │
     ▼
SessionManager.get_session(session_id)
     │
     ▼
IntentAnalyzer.analyze(prompt)
     │
     ▼
TaskPlanner.create_plan(prompt, analysis)
     │
     ▼
ExecutionRunner.execute_plan(plan)
     │  ├─ @safety_gate check per tool
     │  ├─ ModelRouter.generate() with circuit breaker failover
     │  ├─ MemoryService.search_memories() for context
     │  └─ InMemoryAsyncBus.publish(StepExecutionEvent)
     │
     ▼
ResponseSynthesizer.synthesize(plan)
     │
     ▼
Streamed Response (SSE/WS) or JSON (REST)
```

---

## 7. Memory Subsystem (Hybrid)

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryService (Façade)                   │
├─────────────────────────────────────────────────────────────┤
│  store_memory(key, value, category, memory_type)            │
│  search_memories(query, limit=5) → List[MemoryRecord]       │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌─────────────────┐      ┌─────────────────┐
     │  ChromaDB       │      │  BM25           │
     │  Vector Search  │      │  Keyword Search │
     │  (dense)        │      │  (sparse)       │
     └────────┬────────┘      └────────┬────────┘
              │                        │
              └────────────┬───────────┘
                           ▼
              ┌─────────────────────────┐
              │  Hybrid Ranker          │
              │  (configurable weights) │
              └─────────────────────────┘
```

---

## 8. LLM Provider Pool & Failover

```
ModelRouter
     │
     ├─ register_provider(provider, default?)
     │
     ├─ generate(prompt, model?, preferred_provider?, task_type?)
     │     │
     │     ├─ ResourceManager.check_health(provider)
     │     │     ├─ CLOSED → proceed
     │     │     ├─ OPEN → skip to next provider
     │     │     └─ HALF_OPEN → test request
     │     │
     │     └─ On 429/503 → circuit_breaker.trip() → failover
     │
     └─ Providers (config.yaml):
           • local_general (llamacpp, Ollama-compatible)
           • grok (xAI)
           • openrouter (qwen/qwen3-coder:free)
           • google_general (gemini-2.0-flash)
```

---

## 9. n8n Integration Contract

| Aspect | Specification |
|--------|---------------|
| **Authentication** | n8n uses `JARVIS_API_KEY` via Bearer header |
| **Endpoints** | `POST /api/v1/chat/completions`, `GET /api/v1/health`, `WS /ws/chat` |
| **Workflow Triggers** | n8n webhook nodes → JARVIS REST API |
| **Human-in-the-Loop** | n8n "Wait for Webhook" / "Manual Approval" nodes → JARVIS HITL endpoints |
| **State** | n8n owns workflow state; JARVIS is stateless per request (session via `session_id`) |
| **Error Handling** | n8n retries with exponential backoff; JARVIS returns structured errors |

---

## 10. What Is NOT in JARVIS Runtime

| Component | Location | Reason |
|-----------|----------|--------|
| Workflow engine | **n8n (external)** | Separation of concerns |
| Scheduler/cron | **n8n** | n8n handles scheduling |
| Multi-agent orchestration | **PROFESSOR-J (separate repo)** | Capability Contract defines interface |
| Persistent workflow state | **n8n** | JARVIS is request-scoped |
| UI/UX flows | **Frontend (separate)** | JARVIS serves API only |

---

## 11. Version & Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| JARVIS Runtime | 3.0.0 | `app/config/version.py` |
| Python | **3.11/3.12** (NOT 3.14) | 3.14 breaks ML deps |
| FastAPI | 0.115+ | |
| ChromaDB | 0.5+ | Vector backend |
| n8n | Latest stable | External orchestration |

---

## 12. Architectural Decisions (ADR Index)

| ADR | Title | Status |
|-----|-------|--------|
| ADR-006 | Pragmatic Hybrid Architecture | ✅ IMPLEMENTED |
| ADR-007 | Domain Purity & Dataclasses | ✅ IMPLEMENTED |
| ADR-008 | Tiered Tool Safety Policy | ✅ IMPLEMENTED |
| ADR-009 | Multi-Provider Circuit Breaker | ✅ IMPLEMENTED |
| ADR-010 | n8n External Orchestration | 🟡 PROPOSED |

---

**Next**: See `GOVERNANCE.md` for decision-making process, `ROADMAP.md` for rebuild plan, `DEVELOPMENT.md` for workflow standards.
