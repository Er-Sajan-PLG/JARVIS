"""
Unit tests for app.knowledge.findings.save_finding and the MemoryManager
metadata-forwarding it relies on.

Uses a temp memories.json path so the real data/ directory is never touched.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from app.knowledge.findings import (
    save_finding,
    CATEGORY_FINDING,
    TYPE_PAPER_NOTE,
    _normalize_source_meta,
)
from app.memory.manager import MemoryManager
from app.memory.schema import Memory


class TestNormalizeSourceMeta(unittest.TestCase):
    def test_empty_returns_default_page(self):
        # page defaults to 0 (unknown) even with no source meta.
        self.assertEqual(_normalize_source_meta(None), {"page": 0})
        self.assertEqual(_normalize_source_meta({}), {"page": 0})

    def test_extracts_known_fields(self):
        meta = _normalize_source_meta(
            {"source_title": "Battery Intro", "page": 3, "doc_id": "abc123"}
        )
        self.assertEqual(meta, {"source_title": "Battery Intro", "page": 3, "doc_id": "abc123"})

    def test_accepts_title_alias(self):
        self.assertEqual(
            _normalize_source_meta({"title": "X", "page": "5"})["source_title"], "X"
        )

    def test_bad_page_defaults_to_zero(self):
        self.assertEqual(_normalize_source_meta({"page": "nope"})["page"], 0)

    def test_unknown_keys_ignored(self):
        # page defaults to 0 (unknown) and junk keys are dropped; doc_id only
        # present when non-empty.
        self.assertEqual(
            _normalize_source_meta({"source_title": "T", "junk": 1}),
            {"source_title": "T", "page": 0},
        )


class TestSaveFinding(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._path = Path(self._tmp) / "memories.json"
        self._mgr = MemoryManager(path=self._path)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_text_returns_none(self):
        self.assertIsNone(save_finding(self._mgr, "   "))
        self.assertEqual(self._mgr.count(), 0)

    def test_stores_finding_with_metadata_in_one_call(self):
        mem = save_finding(
            self._mgr,
            "Solid-state batteries replace the liquid electrolyte.",
            source_meta={"source_title": "Battery Intro", "page": 2, "doc_id": "d1"},
        )
        self.assertIsInstance(mem, Memory)
        self.assertEqual(mem.category, CATEGORY_FINDING)
        self.assertEqual(mem.memory_type, TYPE_PAPER_NOTE)
        self.assertEqual(
            mem.value, "Solid-state batteries replace the liquid electrolyte."
        )
        # Metadata must be set in the single store() call (architecture fix).
        self.assertEqual(mem.metadata.get("source_title"), "Battery Intro")
        self.assertEqual(mem.metadata.get("page"), 2)
        self.assertEqual(mem.metadata.get("doc_id"), "d1")

    def test_persistence_roundtrip_keeps_metadata(self):
        save_finding(
            self._mgr,
            "Li-ion uses intercalation electrodes.",
            source_meta={"source_title": "Battery Intro", "page": 1, "doc_id": "d1"},
        )
        self._mgr.save()
        mgr2 = MemoryManager(path=self._path)
        findings = mgr2.get_by_category(CATEGORY_FINDING)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata.get("source_title"), "Battery Intro")
        self.assertEqual(findings[0].metadata.get("page"), 1)

    def test_no_source_meta_stores_default_page_metadata(self):
        mem = save_finding(self._mgr, "A standalone finding.")
        # No provenance supplied -> page defaults to 0 (unknown).
        self.assertEqual(mem.metadata, {"page": 0})

    def test_listable_under_finding_category(self):
        save_finding(self._mgr, "Finding one", source_meta={"source_title": "A", "page": 1})
        save_finding(self._mgr, "Finding two", source_meta={"source_title": "B", "page": 2})
        self.assertEqual(len(self._mgr.get_by_category(CATEGORY_FINDING)), 2)


if __name__ == "__main__":
    unittest.main()
