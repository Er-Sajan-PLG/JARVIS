"""Unit tests for app/models/google_client.py (GoogleClient).

Deterministic: requests is mocked at the boundary; no network, no wall-clock.
"""

import pytest

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)
from app.models.google_client import GoogleClient, _loads


@pytest.fixture
def client():
    return GoogleClient(model="gemini-2.0-flash-exp", api_key="test-key", role="general")


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #
def test_constructor_sets_fields():
    c = GoogleClient(model="m", api_key="k", role="code")
    assert c._model == "m"
    assert c._role == "code"
    assert c._api_key == "k"
    assert c.model_name == "m"
    assert c.role == "code"


def test_constructor_requires_api_key():
    with pytest.raises(ValueError):
        GoogleClient(model="m", api_key="")


def test_constructor_default_role():
    assert GoogleClient(model="m", api_key="k").role == "general"


# --------------------------------------------------------------------------- #
# Message splitting
# --------------------------------------------------------------------------- #
def test_split_messages_basic_user():
    c = GoogleClient(model="m", api_key="k")
    si, contents = c._split_messages([{"role": "user", "content": "hi"}])
    assert si is None
    assert contents == [{"role": "user", "parts": [{"text": "hi"}]}]


def test_split_messages_system_and_assistant_roles():
    c = GoogleClient(model="m", api_key="k")
    msgs = [
        {"role": "system", "content": "you are a bot"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    si, contents = c._split_messages(msgs)
    assert si == "you are a bot"
    assert contents[0] == {"role": "user", "parts": [{"text": "hello"}]}
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"] == [{"text": "hi there"}]


def test_split_messages_merges_consecutive_same_role():
    c = GoogleClient(model="m", api_key="k")
    msgs = [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
    ]
    _, contents = c._split_messages(msgs)
    assert len(contents) == 1
    assert contents[0]["parts"] == [{"text": "a"}, {"text": "b"}]


def test_split_messages_skips_empty_content():
    c = GoogleClient(model="m", api_key="k")
    si, contents = c._split_messages([{"role": "user", "content": ""}])
    assert si is None
    assert contents == []


def test_split_messages_system_concatenated_with_newlines():
    c = GoogleClient(model="m", api_key="k")
    msgs = [
        {"role": "system", "content": "a"},
        {"role": "system", "content": "b"},
    ]
    si, _ = c._split_messages(msgs)
    assert si == "a\n\nb"


# --------------------------------------------------------------------------- #
# Generation config mapping
# --------------------------------------------------------------------------- #
def test_build_generation_config_maps_kwargs():
    cfg = GoogleClient._build_generation_config(
        temperature=0.7, max_tokens=100, top_p=0.9, top_k=40
    )
    assert cfg == {
        "temperature": 0.7,
        "maxOutputTokens": 100,
        "topP": 0.9,
        "topK": 40,
    }


def test_build_generation_config_max_output_tokens_alias():
    cfg = GoogleClient._build_generation_config(maxOutputTokens=50)
    assert cfg == {"maxOutputTokens": 50}


def test_build_generation_config_empty():
    assert GoogleClient._build_generation_config() == {}


# --------------------------------------------------------------------------- #
# Text extraction
# --------------------------------------------------------------------------- #
def test_extract_text_concatenates_parts():
    candidate = {"content": {"parts": [{"text": "foo"}, {"text": "bar"}]}}
    assert GoogleClient._extract_text(candidate) == "foobar"


def test_extract_text_empty_parts():
    assert GoogleClient._extract_text({"content": {"parts": []}}) == ""


# --------------------------------------------------------------------------- #
# Sync generation (requests mocked)
# --------------------------------------------------------------------------- #
def test_generate_sync_success(monkeypatch):
    c = GoogleClient(model="m", api_key="k")

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "answer"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"totalTokenCount": 5},
            }

    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        calls["headers"] = headers
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    resp = c._generate_sync({"contents": []})
    assert resp.content == "answer"
    assert resp.tokens_used == 5
    assert resp.finish_reason == "STOP"
    assert resp.model == "m"
    assert "/models/m:generateContent" in calls["url"]


def test_generate_sync_api_error(monkeypatch):
    c = GoogleClient(model="m", api_key="k")

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": {"message": "bad request"}}

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResp())
    with pytest.raises(ModelResponseError):
        c._generate_sync({"contents": []})


def test_generate_sync_connection_error(monkeypatch):
    from requests.exceptions import ConnectionError as _ConnError

    c = GoogleClient(model="m", api_key="k")

    def boom(*a, **k):
        raise _ConnError("down")

    monkeypatch.setattr("requests.post", boom)
    with pytest.raises(ModelConnectionError):
        c._generate_sync({"contents": []})


def test_generate_sync_malformed_json(monkeypatch):
    c = GoogleClient(model="m", api_key="k")

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResp())
    with pytest.raises(ModelResponseError):
        c._generate_sync({"contents": []})


# --------------------------------------------------------------------------- #
# Streaming generation (requests mocked)
# --------------------------------------------------------------------------- #
def _stream_response(lines):
    class FakeResp:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter(lines)

    return FakeResp()


def test_generate_stream_success(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    payload = (
        b'data: {"candidates":[{"content":{"parts":[{"text":"hel"}]},'
        b'"finishReason":"STOP"}],"usageMetadata":{"totalTokenCount":3}}'
    )
    sse = [payload, b""]
    monkeypatch.setattr("requests.post", lambda *a, **k: _stream_response(sse))
    tokens = []
    resp = c._generate_stream({"contents": []}, on_token=tokens.append)
    assert resp.content == "hel"
    assert resp.finish_reason == "STOP"
    assert resp.tokens_used == 3
    assert tokens == ["hel"]


def test_generate_stream_no_finish_reason_raises(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    sse = [b'data: {"candidates":[{"content":{"parts":[{"text":"partial"}]}}]}', b""]
    monkeypatch.setattr("requests.post", lambda *a, **k: _stream_response(sse))
    with pytest.raises(ModelConnectionError):
        c._generate_stream({"contents": []}, on_token=None)


def test_generate_stream_malformed_chunk_raises(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    sse = [b"data: {not-json", b""]
    monkeypatch.setattr("requests.post", lambda *a, **k: _stream_response(sse))
    with pytest.raises(ModelResponseError):
        c._generate_stream({"contents": []}, on_token=None)


def test_generate_stream_error_chunk_raises(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    sse = [b'data: {"error":{"message":"nope"}}', b""]
    monkeypatch.setattr("requests.post", lambda *a, **k: _stream_response(sse))
    with pytest.raises(ModelResponseError):
        c._generate_stream({"contents": []}, on_token=None)


# --------------------------------------------------------------------------- #
# generate() dispatch
# --------------------------------------------------------------------------- #
def test_generate_dispatches_sync(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    monkeypatch.setattr(c, "_generate_sync", lambda payload: "SYNC")
    monkeypatch.setattr(c, "_generate_stream", lambda payload, ot: "STREAM")
    assert c.generate([{"role": "user", "content": "x"}], stream=False) == "SYNC"


def test_generate_dispatches_stream(monkeypatch):
    c = GoogleClient(model="m", api_key="k")
    monkeypatch.setattr(c, "_generate_sync", lambda payload: "SYNC")
    monkeypatch.setattr(c, "_generate_stream", lambda payload, ot: "STREAM")
    got = c.generate([{"role": "user", "content": "x"}], stream=True, on_token=lambda t: None)
    assert got == "STREAM"


def test__loads():
    assert _loads('{"a": 1}') == {"a": 1}
