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


def test_vapid_public_key_needs_no_auth(client, monkeypatch):
    """A device subscribes before any key is entered, so this stays public.

    The test supplies its own key rather than assuming one is configured. It
    previously asserted `200` against whatever the ambient environment held, so
    it passed in a developer checkout (which has a `.env`) and returned 503 in a
    fresh worktree, where the CI gate runs. The contract under test is *no auth
    required*, not *VAPID configured* — so the key is injected here and the
    unconfigured case is covered separately below.
    """
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-vapid-public-key")
    r = client.get("/api/v1/push/vapid-public-key")
    assert r.status_code == 200
    assert r.json()["publicKey"] == "test-vapid-public-key"


def test_vapid_public_key_is_unauthenticated_even_when_unconfigured(client, monkeypatch):
    """Unconfigured must read as 503, never 401/403 — the route stays public.

    This is the assertion that holds in every environment, and it is the one the
    original test was reaching for: a device cannot subscribe before it holds a
    credential, so this route must never demand one.
    """
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    r = client.get("/api/v1/push/vapid-public-key")
    assert r.status_code not in (401, 403), (
        f"the public push-key route demanded auth ({r.status_code}); "
        "a device cannot subscribe before it has a credential"
    )
    assert r.status_code == 503


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
