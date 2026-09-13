#!/usr/bin/env python3
"""External link checker — THE ONLY PLACE IN THE DOC PIPELINE THAT USES NETWORK.

Every other documentation script in this repository is required to run offline:
facts, types, links, anchors and claims are all derived from checked-in files. This
one is the deliberate exception, because an external URL's liveness cannot be
derived — it has to be asked. It is kept in its own file, run on its own schedule,
and never wired into the offline gate, so the invariant "the audit path makes no
network calls" stays true and auditable.

Design notes that matter:

- **A block is not a death.** Many hosts (Cloudflare-fronted sites, GitHub at
  volume, most CDNs) answer a bot with 403/406/429 rather than 404. Those are
  indistinguishable from a real failure by status code alone, so they go in
  ALLOW_HOSTS and are reported as "unverified", never as broken. Failing on them
  would train the reader to ignore this check.
- **Hard-dead vs transient is decided by code, not by feeling.** 404/410 and DNS
  failure are hard; 429 and 5xx are transient and retried, then reported as
  warnings. Only hard-dead sets a non-zero exit.
- **Untracked documents are included.** A new document's links should be checked
  before its first commit, not after.

Usage:
    python scripts/check_links.py                 # human report
    python scripts/check_links.py --json          # machine list
    python scripts/check_links.py --table out.md  # markdown table of dead links
    python scripts/check_links.py --offline       # extract only, no network
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

URL_RE = re.compile(r"https?://[^\s)\]<>\"'`*]+")
TRAILING = ".,;:!?"

# Addresses that are *illustrative*, not clickable. A link checker's job is to catch
# a reference a reader will click and find broken; a documented API base URL or a
# local dev-server address is neither, and reporting them as dead is the fastest way
# to teach a reader to ignore this check. Skipped deliberately, and the skip is
# visible here rather than hidden in a per-URL exemption list.
PLACEHOLDER_PATTERNS = re.compile(
    r"^https?://("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|0\.0\.0\.0"
    r"|\[::1\]"
    r"|host\.docker\.internal"
    r")"
    r"|yourdomain\.com"
    r"|example\.(com|org|net)"
    r"|your-?(domain|host|server)",
    re.I,
)

# API base URLs: the host is healthy but the bare base path legitimately has no
# document or returns 404 to a HEAD. Probed by suffix, because the base path is the
# thing that is not browsable.
API_BASE_SUFFIXES = (
    "/api/v1",
    "/api/v1beta",
    "/v1",
    "/v1beta",
)

# Hosts that are known to answer automated requests with a block rather than a true
# status. Curated, and conservative: a host belongs here only if a human has seen it
# block a real, working page.
#
# IMPORTANT — a host in this set is still PROBED. The list only decides how a
# non-success is *classified* (unverified rather than dead). It must never be used to
# skip the request, because that would let a dead path on a listed host pass
# unchecked, which is the exact failure mode a link checker exists to catch.
ALLOW_HOSTS = {
    "github.com",  # 429s under even light load
    "www.github.com",
    "gist.github.com",
    "raw.githubusercontent.com",
    "chatgpt.com",
    "openai.com",
    "platform.openai.com",
    "anthropic.com",
    "www.anthropic.com",
    "docs.anthropic.com",
    "cloudflare.com",
    "www.cloudflare.com",
    "developers.cloudflare.com",
    "medium.com",
    "towardsdatascience.com",
    "stackoverflow.com",
    "www.reddit.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "www.linkedin.com",
    "discord.com",
    "discord.gg",
    "n8n.io",
    "docs.n8n.io",
    "ollama.com",
    "huggingface.co",
    "pypi.org",
    "www.npmjs.com",
    "npmjs.com",
}

HARD_DEAD_STATUS = {404, 410}
TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 JARVIS-doc-link-check"
)

# Documents whose external references are historical and not worth re-checking.
SKIP_DIRS = ("docs/archive/",)


def tracked_and_untracked_docs() -> list[Path]:
    """Markdown under docs/ or at the repo root, including untracked files.

    ``--others --exclude-standard`` is what brings in a document that has not been
    committed yet, so a new doc is checked before it lands.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    files = []
    for line in out.splitlines():
        rel = line.strip()
        if not rel.endswith(".md"):
            continue
        if not (rel.startswith("docs/") or "/" not in rel):
            continue
        if rel.startswith(SKIP_DIRS):
            continue
        p = REPO_ROOT / rel
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def extract_links(paths: list[Path]) -> dict[str, list[str]]:
    """url -> [file:line, ...]. Duplicates across documents are collapsed."""
    found: dict[str, list[str]] = {}
    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue
        in_fence = False
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for url in URL_RE.findall(line):
                url = url.rstrip(TRAILING)
                found.setdefault(url, []).append(f"{rel}:{i}")
    return found


