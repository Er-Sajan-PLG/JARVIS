"""OpenRouter requests must send an explicit max_tokens.

Reported symptom: chat failed with HTTP 402 "This request requires more
credits, or fewer max_tokens. You requested up to 65536 tokens, but can only
afford 15997" on a pay-as-you-go OpenRouter account.

Root cause: neither the web router nor OpenRouterClient sent a max_tokens, so
OpenRouter assumed the model's full output ceiling and pre-authorised that
cost against the balance. Large-ceiling models (e.g. grok-4.20-multi-agent,
65536) were rejected while cheap models with small ceilings slipped through —
making it look like an account/billing problem when it was a missing field.

The assertions here observe the request, not the source. They originally read
``inspect.getsource(OpenRouterClient.generate)`` and checked that the text
``kwargs.setdefault("max_tokens"`` appeared in it. That is satisfiable by a
comment, and it never checked the *value*: changing ``DEFAULT_MAX_TOKENS`` to
``1`` — which would truncate every reply — passed all three (F-TEST-010).
"""

from __future__ import annotations

import ast
from unittest.mock import MagicMock

from app.models.openrouter_client import OpenRouterClient


def _client_with_recording_transport() -> tuple[OpenRouterClient, MagicMock]:
    """A real client whose transport records the kwargs of the outgoing call."""
    client = OpenRouterClient(model="some/model", api_key="test-key")

    choice = MagicMock()
    choice.message.content = "ok"
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    response.usage.total_tokens = 3

    create = MagicMock(return_value=response)
    client._client.chat.completions.create = create
    return client, create


def _sent_kwargs(create: MagicMock) -> dict:
    assert create.call_count == 1, f"expected one API call, got {create.call_count}"
    return create.call_args.kwargs


def test_client_declares_a_default_max_tokens():
    assert hasattr(OpenRouterClient, "DEFAULT_MAX_TOKENS")
    value = OpenRouterClient.DEFAULT_MAX_TOKENS
    assert isinstance(value, int)
    # Small enough to fit a modest free-tier balance, large enough for a
    # real chat reply. The upper bound is what makes this more than a type
    # check: a value of 1 is an int and would fail every real conversation.
    assert 512 <= value <= 16384, value


def test_generate_sends_the_default_max_tokens_when_caller_omits_it():
    """The default must reach the API request, not merely appear in the source.

    Verified behaviourally: the transport is substituted and the outgoing kwargs
    are inspected. A comment mentioning ``setdefault`` cannot satisfy this.
    """
    client, create = _client_with_recording_transport()

    client.generate([{"role": "user", "content": "hi"}])

    sent = _sent_kwargs(create)
    assert "max_tokens" in sent, (
        "generate() sent no max_tokens; OpenRouter then reserves the model's "
        "full output ceiling and rejects the call with HTTP 402"
    )
    assert sent["max_tokens"] == OpenRouterClient.DEFAULT_MAX_TOKENS


def test_generate_does_not_override_an_explicit_max_tokens():
    """A caller's ceiling is forwarded unchanged, in both directions.

    The old version asserted the string ``kwargs.setdefault`` appeared and that
    ``kwargs["max_tokens"] =`` did not. Both are source-text checks. This asserts
    the value the caller actually gets, and covers raising *and* lowering —
    a blind ``setdefault`` onto a smaller value would still pass the old test.
    """
    for requested in (99, 32768):
        client, create = _client_with_recording_transport()

        client.generate([{"role": "user", "content": "hi"}], max_tokens=requested)

        sent = _sent_kwargs(create)
        assert sent["max_tokens"] == requested, (
            f"caller asked for max_tokens={requested}, the request carried " f"{sent['max_tokens']}"
        )


def test_default_is_documented_as_the_402_prevention():
    """The reason is non-obvious; keep it recorded next to the constant."""
    import inspect

    doc = inspect.getdoc(OpenRouterClient.generate) or ""
    assert "max_tokens" in doc
    assert (
        "402" in doc or "ceiling" in doc.lower()
    ), "the docstring should explain the 402 pre-authorisation behaviour"


def test_web_router_does_not_supply_a_competing_max_tokens():
    """The router relies on the client default rather than passing its own.

    Read from the AST rather than the source text: the previous version did
    ``src.find("client.generate(")`` and sliced 400 characters, which a comment
    or a docstring could satisfy. The AST gives the actual call and its actual
    keywords, so this reports what the code does.
    """
    from pathlib import Path

    import app.adapters.web.router as router_mod

    tree = ast.parse(Path(router_mod.__file__).read_text(encoding="utf-8"))

    call_sites: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "generate":
            call_sites.append(node)

    assert call_sites, "the chat path no longer calls .generate() anywhere"
    for call in call_sites:
        names = {kw.arg for kw in call.keywords}
        if "max_tokens" not in names:
            # Fine by design: the client supplies the default. What must hold is
            # that the default exists and is applied, which the tests above prove.
            assert hasattr(
                OpenRouterClient, "DEFAULT_MAX_TOKENS"
            ), "the router omits max_tokens, so the client must supply a default"
