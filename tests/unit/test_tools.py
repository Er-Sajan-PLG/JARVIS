"""Unit tests for app/tools: base, executor, file_tools, git_tools."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.base import ToolDefinition, ToolRegistry, ToolResult
from app.tools.executor import (
    MAX_OUTPUT_CHARS,
    ParsedCall,
    ToolExecutor,
)
from app.tools.file_tools import (
    append_file,
    create_directory,
    list_dir,
    read_file,
    write_file,
)
from app.tools.git_tools import (
    DIFF_MAX_CHARS,
    _run_git,
    git_diff_full,
    git_diff_stat,
    git_log,
    git_show,
    git_status,
    git_tags,
)

# --- Base Tools Tests ---


def test_tool_result() -> None:
    res_ok = ToolResult(success=True, output="All good")
    assert bool(res_ok) is True
    assert str(res_ok) == "All good"

    res_err = ToolResult(success=False, output="", error="Access denied")
    assert bool(res_err) is False
    assert str(res_err) == "Error: Access denied"


def test_tool_definition_execution_and_schema() -> None:
    def sample_handler(x: int) -> int:
        if x < 0:
            raise ValueError("Negative value")
        if x == 42:
            raise PermissionError("Restricted number")
        return x * 2

    tool = ToolDefinition(
        name="double",
        description="Doubles a number",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        handler=sample_handler,
        risk_level="low",
    )

    # Success
    r1 = tool.execute(x=5)
    assert r1.success is True
    assert r1.output == "10"

    # Permission error
    r2 = tool.execute(x=42)
    assert r2.success is False
    assert "Permission denied" in r2.error

    # General exception
    r3 = tool.execute(x=-1)
    assert r3.success is False
    assert "Negative value" in r3.error

    # OpenAI schema
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "double"
    assert "properties" in schema["function"]["parameters"]


def test_tool_registry() -> None:
    reg = ToolRegistry()
    t1 = ToolDefinition(
        "t1", "Tool 1", {"properties": {"a": {"type": "string"}}, "required": ["a"]}, lambda: None
    )
    t2 = ToolDefinition(
        "t2",
        "Tool 2",
        {"properties": {"b": {"type": "int", "default": 0}}},
        lambda: None,
        risk_level="medium",
    )

    reg.register(t1)
    reg.register_many([t2])

    assert reg.get("t1") == t1
    assert reg.get("t2") == t2
    assert reg.get("missing") is None
    assert len(reg.all()) == 2

    schemas = reg.to_openai_schemas()
    assert len(schemas) == 2

    prompt_fmt = reg.format_for_prompt()
    assert "Available tools:" in prompt_fmt
    assert "t1(a: string)" in prompt_fmt
    assert "t2(b: int = 0) [medium risk]" in prompt_fmt


# --- Tool Executor Tests ---


def test_tool_executor_parsing() -> None:
    executor = ToolExecutor(registry=ToolRegistry())

    # Plain text without tool calls
    assert executor.has_calls("Just regular text.") is False
    assert executor.parse("Just regular text.") == []

    # Format 1: standard JSON
    text_f1 = '<tool_call>{"name": "test_tool", "args": {"msg": "hi"}}</tool_call>'
    assert executor.has_calls(text_f1) is True
    calls_f1 = executor.parse(text_f1)
    assert len(calls_f1) == 1
    assert calls_f1[0].name == "test_tool"
    assert calls_f1[0].args == {"msg": "hi"}

    # Format 2: hybrid call
    text_f2 = '<tool_call>git_show({"ref": "HEAD"})</tool_call>'
    assert executor.has_calls(text_f2) is True
    calls_f2 = executor.parse(text_f2)
    assert len(calls_f2) == 1
    assert calls_f2[0].name == "git_show"
    assert calls_f2[0].args == {"ref": "HEAD"}

    # Format 3: positional arg call
    text_f3 = '<tool_call>read_file("docs/CHANGELOG.md")</tool_call>'
    assert executor.has_calls(text_f3) is True
    calls_f3 = executor.parse(text_f3)
    assert len(calls_f3) == 1
    assert calls_f3[0].name == "read_file"
    assert calls_f3[0].args == {"path": "docs/CHANGELOG.md"}

    # Corrupt call
    text_corrupt = "<tool_call>{invalid json</tool_call>"
    assert executor.parse(text_corrupt) == []


def test_tool_executor_execution_and_capping() -> None:
    reg = ToolRegistry()
    t_safe = ToolDefinition("safe_tool", "Safe", {}, lambda **kw: "hello world")
    t_long = ToolDefinition("long_tool", "Long", {}, lambda **kw: "A" * (MAX_OUTPUT_CHARS + 100))
    t_risky = ToolDefinition(
        "risky_tool", "Risky", {}, lambda **kw: "wiped", requires_confirmation=True
    )

    reg.register_many([t_safe, t_long, t_risky])
    executor = ToolExecutor(registry=reg, require_confirmation=True)

    # 1. Unknown tool
    r_unknown = executor.run(ParsedCall("missing", {}, ""))
    assert r_unknown.success is False
    assert "Unknown tool" in r_unknown.error

    # 2. Safe tool
    r_safe = executor.run(ParsedCall("safe_tool", {}, ""))
    assert r_safe.success is True
    assert r_safe.output == "hello world"

    # 3. Output capping
    r_long = executor.run(ParsedCall("long_tool", {}, ""))
    assert r_long.success is True
    assert len(r_long.output) > MAX_OUTPUT_CHARS
    assert "... (100 chars trimmed)" in r_long.output

    # 4. Risky tool declined
    with patch("builtins.input", return_value="n"):
        r_declined = executor.run(ParsedCall("risky_tool", {"flag": True}, ""))
        assert r_declined.success is False
        assert "User declined" in r_declined.error

    # 5. Risky tool confirmed
    with patch("builtins.input", return_value="y"):
        r_accepted = executor.run(ParsedCall("risky_tool", {}, ""))
        assert r_accepted.success is True
        assert r_accepted.output == "wiped"

    # 6. Format result
    formatted = executor.format_result(ParsedCall("safe_tool", {}, ""), r_safe)
    assert '<tool_result name="safe_tool" status="success">' in formatted
    assert "hello world" in formatted


# --- File Tools Tests ---


def test_file_tools(tmp_path: Path) -> None:
    f = tmp_path / "subdir" / "test.txt"

    # read missing
    msg = read_file(str(f))
    assert "file not found" in msg

    # write file
    w_res = write_file(str(f), "Line 1\n")
    assert "Written" in w_res
    assert f.read_text(encoding="utf-8") == "Line 1\n"

    # read existing
    assert read_file(str(f)) == "Line 1\n"

    # append file
    a_res = append_file(str(f), "Line 2\n")
    assert "Appended" in a_res
    assert f.read_text(encoding="utf-8") == "Line 1\nLine 2\n"

    # create directory is DESTRUCTIVE tier: requires HITL approval
    new_dir = tmp_path / "a" / "b" / "c"
    with pytest.raises(Exception) as exc_info:
        create_directory(str(new_dir))
    assert "HITL approval required" in str(exc_info.value)

    d_res = create_directory(str(new_dir), _hitl_approved=True)
    assert "Created directory" in d_res
    assert new_dir.is_dir()

    # list dir
    l_res = list_dir(str(tmp_path))
    assert "subdir/" in l_res
    assert "a/" in l_res

    # list dir missing
    assert "directory not found" in list_dir(str(tmp_path / "non_existent"))


# --- Git Tools Tests ---


def test_git_tools_mocked() -> None:
    # 1. _run_git success
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "abc1234 2026-09-11 Commit msg\n"
        mock_run.return_value = mock_proc

        out = _run_git("log")
        assert "abc1234" in out

    # 2. _run_git failure
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "fatal: not a git repo"
        mock_run.return_value = mock_proc

        with pytest.raises(RuntimeError) as exc_info:
            _run_git("status")
        assert "fatal: not a git repo" in str(exc_info.value)

    # 3. git_log & git_diff_stat
    with patch("app.tools.git_tools._run_git", return_value="mock git log"):
        assert git_log(5) == "mock git log"

    with patch("app.tools.git_tools._run_git", return_value="1 file changed"):
        assert git_diff_stat() == "1 file changed"

    # 4. git_diff_full
    with patch("app.tools.git_tools._run_git", return_value="short diff"):
        assert git_diff_full() == "short diff"

    with patch("app.tools.git_tools._run_git", return_value=""):
        assert git_diff_full() == "(no changes)"

    long_diff = "+" * (DIFF_MAX_CHARS + 500)
    with patch("app.tools.git_tools._run_git", return_value=long_diff):
        truncated = git_diff_full()
        assert f"diff truncated at {DIFF_MAX_CHARS}" in truncated

    # 5. git_status
    with patch("app.tools.git_tools._run_git", return_value="M file.py"):
        assert git_status() == "M file.py"

    with patch("app.tools.git_tools._run_git", return_value=""):
        assert git_status() == "(working tree clean)"

    # 6. git_show
    with patch("app.tools.git_tools._run_git", return_value="commit details"):
        assert git_show("HEAD") == "commit details"

    long_show = "A" * (DIFF_MAX_CHARS + 200)
    with patch("app.tools.git_tools._run_git", return_value=long_show):
        assert "...(truncated)" in git_show("HEAD")

    # 7. git_tags
    with patch("app.tools.git_tools._run_git", return_value="v2.4.0\nv2.3.0"):
        assert git_tags() == "v2.4.0\nv2.3.0"

    with patch("app.tools.git_tools._run_git", side_effect=RuntimeError("no tags")):
        assert git_tags() == "(no tags found)"
