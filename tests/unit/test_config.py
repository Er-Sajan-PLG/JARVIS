"""Unit tests for app/config: Settings, ModelConfig, PromptConfig, Version."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.config.prompt import SYSTEM_PROMPT
from app.config.settings import (
    MemoryConfig,
    ModelConfig,
    PathsConfig,
    Settings,
    _safe_dataclass,
    _safe_model_config,
    get_default_model,
    get_settings,
    reset_settings,
)
from app.config.version import VersionInfo, get_version_info


def test_system_prompt_constant() -> None:
    assert isinstance(SYSTEM_PROMPT, str)
    assert "Jarvis" in SYSTEM_PROMPT
    assert "STEM & Teaching Protocol" in SYSTEM_PROMPT


def test_paths_config_properties() -> None:
    paths = PathsConfig(data_dir=Path("/custom/data"))
    assert paths.memories == Path("/custom/data/memories.json")
    assert paths.conversations_dir == Path("/custom/data/conversations")
    assert paths.default_conversation == Path("/custom/data/conversations/default.json")
    assert paths.ollama_url == "http://localhost:11434"
    assert paths.embed_model == "nomic-embed-text"


def test_safe_dataclass_helper() -> None:
    fallback = MemoryConfig(max_memories=50)

    # Non-dict data returns fallback
    assert _safe_dataclass(MemoryConfig, "not-a-dict", fallback) is fallback

    # Valid dict with extra keys (extra keys ignored)
    valid_data = {"max_memories": 500, "extra_key": 123}
    res = _safe_dataclass(MemoryConfig, valid_data, fallback)
    assert res.max_memories == 500
    assert res.retrieval_limit == 20

    # Type error during instantiation returns fallback
    with patch.object(MemoryConfig, "__init__", side_effect=TypeError("Bad type")):
        res_fail = _safe_dataclass(MemoryConfig, {"max_memories": 10}, fallback)
        assert res_fail is fallback


def test_safe_model_config_helper() -> None:
    # Non-dict data returns None
    assert _safe_model_config("m1", "string") is None

    # Minimal dict using fallback key for name/role
    m = _safe_model_config("m_key", {"backend": "ollama"})
    assert m is not None
    assert m.name == "m_key"
    assert m.role == "m_key"
    assert m.backend == "ollama"

    # Explicit name/role
    m_full = _safe_model_config("k", {"name": "custom_name", "role": "coder", "temperature": 0.2})
    assert m_full is not None
    assert m_full.name == "custom_name"
    assert m_full.role == "coder"
    assert m_full.temperature == 0.2

    # Error during instantiation returns None
    with patch.object(ModelConfig, "__init__", side_effect=ValueError("Bad value")):
        assert _safe_model_config("k", {"name": "val"}) is None


def test_settings_load_defaults(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.yaml"
    settings = Settings.load(str(non_existent))
    assert settings.default_model == "qwen3-8b.gguf"
    assert settings.active_profile == "default"
    assert "general" in settings.models
    assert settings.memory.max_memories == 1000


def test_settings_load_corrupted_or_invalid_yaml(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid: [yaml: broken", encoding="utf-8")
    s_corrupt = Settings.load(str(bad_yaml))
    assert s_corrupt.default_model == "qwen3-8b.gguf"

    non_dict = tmp_path / "list.yaml"
    non_dict.write_text("- item1\n- item2", encoding="utf-8")
    s_non_dict = Settings.load(str(non_dict))
    assert s_non_dict.default_model == "qwen3-8b.gguf"


def test_settings_load_full_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_data = {
        "default_model": "gpt-4o",
        "active_profile": "custom",
        "profiles": {"old": "data"},
        "models": {
            "fast": {
                "name": "llama-fast",
                "role": "fast",
                "backend": "groq",
                "base_url": "https://api.groq.com",
            },
            "broken": "not_a_dict",
        },
        "memory": {
            "max_memories": 2500,
            "min_confidence": 0.5,
        },
        "context": {
            "max_tokens": 8192,
        },
        "conversation": {
            "max_recent_messages": 30,
        },
        "retrieval": {
            "method": "hybrid",
        },
        "ranking": {
            "weight_relevance": 0.5,
        },
    }
    cfg_file.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

    settings = Settings.load(str(cfg_file))
    assert settings.default_model == "gpt-4o"
    assert settings.active_profile == "custom"
    assert "fast" in settings.models
    assert settings.models["fast"].name == "llama-fast"
    assert "broken" not in settings.models
    assert settings.memory.max_memories == 2500
    assert settings.context.max_tokens == 8192
    assert settings.conversation.max_recent_messages == 30
    assert settings.retrieval.method == "hybrid"
    assert settings.ranking.weight_relevance == 0.5


def test_settings_load_invalid_models_section(tmp_path: Path) -> None:
    cfg_file = tmp_path / "invalid_models.yaml"
    cfg_file.write_text("models: 'not-a-dict'\n", encoding="utf-8")
    settings = Settings.load(str(cfg_file))
    # Falls back to default models
    assert "general" in settings.models

    cfg_file_empty = tmp_path / "all_bad_models.yaml"
    cfg_file_empty.write_text("models:\n  bad: 'not_dict'\n", encoding="utf-8")
    settings_empty = Settings.load(str(cfg_file_empty))
    assert "general" in settings_empty.models


def test_singleton_get_and_reset_settings() -> None:
    reset_settings()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    assert get_default_model() == s1.default_model

    reset_settings()
    # After reset, a new instance is constructed
    s3 = get_settings()
    assert s3 is not s1
    reset_settings()


def test_version_info_formatting() -> None:
    # Release tag
    v_rel = VersionInfo(1, 2, 3, "v1.2.3", 0, "abc1234", False, True, "git")
    assert str(v_rel) == "v1.2.3"
    assert v_rel.as_tuple == (1, 2, 3)

    # Release tag but dirty
    v_dirty = VersionInfo(1, 2, 3, "v1.2.3", 0, "abc1234", True, False, "git")
    assert str(v_dirty) == "v1.2.3.dirty"

    # Ahead of tag
    v_ahead = VersionInfo(1, 2, 3, "v1.2.3", 4, "abc1234", False, False, "git")
    assert str(v_ahead) == "v1.2.3+dev.4"

    # Ahead of tag and dirty
    v_ahead_dirty = VersionInfo(1, 2, 3, "v1.2.3", 4, "abc1234", True, False, "git")
    assert str(v_ahead_dirty) == "v1.2.3+dev.4.dirty"


def test_get_version_info_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_VERSION", "v9.8.7")
    with patch("app.config.version._run_git", return_value=None):
        info = get_version_info()
        assert info.major == 9
        assert info.minor == 8
        assert info.patch == 7
        assert info.source == "env"
