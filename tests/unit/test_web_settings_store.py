"""Unit tests for the web settings store (single source of truth)."""

from __future__ import annotations

import json

import pytest

from app.adapters.web import settings as ws


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Point the store at a temp file so tests never touch real settings."""
    path = tmp_path / "web_settings.json"
    monkeypatch.setattr(ws, "_STORAGE_PATH", path)
    yield path


# ── Defaults ─────────────────────────────────────────────────────────────────


def test_get_default_empty_initially():
    assert ws.get_default() == {"provider": "", "model": ""}


def test_set_default_round_trips():
    ws.set_default("openrouter", "deepseek/deepseek-v4-flash-0731")
    assert ws.get_default() == {
        "provider": "openrouter",
        "model": "deepseek/deepseek-v4-flash-0731",
    }


def test_set_default_overwrites():
    ws.set_default("openrouter", "a")
    ws.set_default("groq", "b")
    assert ws.get_default() == {"provider": "groq", "model": "b"}


# ── Custom providers ─────────────────────────────────────────────────────────


def test_add_custom_provider_derives_key():
    rec = ws.add_custom_provider({"name": "My Provider", "base_url": "https://x/v1"})
    assert rec["key"] == "my_provider"
    assert rec["is_custom"] is True


def test_custom_provider_api_key_never_returned():
    ws.add_custom_provider({"name": "Sec", "base_url": "https://x/v1", "api_key": "sk-secret"})
    listed = ws.get_custom_providers()
    assert len(listed) == 1
    assert "api_key" not in listed[0]
    assert listed[0]["has_key"] is True
    # The raw value is still available internally for outbound calls.
    assert ws.get_custom_providers_with_keys()[0]["api_key"] == "sk-secret"


def test_add_custom_provider_strips_trailing_slash():
    rec = ws.add_custom_provider({"name": "Slash", "base_url": "https://x/v1/"})
    assert rec["base_url"] == "https://x/v1"


def test_add_custom_provider_requires_name():
    with pytest.raises(ValueError):
        ws.add_custom_provider({"base_url": "https://x/v1"})


def test_add_custom_provider_updates_in_place():
    ws.add_custom_provider({"name": "Dup", "base_url": "https://a/v1"})
    ws.add_custom_provider({"name": "Dup", "base_url": "https://b/v1"})
    listed = ws.get_custom_providers()
    assert len(listed) == 1
    assert listed[0]["base_url"] == "https://b/v1"


def test_update_with_masked_key_keeps_original():
    ws.add_custom_provider({"name": "Keep", "base_url": "https://x/v1", "api_key": "sk-original"})
    ws.add_custom_provider({
        "name": "Keep", "base_url": "https://x/v1", "api_key": ws.MASK,
    })
    assert ws.get_custom_providers_with_keys()[0]["api_key"] == "sk-original"


def test_delete_custom_provider():
    ws.add_custom_provider({"name": "Gone", "base_url": "https://x/v1"})
    assert ws.delete_custom_provider("gone") is True
    assert ws.get_custom_providers() == []
    assert ws.delete_custom_provider("gone") is False


def test_delete_custom_provider_cascades_to_its_models():
    ws.add_custom_provider({"name": "Casc", "base_url": "https://x/v1"})
    ws.add_custom_model({"provider": "casc", "id": "m1"})
    assert len(ws.get_custom_models()) == 1
    ws.delete_custom_provider("casc")
    assert ws.get_custom_models() == []


# ── Custom models ────────────────────────────────────────────────────────────


def test_add_custom_model():
    rec = ws.add_custom_model({
        "provider": "openrouter", "id": "vendor/model", "name": "Vendor Model",
        "context_length": 128000,
    })
    assert rec["provider"] == "openrouter"
    assert rec["is_custom"] is True
    assert rec["context_length"] == 128000


def test_add_custom_model_requires_provider_and_id():
    with pytest.raises(ValueError):
        ws.add_custom_model({"provider": "", "id": "x"})
    with pytest.raises(ValueError):
        ws.add_custom_model({"provider": "p", "id": ""})

def test_add_custom_model_dedupes_by_provider_and_id():
    ws.add_custom_model({"provider": "p", "id": "m", "name": "First"})
    ws.add_custom_model({"provider": "p", "id": "m", "name": "Second"})
    models = ws.get_custom_models()
    assert len(models) == 1
    assert models[0]["name"] == "Second"


def test_delete_custom_model():
    ws.add_custom_model({"provider": "p", "id": "m"})
    assert ws.delete_custom_model("p", "m") is True
    assert ws.get_custom_models() == []
    assert ws.delete_custom_model("p", "m") is False


# ── Hidden models ────────────────────────────────────────────────────────────


def test_toggle_hidden_model():
    assert ws.toggle_hidden_model("p", "m") is True
    assert "p:m" in ws.get_hidden_models()
    assert ws.toggle_hidden_model("p", "m") is False
    assert ws.get_hidden_models() == []


# ── API keys ─────────────────────────────────────────────────────────────────


def test_set_and_status_api_key():
    ws.set_api_key("groq", "sk-abc")
    assert ws.get_api_keys()["groq"] == "sk-abc"
    assert ws.get_api_key_status() == {"groq": True}


def test_set_api_key_ignores_mask_and_empty():
    ws.set_api_key("groq", "sk-real")
    ws.set_api_key("groq", ws.MASK)
    ws.set_api_key("groq", "")
    assert ws.get_api_keys()["groq"] == "sk-real"


def test_delete_api_key():
    ws.set_api_key("groq", "sk-real")
    assert ws.delete_api_key("groq") is True
    assert ws.get_api_keys() == {}
    assert ws.delete_api_key("groq") is False


def test_resolve_api_key_prefers_stored(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "from-env")
    assert ws.resolve_api_key("groq") == "from-env"
    ws.set_api_key("groq", "from-store")
    assert ws.resolve_api_key("groq") == "from-store"


def test_resolve_api_key_unknown_provider():
    assert ws.resolve_api_key("definitely-not-a-provider") == ""


# ── Durability & robustness ──────────────────────────────────────────────────


def test_settings_persist_to_disk(isolated_store):
    ws.set_default("openrouter", "x")
    ws.set_api_key("groq", "k")
    assert isolated_store.exists()
    stored = json.loads(isolated_store.read_text())
    assert stored["default_provider"] == "openrouter"
    assert stored["api_keys"]["groq"] == "k"


def test_corrupt_store_degrades_to_defaults(isolated_store):
    isolated_store.write_text("{ this is not json")
    assert ws.get_default() == {"provider": "", "model": ""}
    assert ws.get_custom_providers() == []


def test_unknown_fields_in_store_are_normalised(isolated_store):
    isolated_store.write_text(json.dumps({
        "custom_providers": "not-a-list",
        "api_keys": ["not", "a", "dict"],
        "default_provider": "keepme",
    }))
    assert ws.get_custom_providers() == []
    assert ws.get_api_keys() == {}
    # Valid scalar fields survive.
    assert ws.get_default()["provider"] == "keepme"


def test_store_file_is_owner_only(isolated_store):
    ws.set_api_key("groq", "secret")
    mode = isolated_store.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"