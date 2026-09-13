# Domain Layer Subsystem (`app/domain/`) - Version-by-Version History


**Status**: ACTIVE
**Last Updated**: 2026-09-13
**Source**: `app/domain/` at HEAD
## Version-by-Version Evolutionary History

### Version v0.1.0 to v0.4.0 (`e13ee67` - `e5c6fd6`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27*
- **Initial Domain Representation**: Loose string dictionaries representing raw prompt messages and model outputs.
- **Invariants**: No formal domain dataclasses or entity schemas existed.

### Version v0.5.0 (`4034bf7`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 | Tag Release Date: 2026-06-28*
- **First Domain Entity**: Simple key-value tuple schema for persistent user preference facts.
- **Invariants**: Raw JSON dictionary storage (`{"fact": "..."}`).

### Version v0.8.0 (`d43f6e9`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29*
- **Structured Memory Schema**: Introduction of `Memory` dataclass (`key`, `value`, `category`, `importance`, `created_at`).
- **Confidence**: `VERIFIED`

### Version v1.0.0 (`6316917`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29*
- **Behavior-Driven Actions Enum**: Added `MemoryAction` enum (`APPEND`, `REPLACE`, `IGNORE`, `DELETE`).

### Version v2.0.0 to v2.5.0 (`8519f65` - `f9fa068`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 | Tag Release Date: 2026-07-03*
- **TaskType & ToolDefinition**: Added task classification enums (`CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`) and tool metadata structures.

### Version v3.0.0 Refactored (`c5a97b4` - `ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Pure Domain Layer (`app/domain/`)**:
  - `ContentSource` & `ArtifactHandle` (`content.py`): Attachment & binary spillover domain entities.
  - `ConversationState` & `Message` (`conversation.py`): Pure conversation state entities.
  - `MemoryRecord` & `MemoryType` (`memory.py`): Portable memory domain dataclasses (`FACT`, `PREFERENCE`, `SKILL`, `RULE`).
  - `ExecutionPlan`, `ExecutionStep`, `StepStatus`, `SafetyTier` (`plan.py`): Structured cognitive execution entities.
  - `SessionState` & `UserPreferences` (`session.py`): User session state entities.
- **Active Invariants at HEAD**:
  1. Zero infrastructure, database (asyncpg, ChromaDB), or web framework (FastAPI) imports inside `app/domain/`.
  2. All entities are pure Python 3.11+ standard library dataclasses re-exported via `app/domain/__init__.__all__`.
