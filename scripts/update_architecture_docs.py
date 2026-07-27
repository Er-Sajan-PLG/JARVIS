#!/usr/bin/env python3
"""
scripts/update_architecture_docs.py
Updates docs/architecture/*.md to accurately reflect v3.0.0 Refactored (Pragmatic Hybrid Architecture at HEAD).
"""

import os

def update_architecture_md():
    content = """# JARVIS — Master Architecture & Component Topology (`v3.0.0 Refactored`)

> **Source of Truth**: Running implementation under `app/` at `HEAD` (`v3.0.0 Refactored`, commit `ec0dc4e`).
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`c5a97b4` - `ec0dc4e`) | Tag Release Date: 2026-07-28*

---

## 1. High-Level Pragmatic Hybrid Architecture

JARVIS follows a **Single-Tenant Pragmatic Hybrid Architecture**. The core domain layer (`app/domain/`) is 100% pure Python dataclasses without framework dependencies. Core cognitive execution loops use direct `async/await` method calls, while passive telemetry events are published asynchronously to `InMemoryAsyncBus`.

```mermaid
flowchart TB
    subgraph ADAPTERS["I/O Protocol Adapters (app/adapters/)"]
        HTTP["REST HTTP Router<br/>(http/router.py)"]
        WS["WebSocket Stream<br/>(websocket/stream.py)"]
        AUTH["Bearer Key Auth<br/>(validate_api_key)"]
    end

    subgraph BOOTSTRAP["Composition Root (app/bootstrap.py)"]
        CONTAINER["ApplicationContainer<br/>Singletons & Services"]
    end

    subgraph BRAIN["Cognitive Brain Engine (app/brain/)"]
        INTENT["IntentAnalyzer<br/>(analyzer.py)"]
        PLANNER["TaskPlanner<br/>(planner.py)"]
        RUNNER["ExecutionRunner<br/>(runner.py)"]
        SYNTH["ResponseSynthesizer<br/>(synthesizer.py)"]
    end

    subgraph GUARDRAILS["Safety Policy (app/guardrails/)"]
        POLICY["ToolSafetyPolicy<br/>(policy.py)"]
        GATE["@safety_gate<br/>SAFE / SENSITIVE / DESTRUCTIVE"]
    end

    subgraph MODELS["LLM Pool & Circuit Breakers (app/models/, app/resources/)"]
        ROUTER["ModelRouter<br/>(models/router.py)"]
        RESMAN["ResourceManager<br/>(resources/manager.py)"]
        PROVIDERS["LLM Providers<br/>Ollama / LlamaCpp / Cloud APIs"]
    end

    subgraph MEMORY["Memory Subsystem (app/memory/)"]
        MEMSERVICE["MemoryService Façade<br/>(memory/service.py)"]
        STORE["MemoryStore<br/>(memory/store.py)"]
    end

    subgraph INTEGRATIONS["Isolated Integrations (app/integrations/)"]
        CHROMA["ChromaVectorStore<br/>(vector/chroma.py)"]
        OCR["OCRService Backend<br/>(ocr/service.py)"]
    end

    HTTP --> AUTH
    WS --> AUTH
    AUTH --> CONTAINER
    CONTAINER --> BRAIN
    INTENT --> PLANNER
    PLANNER --> RUNNER
    RUNNER --> GATE
    GATE --> POLICY
    RUNNER --> ROUTER
    ROUTER --> RESMAN
    RESMAN --> PROVIDERS
    BRAIN --> MEMSERVICE
    MEMSERVICE --> STORE
    MEMSERVICE --> CHROMA
    RUNNER --> OCR
```

---

## 2. Invariants at HEAD (`v3.0.0 Refactored`)

1. **Domain Purity**: `app/domain/` contains zero framework, database, or vendor imports.
2. **Composition Root**: `ApplicationContainer` in `app/bootstrap.py` is the single source of dependency injection.
3. **Safety Gates**: All destructive filesystem and command tools are wrapped with `@safety_gate` enforcing HITL approval pause states (`AWAITING_APPROVAL`).
4. **Resilient Failover**: `ResourceManager` tracks 3-state circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`) to automatically failover from 429/503 errors.
5. **Decoupled Integrations**: Third-party libraries (`ChromaDB`, `PaddleOCR`) are isolated inside `app/integrations/`.
"""
    with open("docs/architecture/architecture.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/architecture.md")

def update_agents_md():
    content = """# Cognitive Brain Engine & Agent Architecture (`v3.0.0 Refactored`)

> **Source of Truth**: `app/brain/` and `app/guardrails/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`f4d5e01`) | Tag Release Date: 2026-07-28*

---

## 1. Cognitive Brain Execution Cycle

Request processing is decomposed into 4 direct async execution stages:

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client (HTTP/WS Adapter)
    participant Intent as IntentAnalyzer
    participant Planner as TaskPlanner
    participant Runner as ExecutionRunner
    participant Gate as @safety_gate Policy
    participant Router as ModelRouter
    participant Synth as ResponseSynthesizer

    Client->>Intent: analyze_intent(prompt)
    Intent-->>Planner: IntentAnalysis (complexity, strategy)
    Planner->>Planner: generate_plan(prompt, intent)
    Planner-->>Runner: ExecutionPlan (steps)
    loop Each Step in ExecutionPlan
        Runner->>Gate: check_policy(step.tool_name)
        alt Step is DESTRUCTIVE & unapproved
            Gate-->>Runner: HITLRequiredError (AWAITING_APPROVAL)
            Runner-->>Client: Emit HITL Approval Request
        else Step is Approved / SAFE
            Runner->>Router: execute_step(step)
            Router-->>Runner: StepResult
        end
    end
    Runner->>Synth: synthesize(results)
    Synth-->>Client: Final Response Stream
```

---

## 2. Tiered Tool Safety Policy

| Tier | Policy Behavior | Example Tools |
| :--- | :--- | :--- |
| **`SAFE`** | Auto-approved execution | `calculator`, `read_file`, `get_status` |
| **`SENSITIVE`** | Logged & checked against policy rules | `write_file`, `git_commit` |
| **`DESTRUCTIVE`** | Mandatory HITL pause-and-resume gate | `delete_file`, `exec_shell`, `git_push` |
"""
    with open("docs/architecture/agents.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/agents.md")

