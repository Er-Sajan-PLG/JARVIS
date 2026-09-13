"""Unit tests for app/models/exceptions.py."""

from app.models import exceptions
from app.models.exceptions import (
    RESPONSE_SHAPE_ERRORS,
    ModelConnectionError,
    ModelError,
    ModelRateLimitError,
    ModelResponseError,
    ModelTimeoutError,
    _httpx_timeout_errors,
    map_ollama_error,
    map_openai_error,
    ollama_transport_errors,
)


def test_model_error_without_cause():
    err = ModelError("something went wrong")
    assert str(err) == "something went wrong"
    assert err.cause is None
    assert "caused by" not in repr(err)


def test_model_error_with_cause():
    cause = ValueError("root failure")
    err = ModelError("wrapped failure", cause=cause)
    assert str(err) == "wrapped failure"
    assert err.cause is cause
    assert "caused by ValueError: root failure" in repr(err)


def test_subclasses_inherit_from_model_error():
    assert issubclass(ModelConnectionError, ModelError)
    assert issubclass(ModelTimeoutError, ModelError)
    assert issubclass(ModelRateLimitError, ModelError)
    assert issubclass(ModelResponseError, ModelError)


def test_ollama_transport_errors(monkeypatch):
    import httpx

    assert ollama_transport_errors() == (httpx.HTTPError,)

    monkeypatch.setattr(exceptions, "httpx", None)
    assert ollama_transport_errors() == ()


def test_httpx_timeout_errors(monkeypatch):
    import httpx

    assert _httpx_timeout_errors() == (httpx.TimeoutException,)

    monkeypatch.setattr(exceptions, "httpx", None)
    assert _httpx_timeout_errors() == ()


def test_response_shape_errors():
    assert KeyError in RESPONSE_SHAPE_ERRORS
    assert IndexError in RESPONSE_SHAPE_ERRORS
    assert TypeError in RESPONSE_SHAPE_ERRORS
    assert AttributeError in RESPONSE_SHAPE_ERRORS


def test_map_openai_error():
    import httpx
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    dummy_request = httpx.Request("POST", "https://example.com")

    # APITimeoutError
    err = map_openai_error(APITimeoutError(dummy_request), "test-model")
    assert isinstance(err, ModelTimeoutError)
    assert "test-model" in str(err)

    # RateLimitError
    r_resp = httpx.Response(429, request=dummy_request)
    err = map_openai_error(RateLimitError("rate limited", response=r_resp, body=None), "test-model")
    assert isinstance(err, ModelRateLimitError)

    # AuthenticationError
    a_resp = httpx.Response(401, request=dummy_request)
    err = map_openai_error(
        AuthenticationError("unauthorized", response=a_resp, body=None), "test-model"
    )
    assert isinstance(err, ModelResponseError)
    assert "Authentication failed" in str(err)

    # APIConnectionError
    err = map_openai_error(APIConnectionError(request=dummy_request), "test-model")
    assert isinstance(err, ModelConnectionError)

    # BadRequestError
    b_resp = httpx.Response(400, request=dummy_request)
    err = map_openai_error(BadRequestError("bad", response=b_resp, body=None), "test-model")
    assert isinstance(err, ModelResponseError)
    assert "rejected the request" in str(err)

    # APIStatusError
    s_resp = httpx.Response(500, request=dummy_request)
    err = map_openai_error(APIStatusError("error status", response=s_resp, body=None), "test-model")
    assert isinstance(err, ModelResponseError)
    assert "HTTP 500" in str(err)

    # APIError
    err = map_openai_error(
        APIError("generic api error", request=dummy_request, body=None), "test-model"
    )
    assert isinstance(err, ModelResponseError)
    assert "returned an API error" in str(err)

    # Unexpected error
    err = map_openai_error(RuntimeError("weird error"), "test-model")
    assert isinstance(err, ModelError)
    assert not isinstance(
        err, ModelConnectionError | ModelTimeoutError | ModelRateLimitError | ModelResponseError
    )
    assert "Unexpected error" in str(err)


def test_map_ollama_error():
    import httpx
    import ollama

    # ollama.ResponseError
    resp_err = ollama.ResponseError("bad request", status_code=400)
    err = map_ollama_error(resp_err, "test-model")
    assert isinstance(err, ModelResponseError)
    assert "HTTP 400" in str(err)

    # httpx.TimeoutException
    timeout_err = httpx.ReadTimeout("timeout")
    err = map_ollama_error(timeout_err, "test-model")
    assert isinstance(err, ModelTimeoutError)

    # httpx.HTTPError (connection error)
    conn_err = httpx.ConnectError("refused")
    err = map_ollama_error(conn_err, "test-model")
    assert isinstance(err, ModelConnectionError)

    # Unexpected error
    err = map_ollama_error(RuntimeError("strange error"), "test-model")
    assert isinstance(err, ModelError)
    assert not isinstance(err, ModelConnectionError | ModelTimeoutError | ModelResponseError)
    assert "Unexpected error" in str(err)
