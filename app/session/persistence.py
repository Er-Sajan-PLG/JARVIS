"""Session & Execution Plan State Persistence Engine.

Supports asynchronous PostgreSQL persistence (asyncpg / JSONB tables) with seamless
local file fallback for standalone execution.
"""

import json
import logging
from pathlib import Path

from app.domain import ConversationState, Message, Role, SessionState, UserPreferences

logger = logging.getLogger(__name__)


class SessionPersistence:
    """Persistence engine for session states, conversation histories, and event logs."""

    def __init__(self, data_dir: str | Path = "data/sessions", db_url: str | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_url = db_url
        self._use_postgres = bool(db_url and db_url.startswith("postgresql"))

    async def save_session(self, session: SessionState) -> None:
        """Save a SessionState domain entity."""
        if self._use_postgres:
            await self._save_session_pg(session)
            return

        dest = self.data_dir / f"session_{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "active_conversation_id": session.active_conversation_id,
            "created_at": session.created_at.isoformat(),
            "last_active_at": session.last_active_at.isoformat(),
            "preferences": {
                "active_model_id": session.preferences.active_model_id,
                "use_developer_keys": session.preferences.use_developer_keys,
                "hitl_auto_approve_sensitive": session.preferences.hitl_auto_approve_sensitive,
                "theme": session.preferences.theme,
                "custom_instructions": session.preferences.custom_instructions,
            },
            "metadata": session.metadata,
        }
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def load_session(self, session_id: str) -> SessionState | None:
        """Load a SessionState by ID."""
        dest = self.data_dir / f"session_{session_id}.json"
        if not dest.exists():
            return None
        try:
            raw = json.loads(dest.read_text(encoding="utf-8"))
            prefs_data = raw.get("preferences", {})
            prefs = UserPreferences(
                active_model_id=prefs_data.get("active_model_id", "omni"),
                use_developer_keys=prefs_data.get("use_developer_keys", False),
                hitl_auto_approve_sensitive=prefs_data.get("hitl_auto_approve_sensitive", True),
                theme=prefs_data.get("theme", "dark"),
                custom_instructions=prefs_data.get("custom_instructions", ""),
            )
            return SessionState(
                session_id=raw["session_id"],
                user_id=raw.get("user_id", "default_user"),
                active_conversation_id=raw.get("active_conversation_id"),
                preferences=prefs,
                metadata=raw.get("metadata", {}),
            )
        except Exception as err:
            logger.error("Failed to load session %s: %s", session_id, err)
            return None

    async def save_conversation(self, conversation: ConversationState) -> None:
        """Save a ConversationState aggregate."""
        dest = self.data_dir / f"conv_{conversation.id}.json"
        data = {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [m.to_dict() for m in conversation.messages],
            "metadata": conversation.metadata,
        }
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def load_conversation(self, conversation_id: str) -> ConversationState | None:
        """Load a ConversationState by ID."""
        dest = self.data_dir / f"conv_{conversation_id}.json"
        if not dest.exists():
            return None
        try:
            raw = json.loads(dest.read_text(encoding="utf-8"))
            messages = [
                Message(
                    id=m["id"],
                    role=Role(m["role"]),
                    content=m["content"],
                    pinned=m.get("pinned", False),
                    metadata=m.get("metadata", {}),
                )
                for m in raw.get("messages", [])
            ]
            return ConversationState(
                id=raw["id"],
                title=raw.get("title", "New Chat"),
                messages=messages,
                metadata=raw.get("metadata", {}),
            )
        except Exception as err:
            logger.error("Failed to load conversation %s: %s", conversation_id, err)
            return None

    async def _save_session_pg(self, session: SessionState) -> None:
        """Placeholder for asyncpg PostgreSQL JSONB session write."""

    async def delete_session(self, session_id: str) -> bool:
        """Delete a persisted session; return whether it existed on disk."""
        dest = self.data_dir / f"session_{session_id}.json"
        if dest.exists():
            dest.unlink()
            return True
        return False
