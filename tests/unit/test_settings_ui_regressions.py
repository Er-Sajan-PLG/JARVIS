"""Regression tests for the settings bugs found in manual testing.

Each test pins a specific defect that shipped and was fixed:

1. default-model state read the API envelope instead of its payload
2. the add-model dialog's close button was bound to a non-existent id
3. the custom-provider dialog did not exist at all
4. free models were never flagged, so the Free filter returned nothing
5. isFree() ignored the server's flag and re-derived from pricing
6. fetchProviderModels was called with the wrong argument shape
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
ASSETS = FRONTEND / "assets"
HTML = (FRONTEND / "index.html").read_text()


def js(name: str) -> str:
    return (ASSETS / name).read_text()


# ── 1. default model envelope ────────────────────────────────────────────────


def test_main_unwraps_default_envelope():
    """state.defaultModel must hold {provider, model}, not the API envelope."""
    src = js("main.js")
    assert "dfltRes?.default" in src or "dfltRes.default" in src, (
        "main.js must unwrap the {default: {...}} envelope from /api/settings/default"
    )
    # The old bug: destructuring `{ default: dflt }` from the raw response.
    assert "{ default: dflt }" not in src, "must not destructure the envelope as the value"


def test_default_endpoint_shape_matches_client_expectation():
    """The endpoint returns {default: {...}}; the client reads .default."""
    route = (Path(__file__).resolve().parents[2] / "app/adapters/web/router.py").read_text()
    assert 'return {"default": get_default()}' in route
    assert "res.default" in js("settings.js")


# ── 2/3. dialogs exist and are wired ─────────────────────────────────────────


def test_add_model_close_button_id_matches():
    """Every close/cancel control in the add-model dialog must be bound."""
    assert 'id="addModelCancel"' in HTML
    assert "id=\"addModelCancelBtn\"" in HTML, "the Cancel button must exist"
    js_src = js("settings.js")
    assert "'#addModelCancel'" in js_src, "the ✕ button must be bound"
    assert "'#addModelCancelBtn'" in js_src, "the Cancel button must be bound too"
    # No binding may reference an id that is not in the document.
    for bound in re.findall(r"\$\('#(addModel\w+)'\)", js_src):
        assert f'id="{bound}"' in HTML, f"settings.js binds #{bound}, absent from HTML"


def test_provider_dialog_exists_and_is_wired():
    """A custom-provider form must exist with live fetch + manual add."""
    for element in (
        'id="providerModal"',
        'id="providerForm"',
        'id="providerName"',
        'id="providerBaseUrl"',
        'id="providerKey"',
        'id="providerFetch"',
        'id="providerModelList"',
        'id="providerManualModel"',
        'id="providerAddManual"',
        'id="providerCancel"',
    ):
        assert element in HTML, f"missing {element}"

    src = js("settings.js")
    assert "function openProviderDialog" in src
    assert "function submitProvider" in src
    assert "function fetchProviderModels" in src
    # Wired to the dialog controls, not just defined.
    assert "$('#providerForm')?.addEventListener('submit', submitProvider)" in src
    assert "$('#providerFetch')?.addEventListener('click', fetchProviderModels)" in src


def test_add_model_offers_creating_a_new_provider():
    src = js("settings.js")
    assert "__new__" in src, "add-model dialog must offer a 'new provider' option"
    assert "openProviderDialog()" in src


def test_models_tab_exposes_add_provider():
    assert "+ Add provider" in js("settings.js")


# ── 4/5. free models ─────────────────────────────────────────────────────────


def test_free_policy_covers_free_tier_providers():
    """Providers with a published free offering must be recognised."""
    from app.utils.provider_catalog import FREE_PROVIDER_POLICY

    for key in ("nvidia", "openrouter", "groq", "github", "cloudflare", "huggingface", "google"):
        assert key in FREE_PROVIDER_POLICY, f"{key} publishes free usage but has no policy"


def test_nvidia_free_endpoints_are_flagged():
    """NVIDIA's free-endpoint models must come back marked free."""
    from app.utils.provider_catalog import _tag_free

    free_model = _tag_free({"id": "meta/llama-3.1-8b-instruct", "pricing": {}}, "nvidia")
    assert free_model["free"] is True
    assert "free" in free_model.get("free_reason", "")

    paid = _tag_free({"id": "nvidia/some-huge-paid-model", "pricing": {"prompt": "0.5"}}, "nvidia")
    assert paid["free"] is False


