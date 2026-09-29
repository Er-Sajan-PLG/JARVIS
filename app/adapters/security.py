"""Single-tenant credential verification shared by the JARVIS I/O surfaces.

Phase 0 fix F4: the REST surface enforced ``JARVIS_API_KEY`` while the WebSocket
and SSE endpoints on ``ws_router`` enforced nothing, so an unauthenticated client
could stream from JARVIS whenever a key was configured. Both surfaces now consult
this one module instead of each growing its own copy of the rule.

Deliberately framework-free: this module decides *whether* a credential satisfies
the configured key and returns a bool. Raising the protocol-appropriate error is
the adapter's job (``HTTPException`` for HTTP, a close frame for a WebSocket),
which keeps the decision testable without an ASGI server.

The credential is accepted as ``Authorization: Bearer <key>``, ``X-API-Key: <key>``,
or -- only on surfaces where a browser cannot set request headers (``WebSocket``,
``EventSource``) -- as the ``api_key`` query parameter. Query-parameter credentials
can land in access logs and browser history, so that form must be opted into via
``allow_query``; the REST surface does not opt in.

If ``JARVIS_API_KEY`` is unset the check passes everything, which is the
single-tenant local-development behaviour the REST surface has always had.
"""

import hmac
import os
from collections.abc import Mapping

API_KEY_ENV = "JARVIS_API_KEY"
QUERY_PARAM = "api_key"
AUTH_HEADER = "authorization"
API_KEY_HEADER = "x-api-key"


def configured_key() -> str:
    """The configured single-tenant key, or an empty string when auth is disabled."""
    return os.environ.get(API_KEY_ENV, "").strip()


def extract_credential(
    authorization: str | None = None,
    x_api_key: str | None = None,
    query_api_key: str | None = None,
) -> str:
    """Return the presented credential, preferring headers over the query parameter."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_api_key:
        return x_api_key.strip()
    if query_api_key:
        return query_api_key.strip()
    return ""


def is_authorized(
    authorization: str | None = None,
    x_api_key: str | None = None,
    query_api_key: str | None = None,
    *,
    allow_query: bool = False,
) -> bool:
    """Whether the presented credential satisfies the configured key."""
    expected = configured_key()
    if not expected:
        return True

    presented = extract_credential(
        authorization,
        x_api_key,
        query_api_key if allow_query else None,
    )
    if not presented:
        return False

    # Constant-time compare: a plain ``!=`` would leak the key prefix to a timing probe.
    #
    # Compare as *bytes*. Given ``str`` arguments, ``hmac.compare_digest`` raises
    # ``TypeError`` for any value containing non-ASCII characters ("comparing
    # strings with non-ASCII characters is not supported"), so a single stray
    # byte in ``Authorization`` or ``X-API-Key`` became HTTP 500 on every surface
    # sharing this primitive instead of a clean 401. Encoding keeps the
    # comparison constant-time and makes any byte sequence a plain mismatch.
    try:
        return hmac.compare_digest(presented.encode(), expected.encode())
    except UnicodeEncodeError:
        # A lone surrogate cannot be encoded as UTF-8 and can never equal the key.
        return False


def is_authorized_for_streaming(
    headers: Mapping[str, str],
    query_params: Mapping[str, str],
) -> bool:
    """Check for a surface reached by a browser, which cannot set request headers.

    ``WebSocket`` and ``EventSource`` give the client no way to attach an
    ``Authorization`` header, so this variant accepts the key in the query string.
    """
    return is_authorized(
        authorization=headers.get(AUTH_HEADER),
        x_api_key=headers.get(API_KEY_HEADER),
        query_api_key=query_params.get(QUERY_PARAM),
        allow_query=True,
    )
