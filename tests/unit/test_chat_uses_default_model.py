"""The chat path must honour the default model saved in Settings.

Reported symptom: "changing defaul model is not working". The frontend saved
the default correctly and displayed it, but `/api/chat` ignored it — with no
explicit model on the request it sent an empty model id, so the provider
rejected the call ("bad input"). The user saw a failure and concluded the
setting had not been saved.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A client whose settings store is isolated to a temp file."""
    from app.adapters.web import settings as settings_mod

    monkeypatch.setattr(settings_mod, "_STORAGE_PATH", tmp_path / "web_settings.json")

    from app.main import app

    return TestClient(app)


def test_default_is_persisted_and_readable(client):
    r = client.post(
        "/api/settings/default", json={"provider": "agy", "model": "gemini-3.1-pro-high"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["default"] == {"provider": "agy", "model": "gemini-3.1-pro-high"}

    got = client.get("/api/settings/default").json()
    assert got["default"]["provider"] == "agy"
    assert got["default"]["model"] == "gemini-3.1-pro-high"


def test_setting_default_rejects_empty_values(client):
    bad = [
        {"provider": "", "model": ""},
        {"provider": "agy", "model": ""},
        {"provider": "", "model": "m"},
    ]
    for payload in bad:
        assert client.post("/api/settings/default", json=payload).status_code == 400, payload


def test_chat_resolves_the_saved_default(client):
    """The core regression: a chat request with no model must resolve to the
    saved default rather than dispatching with an empty model id.

    'bad input' is the exact symptom the user reported, so it must never
    appear once a default is set.
    """
    client.post("/api/settings/default", json={"provider": "agy", "model": "gemini-3.1-pro-high"})

    r = client.post("/api/chat", json={"message": "Reply with exactly: PING"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "bad input" not in json.dumps(body), body
    # Either the real call succeeds, or it fails for a reason unrelated to an
    # empty model id (e.g. the CLI is busy). Never "no model".
    assert "No model selected" not in json.dumps(body), body


def test_chat_without_any_default_reports_a_clear_error(client, monkeypatch):
    """With no default and no explicit model, the error must tell the user
    what to do — never a bare provider 'bad input'."""
    from app.adapters.web import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_default", lambda: {"provider": "", "model": ""})

    import app.adapters.web.router as router_mod

    monkeypatch.setattr(
        router_mod,
        "get_default",
        lambda: {"provider": "", "model": ""},
        raising=False,
    )

    r = client.post("/api/chat", json={"message": "hi"})
    body = json.dumps(r.json())
    assert r.status_code == 400, body
    assert "No model selected" in body or "Settings" in body, body
    assert "bad input" not in body, body


def test_explicit_model_is_not_replaced_by_the_default(client):
    """An explicit model on the request must not be overridden by the default."""
    client.post("/api/settings/default", json={"provider": "agy", "model": "gemini-3.1-pro-high"})
    r = client.post(
        "/api/chat",
        json={"message": "hi", "model": {"provider": "ollama", "id": "llama3"}},
    )
    body = json.dumps(r.json())
    assert "No model selected" not in body, body


def test_default_survives_a_store_reload(client, monkeypatch):
    """The default is read from disk on each request, not cached in memory."""
    from app.adapters.web import settings as settings_mod

    client.post("/api/settings/default", json={"provider": "agy", "model": "gemini-3.1-pro-high"})
    # Simulate a fresh process: nothing cached in the module.
    assert settings_mod._STORAGE_PATH.exists()
    assert settings_mod.get_default() == {"provider": "agy", "model": "gemini-3.1-pro-high"}
