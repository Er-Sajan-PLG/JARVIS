"""Unit tests for Phase 3: MemoryService and ContextBuilder.

NOTE ON ISOLATION: these tests previously constructed ``MemoryService()`` with no
path override, which points at the REAL store (``data/memories.json``). Each run
wrote a ``user_name: Alice`` record into the user's live memory — it survived
every manual cleanup because the test suite kept re-creating it. The service is
now bound to a tmp_path store so unit tests cannot touch user data again.
"""

from pathlib import Path
import tempfile
import pytest

from app.context.builder import ContextBuilder
from app.domain import ContentSource, ContentType, ConversationState, MemoryRecord, MemoryType, Message, Role, SessionState, UserPreferences
from app.memory.service import MemoryService


@pytest.fixture()
def isolated_service(tmp_path: Path) -> MemoryService:
    """A MemoryService whose store is a temp file, never the user's real store.

    ``MemoryStore`` accepts an explicit path, so bind it there rather than
    monkeypatching internals — that keeps the isolation honest.
    """
    from app.memory.manager import MemoryManager
    from app.memory.store import MemoryStore

    manager = MemoryManager()
    manager._store = MemoryStore(path=tmp_path / "memories.json")  # noqa: SLF001
    return MemoryService(manager=manager)


def test_memory_service_store_and_search(isolated_service: MemoryService) -> None:
    """Verify MemoryService stores and retrieves MemoryRecord domain models."""
    ms = isolated_service

    # Store memory
    import asyncio
    async def _run() -> None:
        rec = await ms.store_memory(
            key="user_name",
            value="TestValueNotReal",
            category="preference",
            memory_type=MemoryType.PREFERENCE,
        )
        assert rec.key == "user_name"
        assert rec.value == "TestValueNotReal"
        assert rec.memory_type == MemoryType.PREFERENCE

        # Retrieve memory
        results = await ms.search_memories("user_name TestValueNotReal")
        assert isinstance(results, list)

    asyncio.run(_run())


def test_context_builder_assembly() -> None:
    """Verify ContextBuilder dynamically assembles prompt context payload."""
    cb = ContextBuilder()

    session = SessionState(
        session_id="sess_123",
        user_id="user_1",
        preferences=UserPreferences(theme="dark", custom_instructions="Focus on clean code."),
    )

    conv = ConversationState(id="conv_1")
    conv.add_message(Message(id="m1", role=Role.USER, content="Hello JARVIS!"))
    conv.add_message(Message(id="m2", role=Role.ASSISTANT, content="Hello! How can I assist?"))
    conv.add_message(Message(id="m3", role=Role.USER, content="Explain recursion."))

    sources = [
        ContentSource(
            source_id="src_1",
            content_type=ContentType.CODE,
            uri="file:///test.py",
            title="test.py",
            raw_text="def recurse(n):\n    return recurse(n-1) if n > 0 else 0",
        )
    ]

    memories = [
        MemoryRecord(
            id="mem_1",
            key="user_name",
            value="Alice",
            category="user_info",
            memory_type=MemoryType.FACT,
        )
    ]

    payload = cb.assemble_context(
        session=session,
        conversation=conv,
        sources=sources,
        memories=memories,
        max_context_tokens=4096,
    )

    assert isinstance(payload, list)
    assert len(payload) >= 2
    assert payload[0]["role"] == "system"
    assert "JARVIS" in payload[0]["content"]
    assert "Alice" in payload[0]["content"]
    assert "test.py" in payload[0]["content"]
    assert payload[-1]["content"] == "Explain recursion."
