#!/usr/bin/env python3
"""
Stress test suite for JARVIS Documentation Agent (v2.4.0)

Run with:  python3 tests/stress_test.py
Run one section: python3 tests/stress_test.py TestParser

What this covers:
  1. Parser      — every weird format a local model might produce
  2. Security    — allowlist, path traversal, adversarial inputs
  3. Git tools   — edge cases, invalid refs, truncation
  4. File tools  — permissions, missing files, empty content
  5. Agent loop  — normal flow, MAX_ITERATIONS ceiling, error propagation
  6. Adversarial — actively trying to break the sandbox
"""

import sys
import os
import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

# Make sure we can import from the project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.tools.base import ToolResult, ToolDefinition, ToolRegistry
from app.tools.executor import ToolExecutor, ParsedCall
from app.tools.git_tools import GIT_TOOLS, git_log, git_diff_stat, git_diff_full
from app.tools.file_tools import FILE_TOOLS, read_file, write_file, ALLOWED_READ, ALLOWED_WRITE
from app.agents.doc_agent import DocumentationAgent, MAX_ITERATIONS
from app.models.client import ModelResponse


# ─── Mock Model ────────────────────────────────────────────────────────────────

class MockModel:
    """
    Scriptable mock model for agent loop testing.
    Replaces the real LLM — returns pre-scripted responses in sequence.
    When the script is exhausted, returns a plain "Done." response.
    """
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._index = 0
        self.call_count = 0

    def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        self.call_count += 1
        if self._index < len(self._responses):
            content = self._responses[self._index]
            self._index += 1
        else:
            content = "Done. All documentation has been generated."
        return ModelResponse(content=content, model="mock")

    @property
    def model_name(self) -> str:
        return "mock"

    @property
    def role(self) -> str:
        return "general"


def _make_executor(require_confirmation: bool = False) -> tuple[ToolRegistry, ToolExecutor]:
    """Build a registry + executor for testing."""
    reg = ToolRegistry()
    reg.register_many(GIT_TOOLS)
    reg.register_many(FILE_TOOLS)
    executor = ToolExecutor(reg, require_confirmation=require_confirmation)
    return reg, executor


# ══════════════════════════════════════════════════════════════════════════════
# 1. PARSER TESTS
#    Every format a local model might produce — does the parser handle it?
# ══════════════════════════════════════════════════════════════════════════════

class TestParser(unittest.TestCase):

    def setUp(self):
        _, self.ex = _make_executor()

    def test_clean_single_call(self):
        text = '<tool_call>{"name": "git_log", "args": {"n": 5}}</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "git_log")
        self.assertEqual(calls[0].args, {"n": 5})

    def test_multiple_calls_one_response(self):
        """Model often batches multiple tool calls in one turn."""
        text = (
            'I will check both.\n'
            '<tool_call>{"name": "git_log", "args": {"n": 10}}</tool_call>\n'
            'And also:\n'
            '<tool_call>{"name": "git_tags", "args": {}}</tool_call>'
        )
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].name, "git_log")
        self.assertEqual(calls[1].name, "git_tags")

    def test_whitespace_and_newlines_inside_tag(self):
        """Model may add newlines inside the tag."""
        text = '<tool_call>\n  {"name": "git_diff_stat", "args": {"from_ref": "HEAD~1"}}\n</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "git_diff_stat")

    def test_model_wraps_in_markdown_code_block(self):
        """Some models wrap output in ```json ... ``` — tag should still be found."""
        text = '```json\n<tool_call>{"name": "git_log", "args": {"n": 3}}</tool_call>\n```'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 1)  # tag found regardless of surrounding markdown

    def test_malformed_json_skipped_gracefully(self):
        """Malformed JSON should be silently skipped, not crash."""
        text = '<tool_call>not valid json at all {{{</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 0)

    def test_partial_json_skipped(self):
        """Partially valid JSON (missing closing brace) should be skipped."""
        text = '<tool_call>{"name": "git_log", "args": {"n": 5}</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 0)

    def test_missing_name_field_skipped(self):
        """Tool call without 'name' should be skipped."""
        text = '<tool_call>{"args": {"n": 5}}</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 0)

    def test_no_tool_calls_returns_empty(self):
        text = "I have reviewed the git history and found no significant changes."
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 0)
        self.assertFalse(self.ex.has_calls(text))

    def test_has_calls_true_positive(self):
        text = 'Some text <tool_call>{"name": "git_log", "args": {}}</tool_call> more text'
        self.assertTrue(self.ex.has_calls(text))

    def test_empty_args_dict(self):
        """Empty args should parse correctly."""
        text = '<tool_call>{"name": "git_tags", "args": {}}</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args, {})

    def test_string_values_in_args(self):
        """String arguments with special characters."""
        text = '<tool_call>{"name": "git_diff_full", "args": {"from_ref": "HEAD~3", "to_ref": "HEAD"}}</tool_call>'
        calls = self.ex.parse(text)
        self.assertEqual(calls[0].args["from_ref"], "HEAD~3")

    def test_100_tool_calls_parsed(self):
        """Volume test: 100 tool calls in one response."""
        calls_text = '\n'.join(
            f'<tool_call>{{"name": "git_log", "args": {{"n": {i}}}}}</tool_call>'
            for i in range(1, 101)
        )
        calls = self.ex.parse(calls_text)
        self.assertEqual(len(calls), 100)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SECURITY TESTS
