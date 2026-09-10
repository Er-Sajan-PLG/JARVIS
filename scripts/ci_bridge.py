#!/usr/bin/env python3
"""GitHub bridge for JARVIS local CI — poll PRs, gate them, publish statuses.

This is the control-plane glue that lets local n8n replace GitHub Actions.
n8n schedules it; it does the GitHub work.

Pipeline
--------
  1. list open PRs (REST, explicit fine-grained token)
  2. skip any PR whose head SHA was already gated (idempotent across polls)
  3. fetch the PR head commit into the local object store
  4. run scripts/ci_gate.py against that SHA in a shadow worktree
  5. publish one commit STATUS per gate context

Why statuses and not check-runs
-------------------------------
Empirically verified against this repo:
  POST /repos/{owner}/{repo}/check-runs  -> 403 "You must authenticate via a
  GitHub App."
  POST /repos/{owner}/{repo}/statuses/{sha} -> 200
A PAT/OAuth token can write commit statuses but CANNOT write check-runs; only a
GitHub App installation can. So the bridge uses /statuses. (Check-runs would
also be the wrong choice for another reason: branch protection is 403 on a
private free-tier repo, so nothing here can gate a merge regardless.)

Auth
----
Reads the token from config, never from the command line (avoids leaking it
into shell history or process listings). Resolution order:
  env GITHUB_MCP_PAT / GITHUB_TOKEN / GH_TOKEN / GITHUB_PAT
  then the first KEY=value match in ~/Projects/.env, ~/.hermes/.env, ./.env
  then `gh auth token`
Use --check-auth to print which source won (the token itself is never echoed).

Usage
-----
  scripts/ci_bridge.py --check-auth          # which token, which account
  scripts/ci_bridge.py --list-prs            # what needs gating
  scripts/ci_bridge.py --pr 43 --dry-run     # gate one PR, publish nothing
  scripts/ci_bridge.py --pr 43               # gate one PR, publish statuses
  scripts/ci_bridge.py --once                # gate every PR that needs it
  scripts/ci_bridge.py --once --json         # machine-readable summary
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OWNER = "Er-Sajan-PLG"
REPO = "JARVIS"
API = "https://api.github.com"

GATE = REPO_ROOT / "scripts" / "ci_gate.py"
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
STATE_FILE = REPO_ROOT / ".governance" / "ci_bridge_state.json"

TOKEN_VARS = ("GITHUB_MCP_PAT", "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT")
TOKEN_FILES = (
    Path.home() / "Projects" / ".env",
    Path.home() / ".hermes" / ".env",
    REPO_ROOT / ".env",
)

# Which gate belongs to which published context. Contexts are the display
# names the intended branch protection would require, so they stay stable
# whether enforcement is local or (later) GitHub-side.
CONTEXT_OF: dict[str, str] = {
    # Static analysis & types
    "ruff_ratchet": "Lint & Typecheck",
    "mypy": "Lint & Typecheck",
    "semgrep": "SAST",
    # Tests
    "pytest": "Tests",
    "contract": "Tests",
    "coverage": "Tests",
    # Secrets & appsec
    "gitleaks": "Security Scan",
    "trufflehog": "Security Scan",
    "bandit": "Security Scan",
    "pip_audit": "Security Scan",
    # Supply chain (SCA / SBOM / licences / provenance / IaC)
    "trivy": "Supply Chain",
    "osv": "Supply Chain",
    "licenses": "Supply Chain",
    "sbom": "Supply Chain",
    "provenance": "Supply Chain",
    "checkov": "Supply Chain",
    # Governance, build, commits
    "board": "Virtual Board Governance",
    "compileall": "Build",
    "hadolint": "Build",
    "docker_build": "Build",
    "worktree": "Build",
    "commitlint": "Conventional Commits",
    # Heavy / ratcheted
    "mutation": "Mutation Testing",
}
CONTEXT_ORDER = (
    "Lint & Typecheck",
    "SAST",
    "Tests",
    "Security Scan",
    "Supply Chain",
    "Conventional Commits",
    "Virtual Board Governance",
    "Build",
    "Mutation Testing",
)


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=value reader. Handles optional quotes and `export `."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            out[key] = value
    return out


def load_token() -> tuple[str, str]:
    """Return (token, source_description). Never logs the token value."""
    for var in TOKEN_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value, f"env:{var}"

    for path in TOKEN_FILES:
        env = _parse_env_file(path)
        for var in TOKEN_VARS:
            value = env.get(var, "").strip()
            if value:
                return value, f"{path}:{var}"

    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip(), "gh auth token"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "", ""


def _mask(token: str) -> str:
    if len(token) <= 12:
        return "***"
    return f"{token[:11]}...{token[-4:]}"


# ─────────────────────────────────────────────────────────────────────────────
# REST helpers (stdlib only — no requests, no gh dependency)
# ─────────────────────────────────────────────────────────────────────────────


def api(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, Any]:
    """Call the GitHub REST API. Returns (status_code, parsed_or_text)."""
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "jarvis-local-ci")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


def check_auth(token: str, source: str) -> int:
    status, body = api("GET", "/user", token)
    masked = _mask(token) if token else "***"
    if status != 200 or not isinstance(body, dict):
        print(f"FAIL  token from {source} rejected: masked={masked} (HTTP {status})")
        return 1
    print("AUTH OK")
    # Token value never printed — only source and masked form for audit; SEC-002.
    print(f"  source : {source}")
    print(f"  token  : masked={_mask(token)}")
    print(f"  login  : {body.get('login')}")

    rl_status, rl = api("GET", "/rate_limit", token)
    if rl_status == 200 and isinstance(rl, dict):
        core = rl.get("resources", {}).get("core", {})
        print(
            f"  limit  : {core.get('remaining')}/{core.get('limit')} "
            f"(resets {core.get('reset')})"
        )

    _, repo = api("GET", f"/repos/{OWNER}/{REPO}", token)
    if isinstance(repo, dict):
        perms = repo.get("permissions", {})
        print(
            f"  repo   : {repo.get('full_name')} "
            f"(private={repo.get('private')}, push={perms.get('push')})"
        )
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# PRs, gating, status publishing
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PRInfo:
    number: int
    head_sha: str
    head_ref: str
    base_ref: str
    title: str
    draft: bool = False

    @property
    def base_branch(self) -> str:
        return f"origin/{self.base_ref}"


def list_open_prs(token: str, limit: int = 20) -> list[PRInfo]:
    status, body = api(
        "GET",
        f"/repos/{OWNER}/{REPO}/pulls?state=open&per_page={limit}" "&sort=updated&direction=desc",
        token,
    )
    if status != 200 or not isinstance(body, list):
        raise RuntimeError(f"cannot list PRs (HTTP {status}): {body}")

    prs: list[PRInfo] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        head = item.get("head") or {}
        base = item.get("base") or {}
        prs.append(
            PRInfo(
                number=int(item.get("number", 0)),
                head_sha=str(head.get("sha", "")),
                head_ref=str(head.get("ref", "")),
                base_ref=str(base.get("ref", "main")),
                title=str(item.get("title", "")),
                draft=bool(item.get("draft")),
            )
        )
    return prs


def load_state() -> dict[str, Any]:
    if STATE_FILE.is_file():
        try:
            data = json.loads(STATE_FILE.read_text())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"gated": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_pr_head(pr: PRInfo) -> tuple[bool, str]:
    """Materialise the PR head commit locally so ci_gate can worktree it.

    Fetches over HTTPS with the fine-grained token so headless runs (n8n,
    systemd services, CI) do not depend on an ssh-agent holding a GitHub key.
    The token is passed through the child environment (not argv) and expanded
    by an inline credential helper, so it never appears in `ps` output.
    Falls back to the configured `origin` remote when no token is available.
    """
    ref = f"refs/remotes/jarvis-pr/{pr.number}"
    refspec = f"+refs/pull/{pr.number}/head:{ref}"

    token, _ = load_token()
    if token:
        url = f"https://github.com/{OWNER}/{REPO}.git"
        helper = "!f() { echo username=x-access-token; " 'echo "password=${JARVIS_GIT_TOKEN}"; }; f'
        env = {**os.environ, "JARVIS_GIT_TOKEN": token, "GIT_TERMINAL_PROMPT": "0"}
        cmd = [
            "git",
            "-c",
            f"credential.helper={helper}",
            "fetch",
            "--no-tags",
            "--force",
            url,
            refspec,
        ]
    else:
        env = None
        cmd = ["git", "fetch", "--no-tags", "--force", "origin", refspec]

    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    if res.returncode != 0:
        return False, (res.stderr or res.stdout).strip()[:400]

    have = subprocess.run(
        ["git", "cat-file", "-e", f"{pr.head_sha}^{{commit}}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if have.returncode != 0:
        return False, f"{pr.head_sha[:12]} not present after fetch"
    return True, ""


def _rev(ref: str) -> str:
    """Resolve a ref to a sha, or "" when it does not exist."""
    res = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return res.stdout.strip() if res.returncode == 0 else ""


def _fetch_ref(branch: str) -> bool:
    """Refresh origin/<branch> over HTTPS with the token (headless-safe)."""
    refspec = f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
    token, _ = load_token()
    if token:
        url = f"https://github.com/{OWNER}/{REPO}.git"
        helper = "!f() { echo username=x-access-token; " 'echo "password=${JARVIS_GIT_TOKEN}"; }; f'
        env = {**os.environ, "JARVIS_GIT_TOKEN": token, "GIT_TERMINAL_PROMPT": "0"}
        cmd = ["git", "-c", f"credential.helper={helper}", "fetch", "--no-tags", url, refspec]
    else:
        env = None
        cmd = ["git", "fetch", "--no-tags", "origin", refspec]
    res = subprocess.run(
        cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600, env=env
    )
    return res.returncode == 0


def merge_gate_ref(pr: PRInfo) -> tuple[str, str, str]:
    """Return (gate_sha, gate_base, note).

    GitHub's `pull_request` jobs check out a MERGE commit — the head merged into the
    base — not the raw head. Gating the raw head means every branch that predates a
    fix on main fails forever, which is exactly what happened to the Dependabot
    backlog after main's test-suite fix landed. We reproduce the merge locally
    (`git merge-tree --write-tree` + `git commit-tree`) so the gate sees what
    GitHub Actions would have seen.
    """
    # PRInfo.base_branch is already origin-prefixed ("origin/main").
    base_ref = pr.base_branch
    _fetch_ref(pr.base_ref)
    base = _rev(base_ref) or _rev(pr.base_ref)
    if not base:
        return pr.head_sha, base_ref, "base ref unavailable — gated raw head"

    anc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, pr.head_sha],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if anc.returncode == 0:
        return pr.head_sha, base_ref, "head already contains base — gated head"

    mt = subprocess.run(
        ["git", "merge-tree", "--write-tree", base, pr.head_sha],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    tree = (mt.stdout or "").splitlines()[0].strip() if mt.stdout else ""
    if mt.returncode != 0 or not tree:
        return pr.head_sha, base_ref, f"MERGE CONFLICT against {pr.base_ref} — gated raw head"

    ct = subprocess.run(
        [
            "git",
            "commit-tree",
            tree,
            "-p",
            base,
            "-p",
            pr.head_sha,
            "-m",
            f"ci: gate merge of {pr.head_sha[:12]} into {pr.base_ref}",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if ct.returncode != 0 or not ct.stdout.strip():
        return pr.head_sha, base_ref, "merge commit failed — gated raw head"
    return ct.stdout.strip(), base_ref, f"gated merge of {pr.head_sha[:12]} into {pr.base_ref}"


def run_gate(pr: PRInfo, timeout: int = 2400) -> dict[str, Any]:
    """Invoke ci_gate.py against the PR's MERGE result and return its parsed report."""
    sha, base, note = merge_gate_ref(pr)
    proc = subprocess.run(
        [str(PYTHON), str(GATE), "--sha", sha, "--base", base, "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = proc.stdout.strip()
    if stdout:
        try:
            report = json.loads(stdout)
            report["merge_gate_note"] = note
            return report
        except json.JSONDecodeError:
            pass
    return {
        "sha": sha,
        "conclusion": "error",
        "checks": [],
        "merge_gate_note": note,
        "error": (proc.stderr or stdout or "no output")[:800],
    }


def aggregate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Collapse per-check results into one outcome per published context."""
    buckets: dict[str, dict[str, Any]] = {}
    for check in report.get("checks", []):
        name = check.get("name", "")
        context = CONTEXT_OF.get(name, check.get("context", name))
        bucket = buckets.setdefault(
            context,
            {
                "blocking": False,
                "blocking_failures": [],
                "reported_failures": [],
                "checks": [],
            },
        )
        bucket["checks"].append(name)
        if check.get("blocking"):
            bucket["blocking"] = True
            if check.get("status") in ("fail", "error"):
                bucket["blocking_failures"].append(f"{name}: {check.get('summary')}")
        elif check.get("status") in ("fail", "error"):
            bucket["reported_failures"].append(f"{name}: {check.get('summary')}")

    for bucket in buckets.values():
        bucket["state"] = "failure" if bucket["blocking_failures"] else "success"
    return buckets


def publish_statuses(
    token: str, sha: str, buckets: dict[str, dict[str, Any]], dry: bool
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for context in CONTEXT_ORDER:
        bucket = buckets.get(context)
        if not bucket:
            continue
        state = bucket["state"]
        if bucket["blocking_failures"]:
            desc = f"{len(bucket['blocking_failures'])} blocking gate(s) failed"
        elif bucket["reported_failures"]:
            desc = (
                f"blocking gates pass; {len(bucket['reported_failures'])} "
                f"reported-only gate(s) failing"
            )
        else:
            desc = "all gates pass"
        desc = desc[:140]

        record = {"context": context, "state": state, "description": desc}
        if dry:
            record["posted"] = False
            published.append(record)
            continue

        status, body = api(
            "POST",
            f"/repos/{OWNER}/{REPO}/statuses/{sha}",
            token,
            payload={"state": state, "context": context, "description": desc},
        )
        record["posted"] = status in (200, 201)
        record["http"] = status
        if not record["posted"]:
            record["error"] = str(body)[:200]
        published.append(record)
    return published


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PRResult:
    number: int
    sha: str
    title: str
    action: str
    conclusion: str = ""
    statuses: list[dict[str, Any]] = field(default_factory=list)


def gate_one(pr: PRInfo, token: str, dry: bool) -> PRResult:
    result = PRResult(pr.number, pr.head_sha, pr.title, "gated")

    ok, err = fetch_pr_head(pr)
    if not ok:
        result.action = "fetch-failed"
        result.conclusion = "error"
        result.statuses = [{"error": err}]
        return result

    report = run_gate(pr)
    result.conclusion = str(report.get("conclusion", "error"))
    buckets = aggregate(report)
    result.statuses = publish_statuses(token, pr.head_sha, buckets, dry)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-auth", action="store_true")
    parser.add_argument("--list-prs", action="store_true")
    parser.add_argument(
        "--once", action="store_true", help="gate every open PR that still needs it"
    )
    parser.add_argument("--pr", type=int, help="gate only this PR number")
    parser.add_argument("--limit", type=int, default=10, help="max PRs to consider (default 10)")
    parser.add_argument("--dry-run", action="store_true", help="run gates but publish nothing")
    parser.add_argument(
        "--force", action="store_true", help="re-gate even if the SHA was already gated"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token, source = load_token()
    if not token:
        print(
            "FATAL: no GitHub token found. Looked in env "
            f"{TOKEN_VARS} and {[str(p) for p in TOKEN_FILES]}, then gh.",
            file=sys.stderr,
        )
        return 2

    if args.check_auth:
        return check_auth(token, source)

    try:
        prs = list_open_prs(token, args.limit if not args.pr else 100)
    except RuntimeError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    if args.pr:
        prs = [p for p in prs if p.number == args.pr]
        if not prs:
            print(f"FATAL: PR #{args.pr} is not open", file=sys.stderr)
            return 1

    state = load_state()
    gated: dict[str, Any] = state.setdefault("gated", {})

    todo: list[PRInfo] = []
    for pr in prs:
        if not args.force and pr.head_sha in gated:
            continue
        todo.append(pr)

    if args.list_prs:
        print(f"open PRs: {len(prs)} | need gating: {len(todo)}")
        for pr in prs:
            mark = "TODO" if pr in todo else "done"
            print(
                f"  [{mark}] #{pr.number:<4} {pr.head_sha[:10]}  "
                f"{pr.head_ref[:44]:<44} {pr.title[:40]}"
            )
        print(f"\ntoken source: {source}")
        return 0

    if not args.once and not args.pr:
        parser.print_help()
        return 0

    if not todo:
        summary = {"considered": len(prs), "gated": 0, "skipped": len(prs), "dry_run": args.dry_run}
        print(
            json.dumps(summary, indent=2)
            if args.json
            else f"nothing to do — all {len(prs)} PR(s) already gated"
        )
        return 0

    started = time.time()
    results: list[PRResult] = []
    for pr in todo:
        print(f"==> #{pr.number} {pr.head_sha[:10]} ({pr.title[:50]})")
        result = gate_one(pr, token, args.dry_run)
        results.append(result)
        print(
            f"    conclusion={result.conclusion} "
            f"statuses={len(result.statuses)} action={result.action}"
        )
        if not args.dry_run and result.action == "gated":
            gated[pr.head_sha] = {
                "pr": pr.number,
                "conclusion": result.conclusion,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            save_state(state)

    summary: dict[str, Any] = {
        "considered": len(prs),
        "gated": len(results),
        "skipped": len(prs) - len(todo),
        "dry_run": args.dry_run,
        "duration_s": round(time.time() - started, 1),
        "token_source": source,
        "results": [
            {
                "pr": r.number,
                "sha": r.sha[:12],
                "conclusion": r.conclusion,
                "action": r.action,
                "statuses": r.statuses,
            }
            for r in results
        ],
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("-" * 68)
        for r in results:
            print(f"  #{r.number:<4} {r.conclusion:<8} {r.action}")
            for s in r.statuses:
                if "context" in s:
                    print(f"         {s['state']:<8} {s['context']}: " f"{s['description']}")
        print(f"gated {len(results)}, skipped {summary['skipped']}, " f"{summary['duration_s']}s")

    return 0 if all(r.action == "gated" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
