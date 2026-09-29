"""Tests for additive IntentAnalysis fields (Migration Plan Step 4)."""

from __future__ import annotations

from app.brain.analyzer import IntentAnalyzer
from app.domain import IntentComplexity
from app.domain.intent import DOMAINS, URGENCY_LEVELS, IntentAnalysis


def test_urgent_bug_is_critical_coding() -> None:
    analysis = IntentAnalyzer().analyze("urgent bug in the API")

    assert analysis.urgency == "critical"
    assert analysis.domain == "coding"


def test_deferred_refactor_is_low_coding() -> None:
    analysis = IntentAnalyzer().analyze("when you have time, refactor this")

    assert analysis.urgency == "low"
    assert analysis.domain == "coding"


def test_search_prompt_detects_web_search_action() -> None:
    analysis = IntentAnalyzer().analyze("search for python asyncio best practices")

    assert analysis.action == "web_search"
    assert analysis.domain == "coding"


def test_lights_prompt_detects_hardware_action() -> None:
    analysis = IntentAnalyzer().analyze("turn on the lights")

    assert analysis.action == "hardware_control"


def test_plain_question_gets_neutral_defaults() -> None:
    analysis = IntentAnalyzer().analyze("Who won the match yesterday?")

    assert analysis.urgency == "normal"
    assert analysis.domain == "general"
    assert analysis.action is None


def test_keywords_match_whole_words_only() -> None:
    """Regression: "api" is a substring of "capital".

    Substring matching classified "what is the capital of France" as *coding*.
    Detectors now require word boundaries (app/brain/analyzer.py:_keyword_hits).
    """
    analysis = IntentAnalyzer().analyze("What is the capital of France?")

    assert analysis.domain == "general"
    assert analysis.action is None


def test_urgency_does_not_fire_on_substrings() -> None:
    """Regression: "soon" is a substring of "season"."""
    assert IntentAnalyzer().analyze("What happens in the season finale?").urgency == "normal"
    assert IntentAnalyzer().analyze("Send it soon please").urgency == "high"


def test_word_boundary_fix_keeps_true_positives() -> None:
    """The fix must not blunt real detection."""
    assert IntentAnalyzer().analyze("write an api endpoint").domain == "coding"
    assert IntentAnalyzer().analyze("help me with my tax return").domain == "finance"
    assert IntentAnalyzer().analyze("search for battery papers").action == "web_search"


def test_high_urgency_and_file_actions() -> None:
    assert IntentAnalyzer().analyze("hurry, fix this fast").urgency == "high"
    assert IntentAnalyzer().analyze("create file notes.txt with the plan").action == "file_write"
    assert IntentAnalyzer().analyze("read file notes.txt for me").action == "file_read"


def test_legacy_construction_still_defaults() -> None:
    analysis = IntentAnalysis(complexity=IntentComplexity.DIRECT_CHAT)

    assert analysis.urgency == "normal"
    assert analysis.domain == "general"
    assert analysis.action is None
    assert analysis.urgency in URGENCY_LEVELS
    assert analysis.domain in DOMAINS
