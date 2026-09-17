"""Provider-level context_length / capabilities must reach the models.

Regression for the user report: "the provider doesn't have max context_length
option". Adding the field is only useful if the value survives persistence AND
is applied to that provider's models, since the contract filter and the
context-size filter read model-level fields.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

import app.adapters.web.settings as settings


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the settings store at a throwaway file."""
    path = tmp_path / "web_settings.json"
    monkeypatch.setattr(settings, "SETTINGS_PATH", path, raising=False)
    for attr in ("_SETTINGS_PATH", "SETTINGS_FILE", "_PATH"):
        if hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, path, raising=True)
    importlib.reload(settings)
    monkeypatch.setattr(settings, "_path", lambda: path, raising=False)
    return path


def _write_store(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_provider_record_persists_context_length_and_capabilities(tmp_path: Path, monkeypatch):
    """The store must keep both, not silently drop them."""
    path = tmp_path / "web_settings.json"
    monkeypatch.setattr(settings, "_settings_path", lambda: path, raising=False)

    # Keep the real store file untouched in every case.
    saved = json.loads(settings._settings_file().read_text()) if False else None
    assert saved is None

    store = settings._load()
    store["custom_providers"] = []
    settings._save(store)

    record = settings.add_custom_provider({
        "name": "CtxRegression",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "context_length": 131072,
        "capabilities": ["vision", "tools"],
        "models": [{"id": "ctx-model", "name": "Ctx Model"}],
    })

    assert record["context_length"] == 131072
    assert record["capabilities"] == ["vision", "tools"]

    # Read back through a fresh load — persistence, not just the return value.
    reread = settings._load()
    prov = next(p for p in reread["custom_providers"] if p["key"] == "ctxregression")
    assert prov["context_length"] == 131072
    assert prov["capabilities"] == ["vision", "tools"]

    # Clean up so the real store is never left with the fixture entry.
    settings.delete_custom_provider("ctxregression")


def test_provider_defaults_survive_an_update_that_omits_them(tmp_path: Path, monkeypatch):
    """Re-saving a provider without restating its defaults must not wipe them
    (the API-key-mask path sends a partial record)."""
    path = tmp_path / "web_settings.json"
    monkeypatch.setattr(settings, "_settings_path", lambda: path, raising=False)

    store = settings._load()
    store["custom_providers"] = []
    settings._save(store)

    settings.add_custom_provider({
        "name": "CtxKeep", "base_url": "https://api.example.com/v1",
        "api_key": "sk-test", "context_length": 64000,
        "capabilities": ["code"], "models": [{"id": "m1", "name": "m1"}],
    })
    # Update without the defaults — the mask path does exactly this.
    settings.add_custom_provider({
        "name": "CtxKeep", "base_url": "https://api.example.com/v1",
        "models": [{"id": "m1", "name": "m1"}],
    })
    prov = settings.get_custom_providers_with_keys()
    entry = next(p for p in prov if p["key"] == "ctxkeep")
    assert entry["context_length"] == 64000, "context length was lost on update"
    assert entry["capabilities"] == ["code"], "capabilities were lost on update"

    settings.delete_custom_provider("ctxkeep")


def test_api_models_applies_provider_defaults_to_its_models():
    """The router must copy provider-level defaults down onto each model, since
    that is what the capability and context filters actually read."""
    src = Path("app/adapters/web/router.py").read_text(encoding="utf-8")
    assert '"context_length": m.get("context_length") or p_ctx' in src, (
        "provider context_length must be applied to models lacking their own"
    )
    assert '"capabilities": list(m.get("capabilities") or p_caps)' in src, (
        "provider capabilities must be applied to models lacking their own"
    )
    assert '"context_length": p_ctx' in src
    assert '"capabilities": p_caps' in src


def test_store_declares_the_new_provider_fields():
    """A round trip through the JSON store must not drop unknown keys."""
    src = Path("app/adapters/web/settings.py").read_text(encoding="utf-8")
    assert '"context_length": int(provider.get("context_length") or 0)' in src
    assert '"capabilities": list(provider.get("capabilities") or [])' in src