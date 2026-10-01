#!/usr/bin/env bash
# Install the scanners scripts/ci_gate.py shells out to.
#
# This is the SINGLE definition of "the tools the gate needs", used by a
# developer machine and by the GitHub Actions workflow alike. It previously lived
# only in ~/.local/share/jarvis-ci-tools/install.sh, outside version control, so
# CI had no way to reproduce a local run and nobody could review what a gate run
# depended on.
#
# Isolation: python tools go into their own venv (default
# ~/.local/share/jarvis-ci-tools/venv) so the project's pinned .venv is never
# disturbed. Go binaries land on PATH via the tools bin dir.
#
# Exit status is load-bearing. The gate is run with --require-tools in CI, which
# turns a missing BLOCKING scanner into a failure; this script fails first and
# more legibly, naming what is absent. A silent partial install is the dangerous
# case: the required status check would go green while enforcing nothing.
set -uo pipefail

TOOLS="${JARVIS_CI_TOOLS_HOME:-$HOME/.local/share/jarvis-ci-tools}"
VENV="$TOOLS/venv"
BIN="${JARVIS_CI_TOOLS_BIN:-$HOME/.local/bin}"
mkdir -p "$TOOLS" "$BIN"
# The gate resolves tools from the project venv, then an isolated scanner venv,
# then PATH. semgrep/checkov/cyclonedx live in the tools venv, so this script's
# own verification must look there too -- checking only $BIN reported semgrep and
# cyclonedx-bom MISSING while both were installed.
export PATH="$VENV/bin:$BIN:$PATH"

# Checks the gate marks blocking=True. Each MUST be present or this exits 1.
REQUIRED_BINARIES=(trivy syft cosign hadolint trufflehog gitleaks semgrep)
REQUIRED_PY_TOOLS=()

log() { printf '%s\n' "  $*"; }

echo "=== [1/3] python tools into isolated venv ($VENV) ==="
if [ ! -x "$VENV/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV" || python3 -m venv "$VENV"
  else
    python3 -m venv "$VENV"
  fi
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$VENV/bin/python" semgrep pip-licenses cyclonedx-bom mutmut 2>&1 | tail -5
  log "checkov (heavy, separate) ..."
  uv pip install --python "$VENV/bin/python" checkov 2>&1 | tail -3
else
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet semgrep pip-licenses cyclonedx-bom mutmut 2>&1 | tail -5
  log "checkov (heavy, separate) ..."
  "$VENV/bin/python" -m pip install --quiet checkov 2>&1 | tail -3
fi

echo "=== [2/3] Go binaries from GitHub releases ==="
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) GOARCH=amd64 ;;
  aarch64 | arm64) GOARCH=arm64 ;;
  *) GOARCH=amd64 ;;
esac

fetch_asset() { # repo  regex  outname  [inner path]
  local repo="$1" rx="$2" out="$3" inner="${4:-}"
  local url
  url=$(curl -sSL --max-time 60 "https://api.github.com/repos/${repo}/releases/latest" |
    python3 -c "
import json,sys,re
rx=re.compile(sys.argv[1])
d=json.load(sys.stdin)
for a in d.get('assets',[]):
    if rx.search(a['name']):
        print(a['browser_download_url']); break
" "$rx")
  if [ -z "$url" ]; then
    log "!! $repo: no asset matching /$rx/"
    return 1
  fi
  log "$repo -> $(basename "$url")"
  local tmp="$TOOLS/dl_$out"
  curl -sSL --max-time 300 "$url" -o "$tmp" || {
    log "!! download failed"
    return 1
  }
  case "$url" in
    *.tar.gz | *.tgz)
      tar -xzf "$tmp" -C "$TOOLS" ${inner:+"$inner"} 2>/dev/null || tar -xzf "$tmp" -C "$TOOLS"
      [ -n "$inner" ] && mv -f "$TOOLS/$inner" "$BIN/$out"
      ;;
    *) mv -f "$tmp" "$BIN/$out" ;;
  esac
  chmod +x "$BIN/$out" 2>/dev/null
}

# hadolint publishes only an x86_64 Linux binary; skip it on arm rather than
# failing the whole install, and let --require-tools report the gap honestly.
fetch_asset aquasecurity/trivy "Linux-64bit.tar.gz$" trivy trivy
fetch_asset anchore/syft "linux_${GOARCH}.tar.gz$" syft syft
fetch_asset sigstore/cosign "cosign-linux-${GOARCH}$" cosign
fetch_asset trufflesecurity/trufflehog "linux_${GOARCH}.tar.gz$" trufflehog trufflehog
# gitleaks names its assets _linux_x64 / _linux_arm64 (not amd64):
GITLEAKS_ARCH="x64"
[ "$GOARCH" = "arm64" ] && GITLEAKS_ARCH="arm64"
fetch_asset gitleaks/gitleaks "linux_${GITLEAKS_ARCH}.tar.gz$" gitleaks gitleaks
if [ "$GOARCH" = "amd64" ]; then
  # hadolint names its asset hadolint-linux-x86_64:
  fetch_asset hadolint/hadolint "linux-x86_64$" hadolint hadolint-linux-x86_64
fi

echo "=== [3/3] verify — this is the part CI depends on ==="
missing=()
for t in "${REQUIRED_BINARIES[@]}"; do
  p="$(command -v "$t" 2>/dev/null || true)"
  [ -z "$p" ] && [ -x "$BIN/$t" ] && p="$BIN/$t"
  if [ -n "$p" ] && [ -x "$p" ]; then
    printf '  %-14s OK   %s\n' "$t" "$("$p" --version 2>&1 | head -1)"
  else
    printf '  %-14s MISSING\n' "$t"
    missing+=("$t")
  fi
done

# cyclonedx-bom installs a binary named `cyclonedx-py`.
for t in semgrep pip-licenses cyclonedx-py checkov; do
  if [ -x "$VENV/bin/$t" ]; then
    printf '  %-14s OK   (tools venv)\n' "$t"
  else
    printf '  %-14s MISSING\n' "$t"
    missing+=("$t")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo
  echo "FAIL: ${#missing[@]} gate tool(s) could not be installed: ${missing[*]}"
  echo "The gate must not run with a hole in it — a missing blocking scanner"
  echo "would otherwise report skip and turn the required check green."
  exit 1
fi

# osv-scanner is non-blocking in the gate, so it is attempted separately: a
# failure here is reported but is not fatal.
if ! command -v osv-scanner >/dev/null 2>&1 && [ ! -x "$VENV/bin/osv-scanner" ]; then
  "$VENV/bin/python" -m pip install --quiet osv-scanner 2>&1 | tail -3 || true
fi

echo "DONE — all blocking gate tools present."
