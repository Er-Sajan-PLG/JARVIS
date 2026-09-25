"""Tests for the web_search runner tool (Migration Plan Step 2)."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

import app.tools
from app.tools import web_search_tool


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    def raise_for_status(self) -> None:
        pass

    async def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    instances: list[_FakeSession] = []
    last_post: tuple[str, dict[str, Any]] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _FakeSession.instances.append(self)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        _FakeSession.last_post = (url, kwargs)
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "Asyncio docs",
                        "url": "https://example.com/asyncio",
                        "text": "x" * 600,
                    },
                    {"title": "Second", "url": "https://example.com/2", "text": "short"},
                ]
            }
        )


@pytest.fixture()
def fake_exa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setattr(web_search_tool.aiohttp, "ClientSession", _FakeSession)
    _FakeSession.instances.clear()
    _FakeSession.last_post = None


async def test_web_search_calls_exa_and_formats_results(
    fake_exa: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")

    result = await web_search_tool.web_search("python asyncio best practices")

    url, kwargs = _FakeSession.last_post or ("", {})
    assert url == "https://api.exa.ai/search"
    assert kwargs["headers"]["x-api-key"] == "test-exa-key"
    assert kwargs["json"] == {"query": "python asyncio best practices", "numResults": 5}
    assert "1. Asyncio docs\nhttps://example.com/asyncio" in result
    assert "2. Second\nhttps://example.com/2" in result
    # 600-char text truncated at 500 + marker (executor.py:43 precedent).
    assert "...[truncated]" in result
    assert "test-exa-key" not in result


async def test_web_search_passes_timeout_through(
    fake_exa: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")

    await web_search_tool.web_search("q", timeout_sec=9)

    timeout = _FakeSession.instances[-1].kwargs["timeout"]
    assert timeout.total == 9


async def test_web_search_without_api_key_fails_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    assert await web_search_tool.web_search("q") == "Search failed: missing EXA_API_KEY"


def test_web_search_not_registered_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_WEB_SEARCH", "0")

    importlib.reload(app.tools)

    assert "web_search" not in app.tools.DEFAULT_TOOLSET


def test_web_search_registered_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_WEB_SEARCH", "1")

    importlib.reload(app.tools)

    assert "web_search" in app.tools.DEFAULT_TOOLSET
    assert app.tools.DEFAULT_TOOLSET["web_search"] is app.tools.web_search
