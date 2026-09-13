"""Unit tests for app/context: ContextBuilder and ContextWindowManager."""

from unittest.mock import MagicMock

from app.context.builder import ContextBuilder
from app.context.manager import ContextWindowManager
from app.domain import (
    ContentSource,
    ContentType,
    ConversationState,
    MemoryRecord,
    Message,
    Role,
    SessionState,
)


def test_context_builder_build_system_prompt() -> None:
    mock_loader = MagicMock()
    mock_loader.render.return_value = "Rendered System Base"

    builder = ContextBuilder(prompt_loader=mock_loader)
    session = SessionState(session_id="s123", user_id="u456")
    session.preferences.custom_instructions = "Custom instructions"

    prompt = builder.build_system_prompt(session, assistant_name="JARVIS-X")
    assert prompt == "Rendered System Base"
    mock_loader.render.assert_called_once_with(
        "system_base.md",
        assistant_name="JARVIS-X",
        user_id="u456",
        session_id="s123",
        theme="dark",
        custom_instructions="Custom instructions",
    )


def test_context_builder_assemble_context_full() -> None:
    mock_loader = MagicMock()
    mock_loader.render.return_value = "System Base Prompt"

    builder = ContextBuilder(prompt_loader=mock_loader)
    session = SessionState(session_id="s1")
    conv = ConversationState(
        id="c1",
        messages=[
            Message(id="m1", role=Role.USER, content="Hello"),
            Message(id="m2", role=Role.ASSISTANT, content="Hi there"),
        ],
    )

    memories = [MemoryRecord(id="rec1", key="favorite_food", value="pizza", category="preferences")]
    sources = [
        ContentSource(
            source_id="src1",
            content_type=ContentType.TEXT,
            uri="file:///note.txt",
            title="Note",
            raw_text="Important content here",
        )
    ]

    messages = builder.assemble_context(
        session=session,
        conversation=conv,
        sources=sources,
        memories=memories,
        max_context_tokens=8192,
    )

    assert len(messages) == 3
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "Relevant User Memories:" in system_msg["content"]
    assert "[preferences] favorite_food: pizza" in system_msg["content"]
    assert "Context Documents & Files:" in system_msg["content"]
    assert "Important content here" in system_msg["content"]

    assert messages[1] == {"role": "user", "content": "Hello"}
    assert messages[2] == {"role": "assistant", "content": "Hi there"}


def test_context_builder_assemble_context_truncation() -> None:
    mock_loader = MagicMock()
    mock_loader.render.return_value = "System Prompt"

    builder = ContextBuilder(prompt_loader=mock_loader)
    session = SessionState(session_id="s1")

    # Create 50 messages of 100 characters each
    long_history = [
        Message(
            id=f"m_{i}",
            role=Role.USER if i % 2 == 0 else Role.ASSISTANT,
            content=f"Message {i} " + "X" * 100,
        )
        for i in range(50)
    ]
    conv = ConversationState(id="c1", messages=long_history)

    # Budget remaining = max(1000, 2500 - system_tokens - 1000) = 1400 tokens
    messages = builder.assemble_context(session=session, conversation=conv, max_context_tokens=2500)

    # System message + truncated history
    assert len(messages) > 1
    assert len(messages) < len(long_history) + 1
    # Most recent message (m_49) must be preserved
    assert messages[-1]["content"].startswith("Message 49")


def test_context_window_manager_content_to_text() -> None:
    # None
    assert ContextWindowManager._content_to_text(None) == ""
    # Str
    assert ContextWindowManager._content_to_text("hello") == "hello"
    # List of blocks
    blocks = [{"text": "part 1"}, {"text": "part 2"}, {"other": "ignored"}]
    assert ContextWindowManager._content_to_text(blocks) == "part 1\npart 2"
    # Non-string object
    assert ContextWindowManager._content_to_text(12345) == "12345"


