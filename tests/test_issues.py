#!/usr/bin/env python3
"""
Targeted verification tests for the issues found after testing.

Run individual issue groups, e.g.:
    python -m unittest tests.test_issues.TestAppendFile -v
    python -m unittest tests.test_issues -v

Each Test* class maps to one issue from the triage list.
"""

import sys
import os
import json
import unittest
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.tools.base import ToolRegistry, ToolDefinition
from app.tools.executor import ToolExecutor, ParsedCall
from app.models.client import ModelResponse


def make_call(name: str, args: dict) -> str:
    """Build a <tool_call>...</tool_call> block from a tool name + args."""
    return f"<tool_call>{json.dumps({'name': name, 'args': args})}</tool_call>"


# ============================================================================
# ISSUE 1 (P0): append_file tool is dead code - doc agent workflow broken
#   Verify append_file is registered, callable, and wired into the doc agent
#   (so the "Use append_file to add entries" instruction is executable).
# ============================================================================

from app.tools.file_tools import FILE_TOOLS, append_file


class TestAppendFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        Path("docs").mkdir()
        self.allowed = "docs/CHANGELOG.md"

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_append_file_is_registered_in_file_tools(self):
        names = {t.name for t in FILE_TOOLS}
        self.assertIn("append_file", names)

    def test_append_file_appends_without_overwriting(self):
        Path(self.allowed).write_text("base\n")
        append_file(self.allowed, "added\n")
        self.assertEqual(Path(self.allowed).read_text(), "base\nadded\n")

    def test_append_file_runs_through_executor(self):
        Path(self.allowed).write_text("base\n")
        reg = ToolRegistry()
        reg.register_many(FILE_TOOLS)
        ex = ToolExecutor(reg, require_confirmation=False)
        result = ex.run(ParsedCall(
            name="append_file",
            args={"path": self.allowed, "content": "appended\n"},
            raw="",
        ))
        self.assertTrue(result.success, result.error)
        self.assertIn("appended", Path(self.allowed).read_text())

    def test_doc_agent_registers_append_file(self):
        from app.agents.doc_agent import DocumentationAgent

        class DummyModel:
            def generate(self, messages, **kwargs):
                return ModelResponse(content="Done.", model="mock")
            @property
            def model_name(self): return "mock"
            @property
            def role(self): return "general"

        agent = DocumentationAgent(model=DummyModel())
        registered = {t.name for t in agent._registry.all()}
        self.assertIn("append_file", registered)

    def test_doc_agent_can_append_in_a_loop(self):
        """End-to-end: a scripted model uses append_file and the file grows."""
        from app.agents.doc_agent import DocumentationAgent

        class ScriptedModel:
            def __init__(self):
                self.n = 0
            def generate(self, messages, **kwargs):
                self.n += 1
                if self.n == 1:
                    return ModelResponse(
                        content=make_call("read_file", {"path": "docs/CHANGELOG.md"}),
                        model="mock",
                    )
                if self.n == 2:
                    return ModelResponse(
                        content=make_call(
                            "append_file",
                            {"path": "docs/CHANGELOG.md", "content": "## v9.9\n- documented\n"},
                        ),
                        model="mock",
                    )
                return ModelResponse(content="Done.", model="mock")
            @property
            def model_name(self): return "mock"
            @property
            def role(self): return "general"

        Path(self.allowed).write_text("# Changelog\n")
        agent = DocumentationAgent(model=ScriptedModel())
        agent._executor._require_confirmation = False
        agent.run("document the latest change", verbose=False)

        content = Path(self.allowed).read_text()
        self.assertIn("## v9.9", content)
        self.assertIn("# Changelog", content)


# ============================================================================
# ISSUE 2 (P0): _memory_to_text nested inside wrong method - dead code
#   Verify _memory_to_text is a real class-level method (not a nested function
#   inside on_index_rebuilt), is actually invoked by the retriever, and
#   produces the correct embedding text.
# ============================================================================

import inspect

from app.memory.schema import Memory
from app.memory.vector_retriever import VectorRetriever


