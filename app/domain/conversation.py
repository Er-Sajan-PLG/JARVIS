"""Pure Domain Entities: Message & Conversation State.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message sender role."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class MessageAttachment:
    """Attachment associated with a conversation message."""
    name: str
    size: int
    mime_type: str = "application/octet-stream"
    file_path: str | None = None
    content_preview: str | None = None


@dataclass
class Message:
    """Single message within a conversation."""
    id: str
    role: Role
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pinned: bool = False
    attachments: list[MessageAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "id": self.id,
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "pinned": self.pinned,
            "attachments": [
                {
                    "name": a.name,
                    "size": a.size,
                    "mime_type": a.mime_type,
                    "file_path": a.file_path,
                }
                for a in self.attachments
            ],
            "metadata": self.metadata,
        }


@dataclass
class ConversationState:
    """Aggregate domain entity representing a complete conversation thread."""
    id: str
    title: str = "New Chat"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        """Append a message and update last modified timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def message_count(self) -> int:
        """Total message count."""
        return len(self.messages)

    @property
    def preview(self) -> str:
        """Generate a short preview snippet from the first user message or last message."""
        for msg in self.messages:
            if msg.role == Role.USER and msg.content.strip():
                return msg.content[:80].strip()
        if self.messages:
            return self.messages[-1].content[:80].strip()
        return "Empty chat"
