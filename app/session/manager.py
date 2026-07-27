"""Live Session Manager.

Manages active sessions, active conversation bindings, user preferences, and persistence orchestration.
"""

import logging
from datetime import datetime, timezone
import uuid

from app.domain import ConversationState, SessionState, UserPreferences
from app.session.persistence import SessionPersistence

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages active user sessions and conversation context bindings."""

    def __init__(self, persistence: SessionPersistence | None = None) -> None:
        self.persistence = persistence or SessionPersistence()
        self._active_sessions: dict[str, SessionState] = {}
        self._active_conversations: dict[str, ConversationState] = {}

    async def get_or_create_session(self, session_id: str = "default") -> SessionState:
        """Retrieve existing active session or load/create one."""
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            session.last_active_at = datetime.now(timezone.utc)
            return session

        loaded = await self.persistence.load_session(session_id)
        if loaded:
            self._active_sessions[session_id] = loaded
            return loaded

        # Create new default session
        new_session = SessionState(
            session_id=session_id,
            user_id="user_default",
            preferences=UserPreferences(),
        )
        self._active_sessions[session_id] = new_session
        await self.persistence.save_session(new_session)
        return new_session

    async def get_or_create_conversation(
        self, conversation_id: str | None = None, session_id: str = "default"
    ) -> ConversationState:
        """Get or create active conversation thread for session."""
        session = await self.get_or_create_session(session_id)
        target_id = conversation_id or session.active_conversation_id or str(uuid.uuid4())

        if target_id in self._active_conversations:
            return self._active_conversations[target_id]

        loaded = await self.persistence.load_conversation(target_id)
        if loaded:
            self._active_conversations[target_id] = loaded
            session.active_conversation_id = target_id
            await self.persistence.save_session(session)
            return loaded

        new_conv = ConversationState(id=target_id, title="New Chat")
        self._active_conversations[target_id] = new_conv
        session.active_conversation_id = target_id
        await self.persistence.save_session(session)
        await self.persistence.save_conversation(new_conv)
        return new_conv

    async def update_preferences(self, session_id: str, preferences: UserPreferences) -> SessionState:
        """Update preferences for active session."""
        session = await self.get_or_create_session(session_id)
        session.preferences = preferences
        await self.persistence.save_session(session)
        return session
