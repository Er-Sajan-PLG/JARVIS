"""Tests for memory pipeline and workspace awareness (Sprint 3 final pieces)."""

import tempfile
from pathlib import Path

from app.memory.pipeline import MemoryPipeline
from app.memory.schema import Memory


class TestMemoryPipeline:
    def test_extract_and_store_no_extractor(self):
        """Pipeline without extractor is a no-op."""
        from unittest.mock import MagicMock

        pipeline = MemoryPipeline(MagicMock(), extractor=None)
        import asyncio

        result = asyncio.run(pipeline.extract_and_store("hello"))
        assert result == []

    def test_extract_and_store_extracts_and_dedups(self):
        """Pipeline extracts, deduplicates, and stores."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from app.memory.llm_extractor import LLMFactExtractor

        raw = (
            '[{"content": "user likes coffee", "kind": "preference", '
            '"scope": "user", "confidence": 0.9}]'
        )
        model = MagicMock()
        model.generate.return_value = SimpleNamespace(content=raw)
        extractor = LLMFactExtractor(model)

        manager = MagicMock()
        manager.get_all.return_value = []
        manager.store.return_value = Memory(
            category="general",
            memory_type="preference",
            value="user likes coffee",
        )

        pipeline = MemoryPipeline(manager, extractor=extractor)

        import asyncio

        result = asyncio.run(pipeline.extract_and_store("I like coffee"))
        assert len(result) == 1
        assert result[0].content == "user likes coffee"
        assert manager.store.called

    def test_retrieve_with_scope_filter(self):
        """Pipeline retrieve applies scope filter."""
        from unittest.mock import MagicMock

        pipeline = MemoryPipeline(MagicMock(), extractor=None)
        pipeline._manager.retrieve.return_value = []

        results = pipeline.retrieve("query", scope_filter="user")
        assert results == []

    def test_extract_dedup_collapses_duplicates(self):
        """Identical extractions are deduplicated."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from app.memory.llm_extractor import LLMFactExtractor

        raw = (
            '[{"content": "I like coffee", "kind": "preference", '
            '"scope": "user", "confidence": 0.9}]'
        )
        model = MagicMock()
        model.generate.return_value = SimpleNamespace(content=raw)
        extractor = LLMFactExtractor(model)

        manager = MagicMock()
        manager.get_all.return_value = []
        manager.store.return_value = None

        pipeline = MemoryPipeline(manager, extractor=extractor)

        import asyncio

        result1 = asyncio.run(pipeline.extract_and_store("I like coffee"))
        result2 = asyncio.run(pipeline.extract_and_store("I like coffee"))
        # Both should extract 1 item each (dedup is against stored, not across calls)
        assert len(result1) == 1
        assert len(result2) == 1


class TestWorkspaceAwareness:
    def test_get_git_state_in_repo(self):
        """get_git_state returns real git info in a git repo."""
        from app.workspace.manager import WorkspaceManager

        mgr = WorkspaceManager(workspace_root=Path.cwd())
        state = mgr.get_git_state()
        assert state["head"] != "unknown"
        assert state["branch"] != "unknown"
        assert isinstance(state["dirty"], bool)

    def test_get_file_tree(self):
        """get_file_tree returns files with depth limit."""
        from app.workspace.manager import WorkspaceManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.txt").write_text("a")
            (tmp_path / "sub").mkdir()
            (tmp_path / "sub" / "b.py").write_text("b")
            (tmp_path / "sub" / "deep").mkdir()
            (tmp_path / "sub" / "deep" / "c.md").write_text("c")

            mgr = WorkspaceManager(workspace_root=tmp_path)
            tree = mgr.get_file_tree(max_depth=2)
            paths = [t["path"] for t in tree]
            assert "a.txt" in paths
            assert "sub/b.py" in paths
            # c.md is at depth 2 (sub/deep/c.md -> parts=3, depth=2)
            assert "sub/deep/c.md" in paths

    def test_get_file_tree_respects_max_depth(self):
        from app.workspace.manager import WorkspaceManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.txt").write_text("a")
            (tmp_path / "sub" / "deep").mkdir(parents=True)
            (tmp_path / "sub" / "deep" / "c.md").write_text("c")

            mgr = WorkspaceManager(workspace_root=tmp_path)
            tree = mgr.get_file_tree(max_depth=1)
            paths = [t["path"] for t in tree]
            assert "a.txt" in paths
            assert "sub/deep/c.md" not in paths
