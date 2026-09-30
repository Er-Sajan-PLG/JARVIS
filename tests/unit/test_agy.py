"""Unit tests for app/adapters/integrations/agy.py — AGYClient integration.

Tests cover CLI discovery, availability checking, model listing, chat request
building and response parsing, and file analysis.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.integrations.agy import (
    _agy_which,
    analyze_file,
    chat,
    get_models,
    is_available,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# Tests: _agy_which
# ---------------------------------------------------------------------------


class TestAgyWhich:
    def test_which_finds_in_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/agy"):
            assert _agy_which() == "/usr/local/bin/agy"

    def test_which_falls_back_to_home_dir(self):
        """When shutil.which returns None, _agy_which checks common install locations."""
        fake_home_agy = MagicMock()
        fake_home_agy.is_file.return_value = True

        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.home", return_value=Path("/home/testuser")),
            patch("os.access", return_value=True),
            patch.object(Path, "is_file", return_value=True),
        ):
            result = _agy_which()
            # Home directory location
            assert result is not None and ".local/bin/agy" in result

    def test_which_returns_none_when_not_found(self):
        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.home", return_value=Path("/nonexistent_home")),
            patch("os.access", return_value=False),
        ):
            # None of the fallback paths exist
            assert _agy_which() is None


# ---------------------------------------------------------------------------
# Tests: is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_available_when_agy_installed(self):
        with patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"):
            assert is_available() is True

    def test_unavailable_when_agy_missing(self):
        with patch("app.adapters.integrations.agy._agy_which", return_value=None):
            assert is_available() is False


# ---------------------------------------------------------------------------
# Tests: get_models
# ---------------------------------------------------------------------------


class TestGetModels:
    def test_get_models_returns_empty_when_no_exe(self):
        with patch("app.adapters.integrations.agy._agy_which", return_value=None):
            assert get_models() == []

    def test_get_models_skips_header_lines(self):
        stdout = "Name\tDisplay Name\n────\t────\nmy-gemini\tGemini Pro\nmy-claude\tClaude 3.5"
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=_make_proc(returncode=0, stdout=stdout)),
        ):
            models = get_models()
            assert len(models) == 2
            assert models[0]["id"] == "my-gemini"
            assert models[0]["name"] == "Gemini Pro"
            assert models[1]["id"] == "my-claude"

    def test_get_models_returns_empty_on_command_failure(self):
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=_make_proc(returncode=1, stderr="error")),
        ):
            assert get_models() == []

    def test_get_models_returns_empty_on_exception(self):
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", side_effect=OSError("command not found")),
        ):
            assert get_models() == []

    def test_get_models_skips_non_tab_lines(self):
        stdout = "Featured Models\nmodel-without-tabs"
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=_make_proc(returncode=0, stdout=stdout)),
        ):
            assert get_models() == []


# ---------------------------------------------------------------------------
# Tests: chat
# ---------------------------------------------------------------------------


class TestChat:
    def test_chat_raises_when_no_exe(self):
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value=None),
            pytest.raises(RuntimeError, match="AGY CLI not found"),
        ):
            chat([{"role": "user", "content": "hello"}])

    def test_chat_builds_correct_command(self):
        expected_response = {"response": "Hello from AGY"}
        proc = _make_proc(returncode=0, stdout=json.dumps(expected_response))

        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = proc
            result = chat(
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ],
                model="gemini-3.1-pro-high",
                effort="high",
                timeout=120,
            )

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            # Verify the command structure
            assert cmd[0] == "/usr/bin/agy"
            assert "--print=" in cmd[1]
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "--model" in cmd
            assert "gemini-3.1-pro-high" in cmd
            assert "--effort" in cmd
            assert "high" in cmd
            # timeout converted to minutes
            assert "2m" in cmd

            # Verify the parsed result
            assert result["content"] == "Hello from AGY"
            assert result["model"] == "gemini-3.1-pro-high"
            assert result["tokens_used"] is None
            assert result["finish_reason"] == "stop"

    def test_chat_parses_string_response(self):
        """When the JSON response is a plain string, use it as content."""
        proc = _make_proc(returncode=0, stdout=json.dumps("Just a string response"))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = chat([{"role": "user", "content": "hi"}])
            assert result["content"] == "Just a string response"

    def test_chat_parses_dict_with_text_field(self):
        proc = _make_proc(returncode=0, stdout=json.dumps({"text": "Text field"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = chat([{"role": "user", "content": "hi"}])
            assert result["content"] == "Text field"

    def test_chat_parses_dict_with_output_field(self):
        proc = _make_proc(returncode=0, stdout=json.dumps({"output": "Output field"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = chat([{"role": "user", "content": "hi"}])
            assert result["content"] == "Output field"

    def test_chat_parses_dict_with_content_field(self):
        proc = _make_proc(returncode=0, stdout=json.dumps({"content": "Content field"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = chat([{"role": "user", "content": "hi"}])
            assert result["content"] == "Content field"

    def test_chat_parses_non_json_output(self):
        """When output is not JSON, use raw text as content."""
        proc = _make_proc(returncode=0, stdout="Raw non-JSON output")
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = chat([{"role": "user", "content": "hi"}])
            assert result["content"] == "Raw non-JSON output"

    def test_chat_raises_on_command_failure(self):
        proc = _make_proc(returncode=1, stderr="some error")
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
            pytest.raises(RuntimeError, match="AGY CLI returned 1"),
        ):
            chat([{"role": "user", "content": "hi"}])

    def test_chat_raises_on_empty_output(self):
        proc = _make_proc(returncode=0, stdout="")
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
            pytest.raises(RuntimeError, match="no response"),
        ):
            chat([{"role": "user", "content": "hi"}])

    def test_chat_raises_on_timeout(self):
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="agy", timeout=300)),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            chat([{"role": "user", "content": "hi"}])

    def test_chat_raises_on_os_error(self):
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", side_effect=OSError("exec failed")),
            pytest.raises(RuntimeError, match="failed to start"),
        ):
            chat([{"role": "user", "content": "hi"}])

    def test_chat_includes_all_message_roles(self):
        """Verify system, assistant, and user messages are all included."""
        proc = _make_proc(returncode=0, stdout=json.dumps({"response": "ok"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = proc
            chat(
                messages=[
                    {"role": "system", "content": "Be helpful"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                    {"role": "user", "content": "Follow up"},
                ]
            )
            cmd = mock_run.call_args[0][0]
            prompt_flag = cmd[1]
            assert prompt_flag.startswith("--print=")
            prompt_text = prompt_flag[len("--print="):]
            assert "[System]" in prompt_text
            assert "[User]" in prompt_text
            assert "[Assistant]" in prompt_text
            assert "Be helpful" in prompt_text
            assert "Hello" in prompt_text
            assert "Hi there" in prompt_text
            assert "Follow up" in prompt_text

    def test_chat_without_effort_flag(self):
        """When effort is None, --effort flag should not appear."""
        proc = _make_proc(returncode=0, stdout=json.dumps({"response": "ok"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = proc
            chat([{"role": "user", "content": "hi"}], effort=None)
            cmd = mock_run.call_args[0][0]
            assert "--effort" not in cmd


# ---------------------------------------------------------------------------
# Tests: analyze_file
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_analyze_file_success(self, tmp_path: Path):
        test_file = tmp_path / "test_doc.txt"
        test_file.write_text("This is a test document content.")

        expected_response = {"response": "Analysis result"}
        proc = _make_proc(returncode=0, stdout=json.dumps(expected_response))

        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = analyze_file(
                file_path=str(test_file),
                query="What is this about?",
                model="gemini-3.1-pro-high",
            )
            assert result == "Analysis result"

    def test_analyze_file_binary_content(self, tmp_path: Path):
        """Binary file content is replaced with placeholder text."""
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        expected_response = {"response": "Binary analysis"}
        proc = _make_proc(returncode=0, stdout=json.dumps(expected_response))

        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = analyze_file(file_path=str(test_file), query="analyze this")
            assert result == "Binary analysis"

    def test_analyze_file_wraps_exception(self, tmp_path: Path):
        """Exceptions from chat are wrapped in RuntimeError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with (
            patch("app.adapters.integrations.agy._agy_which", return_value=None),
            pytest.raises(RuntimeError, match="File analysis failed"),
        ):
            analyze_file(file_path=str(test_file), query="what?")

    def test_analyze_file_uses_custom_mime_type(self, tmp_path: Path):
        """mime_type param is accepted (even if not sent to CLI currently)."""
        test_file = tmp_path / "data.csv"
        test_file.write_text("a,b,c\n1,2,3\n")

        expected_response = {"response": "CSV analysis"}
        proc = _make_proc(returncode=0, stdout=json.dumps(expected_response))

        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run", return_value=proc),
        ):
            result = analyze_file(
                file_path=str(test_file),
                query="summarize",
                mime_type="text/csv",
            )
            assert result == "CSV analysis"

