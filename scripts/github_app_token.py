"""Mint short-lived GitHub App installation tokens (ADR-012).

A GitHub App authenticates as itself, not as a person:

  1. sign a short JWT (RS256) with the App's private key, `iss` = the App id
  2. exchange that JWT for an **installation access token** (a `ghs_...` value)
  3. use the installation token as the bearer token for the REST API

Installation tokens expire after **one hour**, so they are minted on demand and
cached on disk until they are nearly expired. Nothing long-lived is ever written
down except the App's private key, which never leaves this machine.

Why this exists (ADR-012): a personal access token is tied to a human, is
long-lived, and is capped at 50 per user. An App is tied to the repository, uses
1-hour tokens, and shows up in the audit log as the App rather than a person.

Usage
-----
    scripts/github_app_token.py --check          # is the App wired up?
    scripts/github_app_token.py --print-token    # DANGER: only for a one-off curl
    scripts/github_app_token.py --installation-id

The module is importable so `ci_bridge.py` can call `get_installation_token()`
without shelling out. That function returns `(token, source)` and returns an
empty token when the App is not configured, which is how the bridge keeps
working on a PAT until the App is in place.

Configuration (in `.ci-bridge.env`, which is a systemd EnvironmentFile):

    JARVIS_APP_ID=<numeric app id>
    JARVIS_APP_PRIVATE_KEY_PATH=/home/sajan/.jarvis/jarvis-ci-app.pem
    JARVIS_APP_INSTALLATION_ID=<numeric installation id>   # optional; discovered

Never put the private key *contents* in an environment variable — point at the
file, keep it mode 0600, and keep it outside the repository.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"

# Mint a new token when fewer than this many seconds remain. Five minutes is
# comfortably longer than any single gate run, and short enough that the cache
# is still used across a 30-minute schedule.
_RENEW_BEFORE_SECONDS = 300

# The JWT is the intermediate credential. GitHub rejects anything older than 10
# minutes or with an `exp` more than 10 minutes out; 9 is the documented ceiling.
_JWT_LIFETIME_SECONDS = 540

DEFAULT_CACHE = Path.home() / ".jarvis" / "app-token-cache.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def app_configured() -> bool:
    """True when enough config exists to attempt minting an App token."""
    return bool(_env("JARVIS_APP_ID") and _env("JARVIS_APP_PRIVATE_KEY_PATH"))


def _app_id() -> str:
    app_id = _env("JARVIS_APP_ID")
    if not app_id.isdigit():
        raise RuntimeError("JARVIS_APP_ID is missing or not numeric. Set it in .ci-bridge.env.")
    return app_id


def _key_path() -> Path:
    raw = _env("JARVIS_APP_PRIVATE_KEY_PATH")
    if not raw:
        raise RuntimeError("JARVIS_APP_PRIVATE_KEY_PATH is not set in .ci-bridge.env.")
    path = Path(raw).expanduser()
    if not path.is_file():
        raise RuntimeError(f"App private key not found at {path}")
    return path


def check_key_permissions(path: Path) -> str | None:
    """Return a warning if the private key is readable by anyone but its owner."""
    mode = path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        return f"{path} is group/world readable (mode {oct(mode)[-3:]}); chmod 600 it"
    return None


# ---------------------------------------------------------------------------
# JWT (RS256)
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_jwt(app_id: str, private_key_pem: bytes, now: int | None = None) -> str:
    """Build the signed RS256 JWT GitHub wants for App authentication.

    `iat` is backdated 60s because GitHub rejects a token whose `iat` is in the
    future, and clock drift between this machine and GitHub's API is real.
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    issued = (now if now is not None else int(time.time())) - 60
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iat": issued,
        "exp": issued + 60 + _JWT_LIFETIME_SECONDS,
        "iss": app_id,
    }

    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    ).encode("ascii")

    loaded = serialization.load_pem_private_key(private_key_pem, password=None)
    # GitHub Apps use an RSA key. Narrow the union explicitly so the RS256
    # signing call is type-safe and a wrong key type fails loudly here rather
    # than as an opaque 401 from the token exchange.
    if not isinstance(loaded, rsa.RSAPrivateKey):
        raise RuntimeError(
            f"the App private key must be RSA (for RS256), got {type(loaded).__name__}"
        )
    signature = loaded.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode('ascii')}.{_b64url(signature)}"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _request(method: str, path: str, token: str, payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        path if path.startswith("http") else f"{API}{path}",
        data=body,
        method=method,
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "jarvis-app-auth")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"message": raw[:300]}


