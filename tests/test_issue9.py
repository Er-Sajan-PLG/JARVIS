"""
Issue 9 (P1): Add test coverage for the memory, conversation, context, and
routing modules.

These are pure behavioral/unit tests that exercise the public APIs of:
- app.models.router.ModelRouter / TaskType
- app.memory.store.MemoryStore
- app.memory.manager.MemoryManager
- app.conversation.manager.ConversationManager
- app.context.manager.ContextWindowManager

All stores use temp-file paths so the real data/ directory is never touched.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.models.router import ModelRouter, TaskType
from app.memory.store import MemoryStore
from app.memory.manager import MemoryManager
from app.memory.schema import Memory
from app.conversation.manager import ConversationManager
from app.config.settings import ConversationConfig
from app.context.manager import ContextWindowManager


class _StubClient:
    """Minimal stand-in for a ModelClient; just carries a name for assertions."""
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"StubClient({self.name!r})"


class TestModelRouter(unittest.TestCase):
    def _wired(self):
        r = ModelRouter()
        r.set_default(_StubClient("default"))
        for tt in TaskType:
            r.register(tt, _StubClient(tt.value))
        return r

    def test_select_explicit_task_type(self):
        r = ModelRouter()
        code = _StubClient("code")
        stem = _StubClient("stem")
        r.register(TaskType.CODE, code)
        r.register(TaskType.STEM, stem)
        self.assertIs(r.select(TaskType.CODE), code)
        self.assertIs(r.select(TaskType.STEM), stem)

    def test_select_falls_back_to_default(self):
        r = ModelRouter()
        r.register(TaskType.CODE, _StubClient("code"))
        default = _StubClient("default")
        r.set_default(default)
        self.assertIs(r.select(TaskType.STEM), default)

    def test_select_raises_when_no_model_and_no_default(self):
        r = ModelRouter()
        with self.assertRaises(ValueError):
            r.select(TaskType.CODE)

    def test_route_classifies_code(self):
        r = self._wired()

        client, tt = r.route("write a function to debug this bug")
        self.assertEqual(tt, TaskType.CODE)

    def test_route_classifies_stem(self):
        r = self._wired()
        _, tt = r.route("solve the math equation with a formula")
        self.assertEqual(tt, TaskType.STEM)

    def test_route_classifies_reasoning(self):
        r = self._wired()
        _, tt = r.route("analyze and reason about the argument")
        self.assertEqual(tt, TaskType.REASONING)

    def test_route_classifies_docs(self):
        r = self._wired()
        _, tt = r.route("update the documentation and readme")
        self.assertEqual(tt, TaskType.DOCS)
        _, tt2 = r.route("add an api reference section to the tutorial")
        self.assertEqual(tt2, TaskType.DOCS)

    def test_route_unknown_prompt_defaults_general(self):
        r = self._wired()
        _, tt = r.route("tell me a fun fact about otters")
        self.assertEqual(tt, TaskType.GENERAL)

    def test_tiebreak_code_over_stem(self):
        r = self._wired()
        _, tt = r.route("implement calculate")
        self.assertEqual(tt, TaskType.CODE)

    def test_tiebreak_stem_over_reasoning(self):
        r = self._wired()
        _, tt = r.route("think calculate")
        self.assertEqual(tt, TaskType.STEM)

    def test_tiebreak_reasoning_over_general(self):
        r = self._wired()
        _, tt = r.route("think general")
        self.assertEqual(tt, TaskType.REASONING)

    def test_route_returns_client_and_task_type(self):
        r = self._wired()
        result = r.route("write a function to debug this bug")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        client, tt = result
        self.assertEqual(tt, TaskType.CODE)
        self.assertEqual(client.name, "code")


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._path = Path(self._tmp) / "memories.json"

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _store(self):
        return MemoryStore(path=self._path)

    def _make(self, value="Sajan likes Python", category="preference", mtype="like"):
        return Memory(category=category, memory_type=mtype, value=value)

    def test_add_and_get_by_id(self):
        s = self._store()
        m = s.add(self._make())
        self.assertEqual(s.count(), 1)
        self.assertIs(s.get_by_id(m.id), m)

    def test_update_fields_valid(self):
        s = self._store()
        m = s.add(self._make())
        s.update_fields(m.id, {"value": "Sajan likes Rust", "confidence": 0.9})
        self.assertEqual(m.value, "Sajan likes Rust")
        self.assertAlmostEqual(m.confidence, 0.9)

    def test_update_fields_rejects_immutable_id(self):
        s = self._store()
        m = s.add(self._make())
        original = m.id
        s.update_fields(m.id, {"id": "hacked"})
        self.assertEqual(m.id, original)

    def test_update_fields_rejects_unknown_field(self):
        s = self._store()
        m = s.add(self._make())
        s.update_fields(m.id, {"bogus_field": 123})
        self.assertEqual(m.value, "Sajan likes Python")

    def test_update_fields_rejects_out_of_range_confidence(self):
        s = self._store()
        m = s.add(self._make())
        s.update_fields(m.id, {"confidence": 1.5})
        self.assertAlmostEqual(m.confidence, 1.0)

    def test_remove(self):
        s = self._store()
        m = s.add(self._make())
        removed = s.remove(m.id)
        self.assertIs(removed, m)
        self.assertEqual(s.count(), 0)
        self.assertIsNone(s.get_by_id(m.id))

    def test_find_by_category_and_type(self):
        s = self._store()
        s.add(Memory(category="identity", memory_type="name", value="Sajan"))
        s.add(Memory(category="identity", memory_type="name", value="Also Sajan"))
        s.add(Memory(category="preference", memory_type="like", value="Python"))
        found = s.find_by_category_and_type("identity", "name")
        self.assertEqual(len(found), 2)

    def test_persistence_roundtrip(self):
        s = self._store()
        m = s.add(self._make(value="persisted value"))
        s.save()
        s2 = self._store()
        loaded = s2.get_by_id(m.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.value, "persisted value")
        self.assertEqual(loaded.id, m.id)

    def test_clear_persists_empty(self):
        s = self._store()
        s.add(self._make())
        s.clear()
        self.assertEqual(s.count(), 0)
        s2 = self._store()
        self.assertEqual(s2.count(), 0)


class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._path = Path(self._tmp) / "memories.json"

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _manager(self):
        return MemoryManager(path=self._path)

    def test_store_and_get(self):
        mm = self._manager()
        mem = mm.store({"category": "identity", "type": "name", "value": "Sajan"})
        self.assertIsNotNone(mem)
        self.assertEqual(mm.count(), 1)
        self.assertEqual(mm.get_by_id(mem.id).value, "Sajan")

    def test_update(self):
        mm = self._manager()
        mem = mm.store({"category": "identity", "type": "name", "value": "Sajan"})
        mm.update(mem.id, {"value": "Sajan K"})
        self.assertEqual(mm.get_by_id(mem.id).value, "Sajan K")

    def test_delete(self):
        mm = self._manager()
        mem = mm.store({"category": "identity", "type": "name", "value": "Sajan"})
        self.assertTrue(mm.delete(mem.id))
        self.assertIsNone(mm.get_by_id(mem.id))
        self.assertEqual(mm.count(), 0)

    def test_persistence_roundtrip(self):
        mm = self._manager()
        mem = mm.store({"category": "identity", "type": "name", "value": "Sajan"})
        mm.save()
        mm2 = self._manager()
        loaded = mm2.get_by_id(mem.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.value, "Sajan")


class TestConversationManager(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._path = Path(self._tmp) / "conversation.json"

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _manager(self, save_every=True):
        cfg = ConversationConfig(save_on_every_message=save_every)
        return ConversationManager(path=self._path, config=cfg)

    def test_add_and_get_recent(self):
        c = self._manager()
        c.add_message("user", "hi")
        c.add_message("assistant", "hello")
        self.assertEqual(c.count(), 2)
        self.assertEqual(len(c.get_recent()), 2)

    def test_get_recent_limit(self):
        c = self._manager()
        for i in range(3):
            c.add_message("user", f"msg{i}")
        recent = c.get_recent(limit=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].content, "msg2")

    def test_get_recent_formatted(self):
        c = self._manager()
        c.add_message("user", "hi")
        c.add_message("assistant", "hello")
        formatted = c.get_recent_formatted()
        self.assertEqual(formatted[0], {"role": "user", "content": "hi"})
        self.assertEqual(formatted[1], {"role": "assistant", "content": "hello"})

    def test_persistence_roundtrip(self):
        c = self._manager(save_every=False)
        c.add_message("user", "hi")
        c.add_message("assistant", "hello")
        c.save()
        c2 = self._manager()
        self.assertEqual(c2.count(), 2)
        self.assertEqual(c2.get_recent_formatted()[0]["content"], "hi")
        self.assertEqual(c2.get_recent_formatted()[1]["content"], "hello")


class TestContextWindowManager(unittest.TestCase):
    def _word_counter(self, text):
        # Deterministic token estimate: one token per whitespace-separated word.
        return len(text.split()) if text else 0

    def _cwm(self, max_tokens=100, safety_margin=0):
        return ContextWindowManager(
            max_tokens=max_tokens,
            safety_margin=safety_margin,
            token_counter=self._word_counter,
        )

    def test_fit_small_conversation_not_trimmed(self):
        cwm = self._cwm(max_tokens=100)
        msgs = [
            {"role": "user", "content": "hi there"},
            {"role": "assistant", "content": "hello there"},
        ]
        fitted = cwm.fit(msgs)
        self.assertEqual(len(fitted), 2)
        self.assertFalse(cwm.get_stats().was_trimmed)

    def test_fit_trims_oldest_pairs(self):
        cwm = self._cwm(max_tokens=100)
        msgs = []
        for i in range(5):
            content = f"pair{i} " + "x " * 9  # 10 words -> 10 tokens + 4 overhead
            msgs.append({"role": "user", "content": content})
            msgs.append({"role": "assistant", "content": content})
        fitted = cwm.fit(msgs)
        # 3 newest pairs (6 messages) fit within 100 tokens; 2 oldest dropped.
        self.assertEqual(len(fitted), 6)
        stats = cwm.get_stats()
        self.assertTrue(stats.was_trimmed)
        self.assertEqual(stats.pairs_kept, 3)
        self.assertEqual(stats.pairs_trimmed, 2)
        # Pairing preserved: equal user/assistant counts, chronological among kept.
        roles = [m["role"] for m in fitted]
        self.assertEqual(roles.count("user"), 3)
        self.assertEqual(roles.count("assistant"), 3)
        kept_indices = [int(m["content"].split()[0].replace("pair", "")) for m in fitted]
        self.assertEqual(kept_indices, [2, 2, 3, 3, 4, 4])

    def test_fit_keeps_single_overflowing_pair(self):
        # Risk guard: even if a single pair overflows, it is never dropped.
        cwm = self._cwm(max_tokens=20)
        big = " ".join(f"w{i}" for i in range(100))  # ~100 tokens > 20
        msgs = [
            {"role": "user", "content": big},
            {"role": "assistant", "content": big},
        ]
        fitted = cwm.fit(msgs)
        self.assertEqual(len(fitted), 2)
        stats = cwm.get_stats()
        self.assertTrue(stats.was_trimmed)
        self.assertEqual(stats.pairs_kept, 1)
        self.assertEqual(stats.pairs_trimmed, 0)

    def test_fit_preserves_system_message(self):
        cwm = self._cwm(max_tokens=30)
        sys_msg = {"role": "system", "content": "you are helpful"}
        conv = []
        for i in range(2):
            content = f"pair{i} " + "x " * 9
            conv.append({"role": "user", "content": content})
            conv.append({"role": "assistant", "content": content})
        msgs = [sys_msg] + conv
        fitted = cwm.fit(msgs)
        # System is always kept; only one conversation pair fits the budget.
        self.assertEqual(fitted[0]["role"], "system")
        self.assertEqual(len(fitted), 3)
        self.assertTrue(cwm.get_stats().was_trimmed)

    def test_count_tokens_content_coercion(self):
        cwm = self._cwm()
        # None content -> 0 word tokens + 4 overhead
        self.assertEqual(cwm.count_tokens([{"role": "user", "content": None}]), 4)
        # Plain string: 3 words + 4 overhead
        self.assertEqual(
            cwm.count_tokens([{"role": "user", "content": "plain text here"}]), 7
        )
        # List content (multimodal/tool blocks) -> joined text "hello world" -> 2 + 4
        self.assertEqual(
            cwm.count_tokens(
                [{"role": "user", "content": [{"text": "hello world"}]}]
            ),
            6,
        )
        # Non-string non-list -> str() coercion: "123" -> 1 word + 4
        self.assertEqual(cwm.count_tokens([{"role": "user", "content": 123}]), 5)


if __name__ == "__main__":
    unittest.main()
