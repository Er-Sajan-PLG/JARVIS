"""Helpers for detecting and auto-starting the local model servers JARVIS needs.

JARVIS talks to two kinds of local servers:

* **llama.cpp** OpenAI-compatible servers (one per local model, e.g. port 8080
  for the main chat model, 8082 for autocomplete). These are launched by JARVIS
  itself via ``llama-server`` if they are not already running.
* **Ollama** (port 11434 by default) which serves embeddings AND chat models.
  Ollama is an external program JARVIS cannot launch, so we only *detect* it and
  warn if it is missing. As a convenience, when a configured llama.cpp model has
  no server and no binary to launch it, we try to remap it to an equivalently
  named Ollama model that *is* available.

All auto-start is best-effort and **non-fatal**: if a server cannot be started
JARVIS logs a warning and continues, so cloud/API models still work.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import urllib.parse

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


def is_port_open(port: int, host: str = "localhost") -> bool:
    """Check if a TCP port is already listening on ``host``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def port_from_url(url: str) -> int:
    """Extract the port number from a base_url like ``http://localhost:8080/v1``."""
    parsed = urllib.parse.urlparse(url)
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def is_local_url(url: str) -> bool:
    """True if ``url`` points at this machine (localhost / 127.0.0.1)."""
    host = urllib.parse.urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "")


def find_llama_server_binary() -> str | None:
    """Locate the ``llama-server`` binary.

    Resolution order:
    1. ``$LLAMA_SERVER_PATH`` environment variable (explicit override).
    2. ``llama-server`` / ``llama-server.exe`` on ``$PATH``.
    3. ``./llama-server`` in the project root.
    """
    override = os.environ.get("LLAMA_SERVER_PATH")
    if override:
        return override

    found = shutil.which("llama-server")
    if found:
        return found

    local = os.path.join(os.getcwd(), "llama-server")
    if os.path.exists(local):
        return local

    return None


def ollama_model_names(url: str) -> list[str]:
    """Return the list of model names Ollama has pulled (empty list if down)."""
    try:
        resp = requests.get(f"{url.rstrip('/')}/api/tags", timeout=3)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def match_ollama_model(llamacpp_name: str, available: list[str]) -> str | None:
    """Find an Ollama model that corresponds to a llama.cpp model filename.

    ``qwen3-8b.gguf`` -> ``qwen3:8b`` (strip ``.gguf``, map ``-8b`` -> ``:8b``).
    Returns the Ollama model name or ``None`` if nothing matches.
    """
    base = llamacpp_name.lower().removesuffix(".gguf")
    # Build candidate forms: "qwen3-8b" -> "qwen3:8b"
    candidates = {base, base.replace("-", ":")}
    for name in available:
        low = name.lower()
        if low in candidates or base in low:
            return name
    return None


def ensure_server_running(
    port: int,
    command: list[str],
    name: str = "LLM",
    host: str = "localhost",
    timeout: int = 30,
) -> bool:
    """Ensure a server is listening on ``(host, port)``.

    If the port is already open, return immediately. Otherwise start
    ``command`` in the background and wait up to ``timeout`` seconds for the
    port to open.

    Returns ``True`` if the server is reachable (already was or was started),
    ``False`` if it could not be started in time. Never raises and never
    calls ``sys.exit`` — the caller decides how to react.
    """
    if is_port_open(port, host):
        print(f"✅ {name} already running on port {port}")
        return True

    binary = command[0] if command else "<command>"
    if shutil.which(binary) is None and not os.path.exists(binary):
        print(f"⚠️  {name}: server binary '{binary}' not found — cannot auto-start.")
        print("    Install llama.cpp or set $LLAMA_SERVER_PATH and retry.")
        return False

    print(f"⏳ {name} not found on port {port}. Starting in background...")
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError) as e:
        print(f"⚠️  {name}: failed to launch ({e}).")
        return False

    for i in range(timeout):
        time.sleep(1)
        if is_port_open(port, host):
            print(f"✅ {name} started successfully on port {port}")
            return True
        print(f"   Waiting for {name} to boot... ({i + 1}s)")

    print(f"❌ {name} did not come up on port {port} within {timeout}s.")
    return False


def llamacpp_live_models(settings) -> list[dict]:
    """Return local llama.cpp models whose server port is actually listening.

    Unlike Ollama (which exposes a tag list) llama.cpp has no discovery
    endpoint, so we treat a model as "available" only when its configured
    ``base_url`` points at this machine *and* the port is open. Each entry is
    ``{"key", "name", "base_url"}`` so the startup selector can offer the user a
    concrete, currently-runnable local model instead of a hardcoded profile.

    Returns an empty list when no local llama.cpp server is up.
    """
    live = []
    seen_ports: set[int] = set()
    for key, cfg in settings.models.items():
        if cfg.backend != "llamacpp":
            continue
        if not is_local_url(cfg.base_url):
            continue  # remote endpoint (OpenRouter/xAI) — not a local server
        port = port_from_url(cfg.base_url)
        if port in seen_ports:
            continue  # already represented by another model on the same port
        seen_ports.add(port)
        if is_port_open(port):
            live.append(
                {
                    "key": key,
                    "name": cfg.name,
                    "base_url": cfg.base_url,
                }
            )
    return live


def warn_if_missing(url: str, name: str) -> bool:
    """Detect an external server (e.g. Ollama) and warn if it is unreachable.

    Returns ``True`` if reachable, ``False`` if missing. JARVIS cannot launch
    external servers, so this only reports status.
    """
    host = urllib.parse.urlparse(url).hostname or "localhost"
    port = port_from_url(url)
    if is_port_open(port, host):
        print(f"✅ {name} reachable at {url}")
        return True
    print(f"⚠️  {name} NOT reachable at {url}.")
    print("    Start it manually (e.g. `ollama serve`) before using features " "that depend on it.")
    return False
