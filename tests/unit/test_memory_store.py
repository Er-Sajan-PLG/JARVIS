"""Unit tests for MemoryStore in app/memory/store.py."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config.settings import MemoryConfig
from app.memory.schema import Memory
from app.memory.store import MemoryStore, _validate_field_value


@pytest.fixture
def sample_memory() -> Memory:
    return Memory(
        id="mem-1",
        category="preference",
        memory_type="editor",
        value="neovim",
        confidence=0.9,
        importance=0.8,
        access_count=3,
        metadata={"theme": "dark"},
    )


@pytest.fixture
def sample_memory_2() -> Memory:
    return Memory(
        id="mem-2",
        category="preference",
        memory_type="editor",
        value="vscode",
        confidence=0.7,
        importance=0.6,
        access_count=1,
    )


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    path = tmp_path / "memories.json"
    return MemoryStore(path=path)


# ===== _validate_field_value Tests =====


def test_validate_field_unknown_field():
    """Verify unknown field names raise ValueError."""
    with pytest.raises(ValueError, match="unknown field 'nonexistent'"):
        _validate_field_value("nonexistent", "value")


def test_validate_field_immutable_fields():
    """Verify id and created_at cannot be validated for mutation."""
    with pytest.raises(ValueError, match="field 'id' is immutable"):
        _validate_field_value("id", "new-id")

    with pytest.raises(ValueError, match="field 'created_at' is immutable"):
        _validate_field_value("created_at", 123456789.0)


def test_validate_field_float_confidence_and_importance():
    """Verify float field validation and range check (0.0 to 1.0)."""
    # Valid float coercions
    assert _validate_field_value("confidence", 0.5) == 0.5
    assert _validate_field_value("confidence", "0.85") == 0.85
    assert _validate_field_value("importance", 0.0) == 0.0
    assert _validate_field_value("importance", 1.0) == 1.0

    # Non-number values
    with pytest.raises(ValueError, match="must be a number"):
        _validate_field_value("confidence", "invalid-float")

    with pytest.raises(ValueError, match="must be a number"):
        _validate_field_value("importance", None)

    # Out-of-bounds float values
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        _validate_field_value("confidence", -0.1)

    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        _validate_field_value("importance", 1.05)


def test_validate_field_int_access_count():
    """Verify int field validation and non-negative requirement."""
    assert _validate_field_value("access_count", 10) == 10
    assert _validate_field_value("access_count", "42") == 42

    with pytest.raises(ValueError, match="must be an integer"):
        _validate_field_value("access_count", "not-an-int")

    with pytest.raises(ValueError, match="must be >= 0"):
        _validate_field_value("access_count", -5)


def test_validate_field_string_fields():
    """Verify string field validation and rejection of None."""
    assert _validate_field_value("value", "test-val") == "test-val"
    assert _validate_field_value("value", 123) == "123"

    with pytest.raises(ValueError, match="must not be None"):
        _validate_field_value("value", None)


def test_validate_field_dict_metadata():
    """Verify dict field validation for metadata."""
    assert _validate_field_value("metadata", {"a": 1}) == {"a": 1}

    with pytest.raises(ValueError, match="must be a dict"):
        _validate_field_value("metadata", "not-a-dict")


# ===== CRUD Tests =====


def test_store_init_default_path():
    """Verify MemoryStore initializes with default settings path when none provided."""
    with patch("app.memory.store.get_settings") as mock_settings:
        mock_settings.return_value.paths.memories = Path("/tmp/mock_memories.json")
        mock_settings.return_value.memory = MemoryConfig()
        ms = MemoryStore(path=None)
        assert ms.path == Path("/tmp/mock_memories.json")
        assert ms.count() == 0


def test_add_and_get_all(store, sample_memory):
    """Verify add stores memory, marks dirty, and get_all returns it."""
    assert store.count() == 0
    assert store.is_dirty is False

    ret = store.add(sample_memory)
    assert ret == sample_memory
    assert store.count() == 1
    assert store.is_dirty is True
    assert store.get_all() == [sample_memory]
    # Verify get_all returns a fresh list copy
    all_mems = store.get_all()
    all_mems.clear()
    assert store.count() == 1


def test_get_by_id(store, sample_memory):
    """Verify get_by_id finds matching memory or returns None."""
    store.add(sample_memory)
    assert store.get_by_id(sample_memory.id) == sample_memory
    assert store.get_by_id("non-existent") is None


def test_find_by_category_and_type(store, sample_memory, sample_memory_2):
    """Verify find_by_category_and_type filters correctly."""
    store.add(sample_memory)
    store.add(sample_memory_2)

    matches = store.find_by_category_and_type("preference", "editor")
    assert len(matches) == 2
    assert {m.id for m in matches} == {sample_memory.id, sample_memory_2.id}

    assert store.find_by_category_and_type("preference", "food") == []
    assert store.find_by_category_and_type("skills", "editor") == []


def test_update_fields_success(store, sample_memory):
    """Verify update_fields applies valid updates and sets dirty."""
    store.add(sample_memory)
    store._dirty = False

    updated = store.update_fields(
        sample_memory.id,
        {
            "value": "emacs",
            "confidence": 0.95,
            "access_count": 10,
            "metadata": {"key": "val"},
        },
    )

    assert updated is not None
    assert updated.value == "emacs"
    assert updated.confidence == 0.95
    assert updated.access_count == 10
    assert updated.metadata == {"key": "val"}
    assert store.is_dirty is True


def test_update_fields_non_existent(store):
    """Verify update_fields returns None when memory ID is not found."""
    assert store.update_fields("unknown", {"value": "new"}) is None


def test_update_fields_skips_invalid_fields(store, sample_memory, caplog):
    """Verify update_fields logs a warning and skips invalid updates without crashing."""
    store.add(sample_memory)

    with caplog.at_level(logging.WARNING):
        updated = store.update_fields(
            sample_memory.id,
            {
                "id": "trying-to-change-id",
                "confidence": "not-a-float",
                "value": "valid-update",
            },
        )

    assert updated is not None
    assert updated.id == sample_memory.id  # unchanged
    assert updated.value == "valid-update"  # applied
    assert "Skipping invalid update to memory mem-1" in caplog.text


def test_remove_existing_and_non_existing(store, sample_memory):
    """Verify remove pops memory and marks dirty; non-existing returns None."""
    store.add(sample_memory)
    store._dirty = False

    removed = store.remove(sample_memory.id)
    assert removed == sample_memory
    assert store.count() == 0
    assert store.is_dirty is True

    # Removing again
    assert store.remove(sample_memory.id) is None


def test_remove_by_category_and_type(store, sample_memory, sample_memory_2):
    """Verify remove_by_category_and_type removes all matching memories."""
    store.add(sample_memory)
    store.add(sample_memory_2)
    store._dirty = False

    removed = store.remove_by_category_and_type("preference", "editor")
    assert len(removed) == 2
    assert store.count() == 0
    assert store.is_dirty is True

    # Non-matching removal does not mark dirty
    store._dirty = False
    assert store.remove_by_category_and_type("preference", "editor") == []
    assert store.is_dirty is False


def test_clear(store, sample_memory):
    """Verify clear empties memories, marks dirty, and persists empty state."""
    store.add(sample_memory)
    store.save()
    assert store.path.exists()

    store.clear()
    assert store.count() == 0
    assert store.is_dirty is False  # save() resets dirty

    # Verify on-disk file was updated
    data = json.loads(store.path.read_text())
    assert data["memories"] == []


# ===== Persistence Tests =====


def test_save_not_dirty_noop(tmp_path: Path):
    """Verify save does nothing if store is not dirty."""
    path = tmp_path / "never_created.json"
    ms = MemoryStore(path=path)
    ms.save()
    assert not path.exists()


def test_save_creates_parent_directory(tmp_path: Path, sample_memory):
    """Verify save creates missing parent directories."""
    path = tmp_path / "deep" / "nested" / "dir" / "memories.json"
    ms = MemoryStore(path=path)
    ms.add(sample_memory)
    ms.save()

    assert path.exists()
    assert ms.is_dirty is False
    data = json.loads(path.read_text())
    assert data["version"] == "2.0"
    assert len(data["memories"]) == 1
    assert data["memories"][0]["id"] == sample_memory.id


def test_save_if_dirty_and_force_save(tmp_path: Path, sample_memory):
    """Verify save_if_dirty and force_save methods."""
    path = tmp_path / "save_modes.json"
    ms = MemoryStore(path=path)
    ms.add(sample_memory)

    ms.save_if_dirty()
    assert path.exists()
    assert ms.is_dirty is False

    # force_save saves even when _dirty was False
    with patch("json.dump", wraps=json.dump) as mock_dump:
        ms.force_save()
        mock_dump.assert_called_once()
        assert ms.is_dirty is False


def test_save_exception_cleans_up_tmp_file(tmp_path: Path, sample_memory):
    """Verify temp file cleanup if error occurs during atomic save."""
    path = tmp_path / "fail.json"
    ms = MemoryStore(path=path)
    ms.add(sample_memory)

    with (
        patch("os.replace", side_effect=OSError("Replace failed")),
        pytest.raises(OSError, match="Replace failed"),
    ):
        ms.save()

    # Ensure no leftover temp files
    tmp_files = list(tmp_path.glob("fail.json.tmp.*"))
    assert len(tmp_files) == 0


def test_save_exception_cleanup_handles_unlink_oserror(tmp_path: Path, sample_memory):
    """Verify save exception handler suppresses OSError during tmp file unlink."""
    path = tmp_path / "fail_unlink.json"
    ms = MemoryStore(path=path)
    ms.add(sample_memory)

    with (
        patch("os.replace", side_effect=OSError("Replace failed")),
        patch.object(Path, "unlink", side_effect=OSError("Unlink failed")),
        pytest.raises(OSError, match="Replace failed"),
    ):
        ms.save()


# ===== Load and Deserialization Tests =====


def test_load_non_existent_file(tmp_path: Path):
    """Verify loading from non-existent file starts with empty memories and clean state."""
    ms = MemoryStore(path=tmp_path / "missing.json")
    assert ms.count() == 0
    assert ms.is_dirty is False


def test_load_corrupt_json_quarantines_file(tmp_path: Path, caplog):
    """Verify unparseable JSON file is backed up and corruption is reported."""
    bad_file = tmp_path / "corrupt_memories.json"
    bad_file.write_text("{broken json syntax", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        ms = MemoryStore(path=bad_file)

    assert ms.count() == 0
    assert ms.is_dirty is False
    # Backed up file exists
    backups = list(tmp_path.glob("corrupt_memories.json.corrupt-*"))
    assert len(backups) == 1
    assert "quarantined to" in caplog.text


def test_load_v2_format(tmp_path: Path, sample_memory):
    """Verify loading valid v2 schema file."""
    path = tmp_path / "v2.json"
    data = {
        "version": "2.0",
        "memories": [sample_memory.to_dict()],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    ms = MemoryStore(path=path)
    assert ms.count() == 1
    loaded = ms.get_by_id(sample_memory.id)
    assert loaded is not None
    assert loaded.value == sample_memory.value
    assert ms.is_dirty is False


def test_load_v1_facts_format(tmp_path: Path):
    """Verify loading legacy v1 format with 'facts' list."""
    path = tmp_path / "v1.json"
    data = {
        "facts": [
            {
                "category": "user",
                "type": "language",
                "value": "English",
                "timestamp": 1700000000.0,
            }
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    ms = MemoryStore(path=path)
    assert ms.count() == 1
    mem = ms.get_all()[0]
    assert mem.category == "user"
    assert mem.memory_type == "language"
    assert mem.value == "English"
    assert ms.is_dirty is False


def test_load_bare_list_format(tmp_path: Path, caplog):
    """Verify bare list structure logs warning and starts empty."""
    path = tmp_path / "bare_list.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        ms = MemoryStore(path=path)

    assert ms.count() == 0
    assert ms.is_dirty is False
    assert "contained a bare list" in caplog.text


def test_load_unrecognized_structure(tmp_path: Path, caplog):
    """Verify non-dict/non-list structure logs warning and starts empty."""
    path = tmp_path / "scalar.json"
    path.write_text(json.dumps("some string"), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        ms = MemoryStore(path=path)

    assert ms.count() == 0
    assert ms.is_dirty is False
    assert "Unrecognized memories file structure" in caplog.text


def test_load_skips_malformed_records_and_marks_dirty(tmp_path: Path, sample_memory, caplog):
    """Verify individual malformed records in list are dropped while valid ones are kept."""
    path = tmp_path / "mixed.json"
    data = {
        "version": "2.0",
        "memories": [
            sample_memory.to_dict(),
            "not a dict record",
            {"missing_category_and_type": True},
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        ms = MemoryStore(path=path)

    assert ms.count() == 1
    assert ms.get_by_id(sample_memory.id) is not None
    # Had bad records, so store is marked dirty to rewrite clean file on next save
    assert ms.is_dirty is True
    assert "Dropped 2 malformed memory record(s)" in caplog.text