def host_of(url: str) -> str:
    return url.split("/", 3)[2].lower().split(":")[0]


def is_placeholder(url: str) -> bool:
    """True for a documented address that no reader will click as a link."""
    return bool(PLACEHOLDER_PATTERNS.search(url))


def probe(url: str, timeout: float = 15.0) -> tuple[str, str]:
    """Return (verdict, detail) where verdict is ok | unverified | transient | dead.

    Ordering here is the whole design, and it is deliberate:

    1. **Placeholders are skipped** without a request — they are illustrative
       addresses (`localhost`, `example.com`), not links any reader clicks.
    2. **The host is probed, always.** A host allowlist must never mean "do not
       check this URL": that would let `https://github.com/some/dead/path` pass
       merely because `github.com` is listed, which defeats the checker. The
       allowlist below is consulted *after* the probe to decide how to classify a
       non-success, never to skip the probe.
    3. **DNS failure is hard-dead for every URL**, including an API base. A hostname
       that does not resolve is dead whatever path follows it, so the API-base
       special case (added for non-browsable endpoints on *live* hosts) must not
       swallow it.
    """
    if is_placeholder(url):
        return "skipped", "local or example address, not a clickable link"

    api_base = url.rstrip("/").endswith(API_BASE_SUFFIXES)
    host = host_of(url)

    # An API base URL is not browsable: the base path is meant to be *called*, so a
    # 404 there says nothing about health. Probe the host root instead — but that is
    # still a real probe, and a dead hostname stays dead.
    target = f"https://{host}/" if api_base else url

    verdict, detail = _probe_url(target, timeout)

    # DNS is authoritative: an unresolvable host is dead, full stop. Checked before
    # any downgrade path so a dead hostname can never be reported as unverified.
    if "DNS failure" in detail:
        return "dead", detail

    if verdict == "dead" and api_base:
        # The host answered, so it is alive; only the non-browsable base path 404'd.
        return "unverified", f"API base URL (not browsable; host root said {detail})"

    # A host that blocks automated requests gets the benefit of the doubt *only for a
    # status that could plausibly be a block* (401/403/405/406/429). A definite
    # verdict is never downgraded merely because the host is familiar: a 404 means
    # this URL does not exist, on github.com exactly as anywhere else. Downgrading it
    # would reopen the hole where a dead path hides behind an allowlisted host.
    inconclusive = detail.startswith(("HTTP 401", "HTTP 403", "HTTP 405", "HTTP 406", "HTTP 999"))
    if verdict != "ok" and host in ALLOW_HOSTS and (inconclusive or verdict == "transient"):
        return "unverified", f"{detail} (host is known to block automated requests)"

    return verdict, detail


