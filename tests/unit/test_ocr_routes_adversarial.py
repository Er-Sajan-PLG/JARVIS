"""Adversarial verification of the OCR router's auth + path-safety fix (F-SEC-002).

The sibling ``test_ocr_routes_auth`` asserts the *intended* contract. This file
tries to break it: nearly every test here is an attack, written to fail loudly if
the fix is weaker than claimed. The recorder, the fixture key and the app
scaffolding are imported from the contract test rather than copied.

Status of each attack group, as measured:

* **A. Authentication** -- no bypass. Two defects were found and, since this file
  was first written, fixed: a non-ASCII credential used to raise ``TypeError``
  out of ``hmac.compare_digest`` (HTTP 500 instead of 401), and a padded but
  otherwise valid key authenticating is *correct* behaviour, not a bypass. Both
  are now asserted as fixed.
* **B. Path traversal on /process** -- no escape, for any name tried. The
  extension check runs on the raw client string, the join uses ``Path(...).name``,
  and no value was found that passes the first while escaping the second.
* **C. /process-path filter** -- **one bypass**: the filter reads the symlink's
  *name*, so ``innocent.png -> not-an-image.txt`` is accepted, and the engine's
  content validator accepts the target when it is a real image. Vocabulary and
  location are never checked: there is no allowed-root confinement.
* **D. Resource bounds** -- ``dpi``/``max_tokens``/``ngram_window`` are forwarded
  unbounded; the upload size gate runs after the body is buffered; and the body
  is buffered *before* the auth dependency runs, so an anonymous caller can still
  make the server parse and spool an arbitrary upload (see the one xfail).

One ``xfail(strict=True)`` remains, for that last open finding. It keeps the
suite green while marking the defect, and turns into an XPASS failure when fixed.
"""

from __future__ import annotations

import os
import struct
import tempfile
import zlib
from dataclasses import dataclass, field, replace as dc_replace
from pathlib import Path
from typing import Any

import pytest
import test_ocr_routes_auth as auth_contract
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.security import API_KEY_ENV, is_authorized
from app.api.ocr import routes as ocr_routes
from app.config.settings import get_settings
from app.utils.image import validate_image
from app.utils.pdf import is_pdf

TEST_KEY = auth_contract.TEST_KEY

_UNAUTHORIZED = 401


# --- scaffolding ----------------------------------------------------------


class _RecordingService(auth_contract._StubService):
    """The contract test's recorder, plus what the path actually looked like.

    Recording the ``OCRRequest`` is the only way to see what the route forwards
    to the engine without loading a model. Recording the payload and the
    directory listing is done *while the handler is still running* -- the
    directory is removed before the response is sent, so this is the only moment
    the filesystem state exists to be inspected.
    """

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[Any] = []
        self.payloads: list[bytes] = []
        self.listings: list[list[str]] = []

    async def process_upload(self, path: str, request: Any) -> dict[str, Any]:
        self.requests.append(request)
        payload = b""
        listing: list[str] = []
        try:
            payload = Path(path).read_bytes()
            listing = sorted(os.listdir(os.path.dirname(path)))
        except OSError:
            pass
        self.payloads.append(payload)
        self.listings.append(listing)
        return await super().process_upload(path, request)


@dataclass
class _UploadRoot:
    """Where the route's ``mkdtemp`` was redirected, and what it created."""

    root: Path
    created: list[Path] = field(default_factory=list)


@pytest.fixture
def service() -> _RecordingService:
    return _RecordingService()


