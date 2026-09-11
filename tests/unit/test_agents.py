"""Unit tests for app/agents/doc_agent.py (DocumentationAgent, run_interactive)."""

from unittest.mock import MagicMock, patch

from app.agents.doc_agent import MAX_ITERATIONS, DocumentationAgent, run_interactive
from app.models.client import ModelResponse
from app.tools.base import ToolResult


def test_doc_agent_init() -> None:
    mock_model = MagicMock()
    agent = DocumentationAgent(mock_model)
    assert agent._model == mock_model
    assert "git_log" in agent._registry._tools
    assert "read_file" in agent._registry._tools


def test_doc_agent_run_immediate_response() -> None:
    mock_model = MagicMock()
    mock_model.generate.return_value = ModelResponse(
        content="Here is the changelog entry without any tools needed.",
        model="omni",
    )
    agent = DocumentationAgent(mock_model)
    result = agent.run("Generate changelog", verbose=False)

    assert result == "Here is the changelog entry without any tools needed."
    assert mock_model.generate.call_count == 1


def test_doc_agent_run_with_tool_call() -> None:
    mock_model = MagicMock()
    # First response makes a tool call, second response concludes
    mock_model.generate.side_effect = [
        ModelResponse(
            content='<tool_call>{"name": "git_status", "args": {}}</tool_call>',
            model="omni",
        ),
        ModelResponse(
            content="Changelog finalized after inspecting git status.",
            model="omni",
        ),
    ]

    agent = DocumentationAgent(mock_model)
    with patch.object(
        agent._executor, "run", return_value=ToolResult(success=True, output="clean")
    ):
        result = agent.run("Document git status", verbose=True)

    assert result == "Changelog finalized after inspecting git status."
    assert mock_model.generate.call_count == 2


def test_doc_agent_run_max_iterations_exceeded() -> None:
    mock_model = MagicMock()
    # Endless tool calls
    mock_model.generate.return_value = ModelResponse(
        content='<tool_call>{"name": "git_status", "args": {}}</tool_call>',
        model="omni",
    )

    agent = DocumentationAgent(mock_model)
    with patch.object(
        agent._executor, "run", return_value=ToolResult(success=True, output="clean")
    ):
        result = agent.run("Infinite loop test", verbose=False)

    assert "reached iteration limit" in result
    assert mock_model.generate.call_count == MAX_ITERATIONS


def test_run_interactive_cancel_and_invalid() -> None:
    mock_agent = MagicMock()

    # Cancel
    with patch("builtins.input", return_value="q"):
        run_interactive(mock_agent)
        mock_agent.run.assert_not_called()

    # Invalid choice
    with patch("builtins.input", return_value="invalid"):
        run_interactive(mock_agent)
        mock_agent.run.assert_not_called()


def test_run_interactive_presets() -> None:
    mock_agent = MagicMock()
    mock_agent.run.return_value = "Done"

    # Preset 1: changelog
    with patch("builtins.input", return_value="1"):
        run_interactive(mock_agent)
        mock_agent.run.assert_called_once()
        assert "CHANGELOG.md" in mock_agent.run.call_args[0][0]

    mock_agent.reset_mock()
    # Preset 2: devlog
    with patch("builtins.input", return_value="2"):
        run_interactive(mock_agent)
        mock_agent.run.assert_called_once()
        assert "DEVLOG.md" in mock_agent.run.call_args[0][0]

    mock_agent.reset_mock()
    # Preset 3: both
    with patch("builtins.input", return_value="3"):
        run_interactive(mock_agent)
        mock_agent.run.assert_called_once()
        assert "history" in mock_agent.run.call_args[0][0]


def test_run_interactive_custom_task() -> None:
    mock_agent = MagicMock()
    mock_agent.run.return_value = "Done custom"

    # Custom valid task
    with patch("builtins.input", side_effect=["4", "Analyze security audit"]):
        run_interactive(mock_agent)
        mock_agent.run.assert_called_once_with("Analyze security audit", verbose=True)

    mock_agent.reset_mock()
    # Custom empty task cancels
    with patch("builtins.input", side_effect=["4", ""]):
        run_interactive(mock_agent)
        mock_agent.run.assert_not_called()
