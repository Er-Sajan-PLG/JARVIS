"""Live Session Manager.

Manages active sessions, active conversation bindings, user preferences, and
persistence orchestration.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.domain import ConversationState, SessionState, UserPreferences
from app.session.persistence import SessionPersistence

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages active user sessions and conversation context bindings."""

    def __init__(self, persistence: SessionPersistence | None = None) -> None:
        self.persistence = persistence or SessionPersistence()
        self._active_sessions: dict[str, SessionState] = {}
        self._active_conversations: dict[str, ConversationState] = {}

    def get_or_create_session_sync(self, session_id: str = "default") -> SessionState:
        """Synchronous wrapper for get_or_create_session."""
        import asyncio

        try:
            asyncio.get_running_loop()
            # We're in an async context — can't use run, so we return a coroutine
            # Callers in sync context should not hit this, but handle gracefully
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.get_or_create_session(session_id))
                return future.result()
        except RuntimeError:
            # No running loop — safe to use asyncio.run
            return asyncio.run(self.get_or_create_session(session_id))

    async def get_or_create_session(self, session_id: str = "default") -> SessionState:
        """Retrieve existing active session or load/create one."""
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            session.last_active_at = datetime.now(UTC)
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

    async def update_preferences(
        self, session_id: str, preferences: UserPreferences
    ) -> SessionState:
        """Update preferences for active session."""
        session = await self.get_or_create_session(session_id)
        session.preferences = preferences
        await self.persistence.save_session(session)
        return session

    async def fork_session(
        self,
        session_id: str,
        new_session_id: str | None = None,
    ) -> SessionState:
        """Fork an existing session into a new, independent session.

        Copies the source session's preferences and metadata, but starts the
        fork with a fresh conversation binding so the two sessions can diverge.
        """
        source = await self.get_or_create_session(session_id)
        target_id = new_session_id or f"{session_id}-fork-{uuid.uuid4().hex[:8]}"

        forked = SessionState(
            session_id=target_id,
            user_id=source.user_id,
            preferences=source.preferences,
            metadata={**source.metadata, "forked_from": session_id},
        )
        self._active_sessions[target_id] = forked
        await self.persistence.save_session(forked)
        return forked

    def fork_session_sync(self, session_id: str, new_session_id: str | None = None) -> SessionState:
        """Synchronous wrapper for fork_session."""
        import asyncio

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.fork_session(session_id, new_session_id))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.fork_session(session_id, new_session_id))

    async def archive_session(self, session_id: str) -> SessionState:
        """Mark a session as archived (keeps it out of the active set)."""
        session = await self.get_or_create_session(session_id)
        session.metadata["archived"] = True
        await self.persistence.save_session(session)
        self._active_sessions.pop(session_id, None)
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from the active set and persistence."""
        self._active_sessions.pop(session_id, None)
        return await self.persistence.delete_session(session_id)