class TestSprint83:
    """Threading, passthrough, usage parsing, fresh defaults."""

    def _run(self, stdout, **kwargs):
        from app.adapters.integrations.agy import chat

        proc = _make_proc(returncode=0, stdout=stdout)
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = proc
            result = chat(messages=[{"role": "user", "content": "hi"}], **kwargs)
        return mock_run.call_args[0][0], result

    def test_default_model_is_current(self):
        from app.adapters.integrations.agy import DEFAULT_MODEL

        assert DEFAULT_MODEL == "gemini-3.8-flash-medium"

    def test_timeout_rounds_up_not_down(self):
        cmd, _ = self._run('{"response": "x"}', timeout=90)
        assert "2m" in cmd  # truncation made this "1m" and starved the CLI

    def test_threading_and_passthrough_flags(self):
        cmd, _ = self._run(
            '{"response": "x"}',
            conversation_id="conv-1",
            agent="plan",
            mode="plan",
            add_dirs=["./scope"],
            project="proj",
        )
        for flag in ("--conversation", "conv-1", "--agent", "plan", "--mode"):
            assert flag in cmd
        assert "./scope" in cmd and "proj" in cmd

    def test_usage_and_conversation_parsed(self):
        payload = {
            "response": "hi",
            "conversation_id": "conv-9",
            "usage": {"total_tokens": 123},
        }
        _, result = self._run(json.dumps(payload))
        assert result["conversation_id"] == "conv-9"
        assert result["tokens_used"] == 123

    def test_analyze_file_caps_and_mime_hint(self, tmp_path: Path):
        from app.adapters.integrations.agy import analyze_file

        big = tmp_path / "big.txt"
        big.write_text("z" * 70000)
        proc = _make_proc(returncode=0, stdout=json.dumps({"response": "ok"}))
        with (
            patch("app.adapters.integrations.agy._agy_which", return_value="/usr/bin/agy"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = proc
            analyze_file(str(big), "sum", mime_type="text/plain")
            prompt = mock_run.call_args[0][0][1]
            assert "truncated" in prompt and "MIME: text/plain" in prompt