def update_models_md():
    content = """# LLM Multi-Provider Pool & Circuit Breaker Architecture (`v3.0.0 Refactored`)

> **Source of Truth**: `app/models/` and `app/resources/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`bb7e20b`) | Tag Release Date: 2026-07-28*

---

## 1. Provider Failover Topology

`ModelRouter` delegates provider health tracking and rate limiting to `ResourceManager`:

```mermaid
flowchart LR
    REQUEST["Router Request"] --> ROUTER["ModelRouter"]
    ROUTER --> RESMAN["ResourceManager"]
    
    subgraph HEALTH["Provider Health & Circuit Breakers"]
        MONITOR["ProviderHealthMonitor"]
        CB1["Ollama (CLOSED)"]
        CB2["Google AI Studio (CLOSED)"]
        CB3["OpenRouter (OPEN - 429)"]
    end
    
    RESMAN --> MONITOR
    MONITOR --> CB1
    MONITOR --> CB2
    MONITOR --> CB3
    
    CB1 -->|"Primary Execution"| OLLAMA["OllamaClient"]
    CB2 -->|"Fallback 1"| GOOGLE["GoogleClient"]
    CB3 -.->|"Bypassed (Circuit Open)"| OPENROUTER["OpenRouterClient"]
```

---

## 2. Circuit Breaker States

- **`CLOSED`**: Healthy provider; 100% request routing.
- **`OPEN`**: Provider returned 429/503 errors; requests routed to fallback for cooldown period.
- **`HALF_OPEN`**: Cooldown expired; testing probe requests to verify provider recovery.
"""
    with open("docs/architecture/models.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/models.md")

def update_data_flow_md():
    content = """# Data Flow Architecture (`v3.0.0 Refactored`)

> **Source of Truth**: `app/domain/`, `app/brain/`, and `app/adapters/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`ec0dc4e`) | Tag Release Date: 2026-07-28*

---

## 1. End-to-End Streaming Data Flow

```mermaid
flowchart TD
    CLIENT["Client UI / API Key Header"] --> REST["app/adapters/http/router.py"]
    CLIENT --> WS["app/adapters/websocket/stream.py"]
    
    REST --> INGEST["Domain SessionState Ingestion"]
    WS --> INGEST
    
    INGEST --> BRAIN["app/brain/ (Cognitive Engine)"]
    BRAIN --> MEM["app/memory/service.py (MemoryService)"]
    BRAIN --> LLM["app/models/router.py (ModelRouter)"]
    
    LLM --> BUS["app/events/ (InMemoryAsyncBus)"]
    BUS -.->|"Passive Telemetry"| LOG["app/telemetry/ (EventLogger / Tracer)"]
    
    BRAIN --> OUT["Streamed Chunk Synthesis"]
    OUT --> CLIENT
```
"""
    with open("docs/architecture/data-flow.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/data-flow.md")

def update_startup_flow_md():
    content = """# System Startup & Composition Root (`v3.0.0 Refactored`)

> **Source of Truth**: `app/bootstrap.py` and `app/config/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`fef3297`) | Tag Release Date: 2026-07-28*

---

## 1. Composition Root Bootstrap Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Main as app/bootstrap.py
    participant Settings as Settings Engine
    participant Bus as InMemoryAsyncBus
    participant ResMan as ResourceManager
    participant ModelRouter as ModelRouter
    participant MemoryService as MemoryService
    participant Brain as Cognitive Brain Engine
    participant Container as ApplicationContainer

    Main->>Settings: load_settings()
    Main->>Bus: initialize_bus()
    Main->>ResMan: initialize_resource_manager()
    Main->>ModelRouter: register_providers(ResMan)
    Main->>MemoryService: initialize_memory_facade()
    Main->>Brain: assemble_cognitive_services()
    Main->>Container: wire_singletons()
    Container-->>Main: Ready ApplicationContainer
```
"""
    with open("docs/architecture/startup-flow.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/startup-flow.md")

def update_memory_md():
    content = """# Memory Subsystem Architecture (`v3.0.0 Refactored`)

> **Source of Truth**: `app/memory/` and `app/integrations/vector/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`8a34243`) | Tag Release Date: 2026-07-28*

---

## 1. Hybrid Search & Memory Façade

```mermaid
flowchart TB
    CALLER["Cognitive Brain / ContextBuilder"] --> SERVICE["MemoryService Façade<br/>(app/memory/service.py)"]
    
    SERVICE --> STORE["MemoryStore (BM25 / Keyword)<br/>(app/memory/store.py)"]
    SERVICE --> CHROMA["ChromaVectorStore (Semantic)<br/>(app/integrations/vector/chroma.py)"]
    
    STORE --> FILE["data/memories.json"]
    CHROMA --> DB["data/chroma/"]
```
"""
    with open("docs/architecture/memory.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[+] Updated docs/architecture/memory.md")

if __name__ == "__main__":
    update_architecture_md()
    update_agents_md()
    update_models_md()
    update_data_flow_md()
    update_startup_flow_md()
    update_memory_md()
