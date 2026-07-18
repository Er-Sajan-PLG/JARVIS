"""
Startup model selector for JARVIS.

Presents the user with a backend picker (Ollama / llama.cpp / Google / Grok /
OpenRouter) and the concrete models each can serve, then applies the choice to
the :class:`~app.models.switcher.ModelSwitcher` before the chat loop begins.

Kept separate from ``app/main.py`` so the orchestration file stays focused on
the conversation pipeline.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from app.utils.server_manager import ollama_model_names, llamacpp_live_models


def _categorize_cloud_models(settings) -> dict:
    """
    Group cloud model KEYS by provider.

    Providers are inferred from `base_url` host for OpenAI-compatible backends
    (grok, openrouter, ...). Backends whose endpoint isn't encoded in `base_url`
    — e.g. `google` (Gemini uses a fixed REST endpoint) — are grouped by their
    `backend` field instead via `backend_map`.
    """
    host_map = {
        "api.x.ai": "grok",
        "openrouter.ai": "openrouter",
        "generativelanguage.googleapis.com": "google",
    }
    backend_map = {
        "google": "google",
    }
    groups = {}
    for key, cfg in settings.models.items():
        if "localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url:
            # Some cloud backends (e.g. google) don't encode their host in base_url.
            provider = backend_map.get(cfg.backend)
            if provider:
                groups.setdefault(provider, []).append(key)
            continue
        host = urlparse(cfg.base_url).netloc
        provider = host_map.get(host, host)
        groups.setdefault(provider, []).append(key)
    return groups


def _build_ollama_router(switcher, model_name: str, base_url: str) -> bool:
    """Build an ad-hoc single-model router backed by a live Ollama model.

    Unlike the predefined profiles, Ollama models pulled at runtime aren't
    keys in ``settings.models``. This constructs an :class:`OllamaClient`
    directly and registers it for every role so ``route()`` resolves to it.
    Returns True on success, False if the client could not be created.
    """
    from app.models.ollama_client import OllamaClient
    from app.models.router import ModelRouter, TaskType

    try:
        client = OllamaClient(model=model_name, base_url=base_url, role="general")
    except Exception as e:  # pragma: no cover - depends on environment
        print(f"  ⚠️ Could not create Ollama client for '{model_name}': {e}")
        return False

    router = ModelRouter()
    for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
        try:
            router.register(TaskType(role), client)
        except ValueError:
            pass
    router.set_default(client)
    key = f"ollama:{model_name}"
    switcher._routers[key] = router  # type: ignore[attr-defined]
    switcher._active_profile = key  # type: ignore[attr-defined]
    return True


def _startup_model_select(switcher, settings) -> None:
    """Run the model-selection menu at JARVIS startup.

    Presents three backend groups and the concrete models each can serve:

      [1] Ollama       — live pulled models (local, no API key)
      [2] llama.cpp    — local profiles / servers on this machine
      [3] Google       — free Gemini API (needs GOOGLE_API_KEY)
      [4] Grok         — free XAI API  (needs XAI_API_KEY)
      [5] OpenRouter   — free Llama 70B (needs OPENROUTER_API_KEY)

    Selecting a backend lists its models with a live status (running / key
    present / missing) and applies the choice to the switcher. If the user
    just presses Enter, the already-active profile is kept.
    """
    def _free_key(var: str) -> bool:
        return bool(os.environ.get(var, ""))

    def _ollama_url() -> str:
        return settings.paths.ollama_url

    # ----- Build the backend menu -----
    print("\n" + "═" * 54)
    print("         JARVIS — Select your model backend")
    print("═" * 54)

    ollama_models = ollama_model_names(_ollama_url())
    local_models = llamacpp_live_models(settings)
    cloud = _categorize_cloud_models(settings)

    # Entry index -> resolver
    entries: list[dict] = []

    # [1] Ollama
    ollama_status = f"{len(ollama_models)} model(s) pulled" if ollama_models else "not reachable"
    entries.append({
        "label": "Ollama (local, free)",
        "detail": ollama_status,
        "kind": "ollama",
    })

    # [2] llama.cpp (live local servers)
    if local_models:
        names = ", ".join(m["name"] for m in local_models)
        entries.append({
            "label": "llama.cpp (local server)",
            "detail": f"running: {names}",
            "kind": "local",
        })

    # [3..] Free cloud APIs
    free_apis = [
        ("Google", "google", "GOOGLE_API_KEY", "gemini-2.0-flash (free tier)"),
        ("Grok", "grok", "XAI_API_KEY", "grok-3-beta (free tier)"),
        ("OpenRouter", "openrouter", "OPENROUTER_API_KEY", "llama-3.3-70b:free"),
    ]
    for pretty, provider, env_var, model_desc in free_apis:
        keys = cloud.get(provider, [])
        if not keys:
            continue  # nothing configured for this provider
        has_key = _free_key(env_var)
        entries.append({
            "label": f"{pretty} (free API)",
            "detail": f"{model_desc} — {'✓ key set' if has_key else '✗ ' + env_var + ' missing'}",
            "kind": "cloud",
            "provider": provider,
            "env_var": env_var,
            "has_key": has_key,
        })

    # [6] OpenRouter — live "all models" catalog (pick ANY model, no config needed)
    if _free_key("OPENROUTER_API_KEY"):
        from app.utils.openrouter_catalog import fetch_openrouter_models
        catalog = fetch_openrouter_models()
        if catalog:
            entries.append({
                "label": "OpenRouter (ALL models, live)",
                "detail": f"{len(catalog)} models available — browse & pick any",
                "kind": "openrouter-catalog",
            })

    if not entries:
        print("  No backends/models configured. Using default profile.\n")
        return

    for i, e in enumerate(entries, 1):
        marker = "●" if (
            e["kind"] == "local"
            and (settings.active_profile == "local"
                 or settings.active_profile.startswith("model:"))
        ) else " "
        print(f"  {i}. {marker} {e['label']}")
        print(f"       ↳ {e['detail']}")

    print("  [Enter] keep current ('%s')" % settings.active_profile)
    choice = input("Backend (number, or Enter to skip): ").strip()
    if not choice:
        print(f"  Keeping '{settings.active_profile}'.\n")
        return
    try:
        entry = entries[int(choice) - 1]
    except (ValueError, IndexError):
        print("  Invalid selection — keeping current profile.\n")
        return

    # ----- Resolve the chosen backend -----
    if entry["kind"] == "ollama":
        if not ollama_models:
            print("  ⚠️ Ollama is not reachable. Start `ollama serve` first.\n")
            return
        print("\n  Ollama models available:")
        for i, m in enumerate(ollama_models, 1):
            print(f"    {i}. {m}")
        sel = input(f"  Select model (1-{len(ollama_models)}): ").strip()
        try:
            model_name = ollama_models[int(sel) - 1]
        except (ValueError, IndexError):
            print("  Invalid selection — keeping current profile.\n")
            return
        if _build_ollama_router(switcher, model_name, _ollama_url()):
            print(f"  ✅ Using Ollama model: {model_name}\n")
        return

    if entry["kind"] == "local":
        pool = local_models
        print("\n  Running local llama.cpp models:")
        for i, m in enumerate(pool, 1):
            marker = "●" if settings.active_profile == f"model:{m['key']}" else " "
            print(f"    {i}. {marker} {m['name']}  [{m['key']}]")
        sel = input(f"  Select model (1-{len(pool)}): ").strip()
        try:
            chosen = pool[int(sel) - 1]
        except (ValueError, IndexError):
            print("  Invalid selection — keeping current profile.\n")
            return
        if switcher.switch_to_model(chosen["key"]):
            print(f"  ✅ Using local model: {chosen['name']}\n")
        else:
            print(f"  ⚠️ Model '{chosen['name']}' is not loaded (server down?).\n")
        return

    if entry["kind"] == "cloud":
        provider = entry["provider"]
        if not entry["has_key"]:
            print(f"  ⚠️ {entry['env_var']} is not set in your .env file.")
            print(f"     Get a free key and add it, then restart JARVIS.\n")
            return
        keys = cloud[provider]
        print(f"\n  {provider} models available:")
        for i, m in enumerate(keys, 1):
            client = switcher.get_client(m)
            status = "✓ loaded" if client else "✗ not loaded"
            print(f"    {i}. {settings.models[m].name}  [{m}]  {status}")
        sel = input(f"  Select model (1-{len(keys)}): ").strip()
        try:
            model_key = keys[int(sel) - 1]
        except (ValueError, IndexError):
            print("  Invalid selection — keeping current profile.\n")
            return
        if switcher.switch_to_model(model_key):
            print(f"  ✅ Using {provider} model: {settings.models[model_key].name}\n")
        else:
            print("  ⚠️ Model not loaded — check its API key in .env.\n")
        return

    if entry["kind"] == "openrouter-catalog":
        from app.utils.openrouter_catalog import fetch_openrouter_models
        catalog = fetch_openrouter_models()
        if not catalog:
            print("  ⚠️ Could not fetch the OpenRouter catalog (network down?).\n")
            return
        print(f"\n  OpenRouter — {len(catalog)} models (type to filter, or pick by number):")
        # Show a curated page sorted by context length (flagship models first).
        page = sorted(catalog, key=lambda m: (m["context_length"], m["id"]), reverse=True)[:40]
        for i, m in enumerate(page, 1):
            ctx = f" · {m['context_length']//1000}k ctx" if m["context_length"] else ""
            print(f"    {i:2}. {m['id']}{ctx}")
        sel = input(f"  Select model (1-{len(page)}), or type a full model id: ").strip()
        model_id = sel
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(page):
                model_id = page[idx]["id"]
        except ValueError:
            pass  # treat as a literal model id
        if switcher.switch_to_dynamic_model("openrouter", model_id, "OPENROUTER_API_KEY"):
            print(f"  ✅ Using OpenRouter model: {model_id}\n")
        else:
            print("  ⚠️ Could not load that model — check your key in .env.\n")
        return
