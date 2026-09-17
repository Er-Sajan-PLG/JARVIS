"""/api/chat must accept `model` as a dict OR a bare string.

Regression: the endpoint assumed ``model`` was always a dict and called
``.get()`` on it. Any caller sending a bare model id — the CLI, probes, and
hand-written curl requests all do — got HTTP 500
``'str' object has no attribute 'get'``.

Provider resolution must NOT be done by splitting on "/": catalogue ids are not
reliably "provider/model" ("x-ai/grok-4.20" is an *openrouter* model; agy ids
like "gemini-3.8-flash-high" have no slash at all). Splitting misroutes, or
falls through to the default and silently ignores the requested model.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

API = "http://localhost:8000/api/chat"


def _post(payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        API, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {"body": e.read().decode()[:400]}
    except (urllib.error.URLError, TimeoutError, OSError):
        pytest.skip("server not running on :8000")


def test_string_model_does_not_500() -> None:
    """The exact regression: a bare model id must not crash the endpoint."""
    status, data = _post(
        {"message": "Say OK.", "model": "nvidia/nemotron-3-super-120b-a12b"}
    )
    assert status == 200, f"string model id returned {status}: {data}"
    assert data.get("response")


def test_dict_model_still_works() -> None:
    """The original dict shape must keep working."""
    status, data = _post(
        {
            "message": "Say OK.",
            "model": {"provider": "nvidia", "id": "nvidia/nemotron-3-super-120b-a12b"},
        }
    )
    assert status == 200, f"dict model returned {status}: {data}"


def test_no_model_falls_back_to_default() -> None:
    """Omitting model must still resolve the Settings default."""
    status, _ = _post({"message": "Say OK."})
    assert status == 200


def test_chat_source_does_not_split_model_on_slash() -> None:
    """Guard the source: the slash-splitting inference must not come back."""
    src = (
        Path(__file__).resolve().parents[2] / "app" / "adapters" / "web" / "router.py"
    ).read_text()
    assert 'raw_model.split("/", 1)[0]' not in src, (
        "provider inference by string splitting is back — model ids are not "
        "'provider/model' (see module docstring)"
    )
    assert "isinstance(raw_model, str)" in src, "string model handling removed"
