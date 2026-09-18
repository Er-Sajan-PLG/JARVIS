"""Contract tests for the comms surface: push key, notify, voice, email routes.

Pins the infrastructure a phone needs to talk to JARVIS: the public VAPID
key (no auth), the notify dispatcher (auth + validation), the voice
endpoints (auth, no model load on status), and the email route order
(/search must beat /{email_id}).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def secured_client(api_key_env):
    """Client for an app with a key configured (see tests/conftest.py)."""
    from app.main import app

    with TestClient(app) as c:
        c.api_key = api_key_env
        yield c


def _auth(secured_client):
    return {"Authorization": f"Bearer {secured_client.api_key}"}


# ─── VAPID public key (public by design) ─────────────────────────────────────


def test_vapid_public_key_needs_no_auth(client):
    """A device subscribes before any key is entered, so this stays public."""
    r = client.get("/api/v1/push/vapid-public-key")
    assert r.status_code == 200
    assert r.json()["publicKey"]


# ─── Notify dispatcher ───────────────────────────────────────────────────────


def test_notify_rejects_anonymous(secured_client):
    r = secured_client.post("/api/v1/notify/", json={"body": "hi"})
    assert r.status_code == 401


def test_notify_requires_body(secured_client):
    r = secured_client.post("/api/v1/notify/", headers=_auth(secured_client), json={})
    assert r.status_code == 400


def test_notify_rejects_unknown_channel(secured_client):
    r = secured_client.post(
        "/api/v1/notify/",
        headers=_auth(secured_client),
        json={"body": "hi", "channels": ["smoke-signal"]},
    )
    assert r.status_code == 400


def test_notify_push_dispatches(secured_client):
    with patch(
        "app.adapters.web.notify_routes._push_service.send",
        new=AsyncMock(return_value={"success": 1, "failed": 0, "total": 1}),
    ):
        r = secured_client.post(
            "/api/v1/notify/",
            headers=_auth(secured_client),
            json={"title": "T", "body": "hi", "channels": ["push"]},
        )
    assert r.status_code == 200
    assert r.json()["results"]["push"]["success"] == 1


def test_notify_telegram_skips_when_unconfigured(secured_client, monkeypatch):
    # The repo .env carries a real bot token; isolate so this pins the
    # unconfigured path instead of sending a live message.
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_API_KEYS", raising=False)
    r = secured_client.post(
        "/api/v1/notify/",
        headers=_auth(secured_client),
        json={"body": "hi", "channels": ["telegram"]},
    )
    assert r.status_code == 200
    assert r.json()["results"]["telegram"]["success"] is False


# ─── Voice endpoints ─────────────────────────────────────────────────────────


def test_voice_status_needs_auth(secured_client):
    r = secured_client.get("/api/v1/voice/status")
    assert r.status_code == 401


def test_voice_status_loads_no_model(secured_client):
    """Status must not download a model; the phone checks this on boot."""
    r = secured_client.get("/api/v1/voice/status", headers=_auth(secured_client))
    assert r.status_code == 200
    assert r.json()["stt_loaded"] is False


def test_voice_tts_requires_text(secured_client):
    r = secured_client.post("/api/v1/voice/tts", headers=_auth(secured_client), json={"text": ""})
    assert r.status_code == 400


def test_voice_stt_rejects_empty(secured_client):
    r = secured_client.post(
        "/api/v1/voice/stt",
        headers=_auth(secured_client),
        files={"audio": ("voice.webm", b"", "audio/webm")},
    )
    assert r.status_code == 400


# ─── Email route order ───────────────────────────────────────────────────────


def test_email_search_route_beats_email_id():
    """GET /search must resolve to search, not to get_email('search').

    FastAPI matches in registration order, so the static /search route must
    be registered before the /{email_id} parameter route. Checked on the
    router itself: app.routes flattens included routers lazily.
    """
    from app.adapters.web.email_routes import email_router

    paths = [r.path for r in email_router.routes]
    assert "/api/v1/emails/search" in paths
    assert paths.index("/api/v1/emails/search") < paths.index("/api/v1/emails/{email_id}")
