"""OpenRouter requests must send an explicit max_tokens.

Reported symptom: chat failed with HTTP 402 "This request requires more
credits, or fewer max_tokens. You requested up to 65536 tokens, but can only
afford 15997" on a pay-as-you-go OpenRouter account.

Root cause: neither the web router nor OpenRouterClient sent a max_tokens, so
OpenRouter assumed the model's full output ceiling and pre-authorised that
cost against the balance. Large-ceiling models (e.g. grok-4.20-multi-agent,
65536) were rejected while cheap models with small ceilings slipped through —
making it look like an account/billing problem when it was a missing field.
"""

from __future__ import annotations

import inspect

from app.models.openrouter_client import OpenRouterClient


def test_client_declares_a_default_max_tokens():
    assert hasattr(OpenRouterClient, "DEFAULT_MAX_TOKENS")
    value = OpenRouterClient.DEFAULT_MAX_TOKENS
    assert isinstance(value, int)
    # Small enough to fit a modest free-tier balance, large enough for a
    # real chat reply.
    assert 512 <= value <= 16384, value


def test_generate_sends_max_tokens_when_caller_omits_it():
    """The default must be applied inside generate(), so every caller —
    the web router, CLI, agents — is covered without changing each one."""
    src = inspect.getsource(OpenRouterClient.generate)
    assert 'kwargs.setdefault("max_tokens"' in src or "kwargs.setdefault('max_tokens'" in src, (
        "generate() must default max_tokens; otherwise OpenRouter reserves the "
        "model's full output ceiling and rejects the call with HTTP 402"
    )


def test_generate_does_not_override_an_explicit_max_tokens():
    """setdefault, not a blind assignment: callers must be able to raise or
    lower the ceiling deliberately."""
    src = inspect.getsource(OpenRouterClient.generate)
    assert "kwargs.setdefault" in src
    assert 'kwargs["max_tokens"] =' not in src, "must not clobber a caller's value"


def test_default_is_documented_as_the_402_prevention():
    """The reason is non-obvious; keep it recorded next to the constant."""
    doc = inspect.getdoc(OpenRouterClient.generate) or ""
    assert "max_tokens" in doc
    assert "402" in doc or "ceiling" in doc.lower(), (
        "the docstring should explain the 402 pre-authorisation behaviour"
    )


def test_web_router_forwards_generate_unchanged():
    """The router relies on the client's default rather than passing its own,
    so a change to the router must not reintroduce the gap."""
    from app.adapters.web import router as router_mod

    src = inspect.getsource(router_mod)
    idx = src.find("client.generate(")
    assert idx != -1, "the chat path should call client.generate()"
    call = src[idx:idx + 400]
    # Either the client supplies the default (current design) or the router
    # passes one explicitly. Sending neither is the bug.
    if "max_tokens" not in call:
        assert hasattr(OpenRouterClient, "DEFAULT_MAX_TOKENS"), (
            "router omits max_tokens, so the client must supply a default"
        )
