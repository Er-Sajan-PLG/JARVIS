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

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config.settings import ConversationConfig, get_settings
from app.utils.corruption import backup_corrupt_file, report_corruption

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single conversation message"""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    pinned: bool = False  # For pin/favorite messages

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
            pinned=data.get("pinned", False),
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

    @property
    def is_dirty(self) -> bool:
        """Whether there are unsaved changes."""
        return self._dirty

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

    def pop_last_message(self) -> "Message | None":
        """
        Remove the last message from the conversation.
        Used for error recovery if a model fails to respond.
        """
        if self._messages:
            popped = self._messages.pop()
            # Mark dirty BEFORE saving: with save_on_every_message=True the
            # prior add_message() already flushed and reset _dirty, so without
            # this flag the removal is never persisted and the "popped" message
            # silently reappears on reload (broken save/load cycle).
            self._dirty = True
            self.save()
            return popped
        return None

    # Pin/Favorite methods
    def toggle_pin(self, message_index: int) -> bool:
        """Toggle pin status of a message by index."""
        if 0 <= message_index < len(self._messages):
            self._messages[message_index].pinned = not self._messages[message_index].pinned
            self._dirty = True
            self.save()
            return self._messages[message_index].pinned
        return False

    def get_pinned_messages(self) -> list[Message]:
        """Get all pinned messages."""
        return [m for m in self._messages if m.pinned]

    def search_messages(self, query: str) -> list[dict]:
        """Search messages by content."""
        q = query.lower().strip()
        if not q:
            return []
        results = []
        for i, m in enumerate(self._messages):
            if q in m.content.lower():
                results.append(
                    {
                        "index": i,
                        "role": m.role,
                        "content": m.content[:200] + ("..." if len(m.content) > 200 else ""),
                        "timestamp": m.timestamp,
                        "pinned": m.pinned,
                    }
                )
        return results

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

        # Write to a temp file in the SAME directory, then atomically replace
        # the target with os.replace(). Opening the target directly with "w"
        # truncates it first, so an interrupted write leaves a truncated/corrupt
        # file and loses the whole conversation. os.replace() is atomic on
        # POSIX/Windows, so readers only ever see the old or the new file.
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            # Clean up the partial temp file, then re-raise so callers know the
            # write failed and _dirty stays True for a retry.
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise

        self._dirty = False

    def save_if_dirty(self):
        """Public method to save only if changes were made"""
        self.save()

    def _load(self):
        """Load conversation from disk"""
        if not self.path.exists():
            return

        try:
            with open(self.path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # Corruption / unreadable file: do NOT silently start empty.
            # Quarantine the bad file so the next save() can't destroy it,
            # then warn loudly.
            backup = backup_corrupt_file(self.path)
            report_corruption(logger, "conversation", self.path, exc, backup)
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