def _build_app(service: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(ocr_routes.ocr_router)
    app.dependency_overrides[ocr_routes.get_service] = lambda: service
    return app


@pytest.fixture
def client(service: _RecordingService, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    return TestClient(_build_app(service))


@pytest.fixture
def upload_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _UploadRoot:
    """Redirect the route's temp directory into ``tmp_path``.

    Without this the route writes to a random ``/tmp/jarvis_ocr_*`` and a test
    can only assert on the string it handed the service. With it, the test can
    assert on the real filesystem: what was created, where, and what survived.
    """
    root = tmp_path / "uploads"
    root.mkdir()
    tracked = _UploadRoot(root=root)
    real_mkdtemp = tempfile.mkdtemp

    def _mkdtemp(prefix: str = "jarvis_ocr_", dir: str | None = None) -> str:
        created = real_mkdtemp(prefix=prefix, dir=str(root))
        tracked.created.append(Path(created))
        return created

    monkeypatch.setattr(ocr_routes.tempfile, "mkdtemp", _mkdtemp)
    return tracked


def _png_bytes() -> bytes:
    """A minimal valid 1x1 PNG -- content the real validator accepts."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return len(data).to_bytes(4, "big") + body + zlib.crc32(body).to_bytes(4, "big")

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_KEY}"}


def _upload(client: TestClient, filename: str, content: bytes = b"\x89PNG\r\n\x1a\n") -> Any:
    return client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": (filename, content, "image/png")},
    )


def _raw_upload(client: TestClient, filename: bytes, content: bytes = b"\x89PNG\r\n\x1a\n") -> Any:
    """A multipart body written by hand, so the filename bytes are unambiguous.

    ``httpx`` normalises a filename before it reaches the wire -- it rewrites a
    NUL as ``%00`` and drops an empty filename entirely, turning the part into a
    form field. A hostile client writes the bytes it likes, so the raw body is
    the authoritative path and the httpx path is tested separately as the
    harness artefact it is.
    """
    body = (
        b"--B\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + filename + b'"\r\n'
        b"Content-Type: image/png\r\n\r\n" + content + b"\r\n--B--\r\n"
    )
    headers = {**_auth(), "Content-Type": "multipart/form-data; boundary=B"}
    return client.post("/api/ocr/process", headers=headers, content=body)


async def _asgi_request(
    app: FastAPI,
    *,
    method: str,
    path: str,
    headers: list[tuple[bytes, bytes]],
    body: bytes = b"",
) -> tuple[int, int]:
    """Drive the ASGI app directly; return ``(status, body bytes pulled)``.

    Two attacks cannot be measured through ``TestClient``: it is not
    byte-transparent for non-ASCII header values (a latin-1 credential arrives
    as mojibake, proven below), and it always sends the whole body, so a body
    the server never reads is indistinguishable from one it swallowed. uvicorn
    hands the app exactly what this helper hands it, so this is the authoritative
    protocol path for those two questions.
    """
    pulled = {"bytes": 0}
    delivered = {"done": False}

    async def receive() -> dict[str, Any]:
        if delivered["done"]:
            return {"type": "http.disconnect"}
        delivered["done"] = True
        pulled["bytes"] += len(body)
        return {"type": "http.request", "body": body, "more_body": False}

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), *headers],
        "client": ("203.0.113.7", 12345),
        "server": ("testserver", 80),
    }
    await app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    return int(start["status"]), pulled["bytes"]


# Hostile upload filenames. Every one of these either escapes ``temp_dir`` on
# the pre-fix code (``../../x``, ``/etc/cron.d/x``) or is a documented way to
# defeat a basename reduction.
HOSTILE_FILENAMES = [
    "../../etc/passwd.png",
    "../../../pwned.png",
    "..%2F..%2Fetc%2Fpasswd.png",
    "..%252F..%252Fetc%252Fpasswd.png",
    "....//....//pwned.png",
    "..\\..\\windows.png",
    "..\\..\\..\\pwned.png",
    "/etc/cron.d/x.png",
    "//etc/passwd.png",
    "/tmp/x.png",
    "./x.png",
    "a.png/./b.png",
    "x.pdf/../y.png",
    "%2e%2e%2fetc%2fpasswd.png",
    "x.png/",
    "x.png//",
    "x.png/.",
    "~/.ssh/id_rsa.png",
    "file:///etc/passwd.png",
    "/tmp/*.png",
    "C:\\Windows\\x.png",
    "x.PNG",
    "...png",
    "..png",
    "  x.png",
    "id_rsa.png",
]


# --- A. authentication ----------------------------------------------------

# (headers, status the request must produce). Every entry must stay out of the
# handlers. The high-bit entries used to be 500s (TypeError inside
# ``hmac.compare_digest``); they are clean 401s now that the comparison is done
# on bytes, and they are pinned here so the regression cannot come back quietly.
_NO_CREDENTIAL: list[Any] = [
    pytest.param({}, 401, id="no-header"),
    pytest.param({"Authorization": ""}, 401, id="empty-authorization"),
    pytest.param({"Authorization": "Bearer "}, 401, id="bearer-empty-value"),
    pytest.param({"Authorization": "Bearer"}, 401, id="bearer-no-value-no-space"),
    pytest.param({"Authorization": "Bearer    "}, 401, id="bearer-spaces-only"),
    pytest.param({"Authorization": "Bearer wrong"}, 401, id="bearer-wrong-key"),
    pytest.param({"Authorization": f"Bearer {TEST_KEY[:-1]}"}, 401, id="key-prefix"),
    pytest.param({"Authorization": f"Bearer {TEST_KEY[1:]}"}, 401, id="key-suffix"),
    pytest.param({"Authorization": f"Bearer {TEST_KEY.upper()}"}, 401, id="key-uppercased"),
    pytest.param({"Authorization": f"Bearer {TEST_KEY}x"}, 401, id="key-plus-suffix"),
    pytest.param({"Authorization": f"Bearer x{TEST_KEY}"}, 401, id="key-plus-prefix"),
    pytest.param({"Authorization": f"Bearer {TEST_KEY} extra"}, 401, id="key-plus-token"),
    pytest.param({"Authorization": f"Basic {TEST_KEY}"}, 401, id="basic-scheme"),
    pytest.param({"Authorization": f"Token {TEST_KEY}"}, 401, id="unknown-scheme"),
    pytest.param({"Authorization": f"bearer{TEST_KEY}"}, 401, id="bearer-without-space"),
    pytest.param({"Authorization": f"Bearer\t{TEST_KEY}"}, 401, id="bearer-tab"),
    pytest.param({"X-API-Key": ""}, 401, id="empty-x-api-key"),
    pytest.param({"X-API-Key": "wrong"}, 401, id="wrong-x-api-key"),
    pytest.param({"X-API-Key": TEST_KEY[:-1]}, 401, id="x-api-key-prefix"),
    pytest.param({"X-API-Key": TEST_KEY.upper()}, 401, id="x-api-key-uppercased"),
    pytest.param({b"x-api-key": TEST_KEY.encode() + b"\x00"}, 401, id="x-api-key-null-byte"),
    pytest.param({b"x-api-key": b"\xff\xfe"}, 401, id="x-api-key-high-bit-bytes"),
    pytest.param({b"authorization": b"Bearer \xc3\xa9"}, 401, id="bearer-utf8-non-ascii"),
    pytest.param(
        [(b"authorization", b"Bearer wrong"), (b"x-api-key", TEST_KEY.encode())],
        401,
        id="both-headers-bearer-wrong",
    ),
    pytest.param(
        [(b"x-api-key", b"wrong"), (b"authorization", b"Bearer wrong")],
        401,
        id="both-headers-both-wrong",
    ),
]


@pytest.mark.parametrize(("headers", "expected"), _NO_CREDENTIAL)
@pytest.mark.parametrize(
    ("method", "route"),
    [("GET", "/api/ocr/health"), ("POST", "/api/ocr/process"), ("POST", "/api/ocr/process-path")],
)
def test_invalid_credential_cannot_reach_a_handler(
    client: TestClient,
    service: _RecordingService,
    method: str,
    route: str,
    headers: Any,
    expected: int,
) -> None:
    """No credential form may reach a handler -- not even the file primitives."""
    extra = {"data": {"file_path": "/etc/hostname"}} if method == "POST" else {}
    response = client.request(method, route, headers=headers, **extra)
    assert (
        response.status_code == expected
    ), f"{route} answered {response.status_code} to {headers!r}; expected {expected}."
    assert (
        service.processed == []
    ), f"{route} handed {service.processed!r} to the service without a valid credential."


async def test_malformed_credential_bytes_never_produce_a_server_error(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any byte sequence in a credential header is a 401, never a 500.

    This is the regression test for the ``hmac.compare_digest`` TypeError: the
    primitive used to raise on a ``str`` holding anything above 0x7f, which is
    one latin-1 header byte away from any client. Nothing may reach the service
    on the way to that 401.
    """
    payloads = [b"\xff\xfe", b"caf\xe9", b"\xc3\xa9", b"\x00", b"\x80", b"\xed\xa0\x80"]
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = _build_app(service)
    for raw in payloads:
        for method, path in (("GET", "/api/ocr/health"), ("POST", "/api/ocr/process-path")):
            status, _ = await _asgi_request(
                app,
                method=method,
                path=path,
                headers=[
                    (b"x-api-key", raw),
                    (b"content-type", b"application/x-www-form-urlencoded"),
                ],
                body=b"file_path=/etc/hostname",
            )
            assert status == _UNAUTHORIZED, f"{path} answered {status} for credential bytes {raw!r}"
    assert service.processed == []


def test_padded_but_valid_key_authenticates(client: TestClient) -> None:
    """Confirmed correct: ``extract_credential`` strips, so padding still needs the key.

    Whitespace normalisation cannot turn an *invalid* key into a valid one -- it
    can only rescue a correct key that arrived with a copy/paste artefact, which
    is why this is leniency rather than a bypass. The leniency is total, though:
    leading, trailing and embedded padding all authenticate.
    """
    for padded in (f" {TEST_KEY}", f"{TEST_KEY} ", f"\t{TEST_KEY}\n", f"  {TEST_KEY}  "):
        response = client.get("/api/ocr/health", headers={"X-API-Key": padded})
        assert response.status_code == 200, f"padded key {padded!r} was rejected"

    # Padding a *wrong* key changes nothing.
    for padded in (f" {TEST_KEY}x", f"x{TEST_KEY} ", f"\t{TEST_KEY[:-1]}\n"):
        response = client.get("/api/ocr/health", headers={"X-API-Key": padded})
        assert response.status_code == _UNAUTHORIZED


def test_query_parameter_credential_is_disabled(client: TestClient) -> None:
    """An OCR URL is likely to be pasted or logged, so ``allow_query`` stays off.

    ``is_authorized`` accepts a query credential only when the caller opts in;
    ``_validate_api_key`` must not opt in on the caller's behalf.
    """
    assert client.get("/api/ocr/health", params={"api_key": TEST_KEY}).status_code == _UNAUTHORIZED
    response = client.post("/api/ocr/process-path", params={"api_key": TEST_KEY})
    assert response.status_code == _UNAUTHORIZED
    # A valid header beside a *wrong* query parameter must still be accepted:
    # the query string is ignored, not merged into the comparison.
    response = client.get("/api/ocr/health", params={"api_key": "wrong"}, headers=_auth())
    assert response.status_code == 200


def test_authorization_header_wins_over_x_api_key(client: TestClient) -> None:
    """Precedence is fail-closed: a wrong Bearer is not rescued by a good X-API-Key."""
    response = client.get(
        "/api/ocr/health", headers={"Authorization": "Bearer wrong", "X-API-Key": TEST_KEY}
    )
    assert response.status_code == _UNAUTHORIZED

    response = client.get(
        "/api/ocr/health", headers={"Authorization": f"Bearer {TEST_KEY}", "X-API-Key": "wrong"}
    )
    assert response.status_code == 200

    # An empty ``Bearer`` short-circuits ``extract_credential`` to an empty
    # credential, so a valid X-API-Key beside it is ignored. Still fail-closed,
    # but the order is load-bearing rather than incidental.
    response = client.get(
        "/api/ocr/health", headers={"Authorization": "Bearer ", "X-API-Key": TEST_KEY}
    )
    assert response.status_code == _UNAUTHORIZED


@pytest.mark.parametrize("name", ["X-API-Key", "x-api-key", "X-API-KEY", "x-Api-Key"])
def test_api_key_header_casing_is_irrelevant(client: TestClient, name: str) -> None:
    assert client.get("/api/ocr/health", headers={name: TEST_KEY}).status_code == 200


@pytest.mark.parametrize("name", ["Authorization", "authorization", "AUTHORIZATION"])
def test_authorization_header_casing_is_irrelevant(client: TestClient, name: str) -> None:
    assert client.get("/api/ocr/health", headers={name: f"Bearer {TEST_KEY}"}).status_code == 200


def test_valid_credential_is_accepted_on_every_route(client: TestClient, tmp_path: Path) -> None:
    """The gate is authentication, not a blanket denial -- prove the happy paths."""
    target = tmp_path / "document.png"
    target.write_bytes(_png_bytes())

    assert client.get("/api/ocr/health", headers=_auth()).status_code == 200
    assert _upload(client, "document.png").status_code == 200
    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(target)}
    )
    assert response.status_code == 200


