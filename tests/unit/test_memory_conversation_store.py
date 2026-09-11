"""Unit tests for conversation store in app/memory/conversation_store.py."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.memory.conversation_store import ConversationVectorStore


class DummyEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic in-memory embedding function."""

    def __init__(self):
        pass

    @classmethod
    def name(cls) -> str:
        return "dummy"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict):
        return cls()

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.2] * 8 for _ in input]


@dataclass
class DummyMessage:
    role: str
    content: str
    timestamp: float = 1700000000.0


@pytest.fixture
def store(tmp_path):
    """Fixture providing a ConversationVectorStore backed by tmp_path and dummy embeddings."""
    with patch(
        "app.memory.conversation_store.OllamaEmbeddingFunction",
        return_value=DummyEmbeddingFunction(),
    ):
        s = ConversationVectorStore(
            persist_dir=str(tmp_path / "conv_chroma"),
            ollama_url="http://mock:11434",
            embed_model="mock-embed",
        )
        return s


def test_extract_pairs_dict_and_objects(store):
    """Verify _extract_pairs handles both dictionary messages and Message objects."""
    # Test dict messages
    dict_messages = [
        {"role": "user", "content": "How are you?", "timestamp": 100.0},
        {"role": "assistant", "content": "I am doing well!"},
        {"role": "system", "content": "Ignore this system message"},
        {"role": "user", "content": "What is the weather?"},
        {"role": "assistant", "content": "It is sunny."},
    ]
    pairs = store._extract_pairs(dict_messages)
    assert len(pairs) == 2
    assert pairs[0][1] == "How are you?"
    assert pairs[0][2] == "I am doing well!"
    assert pairs[1][1] == "What is the weather?"
    assert pairs[1][2] == "It is sunny."

    # Test Message objects
    obj_messages = [
        DummyMessage(role="user", content="Tell me a joke.", timestamp=200.0),
        DummyMessage(role="assistant", content="Why did the chicken cross the road?"),
    ]
    obj_pairs = store._extract_pairs(obj_messages)
    assert len(obj_pairs) == 1
    assert obj_pairs[0][1] == "Tell me a joke."
    assert obj_pairs[0][2] == "Why did the chicken cross the road?"
    assert obj_pairs[0][3] == 200.0


def test_extract_pairs_edge_cases(store):
    """Verify _extract_pairs handles empty, trailing user, and consecutive user messages."""
    assert store._extract_pairs([]) == []
    assert store._extract_pairs([{"role": "user", "content": "lone user"}]) == []
    assert store._extract_pairs([{"role": "assistant", "content": "lone assistant"}]) == []

    # Consecutive user messages: second user message gets paired with assistant
    consecutive = [
        {"role": "user", "content": "First try"},
        {"role": "user", "content": "Second try"},
        {"role": "assistant", "content": "Got it"},
    ]
    pairs = store._extract_pairs(consecutive)
    assert len(pairs) == 1
    assert pairs[0][1] == "Second try"
    assert pairs[0][2] == "Got it"


def test_index_history_empty(store):
    """Verify index_history returns 0 when no user-assistant pairs exist."""
    assert store.index_history([]) == 0
    assert store.index_history([{"role": "system", "content": "hello"}]) == 0


def test_conversation_store_crud(store):
    """Verify end-to-end conversation store CRUD against tmp path."""
    assert store.count() == 0
    assert store.search("anything") == []

    # Add single exchange
    store.add_exchange(
        user_msg="What is quantum computing?",
        assistant_msg="Quantum computing uses qubits.",
        timestamp=1700000000.0,
    )
    assert store.count() == 1

    # Search exchange
    results = store.search("quantum", limit=1)
    assert len(results) == 1
    assert results[0]["user"] == "What is quantum computing?"
    assert results[0]["assistant"] == "Quantum computing uses qubits."

    # Add exchange with default timestamp (None)
    store.add_exchange(
        user_msg="Thanks for the explanation!",
        assistant_msg="You are welcome!",
    )
    assert store.count() == 2

    # Bulk index history
    bulk_history = [
        {"role": "user", "content": "History user 1"},
        {"role": "assistant", "content": "History assistant 1"},
        {"role": "user", "content": "History user 2"},
        {"role": "assistant", "content": "History assistant 2"},
    ]
    indexed_count = store.index_history(bulk_history)
    assert indexed_count == 2
    assert store.count() == 4

    # Search with limit
    results_limited = store.search("history", limit=2)
    assert len(results_limited) == 2
