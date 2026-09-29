"""Sandbox and egress tests for ``POST /api/agy/analyze-file`` (F-SEC-004, S1).

``analyze_file`` read whatever path it was handed and inlined up to 60,000
characters of it into a prompt sent to Google, so one authenticated request was
an arbitrary-server-file-read *and* exfiltration primitive. The tool sandbox in
``app.tools.workspace_tools`` was never consulted, which defeated the ``.env``
protection that already existed for tools.

These tests assert the contract, not the implementation:

* a refused path is rejected *before* the file is opened and before any prompt
  exists -- proven by recording ``open``, ``subprocess.run`` and ``chat``, and by
  treating any of them being reached as a failure;
* resolution happens *before* the decision, so a symlink or ``..`` cannot smuggle
  a secret past the check;
* a document that is legitimately analysable still is.

No test here reads a live credential. ``EgressRecorder`` fails closed on the real
secret locations, so a regression is *recorded* (the attempt is what the
assertions inspect) without a live key ever entering the process.
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.integrations import agy
from app.adapters.security import API_KEY_ENV
from app.adapters.web.router import web_router
from app.tools.workspace_tools import SECRET_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTE = "/api/agy/analyze-file"
TEST_KEY = "test-key-agy-sandbox"  # noqa: S105 - fixture value, not a real credential
CANARY = "AGY-EGRESS-CANARY-that-must-not-leave-the-machine"
STUB_ANALYSIS = "stub analysis"

# Real locations that must never be read by a test run, even if the code under
# test regresses. ``data/uploads`` is deliberately not covered: it is the
# console's document area, and it is what file analysis is pointed at.
_LIVE_SECRET_ROOTS = (
    REPO_ROOT / ".env",
    REPO_ROOT / "data",
    Path.home() / ".ssh",
)
_LIVE_SECRET_EXCEPTIONS = (REPO_ROOT / "data" / "uploads",)


def _is_live_secret(target: str) -> bool:
    """Whether the test guard must refuse to open ``target``."""
    try:
        resolved = Path(target).expanduser().resolve()
    except (OSError, ValueError):
        return False
    if resolved == Path("/etc/shadow"):
        return True
    for root in _LIVE_SECRET_ROOTS:
        if resolved.is_relative_to(root) and not any(
            resolved.is_relative_to(keep) for keep in _LIVE_SECRET_EXCEPTIONS
        ):
            return True
    return False


class EgressRecorder:
    """Records every way file content could leave, and blocks the live secrets.

    ``open``, ``chat`` and ``subprocess.run`` are the three steps between "a path
    arrived" and "the file is on someone else's server". Any of them being
    reached for a refused path is the regression these tests exist to catch.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opens: list[str] = []
        self.analyze_calls: list[str] = []
        self.prompts: list[str] = []
        self.cli_calls: list[tuple[Any, ...]] = []

        real_open = builtins.open
        real_analyze = agy.analyze_file

        def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            self.opens.append(str(file))
            if _is_live_secret(str(file)):
                raise PermissionError("test guard: refusing to open a live credential file")
            return real_open(file, *args, **kwargs)

        def spy_analyze(
            file_path: str,
            query: str,
            model: str = agy.DEFAULT_MODEL,
            mime_type: str | None = None,
        ) -> str:
            self.analyze_calls.append(str(file_path))
            return real_analyze(file_path, query, model=model, mime_type=mime_type)

        def stub_chat(messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            self.prompts.append("\n".join(str(message.get("content", "")) for message in messages))
            return {
                "content": STUB_ANALYSIS,
                "model": kwargs.get("model", ""),
                "tokens_used": None,
                "finish_reason": "stop",
                "conversation_id": "",
            }

        def refused_cli(*args: Any, **kwargs: Any) -> Any:
            self.cli_calls.append(args)
            raise AssertionError("subprocess.run reached: no CLI may run in a unit test")

        monkeypatch.setattr(builtins, "open", guarded_open)
        monkeypatch.setattr(agy, "analyze_file", spy_analyze)
        monkeypatch.setattr(agy, "chat", stub_chat)
        monkeypatch.setattr(agy, "_agy_which", lambda: "/usr/bin/agy")
        monkeypatch.setattr(agy.subprocess, "run", refused_cli)

    def touched(self, path: str) -> bool:
        """Whether anything tried to open ``path`` (compared after resolution)."""
        target = Path(path).expanduser().resolve()
        for opened in self.opens:
            try:
                if Path(opened).expanduser().resolve() == target:
                    return True
            except (OSError, ValueError):
                continue
        return False

    def assert_silent(self, path: str) -> None:
        """The path was never opened, never turned into a prompt, never sent."""
        assert not self.touched(
            path
        ), f"{path} was opened; a refused path must be rejected before the read"
        assert (
            self.analyze_calls == []
        ), f"the route entered analyze_file with a refused path: {self.analyze_calls}"
        assert self.prompts == [], "a prompt was built for a refused path"
        assert self.cli_calls == [], "the agy CLI was invoked for a refused path"


@pytest.fixture
def egress(monkeypatch: pytest.MonkeyPatch) -> EgressRecorder:
    return EgressRecorder(monkeypatch)


@pytest.fixture
def client(egress: EgressRecorder, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = FastAPI()
    app.include_router(web_router)
    return TestClient(app)


def _analyze(client: TestClient, file_path: str) -> Any:
    return client.post(
        ROUTE,
        headers={"Authorization": f"Bearer {TEST_KEY}"},
        json={"file_path": file_path},
    )


# --- refused paths --------------------------------------------------------

REFUSED_PATHS = (
    pytest.param(str(REPO_ROOT / ".env"), id="env-file"),
    pytest.param(str(REPO_ROOT / "data" / "web_settings.json"), id="key-store"),
    pytest.param(str(Path.home() / ".ssh" / "id_rsa"), id="ssh-private-key"),
    pytest.param("/etc/passwd", id="outside-workspace"),
    pytest.param(str(REPO_ROOT / "data" / ".." / ".env"), id="traversal-to-env"),
    pytest.param(str(REPO_ROOT / "data" / "memories.json"), id="memory-store"),
    pytest.param(str(REPO_ROOT / "data" / "tgcall.session"), id="telegram-session"),
)


@pytest.mark.parametrize("path", REFUSED_PATHS)
def test_refused_path_is_rejected_before_any_read_or_prompt(
    client: TestClient, egress: EgressRecorder, path: str
) -> None:
    """A path the sandbox refuses must be refused at the route, before the read."""
    response = _analyze(client, path)

    assert response.status_code == 403, (
        f"{path} answered {response.status_code}; a refused path must not look like "
        "a completed request, and it must never reach the file system"
    )
    egress.assert_silent(path)


def test_env_file_in_temp_is_refused_and_contents_never_reach_a_prompt(
    client: TestClient, egress: EgressRecorder, tmp_path: Path
) -> None:
    """The secret-name rule applies by name, wherever the file lives."""
    secret = tmp_path / ".env"
    secret.write_text(f"GOOGLE_API_KEY={CANARY}\n")

    response = _analyze(client, str(secret))

    assert response.status_code == 403
    assert CANARY not in response.text, "the route echoed file content back"
    egress.assert_silent(str(secret))
    assert all(CANARY not in prompt for prompt in egress.prompts)


def test_key_store_in_temp_is_refused_by_name(
    client: TestClient, egress: EgressRecorder, tmp_path: Path
) -> None:
    """``web_settings.json`` holds a plaintext provider key, so it is a secret name."""
    store = tmp_path / "web_settings.json"
    store.write_text(f'{{"api_keys": {{"google": "{CANARY}"}}}}')

    response = _analyze(client, str(store))

    assert response.status_code == 403
    assert CANARY not in response.text
    egress.assert_silent(str(store))


# --- resolution before the decision ---------------------------------------


def test_symlink_to_a_secret_is_refused_after_resolution(
    client: TestClient, egress: EgressRecorder, tmp_path: Path
) -> None:
    """An innocently named symlink must not smuggle a secret past the check."""
    secret = tmp_path / ".env"
    secret.write_text(f"GOOGLE_API_KEY={CANARY}\n")
    link = tmp_path / "meeting-notes.txt"
    link.symlink_to(secret)

    response = _analyze(client, str(link))

    assert response.status_code == 403, "a symlink defeated the sandbox check"
    assert CANARY not in response.text
    egress.assert_silent(str(link))
    assert egress.prompts == []


def test_symlink_out_of_the_allowed_roots_is_refused(
    client: TestClient, egress: EgressRecorder, tmp_path: Path
) -> None:
    """A symlink pointing outside the workspace is still outside the workspace."""
    link = tmp_path / "innocent.txt"
    link.symlink_to("/etc/passwd")

    response = _analyze(client, str(link))

    assert response.status_code == 403
    egress.assert_silent(str(link))


def test_private_state_tree_is_refused_by_the_policy() -> None:
    """``data/`` is operator state, not a document; only its uploads are analysable."""
    for relative in ("memories.json", "jarvis.db", "conversations/2026.json"):
        with pytest.raises(PermissionError):
            agy.resolve_analysis_path(str(REPO_ROOT / "data" / relative))

    assert agy.resolve_analysis_path(str(REPO_ROOT / "data" / "uploads" / "report.md"))


def test_analyze_file_raises_a_clear_refusal_not_empty_content(tmp_path: Path) -> None:
    """A refusal is an error, never a silently empty analysis."""
    secret = tmp_path / ".env"
    secret.write_text(f"GOOGLE_API_KEY={CANARY}\n")

    with pytest.raises(PermissionError) as refusal:
        agy.analyze_file(str(secret), "summarise this")

    message = str(refusal.value)
    assert message.strip(), "refusal carried no explanation"
    assert "refused" in message.lower()


def test_egress_denylist_covers_the_tool_sandbox_secret_names() -> None:
    """The egress deny-list must not drift behind the tool sandbox's.

    ``app.adapters`` may not import ``app.tools`` (``scripts/board/review.py``,
    ``check_import_layering``), so the names are maintained in two places. This is
    the test that makes drift a red build instead of a silent hole: a name added
    to ``SECRET_NAMES`` that ``analyze_file`` would still ship fails here.
    """
    missing = sorted(SECRET_NAMES - agy.EGRESS_SECRET_NAMES)
    assert missing == [], (
        f"analyze_file would still exfiltrate these secret names: {missing}; "
        "add them to agy.EGRESS_SECRET_NAMES"
    )


# --- the legitimate feature still works -----------------------------------

LEGITIMATE_MARKER = "legitimate document body"


def _legitimate_target(which: str, tmp_path: Path) -> Path:
    """A file that file analysis is legitimately pointed at."""
    if which == "temp-document":
        target = tmp_path / "notes.md"
        target.write_text(f"# Notes\n\n{LEGITIMATE_MARKER}\n")
        return target
    return REPO_ROOT / "pyproject.toml"


@pytest.mark.parametrize("which", ("temp-document", "workspace-document"))
def test_legitimate_document_is_still_analysed(
    client: TestClient, egress: EgressRecorder, tmp_path: Path, which: str
) -> None:
    """The file-analysis feature must survive the fix, and still inline the content."""
    target = _legitimate_target(which, tmp_path)

    response = _analyze(client, str(target))

    assert response.status_code == 200, response.text
    assert response.json() == {"response": STUB_ANALYSIS}
    assert egress.analyze_calls == [str(target)]
    assert len(egress.prompts) == 1, "the document was not inlined into exactly one prompt"
    if which == "temp-document":
        assert LEGITIMATE_MARKER in egress.prompts[0]