def _probe_url(url: str, timeout: float = 15.0) -> tuple[str, str]:
    for attempt in (1, 2):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return "ok", f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code in HARD_DEAD_STATUS:
                return "dead", f"HTTP {exc.code}"
            if exc.code in TRANSIENT_STATUS:
                if attempt == 1:
                    continue
                return "transient", f"HTTP {exc.code} after retry"
            # 403/406/401: a block, which we cannot distinguish from a failure.
            if exc.code in {401, 403, 405, 406, 999}:
                return "unverified", f"HTTP {exc.code} (likely bot block)"
            # Some servers reject HEAD outright; retry as GET before judging.
            if exc.code == 400:
                try:
                    req_get = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req_get, timeout=timeout) as resp:
                        return "ok", f"HTTP {resp.status} (GET)"
                except urllib.error.HTTPError as exc2:
                    if exc2.code in HARD_DEAD_STATUS:
                        return "dead", f"HTTP {exc2.code}"
                    return "unverified", f"HTTP {exc2.code} (GET)"
                except Exception:  # noqa: BLE001
                    return "unverified", f"HTTP {exc.code}, GET failed"
            return "unverified", f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "Name or service not known" in reason or "nodename" in reason:
                return "dead", "DNS failure"
            if attempt == 1:
                continue
            return "transient", reason[:80]
        except Exception as exc:  # noqa: BLE001 - timeouts, resets, TLS
            if attempt == 1:
                continue
            return "transient", f"{type(exc).__name__}: {str(exc)[:70]}"
    return "transient", "exhausted retries"


def main() -> int:
    ap = argparse.ArgumentParser(description="Check external links in the docs.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--table", metavar="PATH", help="write a markdown table of dead links")
    ap.add_argument("--offline", action="store_true", help="extract links, make no requests")
    args = ap.parse_args()

    docs = tracked_and_untracked_docs()
    links = extract_links(docs)
    if args.offline:
        print(f"check_links: {len(links)} unique external link(s) in {len(docs)} document(s)")
        print("             offline mode — no requests made")
        return 0

    results: dict[str, dict[str, str]] = {}
    for url in sorted(links):
        verdict, detail = probe(url)
        results[url] = {"verdict": verdict, "detail": detail}

    dead = {u: r for u, r in results.items() if r["verdict"] == "dead"}
    transient = {u: r for u, r in results.items() if r["verdict"] == "transient"}
    unverified = {u: r for u, r in results.items() if r["verdict"] == "unverified"}
    skipped = {u: r for u, r in results.items() if r["verdict"] == "skipped"}
    ok = {u: r for u, r in results.items() if r["verdict"] == "ok"}

    if args.json:
        print(
            json.dumps(
                {
                    "results": results,
                    "counts": {
                        "ok": len(ok),
                        "unverified": len(unverified),
                        "skipped": len(skipped),
                        "transient": len(transient),
                        "dead": len(dead),
                    },
                },
                indent=2,
            )
        )
    else:
        print(f"check_links: {len(links)} unique external link(s) in {len(docs)} document(s)")
        print(f"  reachable   : {len(ok)}")
        print(f"  skipped     : {len(skipped)}  (local/example addresses, not links)")
        print(f"  unverified  : {len(unverified)}  (host blocks bots — not a failure)")
        print(f"  transient   : {len(transient)}  (rate-limited or 5xx — retry later)")
        print(f"  dead        : {len(dead)}")
        for url, r in sorted(dead.items()):
            print(f"\n  DEAD {url}  [{r['detail']}]")
            for loc in links[url]:
                print(f"       referenced at {loc}")
        for url, r in sorted(transient.items()):
            print(f"\n  WARN {url}  [{r['detail']}]")
            for loc in links[url][:3]:
                print(f"       referenced at {loc}")

    if args.table and dead:
        rows = ["| URL | Status | Referenced at |", "|---|---|---|"]
        for url, r in sorted(dead.items()):
            rows.append(f"| {url} | {r['detail']} | {', '.join(links[url][:5])} |")
        Path(args.table).write_text("\n".join(rows) + "\n", encoding="utf-8")

    # Only a hard-dead link fails the run. Transient and blocked are reported and
    # exited 0 on purpose: a check that cries wolf gets ignored, and then it is
    # worth nothing.
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