#    Does the allowlist actually hold? Can it be escaped?
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurity(unittest.TestCase):

    def setUp(self):
        # Temp dir so tests never touch real files
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_unlisted_path_blocked(self):
        """Arbitrary file not in allowlist should raise PermissionError."""
        with self.assertRaises(PermissionError):
            read_file("app/memory/manager.py")

    def test_read_path_traversal_blocked(self):
        """Path traversal like ../../etc/passwd must be blocked."""
        with self.assertRaises(PermissionError):
            read_file("../../etc/passwd")

    def test_read_absolute_path_blocked(self):
        """Absolute path not in allowlist must be blocked."""
        with self.assertRaises(PermissionError):
            read_file("/etc/passwd")

    def test_write_unlisted_path_blocked(self):
        """Writing to an unlisted path must raise PermissionError."""
        with self.assertRaises(PermissionError):
            write_file("app/config/settings.py", "malicious content")

    def test_write_path_traversal_blocked(self):
        """Path traversal write must be blocked."""
        with self.assertRaises(PermissionError):
            write_file("../../evil.py", "import os; os.system('rm -rf /')")

    def test_write_absolute_path_blocked(self):
        """Absolute path write must be blocked."""
        with self.assertRaises(PermissionError):
            write_file("/tmp/evil.py", "malicious")

    def test_write_src_py_blocked(self):
        """Model can't overwrite source code even if it tries a clever path."""
        for evil_path in [
            "app/__init__.py",
            "app/agents/doc_agent.py",
            "config.yaml",  # not in ALLOWED_WRITE (only in ALLOWED_READ)
        ]:
            with self.subTest(path=evil_path):
                with self.assertRaises(PermissionError):
                    write_file(evil_path, "malicious")

    def test_executor_unknown_tool_returns_error_not_crash(self):
        """Calling an unknown tool returns ToolResult(success=False), never raises."""
        _, ex = _make_executor()
        call = ParsedCall(name="rm_rf_slash", args={}, raw="")
        result = ex.run(call)
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error)

    def test_tool_exception_wrapped_not_propagated(self):
        """If a tool raises internally, it must become ToolResult(success=False)."""
        def always_raises(**kwargs):
            raise RuntimeError("catastrophic failure")

        _, ex = _make_executor()
        bad_tool = ToolDefinition(
            name="bad_tool",
            description="always fails",
            parameters={"type": "object", "properties": {}},
            handler=always_raises,
        )
        ex._registry.register(bad_tool)
        call = ParsedCall(name="bad_tool", args={}, raw="")
        result = ex.run(call)
        self.assertFalse(result.success)
        self.assertIn("catastrophic failure", result.error)


