"""Contract tests for console API authentication.

Exposing JARVIS to a phone means exposing it to every device that can route to
the host. Tailscale narrows *who* can reach it, but everything on the tailnet --
and anything that later joins it -- still reaches the console. The console API
therefore has to enforce the configured key itself, exactly as the
``/api/v1`` surface already does.

The PWA shell and its assets are deliberately exempt: a browser fetches the
manifest, the service worker and the icons before any credential exists, so
gating those would make the app uninstallable.
"""

import pytest
from fastapi.testclient import TestClient

# Console endpoints that read or mutate real state. None of these may answer
# without a credential once a key is configured.
PROTECTED_PATHS = [
    "/api/models",
    "/api/conversations",
    "/api/memory",
    "/api/files",
    "/api/settings/default",
    "/api/settings/providers",
    "/api/settings/api-keys",
]

# The installable-app surface. These must answer WITHOUT a credential, or the
# service worker cannot install and the app cannot be added to a home screen.
PUBLIC_PATHS = [
    "/",
    "/manifest.json",
    "/service-worker.js",
    "/offline.html",
    "/icon-192.png",
]


@pytest.fixture()
def secured_client(api_key_env):
    """A client for an app with a key configured.

    ``api_key_env`` sets ``JARVIS_API_KEY`` for this test only and yields the
    key, so the tests below present it without a second source of truth. The
    security helpers read the environment per request, so no module reload is
    needed.
    """
    from app.main import app

    with TestClient(app) as c:
        c.api_key = api_key_env  # convenience handle for the tests
        yield c


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_console_api_rejects_missing_credential(secured_client, path):
    """A key is configured, so an anonymous caller must be turned away."""
    r = secured_client.get(path)
    assert r.status_code == 401, f"{path} answered {r.status_code} without a credential"


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_console_api_accepts_bearer_credential(secured_client, path):
    """The key the phone stores must be accepted."""
    r = secured_client.get(path, headers={"Authorization": f"Bearer {secured_client.api_key}"})
    assert r.status_code != 401, f"{path} rejected a valid bearer credential"


def test_console_api_accepts_x_api_key_header(secured_client):
    """Both documented credential forms must work."""
    r = secured_client.get("/api/models", headers={"X-API-Key": secured_client.api_key})
    assert r.status_code != 401


def test_console_api_rejects_wrong_credential(secured_client):
    r = secured_client.get("/api/models", headers={"Authorization": "Bearer wrong-key"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_pwa_surface_stays_public_when_key_configured(secured_client, path):
    """Gating these would make the app uninstallable."""
    r = secured_client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}; it must stay public"
