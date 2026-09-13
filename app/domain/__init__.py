"""JARVIS Domain Layer Package.

Exports pure business domain entities. Guaranteed zero external framework dependencies.
"""

from app.domain.cognitive_state import CognitiveState
from app.domain.content import ArtifactHandle, ContentSource, ContentType, DocumentReference
from app.domain.conversation import ConversationState, Message, MessageAttachment, Role
from app.domain.intent import IntentAnalysis, IntentComplexity
from app.domain.memory import FactExtractionResult, MemoryRecord, MemoryType
from app.domain.plan import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.domain.safety_flag import SafetyFlag
from app.domain.session import SessionState, UserPreferences
from app.domain.tool_result import ToolResult

__all__ = [
    # Content
    "ContentType",
    "DocumentReference",
    "ContentSource",
    "ArtifactHandle",
    # Conversation
    "Role",
    "MessageAttachment",
    "Message",
    "ConversationState",
    # Memory
    "MemoryType",
    "MemoryRecord",
    "FactExtractionResult",
    # Plan
    "SafetyTier",
    "StepStatus",
    "ToolCall",
    "ExecutionStep",
    "ExecutionPlan",
    # Session
    "UserPreferences",
    "SessionState",
    # Safety / results (Sprint 3 contract)
    "SafetyFlag",
    "ToolResult",
    "IntentAnalysis",
    "IntentComplexity",
    # Sprint 3 typed-state contract (LangGraph, ADR-006)
    "CognitiveState",
]