# ══════════════════════════════════════════════════════════════════════════════
# 3. GIT TOOL TESTS
#    Edge cases in git operations — these must fail gracefully
# ══════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(
    subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, cwd=ROOT).returncode == 0,
    "No git repo found — skipping git tests"
)
class TestGitTools(unittest.TestCase):

    def test_git_log_returns_commits(self):
        result = git_log(5)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_git_log_large_n_doesnt_crash(self):
        """Asking for 10,000 commits when only a few exist should just return what's there."""
        result = git_log(10000)
        self.assertIsInstance(result, str)

    def test_git_diff_stat_valid_refs(self):
        result = git_diff_stat("HEAD~1", "HEAD")
        self.assertIsInstance(result, str)

    def test_git_diff_full_truncated_at_limit(self):
        """Diff output must be capped — never blow the context window."""
        from app.tools.git_tools import DIFF_MAX_CHARS
        result = git_diff_full("HEAD~2", "HEAD")
        self.assertLessEqual(len(result), DIFF_MAX_CHARS + 200)  # +200 for the truncation message

    def test_git_diff_invalid_ref_returns_toolresult_error(self):
        """Invalid ref must raise RuntimeError (wrapped by ToolDefinition.execute)."""
        _, ex = _make_executor()
        call = ParsedCall(
            name="git_diff_stat",
            args={"from_ref": "nonexistent-branch-xyz", "to_ref": "HEAD"},
            raw=""
        )
        result = ex.run(call)
        self.assertFalse(result.success)
        self.assertTrue(len(result.error) > 0)

    def test_git_via_executor_roundtrip(self):
        """Full roundtrip: parse text → run tool → get result."""
        _, ex = _make_executor()
        text = '<tool_call>{"name": "git_log", "args": {"n": 3}}</tool_call>'
        calls = ex.parse(text)
        result = ex.run(calls[0])
        self.assertTrue(result.success)
        self.assertIsInstance(result.output, str)


# ══════════════════════════════════════════════════════════════════════════════
# 4. FILE TOOL TESTS
#    Permissions, missing files, empty content, write verification
# ══════════════════════════════════════════════════════════════════════════════

