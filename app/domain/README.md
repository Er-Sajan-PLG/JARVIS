# app/domain

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Domain Layer Package. | — |
| `cognitive_state.py` | Canonical cognitive state for the JARVIS LangGraph loop. | `CognitiveState` |
| `content.py` | Pure Domain Entities: Content Abstractions & Artifact Handles. | `ArtifactHandle`, `ContentSource`, `ContentType`, `DocumentReference` |
| `conversation.py` | Pure Domain Entities: Message & Conversation State. | `ConversationState`, `Message`, `MessageAttachment`, `Role` |
| `intent.py` | Intent analysis domain types. | `IntentAnalysis`, `IntentComplexity` |
| `memory.py` | Pure Domain Entities: Memory Records & Fact Extraction. | `DraftStatus`, `FactExtractionResult`, `MemoryItem`, `MemoryKind`, `MemoryRecord`, `MemoryScope`, `MemoryType`, `_kind_to_memory_type()` |
| `plan.py` | Pure Domain Entities: Inspectable Execution Plans & Steps. | `ExecutionPlan`, `ExecutionStep`, `SafetyTier`, `StepStatus`, `ToolCall` |
| `safety_flag.py` | Safety flag raised during intent analysis. | `SafetyFlag` |
| `session.py` | Pure Domain Entities: Session State & User Preferences. | `SessionState`, `UserPreferences` |
| `state.py` | LangGraph-typed state for the JARVIS cognitive loop. | `ExecutionState`, `IntentState`, `PlanState`, `ResponseState` |
| `tool_result.py` | Result of a tool execution within a cognitive loop turn. | `ToolResult` |

<!-- generated:module_readmes end -->
