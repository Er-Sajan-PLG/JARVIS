# app/models/exceptions.py
"""
Typed errors raised by model clients.

Model clients catch provider-specific failures — connection errors,
timeouts, rate limits, and error/malformed responses — and re-raise them
as one of these classes. This lets the rest of the system (e.g. main.py)
handle model failures uniformly *without* knowing which backend produced
them, and without leaking provider-internal tracebacks to the user.

Historically every client let raw ``openai`` / ``ollama`` / ``httpx``
exceptions bubble up, and the only safety net was a broad
``except Exception`` in main.py that silently swallowed *all* errors
(including genuine programming bugs). Centralising the translation here
fixes both sides of that problem.
"""

from __future__ import annotations

from typing import Optional, Tuple, Type


class ModelError(Exception):
    """Base class for every failure that originates in a model client.

    Carries the original exception (if any) in ``cause`` so callers that
    need details can inspect it, while the public message stays friendly.
    """

    def __init__(self, message: str, *, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.cause = cause

    def __repr__(self) -> str:
        base = super().__repr__()
        if self.cause is not None:
            return f"{base} (caused by {type(self.cause).__name__}: {self.cause})"
        return base


class ModelConnectionError(ModelError):
    """The request never reached a usable backend (DNS, refused, TLS, …)."""


class ModelTimeoutError(ModelError):
    """The backend took too long to respond."""


class ModelRateLimitError(ModelError):
    """The backend rejected the request due to rate limiting or quota."""


class ModelResponseError(ModelError):
    """The backend responded, but the payload was an error or malformed."""


# --------------------------------------------------------------------------- #
# httpx is used under the hood by ollama. We reference its exception classes
# defensively so importing this module never hard-fails if it is missing.
# --------------------------------------------------------------------------- #
try:
    import httpx
except ImportError:  # pragma: no cover - httpx always ships with ollama
    httpx = None


def ollama_transport_errors() -> Tuple[Type[BaseException], ...]:
    """httpx exception types that indicate a transport-level failure.

    ``httpx.HTTPError`` is the common base for both connection errors
    (``ConnectError`` …) and timeouts (``TimeoutException`` …); the timeout
    vs. connection distinction is resolved in :func:`map_ollama_error`.
    """
    if httpx is None:
        return ()
    return (httpx.HTTPError,)


def _httpx_timeout_errors() -> Tuple[Type[BaseException], ...]:
    if httpx is None:
        return ()
    return (httpx.TimeoutException,)


# Exceptions that mean "the response shape wasn't what we expected" rather
# than a transport-level failure. Catching these keeps a malformed/empty
# provider payload from bubbling up as a raw IndexError/KeyError/TypeError.
RESPONSE_SHAPE_ERRORS: Tuple[Type[BaseException], ...] = (
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
)


def map_openai_error(exc: BaseException, model: str) -> ModelError:
    """Translate *any* ``openai`` exception into a typed :class:`ModelError`.

    ``openai.OpenAIError`` is the root of the SDK's exception hierarchy, so
    every provider-level failure lands here; order the checks most-specific
    first (``RateLimitError`` / ``BadRequestError`` are subclasses of
    ``APIStatusError``).
    """
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    if isinstance(exc, APITimeoutError):
        return ModelTimeoutError(
            f"Request to model '{model}' timed out.", cause=exc
        )
    if isinstance(exc, RateLimitError):
        return ModelRateLimitError(
            f"Model '{model}' is rate-limited or over quota.", cause=exc
        )
    if isinstance(exc, AuthenticationError):
        return ModelResponseError(
            f"Authentication failed for model '{model}' (check API key).",
            cause=exc,
        )
    if isinstance(exc, APIConnectionError):
        return ModelConnectionError(
            f"Could not connect to model '{model}'. Is the server running?",
            cause=exc,
        )
    if isinstance(exc, BadRequestError):
        return ModelResponseError(
            f"Model '{model}' rejected the request (bad input).", cause=exc
        )
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", "?")
        return ModelResponseError(
            f"Model '{model}' returned an error response (HTTP {status}).",
            cause=exc,
        )
    if isinstance(exc, APIError):
        return ModelResponseError(
            f"Model '{model}' returned an API error.", cause=exc
        )
    return ModelError(f"Unexpected error from model '{model}': {exc}", cause=exc)


def map_ollama_error(exc: BaseException, model: str) -> ModelError:
    """Translate an ollama/httpx exception into a typed :class:`ModelError`."""
    import ollama

    if isinstance(exc, ollama.ResponseError):
        status = getattr(exc, "status_code", "?")
        return ModelResponseError(
            f"Ollama returned an error for model '{model}' (HTTP {status}).",
            cause=exc,
        )

    for err_type in _httpx_timeout_errors():
        if isinstance(exc, err_type):
            return ModelTimeoutError(
                f"Ollama request for model '{model}' timed out.", cause=exc
            )

    # httpx.HTTPError (and its subclasses) covers connection failures.
    if httpx is not None and isinstance(exc, httpx.HTTPError):
        return ModelConnectionError(
            f"Could not connect to Ollama (model '{model}'). "
            "Is the Ollama server running?",
            cause=exc,
        )

    return ModelError(
        f"Unexpected error from Ollama model '{model}': {exc}", cause=exc
    )
