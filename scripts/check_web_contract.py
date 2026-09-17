"""Contract test: does the live web API return exactly the shapes the
frontend modules read? Run against a live server on :8000."""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://localhost:8000"
fails: list[str] = []
ok: list[str] = []


def get(path: str, timeout: int = 120):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def post(path: str, body: dict, timeout: int = 120):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def delete(path: str, timeout: int = 60):
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def check(name: str, cond: bool, detail: str = "") -> None:
    (ok if cond else fails).append(f"{name}{f' — {detail}' if detail and not cond else ''}")


# ── /api/models ──────────────────────────────────────────────────────────────
d = get("/api/models")
check("models.providers is list", isinstance(d.get("providers"), list))
provs = d["providers"]
check("models.providers non-empty", len(provs) > 0, f"got {len(provs)}")

PROV_FIELDS = {"key", "name", "status", "has_key", "model_count", "models"}
for p in provs:
    missing = PROV_FIELDS - set(p)
    check(f"provider {p.get('key')} has fields", not missing, f"missing {missing}")
    check(
        f"provider {p.get('key')} model_count matches models",
        p.get("model_count") == len(p.get("models", [])),
        f"{p.get('model_count')} vs {len(p.get('models', []))}",
    )

avail = [p for p in provs if p["status"] == "available"]
check("at least 5 providers available", len(avail) >= 5, f"got {len(avail)}")

total_models = sum(p["model_count"] for p in provs)
check("catalogue has >100 models", total_models > 100, f"got {total_models}")

# AGY must surface as a provider
check("agy provider present", any(p["key"] == "agy" for p in provs))

# No fabricated single-model providers: available providers with a key must
# either carry real models or report an error state.
for p in provs:
    if p["status"] == "available" and p["model_count"] == 0 and not p.get("is_custom"):
        check(f"available provider {p['key']} carries models", False, "0 models while available")

# ── /api/settings/default ────────────────────────────────────────────────────
d = get("/api/settings/default")
check("default has provider+model keys", {"provider", "model"} <= set(d.get("default", {})))

# ── /api/settings/api-keys ───────────────────────────────────────────────────
d = get("/api/settings/api-keys")
keys = d.get("keys", {})
check("api-keys returns dict", isinstance(keys, dict) and len(keys) > 0)
first = next(iter(keys.values()))
check("api-key entry has configured+source", {"configured", "source"} <= set(first))
# SECURITY: no raw secret values may cross the wire.
blob = json.dumps(d)
check("api-keys leaks no key values", "sk-" not in blob and "key_value" not in blob)

# ── custom provider + model round trip ───────────────────────────────────────
cp = post(
    "/api/settings/providers",
    {
        "name": "ContractTest",
        "base_url": "https://example.invalid/v1",
        "api_key": "sk-contract-test-should-never-echo",
        "models": [{"id": "test-model", "name": "Test Model"}],
    },
)
check("custom provider created", cp.get("success") is True)
check("custom provider key derived", cp.get("provider", {}).get("key") == "contracttest")

listed = get("/api/settings/providers")
found = [p for p in listed["providers"] if p["key"] == "contracttest"]
check("custom provider listed", len(found) == 1)
if found:
    check("custom provider hides api_key", "api_key" not in found[0], f"keys={list(found[0])}")
    check("custom provider reports has_key", found[0].get("has_key") is True)

# It must also appear in the catalogue, with its models.
cat = get("/api/models")
ct = [p for p in cat["providers"] if p["key"] == "contracttest"]
check("custom provider in catalogue", len(ct) == 1)
if ct:
    check("custom provider is flagged custom", ct[0].get("is_custom") is True)
    check("custom provider carries its model", ct[0]["model_count"] == 1)

# Add a custom model onto a COMMON provider; it must show up right away.
cm = post(
    "/api/settings/models",
    {
        "provider": "openrouter",
        "id": "contract/test-model",
        "name": "Contract Test Model",
        "context_length": 4096,
    },
)
check("custom model created", cm.get("success") is True)

cat2 = get("/api/models")
or_prov = next((p for p in cat2["providers"] if p["key"] == "openrouter"), None)
check("openrouter present after add", or_prov is not None)
if or_prov:
    check(
        "custom model appears in common provider",
        any(m["id"] == "contract/test-model" for m in or_prov["models"]),
    )

# Hide it, then confirm it disappears.
hid = post("/api/settings/models/hide", {"provider": "openrouter", "id": "contract/test-model"})
check("hide toggles on", hid.get("hidden") is True)
cat3 = get("/api/models")
or_prov3 = next((p for p in cat3["providers"] if p["key"] == "openrouter"), None)
if or_prov3:
    check(
        "hidden model removed from catalogue",
        not any(m["id"] == "contract/test-model" for m in or_prov3["models"]),
    )
post("/api/settings/models/hide", {"provider": "openrouter", "id": "contract/test-model"})

# Cleanup
check(
    "custom model deleted",
    delete("/api/settings/models/openrouter/contract%2Ftest-model").get("success") is True,
)
check(
    "custom provider deleted", delete("/api/settings/providers/contracttest").get("success") is True
)
check(
    "custom provider gone from catalogue",
    not any(p["key"] == "contracttest" for p in get("/api/models")["providers"]),
)

# ── /api/files ───────────────────────────────────────────────────────────────
d = get("/api/files")
check("files has files+total", {"files", "total"} <= set(d))
check("files.total matches list", d["total"] == len(d["files"]))
if d["files"]:
    f = d["files"][0]
    check("file record fields", {"id", "filename", "size", "kind", "modified"} <= set(f))
    det = get(f"/api/files/{f['id']}")
    check("file detail has preview key", "preview" in det)

# ── /api/memory ──────────────────────────────────────────────────────────────
d = get("/api/memory")
check("memory has memories+total", {"memories", "total"} <= set(d))
if d["memories"]:
    m = d["memories"][0]
    check("memory record fields", {"id", "value", "category"} <= set(m))

# ── /health ──────────────────────────────────────────────────────────────────
check("health ok", get("/health").get("status") == "healthy")

# ── Report ───────────────────────────────────────────────────────────────────
print(f"PASSED {len(ok)}")
for line in ok:
    print(f"  ✓ {line}")
if fails:
    print(f"\nFAILED {len(fails)}")
    for line in fails:
        print(f"  ✗ {line}")
    sys.exit(1)
print("\nAll contract checks passed.")
