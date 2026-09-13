"""Unit tests for fact extractor in app/memory/fact_extractor.py."""

from app.memory.fact_extractor import (
    _extract_value,
    _split_into_sentences,
    extract_facts,
)
from app.memory.schema import SOURCE_SYSTEM, SOURCE_USER


def test_split_into_sentences_simple():
    """Verify sentence splitting on period, exclamation, and question marks."""
    text = "Hello world. How are you? I am doing great! Have fun"
    sentences = _split_into_sentences(text)
    assert sentences == [
        "Hello world.",
        "How are you?",
        "I am doing great!",
        "Have fun",
    ]


def test_split_into_sentences_abbreviations():
    """Verify common abbreviations do not cause incorrect sentence splitting."""
    text = "Dr. Smith visited the clinic. Prof. Jones stayed home."
    sentences = _split_into_sentences(text)
    assert len(sentences) == 2
    assert sentences[0] == "Dr. Smith visited the clinic."
    assert sentences[1] == "Prof. Jones stayed home."


def test_split_into_sentences_empty_and_whitespace():
    """Verify empty or whitespace strings return empty lists."""
    assert _split_into_sentences("") == []
    assert _split_into_sentences("   \n\t  ") == []


def test_extract_value_missing_trigger():
    """Verify _extract_value returns empty string when trigger is absent."""
    assert _extract_value("hello world", "i am ") == ""


def test_extract_value_boundaries():
    """Verify value is cut at conjunctions and boundaries."""
    # Coordinating conjunction
    assert _extract_value("i like pizza, but i hate pineapples", "i like ") == "pizza"
    assert _extract_value("i enjoy swimming and running", "i enjoy ") == "swimming"
    assert _extract_value("i prefer tea or coffee", "i prefer ") == "tea"

    # Subordinating conjunction
    assert _extract_value("i need to sleep because i am tired", "i need to ") == "sleep"
    assert _extract_value("i plan to study although it is late", "i plan to ") == "study"
    assert _extract_value("i will wait while you finish", "i will ") == "wait"
    assert _extract_value("i can help if you want", "i can ") == "help"

    # Prefixes "that " and "to "
    assert _extract_value("i consider myself that honest", "i consider myself ") == "honest"
    assert _extract_value("i want to travel", "i want ") == "travel"

    # Trailing punctuation
    assert _extract_value("i live in kathmandu.", "i live in ") == "kathmandu"


def test_extract_facts_representative_message_list():
    """Verify fact extraction across all categories from representative messages."""
    messages_and_expectations = [
        # Identity
        ("My name is Sajan.", "identity", "name", "sajan"),
        ("I identify as a creator.", "identity", "self_identification", "a creator"),
        # Preferences
        ("I love artificial intelligence.", "preference", "like", "artificial intelligence"),
        ("I prefer dark mode.", "preference", "like", "dark mode"),
        # Skills
        ("I can build distributed systems.", "skills", "ability", "build distributed systems"),
        ("I am skilled at python.", "skills", "proficiency", "python"),
        ("I have experience with docker and kubernetes.", "skills", "experience", "docker"),
        # Goals
        ("I want to learn rust.", "goals", "desire", "learn rust"),
        ("My goal is building jarvis.", "goals", "objective", "building jarvis"),
        ("I aspire to innovate.", "goals", "aspiration", "innovate"),
        # Plans
        ("I plan to deploy today.", "plans", "intention", "deploy today"),
        ("I will write tests.", "plans", "future_action", "write tests"),
        ("I am going to finish the sprint.", "plans", "near_future", "finish the sprint"),
        # Tasks
        ("I need to review the pull request.", "tasks", "requirement", "review the pull request"),
        ("I have to fix the bug.", "tasks", "obligation", "fix the bug"),
        ("My task is writing documentation.", "tasks", "action_item", "writing documentation"),
        # Location
        ("I am in Kathmandu.", "location", "current_position", "kathmandu"),
        ("I live in Nepal.", "location", "residence", "nepal"),
        ("I am located at the laboratory.", "location", "geographical", "the laboratory"),
        # Profession
        ("I work as a software architect.", "profession", "role", "a software architect"),
        ("My profession is machine learning.", "profession", "career", "machine learning"),
    ]

    for msg, cat, rtype, expected_val in messages_and_expectations:
        facts = extract_facts(msg)
        assert len(facts) >= 1, f"Failed to extract fact from: {msg}"
        match = any(
            f["category"] == cat and f["type"] == rtype and f["value"] == expected_val
            for f in facts
        )
        assert match, f"Expected fact ({cat}, {rtype}, {expected_val}) not found in {facts}"


def test_extract_facts_multi_sentence_and_multiple_facts():
    """Verify multiple facts extracted from multiple sentences in a single message."""
    text = "My name is Sajan. I live in Nepal and I like python. I want to build Jarvis."
    facts = extract_facts(text, source=SOURCE_USER)
    assert len(facts) >= 3

    categories = [f["category"] for f in facts]
    assert "identity" in categories
    assert "location" in categories
    assert "preference" in categories
    assert "goals" in categories

    for f in facts:
        assert f["source"] == SOURCE_USER
        assert f["confidence"] == 1.0
        assert f["behavior"] == "append"


def test_extract_facts_custom_source():
    """Verify custom source parameter propagation."""
    facts = extract_facts("I live in Paris.", source=SOURCE_SYSTEM)
    assert len(facts) == 1
    assert facts[0]["source"] == SOURCE_SYSTEM


def test_extract_facts_short_value_ignored():
    """Verify values with length < 2 are discarded."""
    # "I am x" with trigger "i am " produces "x" (length 1)
    facts = extract_facts("I am x.")
    # The rule for "state" should skip 1-char value "x"
    assert all(f["value"] != "x" for f in facts)
