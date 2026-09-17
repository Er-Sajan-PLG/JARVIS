"""Contract tests for the mobile PWA surface.

A phone can only install JARVIS if the shell actually loads and every asset the
service worker precaches exists. These tests pin that surface: the SPA shell is
served at ``/``, the manifest is valid JSON whose icon URLs resolve, the service
worker is served with a JavaScript content type, and every path the worker
precaches returns 200.

They exercise the real FastAPI app, so they fail loudly when a mount or an asset
path drifts.
"""

import importlib
import json

import pytest
from fastapi.testclient import TestClient

# Paths the service worker precaches. A single 404 here makes ``cache.addAll``
# reject, the install event fail, and the worker never activate -- which also
# silently disables push notifications.
PRECACHE_PATHS = ["/", "/manifest.json", "/offline.html", "/icon-192.png", "/badge.png"]


@pytest.fixture(scope="module")
def client():
    """Build a TestClient against the real app/main.py app."""
    mod = importlib.import_module("app.main")
    importlib.reload(mod)
    with TestClient(mod.app) as c:
        yield c


# ─── SPA shell ───────────────────────────────────────────────────────────────


def test_root_serves_spa_shell(client):
    """The phone navigates to /, so / must return the app, not a 404."""
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "JARVIS" in r.text


def test_root_shell_links_manifest_and_service_worker(client):
    """The shell must reference the manifest and register the service worker."""
    body = client.get("/").text
    assert 'rel="manifest"' in body
    assert "/manifest.json" in body
    assert "/service-worker.js" in body


# ─── Manifest ────────────────────────────────────────────────────────────────


def test_manifest_is_valid_json(client):
    r = client.get("/manifest.json")
    assert r.status_code == 200
    assert "json" in r.headers["content-type"]
    data = json.loads(r.text)
    assert data["name"] == "JARVIS"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"


def test_manifest_icons_resolve(client):
    """Every icon the manifest advertises must be fetchable at its own URL."""
    data = json.loads(client.get("/manifest.json").text)
    assert data["icons"], "manifest declares no icons"
    for icon in data["icons"]:
        r = client.get(icon["src"])
        assert r.status_code == 200, f"manifest icon {icon['src']} -> {r.status_code}"
        assert r.headers["content-type"].startswith("image/")


# ─── Service worker ──────────────────────────────────────────────────────────


def test_service_worker_served_as_javascript(client):
    r = client.get("/service-worker.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


def test_service_worker_scope_header_allows_root(client):
    """Without Service-Worker-Allowed the worker cannot control the root scope."""
    r = client.get("/service-worker.js")
    assert r.headers.get("service-worker-allowed") == "/"


def test_every_precached_path_exists(client):
    """cache.addAll is atomic: one 404 aborts the install and the worker never runs."""
    missing = []
    for path in PRECACHE_PATHS:
        if client.get(path).status_code != 200:
            missing.append(path)
    assert not missing, f"service worker precaches paths that do not exist: {missing}"
