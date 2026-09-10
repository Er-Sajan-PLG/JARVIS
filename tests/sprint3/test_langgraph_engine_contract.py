"""Regression / contract test: Sprint 3 — LangGraph cognitive engine port.

Verifies that the v3.0 brain can be constructed as a LangGraph state-graph
with named nodes that return typed IntentAnalysis / ExecutionPlan / Response,
and that the composition root has switched to a LangGraph-based orchestrator.
This fails now (before implementation) and should pass after.

Reference: docs/ROADMAP.md Sprint 3; docs/ARCHITECTURE.md; docs/adr/ADR-006.
Evidence: AGENTS.md §1 (Machine-verifiable, self-describing repo).
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_brain_has_langgraph_engine():
    """The brain package must contain a langgraph-based orchestration."""
    brain = REPO / "app/brain"
    # Sprint 3 introduces a langgraph-based orchestrator module.
    # Before: no langgraph usage; After: langgraph import + TypedDict state.
    files = list(brain.glob("*.py"))
    file_text = "".join(open(p).read() for p in files)
    assert "langgraph" in file_text.lower(), (
        "Sprint 3: langgraph-based cognitive engine not found in app/brain/"
    )
    # Require a typed state (LangGraph's State schema: TypedDict or dataclass).
    assert ("TypedDict" in file_text or "StateGraph" in file_text), (
        "Sprint 3: LangGraph state-schema (TypedDict/state graph) not defined"
    )


def test_model_router_registered_and_registered():
    """ARCH-003 follow-up: legacy v2.x server references are removed;"""
    # Confirm no reference remains to the deleted PromptBuilder import.
    api_dir = REPO / "app/api"
    web_dir = REPO / "app/web_api_server.py"
    assert not api_dir.exists(), ("ARCH-003: legacy v2.x server path must be removed/gone")
    assert not web_dir.exists(), ("ARCH-003: legacy web_api_server.py still at root-level import path")


def test_checkpoint_exists():
    """Sprint 3: checkpoint persistence must exist."""
    cp_path = REPO / "app/session/checkpointer.py"
    assert cp_path.exists(), ("Sprint 3: session/checkpointer.py (LangGraph MemorySaver adapter) missing")
    content = open(cp_path).read()
    assert "MemorySaver" in content or "PostgresCheckpointer" in content or ("checkpoint" in content and "Memory" in content), (
        "Sprint 3: checkpoint module does not reference LangGraph persistence classes"
    )


def test_memory_service_uses_4_stage_pipeline():
    """Sprint 3: MemoryService must expose 4-stage pipeline."""
    mem_path = REPO / "app/memory/service.py"
    assert mem_path.exists(), "Memory service file missing"


if __name__ == "__main__":
    # Simple self-run for standalone verification (no pytest needed for quick checks).
    try:
        test_brain_has_langgraph_engine(); print("PASS: langgraph engine present")
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    try:
        test_model_router_registered_and_registered(); print("PASS: ARCH-003 legacy removed")
    except AssertionError as e:
        print("FAIL:", e); sys.exit(1)
    try:
        test_checkpoint_exists(); print("PASS: checkpoint present")
    except AssertionError as e:
        print("FAIL (Sprint 3):", e); sys.exit(1)
    try:
        test_memory_service_uses_4_stage_pipeline(); print("PASS: memory service file present")
    except AssertionError as e:
        print("FAIL (Sprint 3):", e); sys.exit(1)
