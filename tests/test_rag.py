"""
Unit tests for app.knowledge.rag.answer.

Exercises prompt construction, empty-source handling, and the happy path with
a stub ModelClient — no ChromaDB or Ollama required.
"""

import unittest

from app.knowledge.rag import answer, RAGResult, _format_context, _citation_for
from app.knowledge.store import PaperStore
from app.knowledge.chunk import Chunk


class _StubClient:
    """Records the messages it received and returns a canned answer."""

    def __init__(self, reply="Battery uses a liquid electrolyte [Battery Intro, p.1]."):
        self.last_messages = None
        self.reply = reply

    def generate(self, messages, **kwargs):
        self.last_messages = messages
        return _Resp(self.reply)


class _Resp:
    def __init__(self, content):
        self.content = content


def _chunks(filename, title, specs):
    return [
        Chunk(doc_id="", filename=filename, title=title, page=p, chunk_index=i, text=t)
        for i, (p, t) in enumerate(specs)
    ]


class FakeStore:
    """In-memory stand-in implementing the search() surface used by answer()."""

    def __init__(self, sources):
        self._sources = sources
        self.last_query = None
        self.last_limit = None

    def search(self, query, limit=6, folder=None):
        self.last_query = query
        self.last_limit = limit
        self.last_folder = folder
        return self._sources[:limit]


class TestRAGHelpers(unittest.TestCase):
    def test_format_context_includes_citation_markers(self):
        src = {"title": "Battery Intro", "filename": "b.pdf", "page": 3,
               "chunk_index": 0, "text": "solid state separator"}
        ctx = _format_context([src])
        self.assertIn("[1] Battery Intro, p.3", ctx)
        self.assertIn("solid state separator", ctx)

    def test_format_context_empty(self):
        self.assertEqual(_format_context([]), "(no excerpts retrieved)")

    def test_citation_for_uses_title_and_page(self):
        self.assertEqual(
            _citation_for({"title": "X", "filename": "x.pdf", "page": 7}),
            "[X, p.7]",
        )

    def test_citation_for_falls_back_to_filename(self):
        self.assertEqual(
            _citation_for({"filename": "y.pdf", "page": 2}),
            "[y.pdf, p.2]",
        )


class TestAnswer(unittest.TestCase):
    def test_empty_query_returns_prompt(self):
        store = FakeStore([])
        res = answer("", _StubClient(), store)
        self.assertIsInstance(res, RAGResult)
        self.assertTrue(res.answer)
        self.assertEqual(res.sources, [])

    def test_no_sources_returns_explanation(self):
        store = FakeStore([])
        res = answer("What is a battery?", _StubClient(), store)
        self.assertIn("couldn't find", res.answer.lower())
        self.assertEqual(res.sources, [])

    def test_happy_path_returns_answer_and_sources(self):
        sources = [
            {"doc_id": "d1", "filename": "b.pdf", "title": "Battery Intro",
             "page": 1, "chunk_index": 0,
             "text": "Lithium ion batteries use a liquid electrolyte."},
            {"doc_id": "d1", "filename": "b.pdf", "title": "Battery Intro",
             "page": 1, "chunk_index": 1,
             "text": "Solid state batteries use a ceramic separator."},
        ]
        store = FakeStore(sources)
        client = _StubClient()
        res = answer("What electrolyte do batteries use?", client, store, limit=4)

        self.assertEqual(res.answer, client.reply)
        self.assertEqual(res.sources, sources)
        # The retrieved excerpts must be forwarded into the user message.
        self.assertIsNotNone(client.last_messages)
        user_msg = client.last_messages[1]["content"]
        self.assertIn("Lithium ion batteries", user_msg)
        self.assertIn("Question: What electrolyte do batteries use?", user_msg)
        self.assertEqual(store.last_query, "What electrolyte do batteries use?")
        self.assertEqual(store.last_limit, 4)

    def test_respects_limit_when_more_sources_available(self):
        sources = [
            {"doc_id": "d", "filename": "f.pdf", "title": "T", "page": i + 1,
             "chunk_index": i, "text": f"chunk {i}"}
            for i in range(10)
        ]
        store = FakeStore(sources)
        answer("q", _StubClient(), store, limit=3)
        self.assertEqual(store.last_limit, 3)


if __name__ == "__main__":
    unittest.main()
