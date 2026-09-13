"""Unit tests for app/conversation/manager.py (ConversationManager, Message)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config.settings import ConversationConfig
from app.conversation.manager import ConversationManager, Message


def test_message_dataclass_methods() -> None:
    msg = Message(role="user", content="Hello", metadata={"client": "cli"}, pinned=True)
    d = msg.to_dict()
    assert d["role"] == "user"
    assert d["content"] == "Hello"
    assert d["metadata"] == {"client": "cli"}
    assert d["pinned"] is True
    assert "timestamp" in d

    restored = Message.from_dict(d)
    assert restored.role == "user"
    assert restored.content == "Hello"
    assert restored.metadata == {"client": "cli"}
    assert restored.pinned is True

    openai_fmt = msg.to_openai_format()
    assert openai_fmt == {"role": "user", "content": "Hello"}


def test_conversation_manager_crud(tmp_path: Path) -> None:
    conv_file = tmp_path / "chat.json"
    cfg = ConversationConfig(max_recent_messages=5, save_on_every_message=True)
    mgr = ConversationManager(path=str(conv_file), config=cfg)

    assert mgr.count() == 0
    assert mgr.get_all() == []
    assert mgr.get_summary() == ""
    assert mgr.is_dirty is False

    # Add messages
    mgr.add_message("user", "What is AI?")
    m2 = mgr.add_message("assistant", "Artificial Intelligence is...")
    m3 = mgr.add_message("user", "Explain ML.")

    assert mgr.count() == 3
    assert mgr.get_recent(limit=2) == [m2, m3]
    assert len(mgr.get_recent_formatted(limit=2)) == 2
    assert mgr.get_recent_formatted(limit=1)[0]["content"] == "Explain ML."

    # Pop message
    popped = mgr.pop_last_message()
    assert popped == m3
    assert mgr.count() == 2

    # Pop until empty
    mgr.pop_last_message()
    mgr.pop_last_message()
    assert mgr.pop_last_message() is None

    # Summary
    mgr.set_summary("Discussion on AI")
    assert mgr.get_summary() == "Discussion on AI"

    # Clear
    mgr.clear()
    assert mgr.count() == 0
    assert mgr.get_summary() == ""


def test_conversation_manager_pins_and_search(tmp_path: Path) -> None:
    conv_file = tmp_path / "chat.json"
    mgr = ConversationManager(path=str(conv_file))

    mgr.add_message("user", "Remember this secret code: 12345")
    mgr.add_message("assistant", "Understood.")
    mgr.add_message("user", "Another message with code word")

    # Pin toggle
    assert mgr.toggle_pin(0) is True
    assert mgr.toggle_pin(0) is False
    assert mgr.toggle_pin(0) is True
    # Invalid index
    assert mgr.toggle_pin(99) is False

    pinned = mgr.get_pinned_messages()
    assert len(pinned) == 1
    assert pinned[0].content == "Remember this secret code: 12345"

    # Search
    assert mgr.search_messages("") == []
    assert mgr.search_messages("   ") == []

    results = mgr.search_messages("CODE")
    assert len(results) == 2
    assert results[0]["index"] == 0
    assert results[0]["pinned"] is True
    assert results[1]["index"] == 2


def test_conversation_manager_persistence_and_reload(tmp_path: Path) -> None:
    conv_file = tmp_path / "persistent.json"
    cfg = ConversationConfig(save_on_every_message=False)
    mgr = ConversationManager(path=str(conv_file), config=cfg)

    mgr.add_message("user", "Persistent message")
    assert mgr.is_dirty is True
    mgr.save_if_dirty()
    assert mgr.is_dirty is False
    mgr.set_summary("Test summary")
    assert mgr.is_dirty is False

    # Reload from disk
    mgr2 = ConversationManager(path=str(conv_file))
    assert mgr2.count() == 1
    assert mgr2.get_summary() == "Test summary"
    assert mgr2.get_all()[0].content == "Persistent message"
    assert len(mgr2.conversation) == 1


def test_conversation_manager_load_legacy_formats(tmp_path: Path) -> None:
    # 1. V1 list format
    list_file = tmp_path / "v1_list.json"
    list_file.write_text(
        json.dumps(
            [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Msg 2"},
                "invalid_item_skipped",
            ]
        ),
        encoding="utf-8",
    )
    mgr_list = ConversationManager(path=str(list_file))
    assert mgr_list.count() == 2

    # 2. V1 conversation key format
    dict_file = tmp_path / "v1_dict.json"
    dict_file.write_text(
        json.dumps(
            {
                "conversation": [
                    {"role": "user", "content": "Msg from dict"},
                ]
            }
        ),
        encoding="utf-8",
    )
    mgr_dict = ConversationManager(path=str(dict_file))
    assert mgr_dict.count() == 1
    assert mgr_dict.get_all()[0].content == "Msg from dict"


def test_conversation_manager_load_corrupted(tmp_path: Path) -> None:
    bad_file = tmp_path / "corrupt_chat.json"
    bad_file.write_text("{broken json", encoding="utf-8")

    mgr = ConversationManager(path=str(bad_file))
    assert mgr.count() == 0  # Starts empty gracefully after quarantine


def test_conversation_manager_save_error_handling(tmp_path: Path) -> None:
    conv_file = tmp_path / "fail.json"
    mgr = ConversationManager(
        path=str(conv_file), config=ConversationConfig(save_on_every_message=False)
    )
    mgr.add_message("user", "Hello")

    with patch("os.replace", side_effect=OSError("Disk full")):
        with pytest.raises(OSError):
            mgr.save()
        assert mgr.is_dirty is True
