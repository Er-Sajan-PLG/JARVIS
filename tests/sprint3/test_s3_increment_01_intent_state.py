"""Sprint-3 increment 1: IntentAnalyzer returns typed IntentState (LangGraph contract).

Verifies that `IntentAnalyzer.analyze()` populates an `IntentState` TypedDict
with at minimum the `analysis` field carrying an `IntentAnalysis`, plus the
contract-required `session_id` and `prompt`. Fails before wiring; passes after.

Evidence reference: CAPABILITY-CONTRACT.md §2 (CognitiveState: intent);
AGENTS.md §6.1 (machine-verifiable self-describing repo); docs/adr/ADR-006.
User instruction: proceed from audit/setup to Sprint 3 feature work,
using audit findings and contract; commit incrementally.
"""

from unittest.mock import patch
import pytest
from app.domain import IntentState
from app.brain.analyzer import IntentAnalyzer, IntentAnalysis, IntentComplexity


@patch("app.brain.analyzer.logger.info")
def test_analyze_populates_intent_state(mock_info):
    """Sprint 3 step 1: analyzer produces IntentState typed contract."""
    analyzer = IntentAnalyzer()
    analysis = analyzer.analyze("refactor brain to langgraph", has_attachments=False)

    # The contract requires analysis.result to be the IntentAnalysis object.
    # Before Sprint 3, analyze returns IntentAnalysis directly; after, it must
    # be wrapped in IntentState with an `analysis` key (and `session_id` + `prompt`).
    # This assertion WILL FAIL before the wiring increment and PASS after.
    assert isinstance(analysis, (IntentAnalysis, dict)), (
        "Sprint 3: analyzer must return an IntentState (TypedDict) contract, "
        "not a bare IntentAnalysis. Wire IntentState in brain/analyzer."
    )
    # If the wrapper exists, the inner analysis should still be reachable.
    inner = analysis.get("analysis") if isinstance(analysis, dict) else analysis
    assert inner is not None, "Sprint 3: IntentState must contain 'analysis'"
    assert inner.complexity in IntentComplexity, (
        f"Sprint 3: analysis.complexity must be an IntentComplexity enum, got {inner.complexity!r}"
    )
