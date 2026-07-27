"""JARVIS Domain Layer Package.

Exports pure business domain entities. Guaranteed zero external framework dependencies.
"""

from app.domain.content import ArtifactHandle, ContentSource, ContentType, DocumentReference
from app.domain.conversation import ConversationState, Message, MessageAttachment, Role
from app.domain.memory import FactExtractionResult, MemoryRecord, MemoryType
from app.domain.plan import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.domain.session import SessionState, UserPreferences

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
]
