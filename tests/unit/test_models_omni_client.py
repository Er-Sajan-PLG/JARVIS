"""Unit tests for app/models/omni_client.py."""

import time
from unittest.mock import MagicMock

import pytest

from app.models.client import ModelResponse
from app.models.exceptions import (
    ModelConnectionError,
    ModelError,
    ModelRateLimitError,
    ModelResponseError,
)
from app.models.omni_client import OmniModelClient


def make_mock_client(name="mock-model", role="general"):
    client = MagicMock()
    client.model_name = name
    client.role = role
    return client


def test_constructor_empty_clients_raises():
    with pytest.raises(ValueError, match="OmniModelClient requires at least one underlying client"):
        OmniModelClient([])


def test_constructor_and_properties():
    c1 = make_mock_client("m1", "code")
    c2 = make_mock_client("m2", "general")
    omni = OmniModelClient([c1, c2], backoff_seconds=15)

    assert omni.model_name == "omni:m1,m2"
    assert omni.role == "code,general"


def test_mark_failed_backoff_timing():
    c1 = make_mock_client("m1")
    omni = OmniModelClient([c1], backoff_seconds=20)

    now = time.time()
    omni._mark_failed(0, ModelRateLimitError("rate limited"))
    assert omni._failed_until[0] >= now + 20

    omni._mark_failed(0, ModelResponseError("bad json"))
    assert omni._failed_until[0] <= time.time() + 10


def test_generate_sync_success_first_client():
    c1 = make_mock_client("m1")
    c1.generate.return_value = ModelResponse(content="resp1", model="m1")

    omni = OmniModelClient([c1])
    res = omni.generate([{"role": "user", "content": "hi"}], stream=False)

    assert res.content == "resp1"
    assert c1.generate.called


def test_generate_sync_round_robin():
    c1 = make_mock_client("c1")
    c2 = make_mock_client("c2")
    c1.generate.return_value = ModelResponse(content="resp_c1", model="c1")
    c2.generate.return_value = ModelResponse(content="resp_c2", model="c2")

    omni = OmniModelClient([c1, c2])
    # OmniModelClient increments self._idx before calling _next_candidates:
    # First call advances _idx from 0 to 1 -> starts with c2
    res1 = omni.generate([{"role": "user", "content": "hi"}], stream=False)
    assert res1.content == "resp_c2"

    # Second call advances _idx from 1 to 0 -> starts with c1
    res2 = omni.generate([{"role": "user", "content": "hi"}], stream=False)
    assert res2.content == "resp_c1"


def test_generate_sync_failover():
    c1 = make_mock_client("c1")
    c2 = make_mock_client("c2")
    # c2 is tried first because _idx advances from 0 to 1
    c2.generate.side_effect = ModelConnectionError("c2 connection error")
    c1.generate.return_value = ModelResponse(content="resp_c1", model="c1")

    omni = OmniModelClient([c1, c2])
    res = omni.generate([{"role": "user", "content": "hi"}], stream=False)

    assert res.content == "resp_c1"
    assert 1 in omni._failed_until


def test_generate_sync_all_fail():
    c1 = make_mock_client("c1")
    c2 = make_mock_client("c2")
    # c2 is tried first (raises c2 rate limited), then c1 is tried (raises c1 failed)
    c2.generate.side_effect = ModelRateLimitError("c2 rate limited")
    c1.generate.side_effect = ModelConnectionError("c1 failed")

    omni = OmniModelClient([c1, c2])
    with pytest.raises(ModelConnectionError, match="c1 failed"):
        omni.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_no_available_candidates():
    c1 = make_mock_client("m1")
    omni = OmniModelClient([c1])
    omni._failed_until[0] = time.time() + 100

    with pytest.raises(ModelError, match="No available model clients in OmniModelClient"):
        omni.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success():
    c1 = make_mock_client("m1")
    c1.generate.return_value = ModelResponse(content="stream resp", model="m1")

    omni = OmniModelClient([c1])
    tokens = []
    res = omni.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert res.content == "stream resp"
    c1.generate.assert_called_once_with(
        [{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append
    )


def test_generate_stream_failover():
    c1 = make_mock_client("c1")
    c2 = make_mock_client("c2")
    # c2 is tried first and fails mid-stream
    c2.generate.side_effect = ModelConnectionError("c2 stream broken")
    c1.generate.return_value = ModelResponse(content="c1 fallback response", model="c1")

    omni = OmniModelClient([c1, c2])
    tokens = []
    res = omni.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert res.content == "c1 fallback response"
    c1.generate.assert_called_once_with(
        [{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append
    )