class TestFileTools(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        # Create docs directory matching the allowlist paths
        Path("docs").mkdir()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_existing_file(self):
        Path("docs/CHANGELOG.md").write_text("# Changelog\n\n## v1.0\n- Initial release")
        content = read_file("docs/CHANGELOG.md")
        self.assertIn("# Changelog", content)

    def test_read_nonexistent_allowed_file_returns_placeholder(self):
        """Non-existent file in allowlist should return a message, not crash."""
        result = read_file("docs/DEVLOG.md")  # doesn't exist yet
        self.assertIn("not found", result)

    def test_write_creates_file(self):
        write_file("docs/CHANGELOG.md", "# Changelog\n\n## v2.0\n- Added things")
        self.assertTrue(Path("docs/CHANGELOG.md").exists())
        self.assertIn("## v2.0", Path("docs/CHANGELOG.md").read_text())

    def test_write_overwrites_existing(self):
        """Write should replace the entire file (agent writes complete content)."""
        Path("docs/CHANGELOG.md").write_text("old content")
        write_file("docs/CHANGELOG.md", "new content")
        self.assertEqual(Path("docs/CHANGELOG.md").read_text(), "new content")

    def test_write_empty_string_allowed(self):
        """Empty writes are allowed — confirmation is the gate, not the allowlist."""
        write_file("docs/CHANGELOG.md", "")
        self.assertEqual(Path("docs/CHANGELOG.md").read_text(), "")

    def test_write_large_content(self):
        """Large file write (100k chars) should not crash."""
        large = "# Changelog\n\n" + ("- Added something\n" * 5000)
        write_file("docs/CHANGELOG.md", large)
        result = Path("docs/CHANGELOG.md").read_text()
        self.assertEqual(result, large)

    def test_output_capped_in_executor(self):
        """Executor must cap tool output — read_file on huge file shouldn't blow context."""
        from app.tools.executor import MAX_OUTPUT_CHARS
        big_content = "x" * (MAX_OUTPUT_CHARS * 3)
        Path("docs/CHANGELOG.md").write_text(big_content)
        _, ex = _make_executor()
        call = ParsedCall(name="read_file", args={"path": "docs/CHANGELOG.md"}, raw="")
        result = ex.run(call)
        self.assertTrue(result.success)
        self.assertLessEqual(len(result.output), MAX_OUTPUT_CHARS + 100)
        self.assertIn("trimmed", result.output)


# ══════════════════════════════════════════════════════════════════════════════
# 5. AGENT LOOP TESTS
#    Does the loop behave correctly with a scripted mock model?
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentLoop(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        Path("docs").mkdir()
        Path("docs/CHANGELOG.md").write_text("# Changelog\n\n## [1.0.0]\n- Initial release\n")
        Path("docs/DEVLOG.md").write_text("# Dev Log\n\n## v1.0.0\nFirst version.\n")

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _agent(self, responses: list[str]) -> tuple[DocumentationAgent, MockModel]:
        model = MockModel(responses)
        agent = DocumentationAgent(model=model)
        # Override executor to skip confirmation prompts in tests
        agent._executor._require_confirmation = False
        return agent, model

    def test_immediate_response_no_tools(self):
        """Model answers immediately — loop runs exactly once."""
        agent, model = self._agent(["Here is the changelog entry."])
        result = agent.run("Generate a changelog entry", verbose=False)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result, "Here is the changelog entry.")

    def test_single_tool_use_then_done(self):
        """Model calls one tool, then answers — loop runs exactly twice."""
        agent, model = self._agent([
            '<tool_call>{"name": "git_log", "args": {"n": 3}}</tool_call>',
            "Here is the changelog based on git history.",
        ])
        result = agent.run("Generate a changelog entry", verbose=False)
        self.assertEqual(model.call_count, 2)
        self.assertNotIn("<tool_call>", result)

    def test_multiple_tools_sequential(self):
        """Model calls tools across multiple iterations."""
        agent, model = self._agent([
            '<tool_call>{"name": "git_log", "args": {"n": 5}}</tool_call>',
            '<tool_call>{"name": "read_file", "args": {"path": "docs/CHANGELOG.md"}}</tool_call>',
            "Here is the final changelog entry.",
        ])
        result = agent.run("Generate a changelog entry", verbose=False)
        self.assertEqual(model.call_count, 3)
        self.assertEqual(result, "Here is the final changelog entry.")

    def test_max_iterations_ceiling_enforced(self):
        """Model that never stops calling tools must hit MAX_ITERATIONS and return error."""
        # Model always requests a tool — never gives a plain text response
        infinite_responses = ['<tool_call>{"name": "git_log", "args": {"n": 1}}</tool_call>'] * 100
        agent, model = self._agent(infinite_responses)
        result = agent.run("Generate a changelog entry", verbose=False)
        self.assertEqual(model.call_count, MAX_ITERATIONS)
        self.assertIn("iteration limit", result.lower())

    def test_unknown_tool_error_propagated_to_model(self):
        """Model calls non-existent tool — gets error result, loop continues."""
        agent, model = self._agent([
            '<tool_call>{"name": "nonexistent_tool", "args": {}}</tool_call>',
            "Okay, I'll work with what I have.",
        ])
        result = agent.run("Generate a changelog entry", verbose=False)
        # Loop completes normally — error was injected as a tool_result
        self.assertEqual(model.call_count, 2)
        self.assertEqual(result, "Okay, I'll work with what I have.")

    def test_tool_result_injected_into_messages(self):
        """Verify tool results actually appear in the conversation the model sees."""
        received = []
        class SpyModel:
            call_count = 0
            def generate(self, messages, **kwargs):
                self.call_count += 1
                received.append(messages.copy())
                if self.call_count == 1:
                    return ModelResponse(
                        content='<tool_call>{"name": "git_log", "args": {"n": 1}}</tool_call>',
                        model="spy"
                    )
                return ModelResponse(content="Done.", model="spy")
            @property
            def model_name(self): return "spy"
            @property
            def role(self): return "general"

        model = SpyModel()
        agent = DocumentationAgent(model=model)
        agent._executor._require_confirmation = False
        agent.run("task", verbose=False)

        # Second call should include the tool result in messages
        second_call_messages = received[1]
        last_message = second_call_messages[-1]
        self.assertEqual(last_message["role"], "user")
        self.assertIn("tool_result", last_message["content"])
        self.assertIn("git_log", last_message["content"])

    def test_agent_writes_file_when_instructed(self):
        """Full flow: model reads format, generates entry, writes file."""
        import json as _json  # local import to avoid confusion
        changelog_path = "docs/CHANGELOG.md"
        new_content = "# Changelog\n\n## [2.0.0]\n- New feature\n\n## [1.0.0]\n- Initial release\n"

        # NOTE: must use json.dumps() not repr() here.
        # The parser uses json.loads() to parse tool call arguments.
        # repr() produces Python syntax (single quotes) which is invalid JSON.
        # This is exactly the bug the parser silently skips — good test of real behavior.
        agent, model = self._agent([
            f'<tool_call>{{"name": "read_file", "args": {{"path": "{changelog_path}"}}}}</tool_call>',
            f'<tool_call>{{"name": "write_file", "args": {{"path": "{changelog_path}", "content": {_json.dumps(new_content)}}}}}</tool_call>',
            "I have written the changelog entry.",
        ])
        agent.run("Generate and write a changelog entry", verbose=False)

        written = Path(changelog_path).read_text()
        self.assertIn("## [2.0.0]", written)
        self.assertIn("## [1.0.0]", written)  # old content preserved


# ══════════════════════════════════════════════════════════════════════════════
# 6. ADVERSARIAL TESTS
#    Actively trying to break things — what a confused model might attempt
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarial(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        Path("docs").mkdir()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _agent(self, responses):
        model = MockModel(responses)
        agent = DocumentationAgent(model=model)
        agent._executor._require_confirmation = False
        return agent

    def test_model_tries_to_write_source_code(self):
        """Model attempts to overwrite source files — must be blocked."""
        agent = self._agent([
            '<tool_call>{"name": "write_file", "args": {"path": "app/agents/doc_agent.py", "content": "# pwned"}}</tool_call>',
            "Done.",
        ])
        agent.run("task", verbose=False)
        # app/agents/doc_agent.py in the REAL project should be untouched
        # In this test, the path simply doesn't exist in tmpdir and is blocked
        self.assertFalse(Path("app/agents/doc_agent.py").exists())

    def test_model_tries_path_traversal_write(self):
        """Model uses ../ to escape docs directory."""
        agent = self._agent([
            '<tool_call>{"name": "write_file", "args": {"path": "../../etc/evil", "content": "bad"}}</tool_call>',
            "Done.",
        ])
        agent.run("task", verbose=False)
        self.assertFalse(Path("/etc/evil").exists())

    def test_model_tries_to_read_secrets(self):
        """Model attempts to read a secrets/config file."""
        # Create a fake .env in tmpdir to simulate having secrets
        Path(".env").write_text("SECRET_KEY=super_secret_123")
        agent = self._agent([
            '<tool_call>{"name": "read_file", "args": {"path": ".env"}}</tool_call>',
            "Done.",
        ])
        # The tool_result injected back to the model should contain an error, not the secret
        received_messages = []
        class SpyModel:
            call_count = 0
            def generate(self, messages, **kwargs):
                self.call_count += 1
                received_messages.append(messages.copy())
                if self.call_count == 1:
                    return ModelResponse(
                        content='<tool_call>{"name": "read_file", "args": {"path": ".env"}}</tool_call>',
                        model="spy"
                    )
                return ModelResponse(content="Done.", model="spy")
            @property
            def model_name(self): return "spy"
            @property
            def role(self): return "general"

        spy = SpyModel()
        a = DocumentationAgent(model=spy)
        a._executor._require_confirmation = False
        a.run("task", verbose=False)

        # The tool result message should NOT contain the secret
        all_content = " ".join(m["content"] for msgs in received_messages for m in msgs)
        self.assertNotIn("super_secret_123", all_content)
        self.assertIn("Permission denied", all_content)

    def test_model_floods_with_massive_output(self):
        """Model returns 10,000 chars per response — loop must not hang or OOM."""
        big_response = "A" * 10_000 + '<tool_call>{"name": "git_log", "args": {"n": 1}}</tool_call>'
        responses = [big_response] * MAX_ITERATIONS
        agent = self._agent(responses)
        result = agent.run("task", verbose=False)
        self.assertIn("iteration limit", result.lower())

    def test_write_with_malicious_filename_in_args(self):
        """Model injects special chars in filename."""
        _, ex = _make_executor()
        call = ParsedCall(
            name="write_file",
            args={"path": "docs/CHANGELOG.md; rm -rf /", "content": "bad"},
            raw=""
        )
        result = ex.run(call)
        self.assertFalse(result.success)
        self.assertIn("Permission denied", result.error)


# ─── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pretty output
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    sections = [
        ("Parser",      TestParser),
        ("Security",    TestSecurity),
        ("Git Tools",   TestGitTools),
        ("File Tools",  TestFileTools),
        ("Agent Loop",  TestAgentLoop),
        ("Adversarial", TestAdversarial),
    ]

    # Allow filtering: python3 stress_test.py TestParser
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None

    for label, cls in sections:
        if filter_name and filter_name not in (label, cls.__name__):
            continue
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)