def find_installation_id(jwt: str) -> int:
    """Ask GitHub which installation of this App we should be using."""
    status, body = _request("GET", "/app/installations", jwt)
    if status != 200 or not isinstance(body, list):
        raise RuntimeError(f"cannot list App installations (HTTP {status}): {body}")
    if not body:
        raise RuntimeError(
            "the App is not installed on any repository yet — install it, then retry"
        )
    if len(body) > 1:
        ids = [i.get("id") for i in body]
        raise RuntimeError(
            f"the App has {len(body)} installations {ids}; set "
            "JARVIS_APP_INSTALLATION_ID explicitly instead of guessing"
        )
    return int(body[0]["id"])


def mint_installation_token(app_id: str, key_path: Path, installation_id: int) -> dict:
    """Exchange a fresh JWT for an installation access token. Returns the raw body."""
    jwt = build_jwt(app_id, key_path.read_bytes())
    status, body = _request("POST", f"/app/installations/{installation_id}/access_tokens", jwt)
    if status not in (200, 201) or "token" not in body:
        raise RuntimeError(f"token exchange failed (HTTP {status}): {body}")
    return body


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _read_cache(path: Path, installation_id: int) -> str:
    if not path.is_file():
        return ""
    try:
        cached = json.loads(path.read_text())
    except Exception:
        return ""
    if cached.get("installation_id") != installation_id:
        return ""
    expires_at = float(cached.get("expires_at_epoch") or 0)
    if expires_at - time.time() < _RENEW_BEFORE_SECONDS:
        return ""
    return str(cached.get("token") or "")


def _write_cache(path: Path, installation_id: int, body: dict) -> None:
    """Persist the token 0600 so it is not world readable between runs."""
    from datetime import datetime

    raw = body.get("expires_at") or ""
    try:
        expires = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=__import__("datetime").timezone.utc
        )
    except Exception:
        expires = None
    epoch = expires.timestamp() if expires else time.time() + 3600

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "installation_id": installation_id,
                "expires_at": raw,
                "expires_at_epoch": epoch,
                "token": body["token"],
                "permissions": body.get("permissions", {}),
            },
            indent=2,
        )
    )
    tmp.chmod(0o600)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Public entry point used by ci_bridge.py
# ---------------------------------------------------------------------------


def get_installation_token(
    cache_path: Path | None = None, *, force_refresh: bool = False
) -> tuple[str, str]:
    """Return `(token, source)`. Empty token means "App not configured".

    Deliberately swallows nothing: if the App *is* configured but broken, the
    caller should hear about it rather than silently falling back to a PAT —
    a silent fallback is how a permission regression hides for weeks.
    """
    if not app_configured():
        return "", ""

    app_id = _app_id()
    key_path = _key_path()
    cache = cache_path or DEFAULT_CACHE

    installation_id = _env("JARVIS_APP_INSTALLATION_ID")
    jwt = build_jwt(app_id, key_path.read_bytes())
    installation = int(installation_id) if installation_id.isdigit() else find_installation_id(jwt)

    if not force_refresh:
        cached = _read_cache(cache, installation)
        if cached:
            return cached, f"github-app:{app_id} (cached)"

    body = mint_installation_token(app_id, key_path, installation)
    _write_cache(cache, installation, body)
    return body["token"], f"github-app:{app_id} (installation {installation})"


def main() -> int:
    first_line = (__doc__ or "Mint GitHub App installation tokens").splitlines()[0]
    parser = argparse.ArgumentParser(description=first_line)
    parser.add_argument("--check", action="store_true", help="report config + validity")
    parser.add_argument("--installation-id", action="store_true")
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="print the token (only for a manual one-off curl; it is a secret)",
    )
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    if not app_configured():
        print("App not configured.")
        print("  set JARVIS_APP_ID and JARVIS_APP_PRIVATE_KEY_PATH in .ci-bridge.env")
        print("  the bridge keeps using the PAT until then")
        return 1

    app_id = _app_id()
    key_path = _key_path()
    print(f"app id     : {app_id}")
    print(f"private key: {key_path}")
    warning = check_key_permissions(key_path)
    print(f"key mode   : {'WARN - ' + warning if warning else 'ok (0600-ish)'}")

    if args.installation_id:
        jwt = build_jwt(app_id, key_path.read_bytes())
        print(f"installation: {find_installation_id(jwt)}")
        return 0

    token, source = get_installation_token(force_refresh=args.force_refresh)
    print(f"source     : {source}")

    status, body = _request("GET", "/installation/repositories", token)
    if status == 200 and isinstance(body, dict):
        repos = [str(entry.get("full_name")) for entry in body.get("repositories", [])]
        print(f"repos      : {', '.join(repos) or '(none)'}")
    else:
        print(f"token check: HTTP {status} {body}")
        return 1

    if args.print_token:
        print(f"token      : {token}")
    else:
        print(f"token      : masked={token[:12]}...{token[-4:]} (len {len(token)})")
    if not args.check:
        print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