async def test_non_ascii_configured_key_is_matched_against_latin1_bytes(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PARTIAL: a non-ASCII key is matched against the header's *latin-1* decoding.

    A header byte above 0x7f is not UTF-8-decoded by Starlette, so an operator
    whose key contains a non-ASCII character has an undocumented wire contract:
    the client must send the key's latin-1 bytes (what ``curl`` and ``requests``
    do). ``httpx`` sends UTF-8 for a non-ASCII *str* header, and any client that
    does the same gets a clean 401 with no hint that the encoding, not the key,
    is wrong. Measured at the ASGI boundary because ``TestClient`` re-encodes
    these header bytes itself and would answer a different question.
    """
    monkeypatch.setenv(API_KEY_ENV, "cl\u00e9-secr\u00e8te")
    app = _build_app(service)
    key = "cl\u00e9-secr\u00e8te"

    latin1, _ = await _asgi_request(
        app, method="GET", path="/api/ocr/health", headers=[(b"x-api-key", key.encode("latin-1"))]
    )
    utf8, _ = await _asgi_request(
        app, method="GET", path="/api/ocr/health", headers=[(b"x-api-key", key.encode())]
    )
    assert latin1 == 200
    assert utf8 == _UNAUTHORIZED

    # The primitive itself has no trouble with non-ASCII on both sides, so the
    # 401 above is the transport's encoding, not the comparison.
    assert is_authorized(x_api_key=key) is True
    assert is_authorized(x_api_key="cl\u00e9-secret") is False


@pytest.mark.parametrize("key", ["\udcff", "\udc80", "key-\udcff-9"])
async def test_unencodable_configured_key_fails_closed(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    """PARTIAL: an operator-set key holding invalid UTF-8 locks every client out.

    ``os.environ`` decodes raw bytes with ``surrogateescape``, so a key made of
    non-UTF-8 bytes becomes a lone surrogate in the ``U+DC80..U+DCFF`` range.
    ``expected.encode()`` then raises ``UnicodeEncodeError`` and ``is_authorized``
    returns False -- even for a byte-exact credential. Fail-closed is the right
    direction, but the symptom is an unexplained 401 for everyone rather than a
    loud configuration error, and no client can recover by changing what it
    sends.
    """
    monkeypatch.setenv(API_KEY_ENV, key)
    assert is_authorized(x_api_key=key) is False
    assert is_authorized(authorization=f"Bearer {key}") is False

    # Any credential at all, including the bytes the key actually holds, is 401.
    for presented in (b"anything", b"\xff\xfe"):
        status, _ = await _asgi_request(
            _build_app(service),
            method="GET",
            path="/api/ocr/health",
            headers=[(b"x-api-key", presented)],
        )
        assert status == _UNAUTHORIZED


def test_lone_high_surrogate_is_not_a_reachable_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``U+D800`` cannot be a configured key: the environment itself refuses it.

    Only the surrogate-escape range survives a round trip through ``os.environ``,
    which is why the lockout above is tested with ``U+DC80..U+DCFF`` and not with
    an arbitrary lone surrogate. Recorded so the boundary of the finding is
    explicit rather than assumed.
    """
    with pytest.raises(UnicodeEncodeError):
        monkeypatch.setenv(API_KEY_ENV, "\ud800")


