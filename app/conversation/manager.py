#app/conversation/manager.py
"""
Conversation Manager for JARVIS v2.0

Handles:
1. Recent history
2. Summaries (future)
3. Retrieved memories (via prompt builder)

Interface:
    conversation.add_message(role, content)
    conversation.get_recent(limit)
    conversation.get_recent_formatted(limit)
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
import json

from app.config.settings import get_settings, ConversationConfig


@dataclass
class Message:
    """A single conversation message"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )
    
    def to_openai_format(self) -> dict:
        """Format for OpenAI API"""
        return {"role": self.role, "content": self.content}


class ConversationManager:
    """
    Manages conversation history.
    
    Future: Will integrate with summarization for long conversations.
    """
    
    def __init__(self, path: str = None, config: ConversationConfig = None):
        settings = get_settings()
        
        self.path = Path(path) if path else settings.paths.default_conversation
        self.config = config or settings.conversation
        
        self._messages: list[Message] = []
        self._summary: str = ""
        self._dirty: bool = False  # Track changes
        
        self._load()
    
    def add_message(self, role: str, content: str, metadata: dict = None) -> Message:
        """Add a message to the conversation."""
        message = Message(role=role, content=content, metadata=metadata or {})
        self._messages.append(message)
        self._dirty = True
        
        # Save based on config
        if self.config.save_on_every_message:
            self.save()
        
        return message
    
    def get_recent(self, limit: int = None) -> list[Message]:
        """Get the most recent messages."""
        limit = limit or self.config.max_recent_messages
        return list(self._messages[-limit:])
    
    def get_recent_formatted(self, limit: int = None) -> list[dict]:
        """Get recent messages in OpenAI format."""
        return [m.to_openai_format() for m in self.get_recent(limit)]
    
    def get_all(self) -> list[Message]:
        """Get all messages"""
        return list(self._messages)
    
    def count(self) -> int:
        """Return number of messages"""
        return len(self._messages)
    
    def clear(self):
        """Clear all messages"""
        self._messages.clear()
        self._summary = ""
        self._dirty = True
        self.save()
    
    def set_summary(self, summary: str):
        """Set conversation summary (future feature)"""
        self._summary = summary
        self._dirty = True
        self.save()
    
    def get_summary(self) -> str:
        """Get conversation summary"""
        return self._summary

    def pop_last_message(self) -> 'Message | None':
        """
        Remove the last message from the conversation.
        Used for error recovery if a model fails to respond.
        """
        if self._messages:
            popped = self._messages.pop()
            self.save()
            return popped
        return None
    
    def save(self):
        """Save conversation to disk"""
        if not self._dirty:
            return
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "2.0",
            "summary": self._summary,
            "messages": [m.to_dict() for m in self._messages],
        }
        
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        
        self._dirty = False
    
    def save_if_dirty(self):
        """Public method to save only if changes were made"""
        self.save()
    
    def _load(self):
        """Load conversation from disk"""
        if not self.path.exists():
            return
        
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        
        # V2 format
        if isinstance(data, dict) and "version" in data:
            self._summary = data.get("summary", "")
            self._messages = [Message.from_dict(m) for m in data.get("messages", [])]
        
        # V1 format (just a list)
        elif isinstance(data, list):
            self._messages = [Message.from_dict(m) for m in data if isinstance(m, dict)]
        
        # V1 format (dict with conversation key)
        elif isinstance(data, dict) and "conversation" in data:
            self._messages = [Message.from_dict(m) for m in data["conversation"]]
        
        self._dirty = False  # Fresh from disk
    
    # Legacy compatibility
    @property
    def conversation(self) -> list[dict]:
        """Legacy property"""
        return [m.to_openai_format() for m in self._messages]