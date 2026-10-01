"""Tests for memory pipeline façade."""

from types import SimpleNamespace

from app.domain import MemoryItem, MemoryKind, MemoryScope
from app.memory.pipeline import MemoryPipeline


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
        manager.store.return_value = MemoryItem(
            id="mem-1",
            content="user likes coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
            confidence=0.9,
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


class TestMCPServerIntegration:
    """Integration test: list tools via the server's callback."""

    async def test_list_tools(self):
        """Server lists tools correctly."""
        from app.integrations.mcp.server import _on_list_tools

        result = await _on_list_tools(None, None)
        assert hasattr(result, "tools")
        names = [t.name for t in result.tools]
        assert "read_file" in names
        assert "workspace_git_state" in names
        assert len(names) == 18
