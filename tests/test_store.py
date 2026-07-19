"""
Unit tests for app.knowledge.store.PaperStore.

Uses an isolated temp ChromaDB directory and a deterministic fake embedding
function so the tests never touch Ollama or the real data/ directory.
"""

import hashlib
import shutil
import tempfile
import unittest

from app.knowledge.store import PaperStore
from app.knowledge.chunk import Chunk


class _FakeEmbedding:
    """Deterministic, meaningfully-similar embedding stand-in.

    ChromaDB invokes the function three ways depending on the operation:
      - add/upsert:  __call__(input=<list[str]>)
      - query:       embed_query(input=<list[str]>)   (list, in this chromadb version)
      - get/delete:  embed_documents (not used by these paths)

    Instead of a hash, we build a bag-of-words vector over a fixed vocab so
    that texts sharing vocabulary are embedded nearby. This lets the ranking
    assertions in the search tests be meaningful without a real model.
    """

    _VOCAB = [
        "lithium", "ion", "battery", "batteries", "solid", "state", "electrolyte",
        "ceramic", "separator", "polyethylene", "polymer", "packaging", "cell",
        "liquid", "content", "chunk", "number", "about", "alpha", "beta",
    ]

    def __init__(self, dim: int = len(_VOCAB)):
        self._dim = dim

    def _vec(self, text: str):
        words = text.lower().split()
        vec = [0.0] * len(self._VOCAB)
        for w in words:
            if w in self._VOCAB:
                vec[self._VOCAB.index(w)] += 1.0
        return vec

    def __call__(self, input, **kwargs):
        items = input if isinstance(input, list) else [input]
        return [self._vec(t) for t in items]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, input, **kwargs):
        items = input if isinstance(input, list) else [input]
        return [self._vec(t) for t in items]


def _chunks(filename, title, specs):
    """Build Chunk objects from (page, text) specs."""
    out = []
    for i, (page, text) in enumerate(specs):
        out.append(
            Chunk(
                doc_id="",
                filename=filename,
                title=title,
                page=page,
                chunk_index=i,
                text=text,
            )
        )
    return out


class TestPaperStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = PaperStore(persist_dir=self._tmp)
        # Swap in the deterministic fake embedding function.
        self._store._collection._embedding_function = _FakeEmbedding()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_store(self):
        self.assertEqual(self._store.count(), 0)
        self.assertEqual(self._store.document_count(), 0)
        self.assertEqual(self._store.list_documents(), [])
        self.assertEqual(self._store.search("anything"), [])

    def test_add_document_returns_doc_id_and_counts(self):
        doc_id = self._store.add_document(
            "battery.pdf",
            "Battery Intro",
            _chunks("battery.pdf", "Battery Intro", [(1, "lithium ion cell")]),
        )
        self.assertTrue(doc_id)
        self.assertEqual(self._store.count(), 1)
        self.assertEqual(self._store.document_count(), 1)
        docs = self._store.list_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["doc_id"], doc_id)
        self.assertEqual(docs[0]["filename"], "battery.pdf")
        self.assertEqual(docs[0]["title"], "Battery Intro")
        self.assertEqual(docs[0]["chunk_count"], 1)

    def test_add_document_empty_chunks_raises(self):
        with self.assertRaises(ValueError):
            self._store.add_document("empty.pdf", "Empty", [])

    def test_reingest_same_doc_overwrites_not_duplicates(self):
        specs = [(1, "first version of the text")]
        doc_id = self._store.add_document(
            "dup.pdf", "Dup", _chunks("dup.pdf", "Dup", specs)
        )
        # Re-ingest with the same doc_id (simulating upsert overwrite).
        self._store.add_document(
            "dup.pdf", "Dup", _chunks("dup.pdf", "Dup", [(1, "second version")])
        )
        # chunk_index 0 is overwritten, not duplicated.
        self.assertEqual(self._store.count(), 1)
        self.assertEqual(self._store.document_count(), 1)
        docs = self._store.list_documents()
        self.assertEqual(docs[0]["chunk_count"], 1)

    def test_list_documents_dedupes_multiple_chunks(self):
        self._store.add_document(
            "a.pdf",
            "Paper A",
            _chunks(
                "a.pdf",
                "Paper A",
                [(1, "alpha one"), (1, "alpha two"), (2, "alpha three")],
            ),
        )
        self._store.add_document(
            "b.pdf", "Paper B", _chunks("b.pdf", "Paper B", [(1, "beta one")])
        )
        docs = self._store.list_documents()
        self.assertEqual(len(docs), 2)
        by_title = {d["title"]: d["chunk_count"] for d in docs}
        self.assertEqual(by_title["Paper A"], 3)
        self.assertEqual(by_title["Paper B"], 1)

    def test_search_returns_text_and_metadata(self):
        self._store.add_document(
            "a.pdf",
            "Battery Intro",
            _chunks(
                "a.pdf",
                "Battery Intro",
                [
                    (1, "Lithium ion batteries use a liquid electrolyte."),
                    (1, "Solid state batteries use a ceramic separator."),
                ],
            ),
        )
        self._store.add_document(
            "b.pdf",
            "Polymers",
            _chunks("b.pdf", "Polymers", [(2, "Polyethylene is a packaging polymer.")]),
        )
        results = self._store.search("solid state battery electrolyte", limit=2)
        self.assertGreaterEqual(len(results), 1)
        first = results[0]
        for key in ("doc_id", "filename", "title", "page", "chunk_index", "text"):
            self.assertIn(key, first)
        # Most relevant chunk should be the solid-state one.
        self.assertIn("solid state", first["text"].lower())

    def test_search_respects_limit(self):
        self._store.add_document(
            "a.pdf",
            "Many",
            _chunks(
                "a.pdf",
                "Many",
                [(i + 1, f"chunk number {i} about batteries") for i in range(5)],
            ),
        )
        results = self._store.search("batteries", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_clear_document_removes_only_that_doc(self):
        doc_a = self._store.add_document(
            "a.pdf", "A", _chunks("a.pdf", "A", [(1, "content a1"), (1, "content a2")])
        )
        self._store.add_document(
            "b.pdf", "B", _chunks("b.pdf", "B", [(1, "content b1")])
        )
        removed = self._store.clear_document(doc_a)
        self.assertEqual(removed, 2)
        self.assertEqual(self._store.count(), 1)
        remaining = self._store.list_documents()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["title"], "B")

    def test_clear_document_unknown_returns_zero(self):
        self.assertEqual(self._store.clear_document("does-not-exist"), 0)


if __name__ == "__main__":
    unittest.main()
