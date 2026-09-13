# Data Flow Architecture

**Status**: ACTIVE
**Last Updated**: 2026-09-13
**Source**: `app/domain/`, `app/brain/`, `app/adapters/` at HEAD

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
