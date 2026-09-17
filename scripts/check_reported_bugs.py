"""Verify every bug reported during manual testing is fixed, live.

Run against the server on :8000. Prints PASS/FAIL per reported symptom.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000"
passed = 0
failed: list[str] = []


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=280) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed.append(label)
        print(f"  FAIL  {label}  {detail}")


cat = call("GET", "/api/models?refresh=true")[1]
by_key = {p["key"]: p for p in cat.get("providers", [])}

print("BUG 1 — changing the default model")
# Snapshot the user's real default first: this script runs against the live
# store, so it must put back whatever it found rather than leaving a test
# value (or clearing a default the user deliberately set).
_orig_st, _orig_res = call("GET", "/api/settings/default")
ORIGINAL_DEFAULT = _orig_res.get("default") or {}

or_models = [m["id"] for m in by_key.get("openrouter", {}).get("models", [])]
pick = or_models[0] if or_models else "openrouter/auto"
st, res = call("POST", "/api/settings/default", {"provider": "openrouter", "model": pick})
# Remember what WE set, so the restore step can tell our value apart from one a
# human changed afterwards. See the restore block at the end of this file.
DEFAULT_SET_BY_SCRIPT = ("openrouter", pick)
check("POST accepts the change", st == 200, str(st))
check(
    "response carries {default:{provider,model}}",
    res.get("default", {}).get("provider") == "openrouter"
    and res.get("default", {}).get("model") == pick,
    str(res),
)
st, back = call("GET", "/api/settings/default")
default = back.get("default") or {}
check("readback persists", default.get("model") == pick, str(back))
check(
    "the model really exists in the live catalogue",
    any(m["id"] == pick for m in by_key.get("openrouter", {}).get("models", [])),
)

print("BUG 2 — API keys show/save")
st, keys = call("GET", "/api/settings/api-keys")
check("status endpoint responds", st == 200)
check("reports presence flags", all("configured" in v for v in keys.get("keys", {}).values()))
check(
    "never returns a secret value",
    not any(set(v) - {"configured", "source"} for v in keys.get("keys", {}).values()),
    str(list(keys.get("keys", {}).values())[:2]),
)
st, _ = call("POST", "/api/settings/api-keys", {"provider": "nvidia", "key": "nvapi-probe-xyz"})
check("saving a key succeeds", st == 200, str(st))
_, after = call("GET", "/api/settings/api-keys")
nv = after.get("keys", {}).get("nvidia", {})
check("saved key now reads configured", nv.get("configured") is True, str(nv))
check("saved key is marked stored", nv.get("source") == "stored", str(nv))
check("key value still absent from the response", "nvapi-probe-xyz" not in json.dumps(after))
st, _ = call("DELETE", "/api/settings/api-keys/nvidia")
check("removing a key succeeds", st == 200, str(st))

print("BUG 3 — free models / free endpoints")
free_total = sum(
    len([m for m in p.get("models", []) if m.get("free")]) for p in cat.get("providers", [])
)
check("free models exist in the catalogue", free_total > 0, f"{free_total}")
nv_free = [m for m in by_key.get("nvidia", {}).get("models", []) if m.get("free")]
check("NVIDIA free endpoints are flagged", len(nv_free) > 0, f"{len(nv_free)}")
for key in ("groq", "github", "cloudflare", "huggingface", "ollama"):
    n = len([m for m in by_key.get(key, {}).get("models", []) if m.get("free")])
    check(f"{key} free models flagged", n > 0, f"{n}")
check(
    "every flagged model explains why",
    all(
        m.get("free_reason")
        for p in cat.get("providers", [])
        for m in p.get("models", [])
        if m.get("free")
    ),
)

print("BUG 4 — custom provider + custom model can be added")
st, _ = call(
    "POST",
    "/api/settings/providers",
    {
        "name": "Verify Provider",
        "base_url": "https://example.invalid/v1",
        "api_key": "verify-secret-key",
        "models": [{"id": "verify-model-1", "name": "Verify Model One"}],
    },
)
check("custom provider accepted", st == 200, str(st))
cat2 = call("GET", "/api/models?refresh=true")[1]
by2 = {p["key"]: p for p in cat2.get("providers", [])}
check("custom provider appears in the catalogue", "verify_provider" in by2)
check(
    "its model is selectable",
    any(m["id"] == "verify-model-1" for m in by2.get("verify_provider", {}).get("models", [])),
)

st, _ = call(
    "POST",
    "/api/settings/models",
    {
        "provider": "openrouter",
        "id": "verify-added-model",
        "name": "Verify Added",
        "custom": True,
    },
)
check("custom model accepted", st == 200, str(st))
cat3 = call("GET", "/api/models?refresh=true")[1]
by3 = {p["key"]: p for p in cat3.get("providers", [])}
check(
    "custom model selectable under its provider",
    any(m["id"] == "verify-added-model" for m in by3.get("openrouter", {}).get("models", [])),
)
check(
    "custom models are marked is_custom",
    any(
        m.get("is_custom")
        for m in by3.get("openrouter", {}).get("models", [])
        if m["id"] == "verify-added-model"
    ),
)

print("BUG 5 — provider model fetch endpoint")
st, fetched = call(
    "POST",
    "/api/settings/providers/fetch-models",
    {"base_url": "https://example.invalid/v1", "api_key": ""},
)
check("fetch endpoint responds without crashing", st == 200, str(st))
check(
    "returns a models list plus an error note",
    "models" in fetched and "error" in fetched,
    str(fetched)[:150],
)

print("BUG 6 — custom model keeps its context window and capability tags")
st, _ = call(
    "POST",
    "/api/settings/models",
    {
        "provider": "ollama",
        "id": "verify-cap-model",
        "name": "Verify Cap",
        "context_length": 131072,
        "capabilities": ["text", "vision", "tools"],
    },
)
check("custom model with caps/ctx accepted", st == 200, str(st))
cat4 = call("GET", "/api/models?refresh=true")[1]
by4 = {p["key"]: p for p in cat4.get("providers", [])}
added = next(
    (m for m in by4.get("ollama", {}).get("models", []) if m["id"] == "verify-cap-model"), None
)
check("custom model is listed", added is not None)
check(
    "context window persisted",
    bool(added) and added.get("context_length") == 131072,
    str(added and added.get("context_length")),
)
check(
    "capabilities persisted",
    bool(added) and sorted(added.get("capabilities") or []) == ["text", "tools", "vision"],
    str(added and added.get("capabilities")),
)

print("BUG 7 — catalogue reports the context data the picker filters on")
with_ctx = [
    m
    for p in cat4.get("providers", [])
    for m in p.get("models", [])
    if (m.get("context_length") or 0) > 0
]
check(
    "models expose a context_length for filtering",
    len(with_ctx) > 0,
    f"{len(with_ctx)} of {sum(len(p.get('models', [])) for p in cat4.get('providers', []))}",
)
vocab = call("GET", "/api/settings/default")[1]
check("default settings still readable after model churn", isinstance(vocab, dict))

# ── BUG 8: custom provider had no max context length field ──────────────────
# User, verbatim: "the provider doesn't have max context_length option".
# Fix must persist it on the provider AND push it down to its models, because
# the context-size filter reads model-level context_length.
print("bug 8: custom provider max context length")
st, created = call(
    "POST",
    "/api/settings/providers",
    {
        "name": "ctx-verify-provider",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-verify",
        "context_length": 131072,
        "capabilities": ["vision", "tools"],
        "models": [{"id": "ctx-verify-model", "name": "Ctx Verify Model"}],
    },
)
check("custom provider accepts context_length", st == 200, str(st))
# The server slugs the name (hyphens -> underscores); look the record up by the
# key it actually returned rather than re-deriving it here.
PROV_KEY = ((created or {}).get("provider") or {}).get("key") or ""
check("server returned a provider key", bool(PROV_KEY), repr(PROV_KEY))

_, provs = call("GET", "/api/settings/providers")
entry = next((p for p in (provs.get("providers") or []) if p.get("key") == PROV_KEY), None)
check("provider persisted", entry is not None)
check(
    "provider kept context_length",
    (entry or {}).get("context_length") == 131072,
    str((entry or {}).get("context_length")),
)
check(
    "provider kept capabilities",
    (entry or {}).get("capabilities") == ["vision", "tools"],
    str((entry or {}).get("capabilities")),
)
check(
    "provider never returns its api_key",
    "sk-verify" not in json.dumps(entry or {}),
    "raw key leaked to the browser",
)

st, models = call("GET", "/api/models")
cprov = next((p for p in (models.get("providers") or []) if p.get("key") == PROV_KEY), None)
check("provider appears in /api/models", cprov is not None)
cmod = next(
    (m for m in ((cprov or {}).get("models") or []) if m.get("id") == "ctx-verify-model"), None
)
check("model surfaced", cmod is not None)
check(
    "provider context_length was applied to its model",
    (cmod or {}).get("context_length") == 131072,
    str((cmod or {}).get("context_length")),
)
check(
    "provider capabilities were applied to its model",
    (cmod or {}).get("capabilities") == ["vision", "tools"],
    str((cmod or {}).get("capabilities")),
)

dst, _ = call("DELETE", f"/api/settings/providers/{PROV_KEY}")
check("delete returned 200", dst == 200, str(dst))
_, after8 = call("GET", "/api/settings/providers")
check(
    "ctx-verify-provider cleaned up",
    all(p.get("key") != PROV_KEY for p in (after8.get("providers") or [])),
    f"{PROV_KEY} survived cleanup",
)

print("cleanup")
call("DELETE", "/api/settings/models/openrouter/verify-added-model")
call("DELETE", "/api/settings/models/ollama/verify-cap-model")
call("DELETE", "/api/settings/providers/verify_provider")

# Restore the default we found, but ONLY if nothing else changed it meanwhile.
#
# History: this used to write ORIGINAL_DEFAULT back unconditionally. That
# silently reverted a default the owner had changed since the run started —
# observed twice on 2026-09-15, once reverting an NVIDIA default back to Grok
# that the owner had deliberately set. A checker must never overwrite a value a
# human changed while it was running.
#
# The guard is a compare-and-swap: read the current default, and only write the
# original back when the store still holds what THIS SCRIPT last set. If a third
# party moved it, we leave their value alone and say so.
_, _cur_res = call("GET", "/api/settings/default")
CURRENT_DEFAULT = _cur_res.get("default") or {}

_we_left = {"provider": DEFAULT_SET_BY_SCRIPT[0], "model": DEFAULT_SET_BY_SCRIPT[1]}
_someone_else_moved_it = bool(CURRENT_DEFAULT) and _we_left != CURRENT_DEFAULT

if not ORIGINAL_DEFAULT.get("provider") or not ORIGINAL_DEFAULT.get("model"):
    print("  (no default was set before this run — nothing to restore)")
elif _someone_else_moved_it:
    check(
        "default changed by someone else mid-run — left untouched",
        True,
        f"current={CURRENT_DEFAULT}, script had set={_we_left}",
    )
else:
    st, _ = call(
        "POST",
        "/api/settings/default",
        {
            "provider": ORIGINAL_DEFAULT["provider"],
            "model": ORIGINAL_DEFAULT["model"],
        },
    )
    check("original default restored", st == 200, str(st))
    _, after = call("GET", "/api/settings/default")
    check(
        "restored default reads back identically",
        (after.get("default") or {}) == ORIGINAL_DEFAULT,
        f"{after.get('default')} != {ORIGINAL_DEFAULT}",
    )

print(f"\n{passed} passed, {len(failed)} failed")
if failed:
    for f in failed:
        print(f"  FAILED: {f}")
    sys.exit(1)
print("ALL REPORTED BUGS VERIFIED FIXED")
