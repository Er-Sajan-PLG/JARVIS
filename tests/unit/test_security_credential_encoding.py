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

from unittest.mock import patch

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
    """The credential must be compared with ``hmac.compare_digest``, as bytes.

    This assertion previously read the function's **source** and checked the
    string ``"compare_digest"`` appeared in it. The function's own comment says
    ``compare_digest``, so replacing the constant-time comparison with a plain
    ``presented == expected`` left the test green -- verified: the whole file
    passed 11/11 under exactly that mutation. A timing-leak guard that a comment
    satisfies guards nothing (F-TEST-007).

    The test now substitutes the primitive and observes the call. A plain ``==``
    fails here because nothing calls ``compare_digest`` at all.
    """
    import app.adapters.security as security

    calls: list[tuple[bytes, bytes]] = []

    def _spy(presented: bytes, expected: bytes) -> bool:
        calls.append((presented, expected))
        return True

    with patch.object(security.hmac, "compare_digest", _spy):
        assert is_authorized(x_api_key=KEY) is True

    assert len(calls) == 1, (
        "is_authorized did not call hmac.compare_digest: the constant-time "
        "comparison was replaced (a plain == would still return the right answer "
        "and would leak the key prefix to a timing probe)."
    )
    presented, expected = calls[0]
    assert isinstance(presented, bytes) and isinstance(expected, bytes), (
        "compare_digest was called with str arguments; non-ASCII would raise "
        "TypeError, which is the defect this module exists to prevent."
    )
    assert presented == KEY.encode() and expected == KEY.encode()


def test_the_return_value_comes_from_the_constant_time_comparison() -> None:
    """``False`` from the primitive must produce ``False`` from ``is_authorized``.

    This pins the wiring in the other direction: a mutation that calls
    ``compare_digest`` for show and then returns something else is caught, and a
    short-circuit that answers before the comparison is caught.
    """
    import app.adapters.security as security

    with patch.object(security.hmac, "compare_digest", return_value=False):
        assert is_authorized(x_api_key=KEY) is False

    with patch.object(security.hmac, "compare_digest", return_value=True):
        assert is_authorized(x_api_key=KEY) is True


def test_only_the_encoding_failure_is_swallowed() -> None:
    """The handler is ``except UnicodeEncodeError``, not ``except Exception``.

    A broadened handler is indistinguishable from the narrow one on every input
    this file otherwise tests: widening it to ``except Exception`` left 12/12
    green. But it would also swallow a genuine fault inside the comparison and
    report it as "wrong credential" -- turning a broken auth primitive into a
    silent 401, which is the class of defect this module was written to remove.

    Pinning it needs a failure the narrow handler does not claim, so this
    substitutes one and requires the exception to surface.
    """
    import app.adapters.security as security

    def _explode(presented: bytes, expected: bytes) -> bool:
        raise RuntimeError("comparison primitive is broken")

    with patch.object(security.hmac, "compare_digest", _explode), pytest.raises(RuntimeError):
        is_authorized(x_api_key=KEY)
