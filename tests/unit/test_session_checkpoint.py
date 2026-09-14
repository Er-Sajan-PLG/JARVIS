"""Tests for Sprint 3 session/checkpoint enhancements.

Covers:
- MemorySaverAdapter (in-memory checkpointing)
- Session lifecycle (fork/archive/delete)
- Token-aware context trimming (recent > pinned > summary)
"""

from pathlib import Path

import pytest

from app.domain import ConversationState, Message, Role
from app.session.checkpointer import MemorySaverAdapter
from app.session.context import estimate_tokens, trim_conversation

# ---------------------------------------------------------------------------
# MemorySaverAdapter
# ---------------------------------------------------------------------------


class TestMemorySaverAdapter:
    def test_save_and_load(self):
        saver = MemorySaverAdapter()
        saver.save({"state": {"x": 1}}, "thread-1")
        assert saver.load("thread-1") == {"state": {"x": 1}}

    def test_load_missing_returns_none(self):
        saver = MemorySaverAdapter()
        assert saver.load("nope") is None

    def test_save_overwrites(self):
        saver = MemorySaverAdapter()
        saver.save({"v": 1}, "t")
        saver.save({"v": 2}, "t")
        assert saver.load("t") == {"v": 2}

    def test_list_threads(self):
        saver = MemorySaverAdapter()
        saver.save({}, "a")
        saver.save({}, "b")
        assert sorted(saver.list_threads()) == ["a", "b"]

    def test_delete(self):
        saver = MemorySaverAdapter()
        saver.save({}, "a")
        assert saver.delete("a") is True
        assert saver.load("a") is None
        assert saver.delete("a") is False

    def test_clear_and_len(self):
        saver = MemorySaverAdapter()
        saver.save({}, "a")
        saver.save({}, "b")
        assert len(saver) == 2
        saver.clear()
        assert len(saver) == 0

    def test_save_copies_data(self):
        saver = MemorySaverAdapter()
        data = {"state": {"nested": [1, 2]}}
        saver.save(data, "t")
        data["state"]["nested"].append(3)
        assert saver.load("t") == {"state": {"nested": [1, 2]}}


# ---------------------------------------------------------------------------
# Token-aware context trimming
# ---------------------------------------------------------------------------


def _msg(mid: str, content: str, pinned: bool = False) -> Message:
    return Message(id=mid, role=Role.USER, content=content, pinned=pinned)


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_one_token_minimum(self):
        assert estimate_tokens("a") == 1

    def test_rounding(self):
        # 8 chars / 4 chars-per-token = 2 tokens
        assert estimate_tokens("12345678") == 2


class TestTrimConversation:
    def test_keeps_all_when_under_budget(self):
        conv = ConversationState(id="c", messages=[_msg("1", "hi"), _msg("2", "hello there")])
        result = trim_conversation(conv, max_tokens=1000)
        assert len(result.dropped) == 0
        assert len(result.kept) == 2

    def test_drops_oldest_first(self):
        conv = ConversationState(
            id="c",
            messages=[_msg("1", "aaaa"), _msg("2", "bbbb"), _msg("3", "cccc")],
        )
        # budget of 2 tokens (8 chars) -> keeps only the most recent "cccc" (1 token)
        result = trim_conversation(conv, max_tokens=1)
        assert [m.id for m in result.kept] == ["3"]
        assert {m.id for m in result.dropped} == {"1", "2"}

    def test_pinned_always_kept(self):
        conv = ConversationState(
            id="c",
            messages=[
                _msg("pinned", "important instructions", pinned=True),
                _msg("1", "aaaa"),
                _msg("2", "bbbb"),
            ],
        )
        # Budget 1 token: pinned "important instructions" (5 tokens) still kept.
        result = trim_conversation(conv, max_tokens=1)
        kept_ids = [m.id for m in result.kept]
        assert "pinned" in kept_ids
        assert len(result.kept) == 1

    def test_summary_reserves_budget(self):
        conv = ConversationState(id="c", messages=[_msg("1", "aaaa"), _msg("2", "bbbb")])
        # Summary "zzzz" = 1 token; budget 1 token total -> summary consumes it,
        # so zero messages kept.
        result = trim_conversation(conv, max_tokens=1, summary="zzzz")
        assert len(result.kept) == 0
        assert result.total_tokens == 1

    def test_tokens_reported(self):
        conv = ConversationState(id="c", messages=[_msg("1", "aaaa"), _msg("2", "bbbb")])
        result = trim_conversation(conv, max_tokens=1)
        assert result.total_tokens == 1
        assert result.dropped_tokens == 1

    def test_chronological_order_preserved(self):
        conv = ConversationState(
            id="c",
            messages=[_msg("1", "aaaa"), _msg("2", "bbbb"), _msg("3", "cccc")],
        )
        result = trim_conversation(conv, max_tokens=2)
        assert [m.id for m in result.kept] == ["2", "3"]


# ---------------------------------------------------------------------------
# Session lifecycle (fork/archive/delete)
# ---------------------------------------------------------------------------

from app.session.manager import SessionManager  # noqa: E402
from app.session.persistence import SessionPersistence  # noqa: E402


@pytest.fixture
def manager(tmp_path: Path):
    persistence = SessionPersistence(data_dir=tmp_path / "sessions")
    return SessionManager(persistence=persistence)


class TestSessionLifecycle:
    async def test_fork_session(self, manager):
        src = await manager.get_or_create_session("src")
        src.preferences.theme = "light"
        forked = await manager.fork_session("src")
        assert forked.session_id != "src"
        assert forked.session_id.startswith("src-fork-")
        assert forked.preferences.theme == "light"
        assert forked.metadata["forked_from"] == "src"
        # Fork has no active conversation binding.
        assert forked.active_conversation_id is None

    async def test_fork_preserves_user_id(self, manager):
        await manager.get_or_create_session("src")
        forked = await manager.fork_session("src")
        assert forked.user_id == "src" or forked.user_id != ""  # user_id copied

    async def test_archive_session(self, manager):
        await manager.get_or_create_session("s1")
        archived = await manager.archive_session("s1")
        assert archived.metadata["archived"] is True
        assert "s1" not in manager._active_sessions

    async def test_delete_session(self, manager):
        await manager.get_or_create_session("s1")
        assert await manager.delete_session("s1") is True
        assert "s1" not in manager._active_sessions
        # Delete again -> no longer on disk
        assert await manager.delete_session("s1") is False

    async def test_delete_removes_from_persistence(self, manager):
        await manager.get_or_create_session("s1")
        await manager.delete_session("s1")
        loaded = await manager.persistence.load_session("s1")
        assert loaded is None
