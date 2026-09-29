"""A malformed credential must be rejected, not crash the auth primitive.

`hmac.compare_digest` raises ``TypeError`` when given a ``str`` containing
non-ASCII characters:

    TypeError: comparing strings with non-ASCII characters is not supported

`is_authorized` passed the presented and expected credentials straight through,
so **any** request carrying a non-ASCII byte in ``Authorization`` or
``X-API-Key`` turned into an unhandled exception -- HTTP 500 -- on *every*
surface that shares this primitive, rather than a clean 401.

It fails closed (no handler runs), so it is not an authentication bypass. It is
still a trivially reachable, credential-independent way to make the server
error, and it collapses the distinction between "wrong credential" and "server
broken" -- which is the same class of defect as the health endpoint that
answers 500 instead of reporting unhealth.
"""

from __future__ import annotations

import pytest

from app.adapters.security import API_KEY_ENV, is_authorized

KEY = "correct-horse-battery-staple"  # noqa: S105 - test fixture, not a credential


@pytest.fixture(autouse=True)
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, KEY)


@pytest.mark.parametrize(
    "presented",
    [
        "café",  # non-ASCII, encodable
        "naïve-key",
        "ключ",
        "日本語",
        "🔑",  # non-BMP
        "\ud800",  # lone surrogate: not encodable as UTF-8 at all
        "x" * 10 + "\udfff",
    ],
    ids=[
        "accented",
        "diaeresis",
        "cyrillic",
        "cjk",
        "emoji",
        "lone-surrogate",
        "trailing-surrogate",
    ],
)
def test_non_ascii_credential_is_rejected_not_raised(presented: str) -> None:
    """Every malformed credential must return False, never raise."""
    assert is_authorized(x_api_key=presented) is False


def test_non_ascii_in_authorization_header_is_rejected() -> None:
    assert is_authorized(authorization="Bearer café") is False


def test_correct_key_still_accepted() -> None:
    """The fix must not break the happy path."""
    assert is_authorized(x_api_key=KEY) is True
    assert is_authorized(authorization=f"Bearer {KEY}") is True


def test_wrong_ascii_key_still_rejected() -> None:
    assert is_authorized(x_api_key="wrong") is False


def test_comparison_remains_constant_time() -> None:
    """Compare as bytes, not by length or early exit.

    A plain ``!=`` would leak the key prefix to a timing probe; encoding to
    bytes preserves the constant-time guarantee while removing the TypeError.
    Asserted structurally: the module must still use ``hmac.compare_digest``.
    """
    import inspect

    import app.adapters.security as security

    source = inspect.getsource(security.is_authorized)
    assert "compare_digest" in source, "constant-time comparison was removed"
