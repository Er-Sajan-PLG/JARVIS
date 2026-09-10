"""Contract tests for scripts/github_app_token.py (ADR-012).

These prove the parts that can be proven without a GitHub App: RS256 JWT
construction, the RSA-key type guard, the cache expiry logic, and — most
importantly — that an unconfigured App yields an EMPTY token so the PAT path in
ci_bridge.load_token() keeps working during the migration.

What is deliberately NOT tested here: the actual token exchange. That needs a
real App id and private key, and is verified live by
`scripts/github_app_token.py --check`.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "github_app_token.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("github_app_token", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["github_app_token"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gat():
    return _load_module()


@pytest.fixture(scope="module")
def rsa_pem() -> bytes:
    """A throwaway 2048-bit RSA key. Never leaves this test."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


class TestBuildJwt:
    def test_header_and_payload_are_rs256_and_correct_issuer(self, gat, rsa_pem):
        token = gat.build_jwt("123456", rsa_pem, now=1_700_000_000)
        header_seg, payload_seg, _ = token.split(".")

        header = json.loads(_b64url_decode(header_seg))
        payload = json.loads(_b64url_decode(payload_seg))

        assert header == {"alg": "RS256", "typ": "JWT"}
        assert payload["iss"] == "123456"

    def test_iat_is_backdated_to_tolerate_clock_drift(self, gat, rsa_pem):
        """GitHub rejects a JWT whose iat is in the future, so iat must lag."""
        now = 1_700_000_000
        token = gat.build_jwt("1", rsa_pem, now=now)
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["iat"] == now - 60
        assert payload["iat"] < now

    def test_exp_is_within_githubs_ten_minute_ceiling(self, gat, rsa_pem):
        now = 1_700_000_000
        token = gat.build_jwt("1", rsa_pem, now=now)
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        # exp is measured from the backdated iat; total must stay <= 600s of now
        assert payload["exp"] - payload["iat"] <= 600

    def test_signature_verifies_against_the_public_key(self, gat, rsa_pem):
        """The whole point of the JWT: GitHub must be able to verify it."""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        token = gat.build_jwt("42", rsa_pem, now=1_700_000_000)
        header_seg, payload_seg, signature_seg = token.split(".")
        signing_input = f"{header_seg}.{payload_seg}".encode("ascii")

        public_key = serialization.load_pem_private_key(rsa_pem, password=None).public_key()
        # Raises InvalidSignature if the signing path is wrong.
        public_key.verify(
            _b64url_decode(signature_seg),
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_a_non_rsa_key_is_rejected_loudly(self, gat):
        """A wrong key type must fail here, not as an opaque 401 from GitHub."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        ed_pem = ed25519.Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with pytest.raises(RuntimeError, match="must be RSA"):
            gat.build_jwt("1", ed_pem, now=1_700_000_000)


class TestCacheExpiry:
    """The cache is what keeps the 30-minute schedule to one mint per hour."""

    @staticmethod
    def _body(seconds_from_now: float) -> dict:
        stamp = time.gmtime(time.time() + seconds_from_now)
        return {
            "token": "ghs_synthetic_test_value_not_a_real_token",
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", stamp),
            "permissions": {"statuses": "write"},
        }

    def test_a_fresh_token_is_reused(self, gat, tmp_path):
        cache = tmp_path / "cache.json"
        gat._write_cache(cache, 99, self._body(3600))
        assert gat._read_cache(cache, 99) == self._body(3600)["token"]

    def test_a_nearly_expired_token_is_not_reused(self, gat, tmp_path):
        cache = tmp_path / "cache.json"
        gat._write_cache(cache, 99, self._body(60))  # inside the 300s margin
        assert gat._read_cache(cache, 99) == ""

    def test_a_token_for_a_different_installation_is_ignored(self, gat, tmp_path):
        cache = tmp_path / "cache.json"
        gat._write_cache(cache, 111, self._body(3600))
        assert gat._read_cache(cache, 222) == ""

    def test_a_missing_cache_file_is_not_an_error(self, gat, tmp_path):
        assert gat._read_cache(tmp_path / "absent.json", 1) == ""

    def test_a_corrupt_cache_file_is_not_an_error(self, gat, tmp_path):
        cache = tmp_path / "cache.json"
        cache.write_text("{ this is not json")
        assert gat._read_cache(cache, 1) == ""

    def test_the_cache_is_written_owner_only(self, gat, tmp_path):
        cache = tmp_path / "cache.json"
        gat._write_cache(cache, 1, self._body(3600))
        assert cache.stat().st_mode & 0o077 == 0


class TestKeyPermissionWarning:
    def test_a_world_readable_key_produces_a_warning(self, gat, tmp_path):
        key = tmp_path / "app.pem"
        key.write_text("not a real key")
        key.chmod(0o644)
        assert gat.check_key_permissions(key) is not None

    def test_a_0600_key_produces_no_warning(self, gat, tmp_path):
        key = tmp_path / "app.pem"
        key.write_text("not a real key")
        key.chmod(0o600)
        assert gat.check_key_permissions(key) is None


class TestMigrationSafety:
    """The behaviour that lets this land without breaking the working PAT."""

    def test_unconfigured_app_yields_an_empty_token(self, gat, monkeypatch):
        monkeypatch.delenv("JARVIS_APP_ID", raising=False)
        monkeypatch.delenv("JARVIS_APP_PRIVATE_KEY_PATH", raising=False)
        assert gat.app_configured() is False
        assert gat.get_installation_token() == ("", "")

    def test_a_non_numeric_app_id_is_rejected(self, gat, monkeypatch):
        monkeypatch.setenv("JARVIS_APP_ID", "not-a-number")
        monkeypatch.setenv("JARVIS_APP_PRIVATE_KEY_PATH", "/tmp/whatever.pem")
        assert gat.app_configured() is True
        with pytest.raises(RuntimeError, match="not numeric"):
            gat.get_installation_token()

    def test_a_missing_key_file_is_rejected(self, gat, monkeypatch, tmp_path):
        monkeypatch.setenv("JARVIS_APP_ID", "123")
        monkeypatch.setenv("JARVIS_APP_PRIVATE_KEY_PATH", str(tmp_path / "does-not-exist.pem"))
        with pytest.raises(RuntimeError, match="not found"):
            gat.get_installation_token()

    def test_a_configured_but_broken_app_never_silently_falls_back(
        self, gat, monkeypatch, tmp_path
    ):
        """A silent fallback to a PAT is how a permission regression hides."""
        monkeypatch.setenv("JARVIS_APP_ID", "123")
        monkeypatch.setenv("JARVIS_APP_PRIVATE_KEY_PATH", str(tmp_path / "missing.pem"))
        with pytest.raises(RuntimeError):
            gat.get_installation_token()
