# System Startup & Composition Root (`v3.0.0 Refactored`)

**Status**: ACTIVE
**Last Updated**: 2026-09-13
**Source**: `app/bootstrap.py`, `app/main.py` at HEAD

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
