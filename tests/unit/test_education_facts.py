"""Education facts must be distinguishable, not collapsed into one category.

The owner corrected this explicitly: the awarding university and the college
where he studied are two different facts, and it must be possible to tell them
apart — "education" alone cannot say which is which.

This file previously asserted the CONTENT of the owner's live memory store: that
it held a record for the awarding university and one for the college where he
studied, that both were typed separately, that no record claimed he studied at
the university, and that the store had no duplicate degree records. Those were
data-validation assertions about a mutable personal file, not tests of
behaviour: they passed on the owner's machine and skipped in every fresh clone
and in CI, so they measured nothing there. They are deleted rather than
re-expressed against a synthetic store — a test whose whole content is "the
facts I just wrote into my own fixture are still there" asserts nothing about
the code.

What survives is the behaviour they were protecting, and the bug that made it
necessary: ``GET /api/memory`` must report each record's ``type`` (the domain
object's ``memory_type``). The endpoint read ``m.type``, which does not exist on
the dataclass, so every record came back with ``type: None`` and a caller could
not distinguish the awarding university from the place of study. The records in
the test below are constructed, so the assertion is about the serializer and not
about any particular person's education.
"""

from __future__ import annotations

import pytest


def test_api_exposes_the_fact_type_not_just_the_category(
    monkeypatch: pytest.MonkeyPatch, api_key_env: str
) -> None:
    """The API must report the fact type, not only a broad category.

    Driven hermetically through ``fastapi.testclient.TestClient``. It used to
    fetch ``http://localhost:8000`` with urllib and skip whenever the server was
    unreachable, so it asserted nothing at all unless a developer happened to
    have the app running. Only ``bootstrap_system`` — the edge that reaches the
    store — is replaced; the route and the serializer are the ones under test.
    """
    from fastapi.testclient import TestClient

    from app.adapters.web import router as web_router_module
    from app.main import app
    from app.memory.schema import Memory

    records = [
        Memory(category="education", memory_type="university", value="Example University"),
        Memory(category="education", memory_type="college", value="Example College"),
    ]

    class _Manager:
        def get_all(self) -> list[Memory]:
            return records

    class _Service:
        def __init__(self) -> None:
            self._manager = _Manager()

    class _Container:
        def __init__(self) -> None:
            self.memory_service = _Service()

    monkeypatch.setattr(web_router_module, "bootstrap_system", lambda *a, **k: _Container())

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {api_key_env}"
        response = client.get("/api/memory")

    assert response.status_code == 200, response.text
    edu = [m for m in response.json()["memories"] if m.get("category") == "education"]
    assert edu, "no education records returned by the API"
    untyped = [m for m in edu if not m.get("type")]
    assert not untyped, (
        "API returned education records with no type, so the awarding university "
        f"and the place of study are indistinguishable: {untyped}"
    )
    types = {m["type"] for m in edu}
    assert "university" in types, f"university type missing from API: {types}"
    assert "college" in types, f"college type missing from API: {types}"