def test_context_window_manager_group_into_pairs() -> None:
    cwm = ContextWindowManager()

    # Empty
    assert cwm._group_into_pairs([]) == []

    # Standard alternating user -> assistant
    msgs = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    pairs = cwm._group_into_pairs(msgs)
    assert len(pairs) == 2
    assert pairs[0] == [msgs[0], msgs[1]]
    assert pairs[1] == [msgs[2], msgs[3]]

    # Two consecutive user messages
    consecutive_user = [
        {"role": "user", "content": "u1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a1"},
    ]
    pairs_consec = cwm._group_into_pairs(consecutive_user)
    assert len(pairs_consec) == 2
    assert pairs_consec[0] == [consecutive_user[0]]
    assert pairs_consec[1] == [consecutive_user[1], consecutive_user[2]]


def test_context_window_manager_fit() -> None:
    # Custom deterministic token counter: length of words
    def dummy_counter(text: str) -> int:
        return len(text.split())

    cwm = ContextWindowManager(max_tokens=50, safety_margin=5, token_counter=dummy_counter)

    msgs = [
        {"role": "system", "content": "system prompt"},  # 2 words + 4 overhead = 6 tokens
        {"role": "user", "content": "old question"},  # 2 words + 4 = 6 tokens
        {
            "role": "assistant",
            "content": "old answer",
        },  # 2 words + 4 = 6 tokens -> pair 1: 12 tokens
        {"role": "user", "content": "new question"},  # 2 words + 4 = 6 tokens
        {
            "role": "assistant",
            "content": "new answer",
        },  # 2 words + 4 = 6 tokens -> pair 2: 12 tokens
    ]

    # Total tokens: 6 + 12 + 12 = 30 tokens <= effective_max 45
    fitted = cwm.fit(msgs)
    assert len(fitted) == 5
    stats = cwm.get_stats()
    assert stats is not None
    assert stats.was_trimmed is False
    assert stats.messages_trimmed == 0
    assert stats.pairs_kept == 2

    # Fit with tight max_tokens (e.g. 20 tokens -> effective 20, system is 6, available is 14)
    # Only pair 2 (12 tokens) fits
    fitted_tight = cwm.fit(msgs, max_tokens=20)
    assert len(fitted_tight) == 3  # system + new question + new answer
    assert fitted_tight[0]["role"] == "system"
    assert fitted_tight[1]["content"] == "new question"
    assert fitted_tight[2]["content"] == "new answer"
    assert cwm.last_stats.was_trimmed is True
    assert cwm.last_stats.pairs_trimmed == 1


def test_context_window_manager_system_prompt_overflow() -> None:
    def count_chars(text: str) -> int:
        return len(text)

    cwm = ContextWindowManager(max_tokens=20, safety_margin=5, token_counter=count_chars)
    msgs = [
        {"role": "system", "content": "a" * 100},  # 104 tokens > 15
        {"role": "user", "content": "hi"},
    ]
    fitted = cwm.fit(msgs)
    assert len(fitted) == 1
    assert fitted[0]["role"] == "system"
    assert cwm.last_stats.was_trimmed is True
    assert cwm.last_stats.pairs_kept == 0


def test_context_window_manager_newest_pair_kept_even_if_overflow() -> None:
    def count_chars(text: str) -> int:
        return len(text)

    cwm = ContextWindowManager(max_tokens=30, safety_margin=0, token_counter=count_chars)
    msgs = [
        {"role": "system", "content": "sys"},  # 3 + 4 = 7 tokens -> available = 23
        {"role": "user", "content": "a" * 50},  # 50 + 4 = 54 tokens (overflows available)
    ]
    fitted = cwm.fit(msgs)
    # The active user prompt should still be kept
    assert len(fitted) == 2
    assert cwm.last_stats.was_trimmed is True
    assert cwm.last_stats.pairs_kept == 1


def test_context_window_manager_misc() -> None:
    cwm = ContextWindowManager(token_counter=lambda t: len(t))
    assert cwm.count_tokens_text("test") == 4
    info = cwm.get_tokenizer_info()
    assert isinstance(info, dict)
