"""Unit tests for app/session: checkpointer, persistence, and manager."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.domain import ConversationState, Message, Role, SessionState, UserPreferences
from app.session.checkpointer import (
    Checkpoint,
    LangGraphCheckpointer,
    MemorySaverAdapter,
    get_checkpointer,
)
from app.session.manager import SessionManager
from app.session.persistence import SessionPersistence


def test_checkpoint_dataclass_and_adapter() -> None:
    now = datetime.now(UTC)
    cp = Checkpoint(
        checkpoint_id="c1",
        thread_id="t1",
        checkpoint_data={"step": 1},
        metadata={"user": "u1"},
        created_at=now,
        parent_checkpoint_id=None,
    )
    assert cp.checkpoint_id == "c1"
    assert cp.thread_id == "t1"

    adapter = MemorySaverAdapter()
    saved = adapter.save({"state": 1}, "t1")
    assert saved == "memory-t1"
    loaded = adapter.load("t1")
    assert loaded == {"thread_id": "t1", "state": {}}


def test_langgraph_checkpointer_sqlite(tmp_path: Path) -> None:
    db_file = tmp_path / "test_cp.db"
    checkpointer = LangGraphCheckpointer(db_path=str(db_file))

    # Initial state for thread
    assert checkpointer.list_checkpoints("thread_1") == []
    assert checkpointer.get_latest_checkpoint("thread_1") is None

    # Save checkpoint
    checkpointer.save_checkpoint(
        thread_id="thread_1",
        checkpoint_data={"state": "started"},
        metadata={"version": "1.0"},
    )

    # List checkpoints
    cps = checkpointer.list_checkpoints("thread_1")
    assert len(cps) == 1
    cp_row = cps[0]
    assert cp_row["thread_id"] == "thread_1"
    assert cp_row["checkpoint_data"] == {"state": "started"}
    assert cp_row["metadata"] == {"version": "1.0"}

    # Get by ID
    retrieved = checkpointer.get_checkpoint(cp_row["checkpoint_id"])
    assert retrieved is not None
    assert retrieved["checkpoint_id"] == cp_row["checkpoint_id"]

    # Get latest
    latest = checkpointer.get_latest_checkpoint("thread_1")
    assert latest is not None
    assert latest["checkpoint_id"] == cp_row["checkpoint_id"]

    # Non-existent checkpoint
    assert checkpointer.get_checkpoint("missing_id") is None

    # Delete single checkpoint
    assert checkpointer.delete_checkpoint(cp_row["checkpoint_id"]) is True
    assert checkpointer.get_checkpoint(cp_row["checkpoint_id"]) is None
    assert checkpointer.delete_checkpoint("already_deleted") is False

    # Multiple checkpoints & delete_thread_checkpoints
    checkpointer.save_checkpoint("thread_2", {"a": 1}, {})
    checkpointer.save_checkpoint("thread_2", {"a": 2}, {})
    assert len(checkpointer.list_checkpoints("thread_2")) == 2
    deleted_count = checkpointer.delete_thread_checkpoints("thread_2")
    assert deleted_count == 2
    assert len(checkpointer.list_checkpoints("thread_2")) == 0


def test_checkpointer_singleton() -> None:
    cp1 = get_checkpointer()
    cp2 = get_checkpointer()
    assert cp1 is cp2


@pytest.mark.asyncio
async def test_session_persistence_files(tmp_path: Path) -> None:
    pers = SessionPersistence(data_dir=tmp_path)

    # 1. Non-existent session
    assert await pers.load_session("missing") is None

    # 2. Save & Load Session
    session = SessionState(session_id="s1", user_id="alice")
    session.preferences.theme = "light"
    session.preferences.custom_instructions = "Be helpful"
    session.metadata = {"client": "web"}
    await pers.save_session(session)

    loaded_session = await pers.load_session("s1")
    assert loaded_session is not None
    assert loaded_session.session_id == "s1"
    assert loaded_session.user_id == "alice"
    assert loaded_session.preferences.theme == "light"
    assert loaded_session.preferences.custom_instructions == "Be helpful"
    assert loaded_session.metadata == {"client": "web"}

    # 3. Corrupted session file
    corrupt_session = tmp_path / "session_corrupt.json"
    corrupt_session.write_text("{bad json", encoding="utf-8")
    assert await pers.load_session("corrupt") is None

    # 4. Save & Load Conversation
    conv = ConversationState(
        id="conv_1",
        title="My Chat",
        messages=[
            Message(id="m1", role=Role.USER, content="Hi", pinned=True),
            Message(id="m2", role=Role.ASSISTANT, content="Hello"),
        ],
    )
    await pers.save_conversation(conv)

    loaded_conv = await pers.load_conversation("conv_1")
    assert loaded_conv is not None
    assert loaded_conv.id == "conv_1"
    assert loaded_conv.title == "My Chat"
    assert len(loaded_conv.messages) == 2
    assert loaded_conv.messages[0].pinned is True
    assert loaded_conv.messages[0].role == Role.USER

    # 5. Non-existent conversation
    assert await pers.load_conversation("missing_conv") is None

    # 6. Corrupted conversation
    corrupt_conv = tmp_path / "conv_bad.json"
    corrupt_conv.write_text("{invalid", encoding="utf-8")
    assert await pers.load_conversation("bad") is None


@pytest.mark.asyncio
async def test_session_persistence_postgres_branch() -> None:
    pers = SessionPersistence(db_url="postgresql://localhost:5432/jarvis")
    assert pers._use_postgres is True
    with patch.object(pers, "_save_session_pg", new_callable=AsyncMock) as mock_pg:
        session = SessionState(session_id="pg_s1")
        await pers.save_session(session)
        mock_pg.assert_called_once_with(session)


@pytest.mark.asyncio
async def test_session_manager_workflow(tmp_path: Path) -> None:
    pers = SessionPersistence(data_dir=tmp_path)
    mgr = SessionManager(persistence=pers)

    # 1. Create default session
    s1 = await mgr.get_or_create_session("sess_1")
    assert s1.session_id == "sess_1"
    assert s1.user_id == "user_default"

    # 2. Cached retrieval
    s1_cached = await mgr.get_or_create_session("sess_1")
    assert s1_cached is s1

    # 3. Create conversation for session
    conv1 = await mgr.get_or_create_conversation(session_id="sess_1")
    assert conv1.id is not None
    assert s1.active_conversation_id == conv1.id

    # 4. Cached conversation retrieval
    conv1_cached = await mgr.get_or_create_conversation(
        conversation_id=conv1.id, session_id="sess_1"
    )
    assert conv1_cached is conv1

    # 5. Update preferences
    new_prefs = UserPreferences(theme="light", active_model_id="claude-3-5")
    updated_session = await mgr.update_preferences("sess_1", new_prefs)
    assert updated_session.preferences.theme == "light"
    assert updated_session.preferences.active_model_id == "claude-3-5"

    # 6. New manager instance loads session and conversation from persistence
    mgr2 = SessionManager(persistence=pers)
    s1_reloaded = await mgr2.get_or_create_session("sess_1")
    assert s1_reloaded.session_id == "sess_1"
    assert s1_reloaded.preferences.theme == "light"

    conv1_reloaded = await mgr2.get_or_create_conversation(
        conversation_id=conv1.id, session_id="sess_1"
    )
    assert conv1_reloaded.id == conv1.id
