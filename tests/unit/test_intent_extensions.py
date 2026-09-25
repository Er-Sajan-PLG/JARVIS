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
    # NB: "capital" contains the substring "api", so it is NOT keyword-free
    # under the spec'd substring matching — this question is verified clean.
    analysis = IntentAnalyzer().analyze("Who won the match yesterday?")

    assert analysis.urgency == "normal"
    assert analysis.domain == "general"
    assert analysis.action is None


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