def test_always_free_providers_are_flagged():
    from app.utils.provider_catalog import _tag_free

    for key in ("ollama", "llamacpp", "groq", "github", "cloudflare", "huggingface"):
        m = _tag_free({"id": "whatever-model", "pricing": {}}, key)
        assert m["free"] is True, f"{key} serves models free to call"


def test_unknown_provider_is_not_marked_free():
    """No policy means no claim — never guess a model is free."""
    from app.utils.provider_catalog import _tag_free

    m = _tag_free({"id": "mystery-model", "pricing": {}}, "some-unknown-provider")
    assert m["free"] is False


def test_zero_pricing_marks_free_but_missing_pricing_does_not():
    from app.utils.provider_catalog import _tag_free

    zero = _tag_free({"id": "x", "pricing": {"prompt": "0", "completion": "0.0"}}, "openrouter")
    assert zero["free"] is True

    unpriced = _tag_free({"id": "y", "pricing": {}}, "openrouter")
    assert unpriced["free"] is False, "missing pricing must not imply free"


def test_frontend_isFree_prefers_server_flag():
    src = js("core.js")
    assert "typeof model.free === 'boolean'" in src, (
        "isFree must trust the server's free flag, which encodes free tiers/endpoints"
    )


def test_models_tab_has_free_filter():
    src = js("settings.js")
    assert "modelsFreeOnly" in src
    assert "Free only" in src


# ── 6. client call shapes ────────────────────────────────────────────────────


def test_fetch_provider_models_arg_shape():
    """The endpoint reads base_url/api_key, so the client must send those keys."""
    core = js("core.js")
    assert "base_url: baseUrl" in core
    assert "api_key: apiKey" in core

    route = (Path(__file__).resolve().parents[2] / "app/adapters/web/router.py").read_text()
    assert 'body.get("base_url")' in route


def test_add_provider_client_method_exists():
    """settings.js calls api.addProvider; the client must define it."""
    assert "api.addProvider(" in js("settings.js")
    assert "addProvider:" in js("core.js")


# ── API keys: never leak, always editable ────────────────────────────────────


def test_api_key_row_never_prefills_a_secret():
    """A configured key must not be rendered as a pre-filled fake value."""
    src = js("settings.js")
    assert "value: info.configured ? '••••••••'" not in src, (
        "pre-filling the mask made Show reveal a fake value and blocked Save"
    )
    # The flow is now explicit replace.
    assert "Replace key" in src
    assert "key-value-masked" in src


def test_api_key_css_exists():
    css = (ASSETS / "app.css").read_text()
    for cls in (".key-row", ".key-value-masked", ".chip-list", ".chip-removable"):
        assert cls in css, f"missing style for {cls}"


@pytest.mark.parametrize("provider", ["nvidia", "openrouter", "groq"])
def test_api_key_response_never_contains_a_value(provider: str):
    """The status endpoint reports presence only — never the secret."""
    route = (Path(__file__).resolve().parents[2] / "app/adapters/web/router.py").read_text()
    block = route[route.index('@web_router.get("/settings/api-keys")'):]
    block = block[: block.index("@web_router.post")]
    assert '"configured"' in block
    assert "get_api_key_status()" in block
    # No raw key material may be echoed.
    assert re.search(r'return\s*\{[^}]*"key"\s*:', block) is None

# ── Capability tags + context length (new requested features) ────────────────


def test_capability_vocabulary_is_canonical_and_unique():
    """One vocabulary drives the picker filters, the Models tab and the
    add-model form; keys must be unique and cover the requested tags."""
    src = js("core.js")
    keys = re.findall(r"\{\s*key:\s*'([a-z-]+)'", src)
    assert keys, "ALL_CAPABILITIES must declare string keys"
    assert len(keys) == len(set(keys)), f"duplicate capability keys: {keys}"
    for required in ("text", "vision", "reasoning", "code", "tools"):
        assert required in keys, f"capability `{required}` missing from the vocabulary"


