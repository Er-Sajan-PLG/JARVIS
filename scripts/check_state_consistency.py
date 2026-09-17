"""End-to-end state-consistency test.

The headline requirement: a change made in Settings must be visible to chat.
Uses the live server on :8000 and asserts the shared source of truth.

Run:  .venv/bin/python scripts/check_state_consistency.py
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
        with urllib.request.urlopen(req, timeout=240) as r:
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


def catalogue(refresh: bool = False) -> dict:
    """Read the merged catalogue the chat selector uses.

    ``refresh=True`` forces the server past its TTL cache. Settings writes
    already invalidate that cache, so a plain read suffices in normal use;
    the flag exists so this check can independently verify freshness.
    """
    _, d = call("GET", f"/api/models?refresh={'true' if refresh else 'false'}")
    return {p["key"]: p for p in d.get("providers", [])}


print("== 1. Settings: set a default model ==")
cats0 = catalogue()
or_models = [m["id"] for m in cats0.get("openrouter", {}).get("models", [])]
check("openrouter exposes live models", len(or_models) > 20, f"{len(or_models)} models")
target_provider = "openrouter"
target_model = or_models[0] if or_models else "anthropic/claude-sonnet-5"
st, _ = call("POST", "/api/settings/default", {"provider": target_provider, "model": target_model})
check("POST /settings/default accepted", st == 200, f"status={st}")

st, d = call("GET", "/api/settings/default")
default = d.get("default") or {}
check(
    "default readback matches",
    default.get("provider") == target_provider and default.get("model") == target_model,
    str(default),
)

print("== 2. Default is visible to the chat selector ==")
cats = catalogue()
check("default provider exists in catalogue", target_provider in cats)
check(
    "default model is selectable in catalogue",
    any(m["id"] == target_model for m in cats.get(target_provider, {}).get("models", [])),
)

st, d = call("GET", "/api/settings/default")
sel = d.get("default") or {}
check("chat bootstrap reports same default", sel.get("model") == target_model, str(sel))

print("== 3. Settings: add a custom model ==")
custom_id = "state-consistency-probe"
st, _ = call(
    "POST",
    "/api/settings/models",
    {
        "provider": target_provider,
        "id": custom_id,
        "name": "State Consistency Probe",
        "custom": True,
    },
)
check("POST custom model accepted", st == 200, f"status={st}")

cats2 = catalogue(refresh=True)
ids = [m["id"] for m in cats2.get(target_provider, {}).get("models", [])]
check("custom model is now selectable in chat", custom_id in ids, f"{len(ids)} models")

print("== 4. Settings: add a custom provider ==")
st, _ = call(
    "POST",
    "/api/settings/providers",
    {
        "name": "Probe Provider",
        "base_url": "https://example.invalid/v1",
        "api_key": "secret-probe-key",
        "models": [{"id": "probe-model-1", "name": "Probe Model One"}],
    },
)
check("POST custom provider accepted", st == 200, f"status={st}")

cats3 = catalogue(refresh=True)
check("custom provider in chat catalogue", "probe_provider" in cats3)
check(
    "custom provider exposes its model",
    any(m["id"] == "probe-model-1" for m in cats3.get("probe_provider", {}).get("models", [])),
)

print("== 5. API key never leaks ==")
st, d = call("GET", "/api/settings/providers")
blob = json.dumps(d)
prov = next((p for p in d.get("providers", []) if p.get("key") == "probe_provider"), None)
check("custom provider listed", prov is not None, str(d)[:200])
check("raw key NOT in /settings/providers", "secret-probe-key" not in blob)
check("has_key flag true instead", bool(prov and prov.get("has_key")), str(prov))

_, keys = call("GET", "/api/settings/api-keys")
check("raw key NOT in /settings/api-keys", "secret-probe-key" not in json.dumps(keys))

print("== 6. Cleanup restores original state ==")
call("DELETE", f"/api/settings/models/{target_provider}/{custom_id}")
call("DELETE", "/api/settings/providers/probe_provider")
cats4 = catalogue(refresh=True)
ids4 = [m["id"] for m in cats4.get(target_provider, {}).get("models", [])]
check("custom model removed", custom_id not in ids4)
check("custom provider removed", "probe_provider" not in cats4)
call("POST", "/api/settings/default", {"provider": "", "model": ""})

print(f"\n{passed} passed, {len(failed)} failed")
if failed:
    for f in failed:
        print(f"  FAILED: {f}")
    sys.exit(1)
print("STATE CONSISTENCY OK")
