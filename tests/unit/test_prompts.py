"""Unit tests for PromptLoader and prompt template variable contracts.
"""

from pathlib import Path
import pytest

from app.prompt.loader import PromptLoader


def test_prompt_loader_variable_contracts() -> None:
    """Verify that required variables for core templates match expected contracts."""
    loader = PromptLoader(prompts_dir="prompts")

    # system_base.md contract
    system_vars = loader.get_required_variables("system_base.md")
    assert "assistant_name" in system_vars
    assert "user_id" in system_vars
    assert "session_id" in system_vars
    assert "theme" in system_vars
    assert "custom_instructions" in system_vars

    # planner.md contract
    planner_vars = loader.get_required_variables("planner.md")
    assert "goal" in planner_vars
    assert "complexity" in planner_vars
    assert "available_tools" in planner_vars

    # synthesizer.md contract
    synth_vars = loader.get_required_variables("synthesizer.md")
    assert "query" in synth_vars
    assert "execution_results" in synth_vars
    assert "context_summary" in synth_vars


def test_prompt_rendering() -> None:
    """Verify successful rendering of system_base.md with kwargs."""
    loader = PromptLoader(prompts_dir="prompts")
    rendered = loader.render(
        "system_base.md",
        assistant_name="JARVIS",
        user_id="user_123",
        session_id="sess_456",
        theme="dark",
        custom_instructions="Be concise.",
    )

    assert "JARVIS" in rendered
    assert "user_123" in rendered
    assert "sess_456" in rendered
    assert "dark" in rendered
    assert "Be concise." in rendered
