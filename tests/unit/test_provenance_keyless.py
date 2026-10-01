"""Provenance signing must work keyless in CI, and still work locally.

RISK-009 records provenance at SLSA L1 because ``gate_provenance`` signs with a
local cosign keypair stored in ``~/.local/share/jarvis-ci-tools``. That key cannot
exist on a GitHub runner, so in CI the gate either skips (making no claim) or needs
the private key pasted into a repo secret — a long-lived signing key guarding a
public repository.

Keyless OIDC removes both problems. GitHub Actions mints a short-lived OIDC token
per job; cosign exchanges it for a Fulcio certificate and writes a Rekor
transparency-log entry. The signature is bound to the workflow identity instead of
a key that can leak, and the record becomes publicly auditable — which is what
L2/L3 asks for and what a local keypair cannot provide.

These tests drive ``gate_provenance`` with a **fake ``cosign`` on PATH** that
records its argv. That observes the actual command the gate builds, rather than
matching the source text for it.
"""

from __future__ import annotations

import importlib
import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


@pytest.fixture()
def ci_gate():
    sys.path.insert(0, str(SCRIPTS))
    if "ci_gate" in sys.modules:
        del sys.modules["ci_gate"]
    mod = importlib.import_module("ci_gate")
    yield mod
    sys.path.remove(str(SCRIPTS))
    sys.modules.pop("ci_gate", None)


@pytest.fixture()
def fake_cosign(tmp_path, monkeypatch):
    """A ``cosign`` that logs its argv and exits 0, so signing 'succeeds'."""
    log = tmp_path / "cosign-argv.log"
    exe = tmp_path / "cosign"
    exe.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        "# Write a bundle file for the --bundle path so later code can find it.\n"
        "for ((i=1;i<=$#;i++)); do\n"
        '  if [[ "${!i}" == "--bundle" ]]; then j=$((i+1)); : > "${!j}"; fi\n'
        "done\n"
        "exit 0\n"
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return log


def _run_and_read(ci_gate, fake_cosign, tmp_path, keyless: bool):
    ci_gate.KEYLESS = keyless
    ci_gate.ARTIFACT_DIR = tmp_path / "artifacts"
    ci_gate.TOOLS_HOME = tmp_path / "tools"
    # A local keypair only matters in keyed mode; create one so keyed mode
    # gets past its early-return.
    ci_gate.TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    (ci_gate.TOOLS_HOME / "cosign.key").write_text("key")
    (ci_gate.TOOLS_HOME / "cosign.pub").write_text("pub")
    ci_gate.gate_provenance(REPO_ROOT, "abc123def456")
    return fake_cosign.read_text().splitlines() if fake_cosign.exists() else []


def test_keyless_signing_omits_the_private_key(ci_gate, fake_cosign, tmp_path) -> None:
    """Keyless mode must not pass ``--key``; that is what makes it keyless."""
    calls = _run_and_read(ci_gate, fake_cosign, tmp_path, keyless=True)
    sign_calls = [c for c in calls if c.startswith("sign-blob")]
    assert sign_calls, f"no sign-blob call was made; cosign saw: {calls}"
    for call in sign_calls:
        assert "--key" not in call, (
            f"keyless signing still passed a private key: {call}\n"
            f"Keyless mode must let cosign use the ambient OIDC token."
        )


def test_keyed_signing_still_uses_the_local_key(ci_gate, fake_cosign, tmp_path) -> None:
    """Local mode is unchanged: the keypair is still the signing material."""
    calls = _run_and_read(ci_gate, fake_cosign, tmp_path, keyless=False)
    sign_calls = [c for c in calls if c.startswith("sign-blob")]
    assert sign_calls, f"no sign-blob call was made; cosign saw: {calls}"
    assert any(
        "--key" in c for c in sign_calls
    ), f"local signing dropped --key; cosign saw: {calls}"


def test_keyless_verification_pins_the_workflow_identity(ci_gate, fake_cosign, tmp_path) -> None:
    """Keyless verification must pin issuer and identity, not just the blob.

    A bundle verified without ``--certificate-identity`` proves only that *some*
    Fulcio certificate signed it — which any GitHub workflow in any repository can
    obtain. Pinning the identity is what makes the provenance mean "this repo's CI
    built this commit".
    """
    calls = _run_and_read(ci_gate, fake_cosign, tmp_path, keyless=True)
    verify_calls = [c for c in calls if c.startswith("verify-blob")]
    assert verify_calls, f"no verify-blob call was made; cosign saw: {calls}"
    for call in verify_calls:
        assert "--certificate-oidc-issuer" in call
        assert "--certificate-identity" in call
        assert "--key" not in call


def test_keyed_verification_still_uses_the_public_key(ci_gate, fake_cosign, tmp_path) -> None:
    """Local verification is unchanged."""
    calls = _run_and_read(ci_gate, fake_cosign, tmp_path, keyless=False)
    verify_calls = [c for c in calls if c.startswith("verify-blob")]
    assert verify_calls, f"no verify-blob call was made; cosign saw: {calls}"
    assert any("--key" in c for c in verify_calls), f"cosign saw: {calls}"


def test_keyless_is_off_unless_ci_asks_for_it(ci_gate) -> None:
    """Negative control: defaulting to keyless would break every local run.

    Locally there is no ambient OIDC token, so a keyless default would make the
    gate fail on the developer machine it is supposed to serve.
    """
    source = (SCRIPTS / "ci_gate.py").read_text(encoding="utf-8")
    assert (
        "KEYLESS = False" in source
    ), "KEYLESS no longer defaults to False; local signing would break"


def test_provenance_statement_is_still_in_toto(ci_gate, fake_cosign, tmp_path) -> None:
    """The signed payload keeps its shape regardless of signing mode."""
    ci_gate.KEYLESS = True
    ci_gate.ARTIFACT_DIR = tmp_path / "artifacts"
    ci_gate.TOOLS_HOME = tmp_path / "tools"
    ci_gate.TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    (ci_gate.TOOLS_HOME / "cosign.key").write_text("key")
    (ci_gate.TOOLS_HOME / "cosign.pub").write_text("pub")

    ci_gate.gate_provenance(REPO_ROOT, "abc123def456")

    stmt = json.loads((tmp_path / "artifacts" / "provenance-abc123def456.intoto.json").read_text())
    assert stmt["_type"] == "https://in-toto.io/Statement/v1"
    assert stmt["predicateType"] == "https://slsa.dev/provenance/v1"
    assert stmt["subject"][0]["digest"]["gitCommit"] == "abc123def456"