class TestMemoryToText(unittest.TestCase):
    def test_memory_to_text_is_class_level_method_not_nested(self):
        # If it were nested inside on_index_rebuilt, the class would NOT
        # expose it as an attribute at all.
        self.assertTrue(
            hasattr(VectorRetriever, "_memory_to_text"),
            "_memory_to_text missing at class level - looks nested/dead",
        )
        self.assertTrue(callable(getattr(VectorRetriever, "_memory_to_text")))

    def test_on_index_rebuilt_does_not_redefine_it_nested(self):
        src = inspect.getsource(VectorRetriever.on_index_rebuilt)
        # No nested `def _memory_to_text` inside on_index_rebuilt.
        self.assertNotIn("def _memory_to_text", src)

    def test_memory_to_text_builds_expected_embedding_text(self):
        mem = Memory(category="preference", memory_type="like", value="chocolate")
        # Called unbound: first arg is `self` (unused by the method body).
        text = VectorRetriever._memory_to_text(None, mem)
        self.assertEqual(text, "preference like: chocolate")

    def test_on_memory_added_invokes_memory_to_text(self):
        # The live method must use _memory_to_text (not an inline f-string),
        # proving the helper is not dead code.
        src = inspect.getsource(VectorRetriever.on_memory_added)
        self.assertIn("_memory_to_text", src)


# ============================================================================
# ISSUE 3 (P0): active_profile never loaded from config.yaml - Config ignored
#   Verify Settings.load() honours `active_profile` from a config file, and
#   gracefully falls back when the value names a non-existent profile.
# ============================================================================

import yaml

from app.config.settings import Settings


class TestActiveProfile(unittest.TestCase):
    def _write_config(self, tmpdir: str, data: dict) -> str:
        path = os.path.join(tmpdir, "config.yaml")
        with open(path, "w") as f:
            yaml.safe_dump(data, f)
        return path

    def test_active_profile_loaded_from_config(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_config(td, {
                "active_profile": "cloud",
                "profiles": {"local": {}, "cloud": {}},
            })
            self.assertEqual(Settings.load(path=path).active_profile, "cloud")

    def test_active_profile_default_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_config(td, {"profiles": {"local": {}, "cloud": {}}})
            self.assertEqual(Settings.load(path=path).active_profile, "local")

    def test_active_profile_invalid_falls_back(self):
        # Names a profile that doesn't exist -> must keep default, not crash.
        with tempfile.TemporaryDirectory() as td:
            path = self._write_config(td, {
                "active_profile": "does_not_exist",
                "profiles": {"local": {}, "cloud": {}},
            })
            self.assertEqual(Settings.load(path=path).active_profile, "local")

    def test_active_profile_propagates_to_switcher(self):
        from app.models.switcher import ModelSwitcher
        with tempfile.TemporaryDirectory() as td:
            path = self._write_config(td, {
                "active_profile": "cloud",
                "profiles": {"local": {}, "cloud": {}},
                "models": {
                    "general": {
                        "name": "stub", "role": "general",
                        "backend": "llamacpp", "base_url": "http://localhost:1/v1",
                    }
                },
            })
            switcher = ModelSwitcher(Settings.load(path=path))
            self.assertEqual(switcher.active_profile, "cloud")


# ============================================================================
# ISSUE 4 (P0): Parser deduplicates by tool name (not call instance)
#   The doc agent emits e.g. several git_show calls in one turn (same name,
#   different args). The parser must return ALL of them, not collapse to one.
# ============================================================================

from app.tools.git_tools import GIT_TOOLS


class TestParserNoNameDedup(unittest.TestCase):
    def setUp(self):
        self.reg = ToolRegistry()
        self.reg.register_many(FILE_TOOLS)
        self.reg.register_many(GIT_TOOLS)
        self.ex = ToolExecutor(self.reg, require_confirmation=False)

    def test_repeated_same_name_json_calls_all_parsed(self):
        text = "\n".join(make_call("git_show", {"ref": f"abc{i}"}) for i in range(3))
        calls = self.ex.parse(text)
        self.assertEqual(len(calls), 3)
        self.assertEqual({c.args["ref"] for c in calls}, {"abc0", "abc1", "abc2"})

    def test_repeated_same_name_hybrid_calls_all_parsed(self):
        text = "\n".join(
            f'<tool_call>git_show({json.dumps({"ref": f"h{i}"})})</tool_call>'
            for i in range(4)
        )
        self.assertEqual(len(self.ex.parse(text)), 4)

    def test_execute_all_parsed_calls_no_data_loss(self):
        # Every parsed call must actually run through the executor (no drop).
        # Use a deterministic, side-effect-free tool so the assertion is about
        # execution, not about git ref validity.
        executed = []
        def recorder(**kwargs):
            executed.append(kwargs)
            return "ok"
        self.reg.register(ToolDefinition(
            name="recorder",
            description="test recorder",
            parameters={"type": "object", "properties": {}},
            handler=recorder,
        ))
        text = "\n".join(make_call("recorder", {"i": i}) for i in range(3))
        for call in self.ex.parse(text):
            result = self.ex.run(call)
            self.assertTrue(result.success, result.error)
        self.assertEqual(len(executed), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
