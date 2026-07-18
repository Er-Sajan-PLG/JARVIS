#!/usr/bin/env python3
"""
Verification tests for ISSUE 6 (P1): Silent data loss on corrupt
memories.json. The store used to `except: return` and silently start empty,
letting the next save() overwrite (and destroy) the corrupt file. Now it must:
  - quarantine the corrupt file to a timestamped .corrupt-*.bak backup,
  - warn loudly (never silently), and
  - skip individual malformed records instead of dropping the whole store.

Run with:
    python -m unittest tests.test_issue6 -v
"""

import sys
import os
import json
import glob
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import unittest

from app.memory.store import MemoryStore
from app.memory.schema import Memory


class TestCorruptMemoriesHandling(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "memories.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, text):
        self.path.write_text(text)

    def _good_record(self):
        return Memory(
            category="preference", memory_type="like", value="chocolate"
        ).to_dict()

    # ------------------------------------------------------------------ #
    def test_corrupt_json_is_quarantined_and_store_starts_empty(self):
        # A truncated / invalid JSON document.
        self._write('{"version": "2.0", "memories": [ {"id": "x"')

        # Must NOT raise; must quarantine the bad file.
        store = MemoryStore(path=self.path)

        self.assertEqual(store.count(), 0)
        backups = glob.glob(str(self.path) + ".corrupt-*.bak")
        self.assertTrue(
            backups,
            "corrupt memory file was not quarantined to a .corrupt-*.bak backup",
        )
        # The original active path should have been moved away (quarantined),
        # so it no longer exists at the live location.
        self.assertFalse(
            self.path.exists(),
            "corrupt file was not removed from the live path",
        )

    def test_corrupt_json_does_not_silently_lose_without_backup(self):
        self._write("this is not json at all ::::")
        store = MemoryStore(path=self.path)
        self.assertEqual(store.count(), 0)
        backups = glob.glob(str(self.path) + ".corrupt-*.bak")
        self.assertTrue(backups, "no quarantine backup created for unreadable file")

    def test_malformed_records_are_skipped_not_fatal(self):
        good = self._good_record()
        bad = {"foo": "not a memory"}
        payload = json.dumps(
            {"version": "2.0", "memories": [good, bad, good]}
        )
        self._write(payload)

        store = MemoryStore(path=self.path)

        # Two valid records survive; the malformed one is dropped.
        self.assertEqual(store.count(), 2)
        # The store is marked dirty so the next save() rewrites a clean file
        # (removing the corrupt entry rather than persisting it).
        self.assertTrue(store.is_dirty)

    def test_valid_file_loads_normally(self):
        payload = json.dumps(
            {"version": "2.0", "memories": [self._good_record(), self._good_record()]}
        )
        self._write(payload)
        store = MemoryStore(path=self.path)
        self.assertEqual(store.count(), 2)
        # A clean load has nothing to rewrite.
        self.assertFalse(store.is_dirty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