def test_anonymous_trailing_slash_request_is_redirected_not_served(client: TestClient) -> None:
    """Starlette's slash redirect is answered without running the dependency.

    The redirect carries no payload and its target is still gated, so this is a
    route-shadowing check rather than an exposure.
    """
    strict = TestClient(client.app, follow_redirects=False)
    response = strict.post("/api/ocr/process-path/")
    assert response.status_code in (307, _UNAUTHORIZED)
    if response.status_code == 307:
        assert strict.post("/api/ocr/process-path").status_code == _UNAUTHORIZED
        assert strict.post(response.headers["location"]).status_code == _UNAUTHORIZED


@pytest.mark.parametrize(
    "path",
    [
        "/api/ocr/health/",
        "/api/ocr//health",
        "/API/OCR/HEALTH",
        "/api/ocr/health%20",
        "/api/ocr/./health",
        "/api/ocr/health/../process-path",
        "//api/ocr/health",
        "/api/../api/ocr/health",
    ],
)
async def test_no_path_alias_reaches_a_handler_without_a_credential(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Route matching is exact: no spelling of the path skips the router guard.

    Sent verbatim (no client-side URL normalisation) because the guard's whole
    claim is that it is attached to the router -- a request that matched a
    differently-mounted copy, or that Starlette normalised into a match, would be
    a bypass. A key is configured, so an unguarded ``health`` would answer 200.
    """
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    status, _ = await _asgi_request(_build_app(service), method="GET", path=path, headers=[])
    assert status != 200, f"{path} reached a handler without a credential (status {status})"
    assert service.processed == []


@pytest.mark.parametrize("method", ["HEAD", "GET", "PUT", "DELETE"])
async def test_method_does_not_skip_the_guard(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """Starlette answers HEAD from the GET route, so the guard must run for it too."""
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    status, _ = await _asgi_request(
        _build_app(service), method=method, path="/api/ocr/health", headers=[]
    )
    assert status in (_UNAUTHORIZED, 405)
    assert status != 200


def test_real_app_rejects_anonymous_on_every_ocr_route(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The synthetic app could hide a mount-time mistake; check the real one.

    ``app.main`` loads the repository ``.env`` at import time, so a key really is
    configured in the deployed composition -- the 401s here are not an artefact
    of a test environment that happens to have no key.
    """
    import app.main

    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = app.main.app
    previous = app.dependency_overrides.get(ocr_routes.get_service)
    app.dependency_overrides[ocr_routes.get_service] = lambda: service
    try:
        real = TestClient(app, follow_redirects=False)
        assert real.get("/api/ocr/health").status_code == _UNAUTHORIZED
        assert real.post("/api/ocr/process").status_code == _UNAUTHORIZED
        assert real.post("/api/ocr/process-path").status_code == _UNAUTHORIZED
        secret = real.post("/api/ocr/process-path", data={"file_path": "/etc/hostname"})
        assert secret.status_code == _UNAUTHORIZED
        query = real.get("/api/ocr/health", params={"api_key": TEST_KEY})
        assert query.status_code == _UNAUTHORIZED
        assert real.get("/api/ocr/health", headers=_auth()).status_code == 200
        assert service.processed == []
    finally:
        if previous is None:
            app.dependency_overrides.pop(ocr_routes.get_service, None)
        else:
            app.dependency_overrides[ocr_routes.get_service] = previous


def test_auth_is_open_by_design_when_key_unset(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ACCEPTED, NOT A BUG: no key means no authentication, by documented design.

    ``app.adapters.security`` states it, ``app.main`` warns about it on a
    non-loopback bind, and the sibling contract test pins it. Recorded here so a
    future reader does not mistake the open behaviour for a regression -- and so
    that the *file primitives* being reachable in that mode is explicit.
    """
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    target = tmp_path / "document.png"
    target.write_bytes(_png_bytes())

    anonymous = TestClient(_build_app(service))

    assert anonymous.get("/api/ocr/health").status_code == 200
    response = anonymous.post("/api/ocr/process-path", data={"file_path": str(target)})
    assert response.status_code == 200
    assert service.processed == [str(target)]


# --- B. path traversal on /process ----------------------------------------


def test_extension_check_implies_a_single_safe_path_component() -> None:
    """The load-bearing invariant behind B, checked without any HTTP.

    The extension check runs on the *raw* client string and the join uses
    ``Path(...).name`` afterwards. If any raw value could pass the check while
    reducing to ``..``, ``.``, an empty name or anything containing a separator,
    the sanitisation would be cosmetic. It cannot: ``pathlib`` only strips a
    trailing ``..`` to a name with no suffix, and an empty ``.name`` implies the
    path had no suffix either. Asserted over the hostile corpus plus the
    ``pathlib`` edge cases that decide the question. Starlette does not reduce a
    filename itself (``_user_safe_decode`` only decodes), so this route-level
    reduction is the only one there is.
    """
    allowed = get_settings().ocr.allowed_extensions
    scratch = "/tmp/jarvis_ocr_invariant"
    extra = ["..", ".", "", "/", "//", "a/..", "x.png/..", "a.png..", ".png", "...png"]
    accepted = 0
    for raw in HOSTILE_FILENAMES + extra:
        if Path(raw).suffix.lower() not in allowed:
            continue
        accepted += 1
        safe_name = Path(raw).name or "upload"
        joined = os.path.join(scratch, safe_name)
        assert safe_name not in {"", ".", ".."}
        assert os.sep not in safe_name
        assert ".." not in Path(safe_name).parts
        assert os.path.dirname(joined) == scratch, f"{raw!r} escaped via {safe_name!r}"
    assert accepted >= 12, "corpus stopped exercising the accepted-extension branch"


@pytest.mark.parametrize("filename", HOSTILE_FILENAMES)
def test_hostile_filename_stays_inside_the_upload_directory(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot, filename: str
) -> None:
    """Every hostile name must land inside ``temp_dir`` -- asserted during the request.

    The body is written by hand so the filename is exactly the one in the corpus:
    ``httpx`` silently rewrites some of these before they reach the wire. One
    name is rewritten even further down -- ``python-multipart`` 0.0.32 reduces a
    Windows *drive-letter* filename (``C:\\Windows\\x.png``) to its basename
    before the route sees it; every other name here arrives verbatim. So the
    assertion is the invariant that matters -- exactly one file, at a single safe
    component, inside the directory the route created -- rather than a predicted
    string the parse layer might have changed.
    """
    response = _raw_upload(client, filename.encode())
    assert response.status_code == 200, f"{filename!r} was not accepted as an image name"

    created = {str(path) for path in upload_root.created}
    assert service.processed, f"{filename!r} never reached the service"
    for recorded in service.processed:
        assert (
            os.path.dirname(recorded) in created
        ), f"filename {filename!r} produced {recorded!r}, outside every created temp dir"
        safe_name = Path(recorded).name
        assert safe_name not in {"", ".", ".."}
        assert os.sep not in safe_name, f"filename {filename!r} kept a separator: {safe_name!r}"
    assert service.listings == [[Path(service.processed[0]).name]], (
        f"filename {filename!r} did not produce exactly one basename in its temp dir: "
        f"{service.listings!r}"
    )
    assert service.payloads == [
        b"\x89PNG\r\n\x1a\n"
    ], f"the bytes for {filename!r} were not readable at the sanitised path"


def test_nothing_is_ever_written_outside_the_upload_directory(
    client: TestClient, upload_root: _UploadRoot, tmp_path: Path
) -> None:
    """Filesystem-level proof: the only new entries are the temp dirs themselves."""
    before = {str(path) for path in tmp_path.rglob("*")}

    for filename in HOSTILE_FILENAMES:
        _upload(client, filename)
    for rejected in ("..", ".", "/"):
        _upload(client, rejected, b"x")
    _raw_upload(client, b"")
    _raw_upload(client, b"a\x00.png")
    client.post("/api/ocr/process", headers=_auth(), files={"file": ("/etc/cron.d/x", b"x")})

    after = {str(path) for path in tmp_path.rglob("*")}
    # Only the directory this fixture made may exist afterwards -- every temp dir
    # the route created, on every path, is removed by its ``finally`` cleanup.
    unexpected = (after - before) - {str(upload_root.root)}
    assert unexpected == set(), f"writes escaped the upload directory: {sorted(unexpected)}"


def test_sanitised_name_is_the_file_the_engine_receives(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """The reduction is not cosmetic: the bytes landed at the basename path."""
    payload = b"sanity-check-body"
    assert _upload(client, "../../kept.png", payload).status_code == 200
    assert len(upload_root.created) == 1
    expected = str(upload_root.created[0] / "kept.png")
    assert service.processed == [expected]
    assert service.payloads == [payload]


@pytest.mark.parametrize("filename", [".", "..", "/", "//", "..%2F..%2F", "x", "no-ext"])
def test_names_without_an_allowed_extension_are_rejected_before_any_write(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot, filename: str
) -> None:
    response = _upload(client, filename)
    assert response.status_code == 400, f"{filename!r} was not rejected by the extension gate"
    assert upload_root.created == [], "a temp dir was created before the extension gate ran"
    assert service.processed == []


def test_empty_filename_is_a_client_artefact_not_a_route_gap(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """An empty filename is rejected, but the two callers disagree on *how*.

    ``httpx`` drops an empty ``filename`` and sends a plain form field, so
    FastAPI reports the missing file (422). A raw body keeps the empty filename,
    which Starlette turns into an ``UploadFile`` with ``filename=""``: the suffix
    check rejects it with 400. Neither reaches the service, and neither creates a
    directory -- but a test that only used the httpx form would be asserting on
    the harness, not on the route.
    """
    assert _upload(client, "", b"x").status_code == 422
    assert _raw_upload(client, b"").status_code == 400
    assert upload_root.created == []
    assert service.processed == []


def test_null_byte_filename_cannot_escape(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """A raw NUL reaches the route and is rejected as a malformed request (400).

    ``Path("a\\x00.png").suffix`` is ``.png`` and the name survives the basename
    reduction, so before the fix the route reached ``open()``, where the OS
    raised ``ValueError: embedded null byte``. A route-wide ``except Exception``
    turned that into a 500. It is a malformed request, so the route now rejects
    it at the extension gate with 400 -- and it never reaches the filesystem, so
    no temp directory is created at all.
    """
    response = _raw_upload(client, b"a\x00.png")
    assert response.status_code == 400
    assert service.processed == []
    assert upload_root.created == [], "the null byte must be rejected before any mkdtemp"


def test_httpx_normalises_a_null_byte_so_the_raw_body_is_the_real_test(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """The same attack through httpx is rewritten to ``%00`` before it is sent.

    Recorded so nobody reads the httpx result as the route sanitising anything:
    the client, not the server, changed the name. The escaped name is harmless
    and stays inside the directory.
    """
    response = _upload(client, "a\x00.png")
    assert response.status_code == 200
    assert len(service.processed) == 1
    assert Path(service.processed[0]).name == "a%00.png"
    assert os.path.dirname(service.processed[0]) == str(upload_root.created[0])


def test_overlong_filename_cannot_escape(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """A NAME_MAX overrun is an OS error (500), and still stays inside ``temp_dir``."""
    response = _upload(client, "x" * 5000 + ".png")
    assert response.status_code in (400, 500)
    assert service.processed == []
    assert all(not directory.exists() for directory in upload_root.created)


def test_windows_separators_are_inert_on_posix(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """``..\\..\\`` is not a separator here, so it becomes one odd basename.

    Recorded explicitly because the fix's safety on Windows rests on ``Path``
    being a ``WindowsPath`` there -- a POSIX-only test cannot prove that.
    """
    response = _upload(client, "..\\..\\pwned.png")
    assert response.status_code == 200
    assert service.processed == [str(upload_root.created[0] / "..\\..\\pwned.png")]


# --- C. /process-path filter bypass ---------------------------------------


def test_symlink_with_allowed_extension_is_accepted_by_the_filter(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """BYPASS: the filter reads the symlink's name, not its target.

    ``Path(file_path).suffix`` is a pure string operation and ``os.path.isfile``
    follows links, so ``innocent.png -> not-an-image.txt`` satisfies both checks
    while the engine is handed a path outside the allow-list. Nothing resolves
    the link, and nothing compares the target's extension -- or its directory.
    """
    secret = tmp_path / "not-an-image.txt"
    secret.write_text("JARVIS_API_KEY=redacted-for-this-test\n")
    link = tmp_path / "innocent.png"
    link.symlink_to(secret)

    response = client.post("/api/ocr/process-path", headers=_auth(), data={"file_path": str(link)})
    assert response.status_code == 200, "expected the filter to be bypassed"
    assert service.processed == [str(link)]
    assert Path(service.processed[0]).resolve() == secret


def test_symlink_target_passes_the_real_content_validator(tmp_path: Path) -> None:
    """The bypass survives the *next* gate too when the target is an image.

    The service validates content, not names (``validate_image`` -> PIL), so an
    image whose real extension is not allowed is accepted the moment it is
    reachable under an allowed name. That is what makes the symlink bypass a
    real read primitive rather than a cosmetic filter defect: the remaining
    control is content type, never authorisation or location.
    """
    disguised = tmp_path / "disguised.dat"
    disguised.write_bytes(_png_bytes())
    link = tmp_path / "disguised.png"
    link.symlink_to(disguised)

    assert validate_image(str(link)) == (True, ""), "content gate would have stopped the read"
    assert Path(link).suffix == ".png"
    assert disguised.suffix == ".dat"


def test_symlink_to_plain_text_is_accepted_by_filter_but_stopped_by_content(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """The bound on the bypass: text and key files do not survive as images.

    Recorded so the finding is not overstated. ``/process-path`` hands the path
    over, but the image backend rejects it and the PDF backend's parser raises
    ``FileDataError`` whose message names only the path -- no file content is
    echoed back to the caller.
    """
    target = tmp_path / "id_rsa"
    target.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-real-key\n")

    as_png = tmp_path / "id_rsa.png"
    as_png.symlink_to(target)
    as_pdf = tmp_path / "id_rsa.pdf"
    as_pdf.symlink_to(target)

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(as_png)}
    )
    assert response.status_code == 200
    assert validate_image(str(as_png))[0] is False

    assert is_pdf(str(as_pdf)) is True  # extension-only, like the route's filter
    pymupdf = pytest.importorskip("pymupdf")
    with pytest.raises(Exception) as excinfo:
        pymupdf.open(str(as_pdf))
    assert "not-a-real-key" not in str(excinfo.value)


def test_fifo_with_an_allowed_extension_is_404(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """``os.path.isfile`` -- not ``exists`` -- is what keeps a FIFO out.

    A named pipe called ``x.png`` would satisfy an ``exists()`` check and then
    block the OCR worker; the switch to ``isfile`` is load-bearing, so it is
    pinned here.
    """
    fifo = tmp_path / "pipe.png"
    os.mkfifo(fifo)
    assert os.path.exists(fifo) and not os.path.isfile(fifo)

    response = client.post("/api/ocr/process-path", headers=_auth(), data={"file_path": str(fifo)})
    assert response.status_code == 404
    assert service.processed == []


def test_directory_with_an_allowed_extension_is_404(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    directory = tmp_path / "folder.png"
    directory.mkdir()
    (directory / "inner.txt").write_text("hidden")

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(directory)}
    )
    assert response.status_code == 404
    assert service.processed == []


def test_trailing_slash_passes_the_suffix_check_but_not_isfile(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """``Path("x.png/").suffix`` is ``.png`` while the path is not a file."""
    target = tmp_path / "document.png"
    target.write_bytes(_png_bytes())
    assert Path(str(target) + "/").suffix == ".png"

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(target) + "/"}
    )
    assert response.status_code == 404
    assert service.processed == []


def test_extension_case_handling_matches_process(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """No asymmetry: both endpoints lowercase the suffix, so ``.PNG`` passes both.

    The five-line check is *duplicated* in the two handlers rather than shared,
    so this pins the behaviour they have in common today; a future edit to one
    copy is what would break it.
    """
    upper = tmp_path / "document.PNG"
    upper.write_bytes(_png_bytes())

    assert _upload(client, "document.PNG").status_code == 200
    response = client.post("/api/ocr/process-path", headers=_auth(), data={"file_path": str(upper)})
    assert response.status_code == 200

    assert len(service.processed) == 2
    assert Path(service.processed[0]).name == "document.PNG"  # sanitised upload copy
    assert service.processed[1] == str(upper)  # the server-side path, untouched


@pytest.mark.parametrize(
    "suffix", ["p\uff4eg", "png\u200b", "png ", "PNG\u0130", "p\u043dg", "\uff50ng"]
)
def test_unicode_lookalike_extensions_are_rejected(
    client: TestClient, service: _RecordingService, tmp_path: Path, suffix: str
) -> None:
    """Case folding is not normalisation: confusables never match the allow-list."""
    target = tmp_path / f"document.{suffix}"
    target.write_bytes(_png_bytes())

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(target)}
    )
    assert response.status_code == 400
    assert service.processed == []


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("glob", "/tmp/*.png"),
        ("file-url", "file:///etc/passwd.png"),
        ("encoded-traversal", "%2e%2e%2fetc%2fpasswd.png"),
        ("encoded-null", "/etc/passwd%00.png"),
        ("relative", "definitely_absent_document.png"),
        ("missing", "/nonexistent/dir/document.png"),
        ("parent-of-valid", "/tmp/../etc/hostname.png"),
    ],
)
def test_non_path_and_missing_inputs_are_rejected(
    client: TestClient, service: _RecordingService, label: str, value: str
) -> None:
    """No glob expansion, no URL handling, no percent-decoding -- a plain 404."""
    response = client.post("/api/ocr/process-path", headers=_auth(), data={"file_path": value})
    assert response.status_code in (400, 404), f"{label} answered {response.status_code}"
    assert service.processed == []


def test_null_byte_path_cannot_truncate_the_check(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """A NUL reaches ``os.path.isfile`` and raises -- it does not truncate to a valid file."""
    target = tmp_path / "document.png"
    target.write_bytes(_png_bytes())

    response = client.post(
        "/api/ocr/process-path",
        headers=_auth(),
        data={"file_path": str(target) + ".png\x00.txt"},
    )
    assert response.status_code in (400, 404, 500)
    assert service.processed == []


def test_extension_filter_is_not_confined_to_any_root(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """PARTIAL: the filter gates the *name*, never the location.

    There is no allowed-root setting, so any readable ``*.png``/``*.pdf`` on the
    host is reachable -- including one inside a directory that merely looks like
    an allowed extension. Extension allow-listing is a content hint, not an
    authorisation boundary.
    """
    nested = tmp_path / "gallery.png"
    nested.mkdir()
    target = nested / "report.pdf"
    target.write_bytes(b"%PDF-1.4 not really")

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(target)}
    )
    assert response.status_code == 200
    assert service.processed == [str(target)]


@pytest.mark.parametrize(
    "target",
    [
        "/etc/passwd",
        "/etc/shadow",
        "~/.ssh/id_rsa",
        "~/.aws/credentials",
        ".env",
        "/proc/self/environ",
    ],
)
def test_classic_secret_paths_never_reach_the_service(
    client: TestClient, service: _RecordingService, target: str
) -> None:
    """The original S0 payloads, pinned: rejected, with no filesystem touch."""
    response = client.post("/api/ocr/process-path", headers=_auth(), data={"file_path": target})
    assert response.status_code == 400
    assert service.processed == []


# --- D. resource bounds ---------------------------------------------------


def test_oversized_dpi_is_rejected_before_it_reaches_the_engine(
    client: TestClient, service: _RecordingService, tmp_path: Path
) -> None:
    """FIXED: ``dpi`` is now bounds-checked, so it cannot multiply a pixmap.

    This test previously recorded the opposite behaviour -- that an unbounded
    ``dpi`` reached ``fitz.Matrix(dpi / 72, dpi / 72)`` and the engine accepted
    it. ``dpi`` multiplies the pixmap allocation for every PDF page, so on a
    100 MB upload it was a memory-exhaustion lever. ``OCRRequest`` now bounds it
    to 50-600 and the form field carries the same constraint, so the value is
    rejected at the boundary (422) and never reaches the service.

    ``max_tokens`` and ``ngram_window`` no longer exist: they were parameters of
    the Unlimited-OCR engine, which was removed.
    """
    target = tmp_path / "document.pdf"
    target.write_bytes(b"%PDF-1.4 fake")

    response = client.post(
        "/api/ocr/process-path", headers=_auth(), data={"file_path": str(target), "dpi": 10**9}
    )
    assert response.status_code == 422
    assert service.requests == []

    response = client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("document.png", _png_bytes(), "image/png")},
        data={"dpi": -1},
    )
    assert response.status_code == 422
    assert service.requests == []


def test_oversized_upload_is_rejected_before_any_filesystem_write(
    client: TestClient,
    service: _RecordingService,
    upload_root: _UploadRoot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The size gate runs before ``mkdtemp`` -- but only after the body is buffered.

    Starlette spools a multipart body before the handler sees it, so the 413
    protects the OCR engine and the upload directory *after* the transfer, not
    the connection itself. See the xfail below for the unauthenticated version
    of the same ordering problem.
    """
    # The size limit now lives on Settings.ocr. Patch the accessor the route
    # uses rather than the deleted app.integrations.ocr.config module.
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr", dc_replace(settings.ocr, max_upload_size_mb=1))

    response = _upload(client, "big.png", b"x" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert upload_root.created == []
    assert service.processed == []


@pytest.mark.xfail(
    strict=True,
    reason="OPEN FINDING: FastAPI parses the multipart body before solving the router's auth "
    "dependency, so an anonymous request can make the server buffer an unbounded upload "
    "before it is rejected",
)
async def test_anonymous_request_body_is_not_read_before_rejection(
    service: _RecordingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Measured at the ASGI boundary, where the body pull is observable.

    ``TestClient`` sends the whole body regardless, so the only way to see this is
    to drive the app with our own ``receive``. FastAPI's request handler parses
    the form (``await request.form()``) *before* ``solve_dependencies`` runs the
    router-level guard, so the entire part is streamed and spooled before the 401
    exists -- and uvicorn applies no body limit of its own. That leaves an
    unauthenticated caller able to spend the server's parse CPU, its disk (a
    spool file past 1 MB) and its event loop on a request it knows will be
    refused. Fixing it needs the guard above the router: middleware, or a check
    the body parser cannot run first.
    """
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = _build_app(service)

    body = (
        b"--B\r\n"
        b'Content-Disposition: form-data; name="file"; filename="big.png"\r\n'
        b"Content-Type: image/png\r\n\r\n" + b"x" * (1024 * 1024) + b"\r\n--B--\r\n"
    )
    status, pulled_bytes = await _asgi_request(
        app,
        method="POST",
        path="/api/ocr/process",
        headers=[
            (b"content-type", b"multipart/form-data; boundary=B"),
            (b"content-length", str(len(body)).encode()),
        ],
        body=body,
    )

    assert status == _UNAUTHORIZED
    assert service.processed == []
    assert pulled_bytes == 0, (
        f"the server read {pulled_bytes} body bytes from an anonymous request "
        f"before answering {status}"
    )


@pytest.mark.parametrize(
    ("name", "exception_name"),
    [("ocr-service-error", "OCRServiceError"), ("unexpected", "RuntimeError")],
)
def test_failed_processing_removes_its_upload_directory(
    upload_root: _UploadRoot,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    exception_name: str,
) -> None:
    """Every failure path cleans up, not just the happy one.

    This is the end-to-end pair to ``test_ocr_temp_cleanup``: the directory the
    route actually created is inspected, so an implementation that cleaned up a
    different path, or that leaked on one path only, would be caught. The old
    code registered ``shutil.rmtree`` on the route response, which FastAPI
    discards when the handler raises -- the 502 and 500 paths both leaked the
    whole upload.
    """
    from app.integrations.ocr import service as service_module

    exception = {
        "OCRServiceError": service_module.OCRServiceError,
        "RuntimeError": RuntimeError,
    }[exception_name]

    class _Exploding(_RecordingService):
        async def process_upload(self, path: str, request: Any) -> dict[str, Any]:
            self.processed.append(str(path))
            raise exception(f"{name} failure")

    exploding = _Exploding()
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    response = TestClient(_build_app(exploding), raise_server_exceptions=False).post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("document.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == (502 if exception_name == "OCRServiceError" else 500)
    assert len(upload_root.created) == 1, "the route never created its upload directory"
    assert not upload_root.created[
        0
    ].exists(), f"{response.status_code} path leaked {upload_root.created[0]}"


def test_successful_processing_removes_its_upload_directory(
    client: TestClient, service: _RecordingService, upload_root: _UploadRoot
) -> None:
    """Control for the failure paths: the upload exists while the engine reads it."""
    assert _upload(client, "document.png").status_code == 200
    assert len(upload_root.created) == 1
    assert service.payloads == [b"\x89PNG\r\n\x1a\n"], "cleanup ran before the engine read it"
    assert not upload_root.created[0].exists()
