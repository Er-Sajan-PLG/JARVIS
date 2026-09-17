"""Shared test scaffolding.

The console API enforces ``JARVIS_API_KEY``, and ``app.main`` loads the
repository ``.env`` at import time. That makes the suite's behaviour depend on
whether the developer happens to have set a key locally -- a gate that passes
on one machine and fails on another for a reason unrelated to the code.

So this module removes that variable: it clears any inherited key at session
start, making the default for the whole suite the documented *unsecured local
development* behaviour (when no key is configured, the security helpers allow
every request). Tests that exercise authentication opt in explicitly with
``api_key_env`` and present a credential via ``auth_headers``.
"""

from __future__ import annotations

import pytest

# A fixed key so authentication tests are deterministic. Real deployments
# generate their own.
TEST_API_KEY = "test-api-key-for-suite"


@pytest.fixture(autouse=True)
def _isolate_api_key_env(monkeypatch) -> None:
    """Keep a developer's local ``JARVIS_API_KEY`` from changing test outcomes.

    Order matters twice over.

    First, ``app.main`` (and the web router) call ``load_dotenv`` at import
    time, which *repopulates* ``JARVIS_API_KEY`` from the repository ``.env``.
    Clearing the variable before anything is imported therefore does not hold,
    which is why the app is imported first here.

    Second, several tests call ``importlib.reload`` on the app module, and a
    reload runs module-level code again -- dotenv included. A session-scoped
    clear would be silently undone mid-run, making results depend on test order.
    This fixture runs around *every* test instead, so each one starts from the
    same state no matter what ran before it.

    The result is the documented unsecured local-development behaviour unless a
    test asks otherwise via ``api_key_env``.
    """
    import app.main  # noqa: F401  -- let its load_dotenv() run before we clear

    monkeypatch.delenv("JARVIS_API_KEY", raising=False)
    yield


@pytest.fixture()
def api_key_env(monkeypatch):
    """Configure a key for one test, restoring the previous state afterwards.

    Returns the key so the test can present it::

        def test_rejects_anonymous(api_key_env):
            client = TestClient(app)
            assert client.get("/api/models").status_code == 401
    """
    monkeypatch.setenv("JARVIS_API_KEY", TEST_API_KEY)
    return TEST_API_KEY


def auth_headers(key: str | None = None) -> dict[str, str]:
    """Bearer credential for a request against a protected surface."""
    return {"Authorization": f"Bearer {key or TEST_API_KEY}"}
