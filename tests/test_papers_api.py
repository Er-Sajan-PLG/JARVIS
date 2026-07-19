"""
Integration tests for the research-papers API (Step 7).

Uses FastAPI's TestClient but isolates the heavy/stateful parts:
- The real PaperStore (ChromaDB + Ollama) is replaced with an in-memory
  FakeStore so no vector DB or embedding server is required.
- ingest_pdf_bytes is patched to feed the FakeStore (and record the folder).
- The active model client is replaced with a stub returning a canned, cited
  answer.

This validates route wiring, the "Materials Science" default folder, folder
threading through ingestion, list/query/findings/delete responses, and that
findings land under the 'finding' category in MemoryManager.
"""

import unittest
from pathlib import Path
import tempfile
import shutil

from fastapi.testclient import TestClient

from app.api.server import create_app
from app.knowledge.store import PaperStore  # only for isinstance / monkeypatch target
from app.knowledge.findings import CATEGORY_FINDING


class _Resp:
    def __init__(self, content):
        self.content = content


class _StubModel:
    def __init__(self):
        self.last_messages = None

    def generate(self, messages, **kwargs):
        self.last_messages = messages
        return _Resp("Solid-state batteries use a ceramic separator [Battery Intro, p.1].")


class FakeStore:
    """In-memory stand-in for PaperStore implementing the API-used surface."""

    def __init__(self):
        self.docs = {}          # doc_id -> {filename, title, folder, chunks: [metadata]}
        self._seq = 0

    def add_document(self, filename, title, chunks, doc_id=None, folder=""):
        self._seq += 1
        did = doc_id or f"doc{self._seq}"
        self.docs[did] = {
            "filename": filename, "title": title, "folder": folder or "",
            "chunks": [
                {"doc_id": did, "filename": filename, "title": title,
                 "page": c.page, "chunk_index": c.chunk_index, "folder": folder or "",
                 "text": c.text}
                for c in chunks
            ],
        }
        return did

    def clear_document(self, doc_id):
        return self.docs.pop(doc_id, {}).get("chunks", []).__len__()

    def list_documents(self, folder=None):
        out = []
        for did, d in self.docs.items():
            if folder is not None and d["folder"] != folder:
                continue
            out.append({
                "doc_id": did, "filename": d["filename"], "title": d["title"],
                "folder": d["folder"], "chunk_count": len(d["chunks"]),
            })
        return out

    def search(self, query, limit=6, folder=None):
        results = []
        for did, d in self.docs.items():
            if folder is not None and d["folder"] != folder:
                continue
            for ch in d["chunks"]:
                results.append(dict(ch))
        return results[:limit]

    def count(self):
        return sum(len(d["chunks"]) for d in self.docs.values())


def _fake_ingest(pdf_bytes, filename, store, title=None, folder="", settings=None,
                persist_dir=None):
    # Emulate the pipeline: 2 chunks, folder threaded through.
    from app.knowledge.chunk import Chunk
    chunks = [
        Chunk(doc_id="", filename=filename, title=title or filename,
              page=1, chunk_index=0, text="Lithium ion batteries use a liquid electrolyte."),
        Chunk(doc_id="", filename=filename, title=title or filename,
              page=1, chunk_index=1, text="Solid state batteries use a ceramic separator."),
    ]
    did = store.add_document(filename=filename, title=title or filename,
                             chunks=chunks, folder=folder)
    return {"doc_id": did, "title": title or filename, "filename": filename,
            "folder": folder, "chunk_count": len(chunks), "pages": 1, "ocr_pages": 0}


class TestPapersAPI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        # Patch ingest at the symbol bound inside server.py (it does a direct
        # `from app.knowledge.ingest import ingest_pdf_bytes`, so patching the
        # source module attribute would NOT redirect the call). Swap the engine
        # papers store + active model too, before any request is served.
        import app.api.server as server_mod
        self._orig_ingest = server_mod.ingest_pdf_bytes
        server_mod.ingest_pdf_bytes = _fake_ingest

        self.app = create_app()
        self.engine = self.app.state.engine
        self.fake = FakeStore()
        self.engine.papers = self.fake
        self.stub = _StubModel()
        self.engine.switcher.router.default_model = self.stub

        self.client = TestClient(self.app)

    def tearDown(self):
        import app.api.server as server_mod
        server_mod.ingest_pdf_bytes = self._orig_ingest
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _upload(self, folder="Materials Science", title=""):
        files = {"file": ("battery.pdf", b"%PDF-1.4 fake", "application/pdf")}
        data = {"folder": folder, "title": title}
        return self.client.post("/api/papers/ingest", files=files, data=data)

    def test_default_folder_created(self):
        resp = self.client.get("/api/papers/folders")
        self.assertEqual(resp.status_code, 200)
        folders = resp.json()["folders"]
        self.assertIn("Materials Science", folders)

    def test_ingest_returns_summary(self):
        resp = self._upload(folder="Materials Science", title="Battery Intro")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["doc_id"])
        self.assertEqual(body["title"], "Battery Intro")
        self.assertEqual(body["folder"], "Materials Science")
        self.assertEqual(body["chunk_count"], 2)

    def test_list_papers(self):
        self._upload()
        resp = self.client.get("/api/papers")
        self.assertEqual(resp.status_code, 200)
        docs = resp.json()["documents"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["folder"], "Materials Science")

    def test_list_papers_filter_by_folder(self):
        self._upload(folder="Materials Science")
        self._upload(folder="Physics")
        resp = self.client.get("/api/papers", params={"folder": "Physics"})
        self.assertEqual(resp.status_code, 200)
        docs = resp.json()["documents"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["folder"], "Physics")

    def test_query_returns_answer_and_sources(self):
        self._upload(folder="Materials Science")
        resp = self.client.post(
            "/api/papers/query",
            json={"query": "What electrolyte do batteries use?", "folder": "Materials Science"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("answer", body)
        self.assertIn("sources", body)
        self.assertTrue(body["sources"])  # folder-scoped search returned chunks

    def test_query_within_wrong_folder_returns_no_sources(self):
        self._upload(folder="Materials Science")
        resp = self.client.post(
            "/api/papers/query",
            json={"query": "x", "folder": "Nonexistent Folder"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["sources"], [])

    def test_save_finding(self):
        resp = self.client.post(
            "/api/papers/findings",
            json={
                "text": "Solid-state batteries replace the liquid electrolyte.",
                "source_meta": {"source_title": "Battery Intro", "page": 1},
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        # The memory must actually be stored under the finding category.
        findings = self.engine.memory.get_by_category(CATEGORY_FINDING)
        self.assertTrue(any(
            "Solid-state" in m.value for m in findings
        ))

    def test_delete_paper(self):
        body = self._upload(folder="Materials Science").json()
        doc_id = body["doc_id"]
        resp = self.client.delete(f"/api/papers/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["removed_chunks"], 2)
        # Now listing is empty.
        self.assertEqual(self.client.get("/api/papers").json()["count"], 0)

    def test_ingest_rejects_non_pdf(self):
        files = {"file": ("notes.txt", b"hello", "text/plain")}
        resp = self.client.post("/api/papers/ingest", files=files, data={"folder": "x"})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
