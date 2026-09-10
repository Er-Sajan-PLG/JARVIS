"""Sprint-3 contract: LangGraph engine (pre-implementation). Fails now; passes after."""
import pytest
from unittest.mock import patch
from pathlib import Path

work = Path(__file__).resolve().parents[1]
from app.domain import IntentState
from app.brain.analyzer import IntentAnalyzer, IntentAnalysis, IntentComplexity


@patch("app.brain.analyzer.logger.info")
def test_brain_has_langgraph_engine(mock_logger):
    # RED TARGET 1: LangGraph engine un-wired at Sprint 3 start.
    brain_path = work / "app/brain"
    files_text = "
".join(open(p).read() for p in brain_path.glob("*.py"))
    assert "langgraph" in files_text.lower(), (
        "Sprint 3 FAIL: langgraph.StateGraph / StateGraph wiring missing in app/brain/; "
        "wire cognitive engine node definitions per docs/ROADMAP.md Sprint 3."
    )


def test_checkpoint_has_memory_saver():
    # RED TARGET 2: MemorySaver / PostgresCheckpointer missing.
    cp_path = work / "app/session/checkpointer.py"
    txt = open(cp_path).read()
    assert ("MemorySaver" in txt) or ("PostgresCheckpointer" in txt) or ("Memory" in txt and "checkpoint" in txt), (
        "Sprint 3 FAIL: checkpoint does not reference LangGraph persistence; add MemorySaver adapter."
    )


def test_legacy_server_import_blocked():
    # RED TARGET 3: ARCH-003 verification (archive complete, import blocked) —
    # this SHOULD PASS after archive; kept as contract for regression.
    import importlib.util
    for name in ("app.api.server", "app.web_api_server"):
        spec = importlib.util.find_spec(name)
        assert spec is None, f"ARCH-003 FAIL: {name} still importable; verify archive in legacy/."


if __name__ == "__main__":
    import sys
    for fn in (test_brain_has_langgraph_engine, test_checkpoint_has_memory_saver, test_legacy_server_import_blocked):
        try:
            fn()
            print("PASS:", fn.__name__)
        except AssertionError as exc:
            print("FAIL:", fn.__name__, "—", exc)
            sys.exit(1)