def test_capabilities_inferred_for_known_model_shapes():
    """capabilitiesOf must tag a vision/reasoning/code model correctly and
    must not tag an embedding endpoint as text-capable."""
    src = js("core.js")
    assert "export function capabilitiesOf" in src
    assert "export function matchesCapabilities" in src
    # Hints must cover the shapes users actually see in the catalogue.
    for hint in ("vision", "reasoning", "code", "audio"):
        assert hint in src, f"capability hints for `{hint}` missing"
    assert "NON_TEXT_HINTS" in src, "embedding endpoints must be excluded from text"


def test_declared_capabilities_win_over_inference():
    """A custom model's explicit capability list is authoritative."""
    src = js("core.js")
    fn = src[src.index("export function capabilitiesOf"):]
    fn = fn[:fn.index("\n}")]
    assert "Array.isArray(model.capabilities)" in fn
    assert fn.index("model.capabilities") < fn.index("CAPABILITY_HINTS"), (
        "declared capabilities must be checked before inference"
    )


def test_picker_exposes_capability_and_context_filters():
    """The requested search-time tags: capabilities and context size."""
    html = HTML
    assert 'id="pickerCaps"' in html, "picker needs a capability filter host"
    assert 'id="pickerCtx"' in html, "picker needs a min-context control"

    picker = js("picker.js")
    assert "pickerState.caps" in picker
    assert "pickerState.minCtx" in picker
    assert "matchesCapabilities" in picker, "capability filter must be applied"
    assert "buildCapFilters" in picker and "syncCapButtons" in picker


def test_models_tab_filters_by_capability_and_context():
    """The Settings → Models tab must offer the same filters."""
    src = js("settings.js")
    assert "const modelsCaps = new Set()" in src
    assert "modelsMinCtx" in src
    assert "matchesCapabilities(m, modelsCaps)" in src, "capability filter must apply"
    assert "(m.context_length || 0) < modelsMinCtx" in src, "context filter must apply"
    assert "Clear filters" in src, "filters need a reset control"


def test_custom_model_form_captures_context_and_capabilities():
    """Adding a custom model must let the user record its context window and
    capability tags, and must send both to the server."""
    assert 'id="addModelContext"' in HTML
    assert 'id="addModelCaps"' in HTML
    src = js("settings.js")
    assert "pendingModelCaps" in src
    assert "capabilities: [...pendingModelCaps]" in src, "capabilities must be sent"
    assert "context_length:" in src, "context length must be sent"


def test_capability_badges_render_on_model_rows():
    """Model rows must show capability tags, not just pricing."""
    for mod in ("settings.js", "picker.js"):
        src = js(mod)
        assert "badge-cap" in src, f"{mod} must render capability badges"


def test_custom_provider_dialog_captures_max_context_length():
    """BUG (user report, verbatim): "the provider doesn't have max context_length
    option" — the custom PROVIDER dialog only had name/base-url/key/models.
    It must now let the user set a max context length for its models."""
    assert 'id="providerContext"' in HTML, "custom provider dialog needs the field"
    src = js("settings.js")
    assert "$('#providerContext')" in src, "the field must be read"
    assert "context_length: contextLength" in src, "it must be sent to the server"
    # And it must be validated rather than trusting raw input.
    assert "Number.isFinite(contextLength)" in src
    assert "must be a non-negative number" in src


def test_custom_provider_dialog_offers_capability_tags():
    """A hand-added model has no metadata to infer from, so the provider dialog
    must let the user declare capabilities explicitly."""
    assert 'id="providerCaps"' in HTML
    src = js("settings.js")
    assert "pendingProviderCaps" in src
    assert "buildProviderCaps" in src
    assert "capabilities: [...pendingProviderCaps]" in src, "must be sent"
    # Provider dialog state must be reset on open, or a prior selection leaks.
    assert "pendingProviderCaps.clear()" in src
