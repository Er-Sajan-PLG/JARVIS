#!/usr/bin/env python3
"""JARVIS CI Bridge — a tiny localhost HTTP wrapper around execution scripts.

n8n v2 removed the "Execute Command" node, so n8n can no longer shell out to a
script directly. This bridge gives n8n a safe, HTTP-only way to trigger the
JARVIS local-CI execution plane:

    n8n (orchestration)  --HTTP-->  ci_bridge_server.py (execution plane)  -->  ci_bridge.py
                                                                       \\->  scheduled_doc_maintenance.py

It binds to 127.0.0.1 only and (optionally) requires a shared token
(env CI_BRIDGE_TOKEN), so it is not reachable from the network.

ENDPOINTS
--------
    GET  /health            -> {"status":"ok", ...}
    POST /run               -> runs scripts/ci_bridge.py, returns captured output
         body (JSON, all optional): {"limit": 1, "dryRun": true, "pr": null}
    POST /docs              -> runs scripts/scheduled_doc_maintenance.py
         body (JSON, all optional): {"checkOnly": true}
    GET  /last              -> last run result (handy for quick debugging)

USAGE
-----
    .venv/bin/python scripts/ci_bridge_server.py            # port 8770
    curl -s localhost:8770/health
    curl -s -X POST localhost:8770/run -H 'Content-Type: application/json' \
         -d '{"limit":1,"dryRun":true}'
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYTHON = str(REPO / ".venv" / "bin" / "python")
BRIDGE = str(REPO / "scripts" / "ci_bridge.py")
DOCS = str(REPO / "scripts" / "scheduled_doc_maintenance.py")

HOST = os.environ.get("CI_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CI_BRIDGE_PORT", "8770"))
TOKEN = os.environ.get("CI_BRIDGE_TOKEN", "").strip()
MAX_TIMEOUT = int(os.environ.get("CI_BRIDGE_TIMEOUT", "900"))  # seconds

LAST: dict = {}


def _build_cmd(body: dict) -> list[str]:
    """Map a JSON body to ci_bridge.py CLI arguments (whitelisted, no shell)."""
    cmd = [PYTHON, BRIDGE, "--once"]
    pr = body.get("pr")
    if pr is not None:
        cmd += ["--pr", str(int(pr))]
    limit = body.get("limit")
    if limit is not None:
        cmd += ["--limit", str(int(limit))]
    if bool(body.get("dryRun", False)):
        cmd += ["--dry-run"]
    return cmd


def run_bridge(body: dict) -> dict:
    global LAST
    cmd = _build_cmd(body)
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=MAX_TIMEOUT,
            shell=False,
        )
        result = {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "durationSec": round(time.time() - started, 1),
            "cmd": " ".join(cmd),
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "exitCode": 124,
            "durationSec": round(time.time() - started, 1),
            "cmd": " ".join(cmd),
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"timed out after {MAX_TIMEOUT}s",
        }
    LAST = result
    return result


def run_docs(body: dict) -> dict:
    global LAST
    cmd = [PYTHON, DOCS]
    if bool(body.get("checkOnly", False)):
        cmd += ["--check-only"]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=MAX_TIMEOUT,
            shell=False,
        )
        result = {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "durationSec": round(time.time() - started, 1),
            "cmd": " ".join(cmd),
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "exitCode": 124,
            "durationSec": round(time.time() - started, 1),
            "cmd": " ".join(cmd),
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"timed out after {MAX_TIMEOUT}s",
        }
    LAST = result
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisCIBridge/1.0"

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        return self.headers.get("X-Bridge-Token", "") == TOKEN

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/health":
            self._send(
                200,
                {
                    "status": "ok",
                    "service": "jarvis-ci-bridge",
                    "repo": str(REPO),
                    "authRequired": bool(TOKEN),
                },
            )
        elif path == "/last":
            self._send(200, LAST or {"info": "no runs yet"})
        else:
            self._send(404, {"error": "not found", "paths": ["/health", "/run", "/last", "/docs"]})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/run":
            if not self._authorized():
                self._send(401, {"error": "invalid or missing X-Bridge-Token"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid JSON body"})
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "body must be a JSON object"})
                return
            self._send(200, run_bridge(body))
        elif path == "/docs":
            if not self._authorized():
                self._send(401, {"error": "invalid or missing X-Bridge-Token"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid JSON body"})
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "body must be a JSON object"})
                return
            self._send(200, run_docs(body))
        else:
            self._send(404, {"error": "not found", "paths": ["/run", "/docs"]})

    def log_message(self, format: str, *args) -> None:  # keep logs quiet-ish, but useful
        sys.stderr.write("[ci-bridge] " + (format % args) + "\n")


def main() -> int:
    if not Path(PYTHON).exists():
        print(f"FATAL: python not found at {PYTHON}", file=sys.stderr)
        return 2
    if not Path(BRIDGE).exists() or not Path(DOCS).exists():
        print(f"FATAL: script not found at {BRIDGE} or {DOCS}", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"jarvis-ci-bridge listening on http://{HOST}:{PORT} "
        f"(auth={'token' if TOKEN else 'none'}, repo={REPO})",
        flush=True,
    )
    with contextlib.suppress(KeyboardInterrupt):
        srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
