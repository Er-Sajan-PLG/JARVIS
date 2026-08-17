import os
import importlib
from fastapi.middleware.cors import CORSMiddleware
import pytest

@pytest.fixture
def override_env():
    old_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old_env)

def test_cors_middleware_does_not_allow_all_origins(override_env):
    # Ensure environment is clean or specific
    if "CORS_ALLOWED_ORIGINS" in os.environ:
        del os.environ["CORS_ALLOWED_ORIGINS"]

    import app.main
    importlib.reload(app.main)

    cors_middlewares = [
        m for m in app.main.app.user_middleware
        if m.cls == CORSMiddleware
    ]

    assert len(cors_middlewares) > 0, "CORSMiddleware should be added to the app"

    for middleware in cors_middlewares:
        allow_origins = middleware.kwargs.get("allow_origins", [])
        assert "*" not in allow_origins, "CORS should not allow all origins ('*')"
        assert "http://localhost:8000" in allow_origins

def test_cors_middleware_custom_origins(override_env):
    os.environ["CORS_ALLOWED_ORIGINS"] = "https://example.com, https://test.com "

    import app.main
    importlib.reload(app.main)

    cors_middlewares = [
        m for m in app.main.app.user_middleware
        if m.cls == CORSMiddleware
    ]

    assert len(cors_middlewares) > 0

    for middleware in cors_middlewares:
        allow_origins = middleware.kwargs.get("allow_origins", [])
        assert "https://example.com" in allow_origins
        assert "https://test.com" in allow_origins
        assert "*" not in allow_origins
