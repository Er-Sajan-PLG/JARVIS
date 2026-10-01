#!/usr/bin/env python3
"""Local CI gate runner for JARVIS — the GitHub-Actions replacement.

Runs the repo's own gates against an ARBITRARY commit without touching the
primary working tree. It materialises the target commit in a detached git
worktree and executes every gate with that worktree as cwd, so ``import app``
resolves to the WORKTREE copy rather than the primary checkout.

Why this exists
---------------
GitHub Actions is unavailable for this private repo on the free tier: every
run dies in ~5s with an account-level billing block
("The job was not started because recent account payments have failed or your
spending limit needs to be increased"). Branch protection is also 403
("Upgrade to GitHub Pro or make this repository public"). Local n8n (Community,
which HAS the Execute Command node) is the automation control plane; this
script is the execution plane it invokes.

Blocking policy mirrors the intended GitHub branch-protection contexts
(see .github/workflows/ci.yml and docs/ACCEPTED_RISKS.md):
  BLOCKING      ruff ratchet, pytest, gitleaks, board governance, compileall
  REPORTED ONLY mypy (RISK-005), coverage floor (RISK-004), bandit, pip-audit
A non-blocking gate that fails does NOT fail the run — but it is still reported
with status "fail" so it can never be mistaken for a pass.

Usage
-----
  scripts/ci_gate.py --sha <commit>                 # human summary
  scripts/ci_gate.py --sha <commit> --json          # machine JSON on stdout
  scripts/ci_gate.py --sha <commit> --base origin/main
  scripts/ci_gate.py --sha <commit> --keep-worktree
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_BIN = REPO_ROOT / ".venv" / "bin"
PYTHON = VENV_BIN / "python"
WORKTREE_BASE = Path("/tmp/jarvis-ci-gate")
OUTPUT_CAP = 4000

# SOTA scanners live in an ISOLATED venv/bin so the project's pinned .venv is never
# disturbed by their (heavy) dependency trees. Evidence artifacts land in artifacts/.
TOOLS_HOME = Path.home() / ".local" / "share" / "jarvis-ci-tools"

# When True, a BLOCKING gate whose scanner is absent is a failure instead of a
# skip. Off by default so a developer machine missing one tool still gets an
# honest "skip"; CI passes --require-tools, because a required status check that
# goes green while enforcing nothing is worse than no check at all.
REQUIRE_TOOLS = False

# When True, provenance is signed keylessly via the ambient OIDC token (Fulcio
# certificate + Rekor transparency-log entry) instead of the local keypair. Set by
# --keyless or JARVIS_COSIGN_KEYLESS=1, which CI does: a runner cannot hold the
# developer's signing key, and pasting it into a repo secret would put a
# long-lived signing key next to a public repository. Keyless also lifts
# provenance from SLSA L1 to L2/L3, since the record becomes publicly auditable.
KEYLESS = False

# Identity a keyless signature must carry to be accepted. The default is this
# repository's own workflow, so verifying a bundle proves "this repo's CI signed
# it" rather than "some Fulcio certificate signed it" -- any GitHub workflow in
# any repository can obtain one of those.
KEYLESS_ISSUER = os.environ.get(
    "JARVIS_COSIGN_OIDC_ISSUER", "https://token.actions.githubusercontent.com"
)
KEYLESS_IDENTITY = os.environ.get(
    "JARVIS_COSIGN_IDENTITY",
    "https://github.com/Er-Sajan-PLG/JARVIS/.github/workflows/ci-gate.yml@refs/heads/main",
)
TOOLS_VENV_BIN = TOOLS_HOME / "venv" / "bin"
ARTIFACT_DIR = REPO_ROOT / "artifacts"


# ─────────────────────────────────────────────────────────────────────────────
# Result model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Check:
    """Outcome of a single gate."""

    name: str
    context: str  # GitHub check-run context this maps to
    blocking: bool
    status: str  # pass | fail | skip | error
    summary: str
    exit_code: int = 0
    duration_ms: int = 0
    output: str = ""

    @property
    def failed(self) -> bool:
        return self.status in ("fail", "error")


@dataclass
class GateReport:
    sha: str
    base: str
    repo: str
    started_at: str
    merge_base: str = ""
    duration_ms: int = 0
    worktree: str = ""
    app_resolved_to: str = ""
    checks: list[Check] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)

    @property
    def blocking_failures(self) -> list[Check]:
        return [c for c in self.checks if c.blocking and c.failed]

    @property
    def concluded(self) -> str:
        if not self.checks:
            return "failure"
        if self.blocking_failures:
            return "failure"
        return "success"


# ─────────────────────────────────────────────────────────────────────────────
# Process helpers
# ─────────────────────────────────────────────────────────────────────────────


def _run(
    cmd: list[str],
    cwd: Path,
    timeout: int = 1800,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, never raising on non-zero exit."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged,
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return subprocess.CompletedProcess(
            cmd,
            124,
            partial,
            f"TIMEOUT after {timeout}s",
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _tail(text: str, cap: int = OUTPUT_CAP) -> str:
    """Keep the most informative part of a long log."""
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    head = text[: cap // 2]
    tail = text[-(cap // 2) :]
    return f"{head}\n... [{len(text) - cap} chars omitted] ...\n{tail}"


def _tool(name: str) -> str | None:
    """Absolute path to a venv-installed tool, else a PATH lookup.

    Resolution order: the project venv (ruff, mypy, bandit, pip-licenses), then the
    isolated scanner venv (semgrep, mutmut, cyclonedx-py), then PATH (gitleaks, trivy,
    syft, cosign, hadolint, trufflehog, osv-scanner).
    """
    for candidate in (VENV_BIN / name, TOOLS_VENV_BIN / name):
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


# ─────────────────────────────────────────────────────────────────────────────
# Worktree lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def _worktree_path(sha: str) -> Path:
    return WORKTREE_BASE / sha[:12]


def _prepare_worktree(sha: str) -> tuple[Path | None, str]:
    """Create a detached worktree at ``sha``. Returns (path, error)."""
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    path = _worktree_path(sha)

    # Clear any leftover from a crashed previous run.
    if path.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        shutil.rmtree(path, ignore_errors=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    res = _run(
        ["git", "worktree", "add", "--detach", "--force", str(path), sha],
        cwd=REPO_ROOT,
        timeout=300,
    )
    if res.returncode != 0:
        return None, f"worktree add failed: {_tail(res.stderr or res.stdout, 800)}"
    return path, ""


def _teardown_worktree(path: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    shutil.rmtree(path, ignore_errors=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _worktree_env(worktree: Path) -> dict[str, str]:
    """Force imports to resolve to the worktree copy, deterministically.

    ``python -m`` puts cwd first on sys.path, but an editable install of the
    primary repo also contributes a path hook. PYTHONPATH makes the worktree
    win unconditionally and removes ambiguity.
    """
    return {"PYTHONPATH": str(worktree), "PYTHONDONTWRITEBYTECODE": "1"}


def _resolve_app(worktree: Path) -> str:
    """Prove which ``app`` package the interpreter will import."""
    res = _run(
        [str(PYTHON), "-c", "import app, sys; print(app.__file__)"],
        cwd=worktree,
        timeout=120,
        env=_worktree_env(worktree),
    )
    if res.returncode != 0:
        return f"<import failed: {_tail(res.stderr, 300)}>"
    return res.stdout.strip()


def _resolve_merge_base(worktree: Path, base: str) -> str:
    """Return the fork point of ``base`` and HEAD — the correct ratchet base.

    Diffing the branch tip against ``base`` directly is WRONG: when the branch
    was cut from an older main (every Dependabot PR), the diff also contains
    main's own newer commits, so unrelated files get linted. CI ratchets are
    defined over the fork point (three-dot semantics), so resolve it here and
    fall back to ``base`` only if merge-base cannot be computed.
    """
    res = _run(["git", "merge-base", base, "HEAD"], cwd=worktree, timeout=120)
    resolved = res.stdout.strip()
    if res.returncode == 0 and resolved:
        return resolved
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Gates
# ─────────────────────────────────────────────────────────────────────────────


def gate_ruff_ratchet(worktree: Path, base: str) -> Check:
    """Ruff on files changed vs ``base`` — the legacy debt is out of scope."""
    ruff = _tool("ruff")
    if not ruff:
        return Check("ruff_ratchet", "Lint & Typecheck", True, "skip", "ruff not installed")

    diff = _run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, "HEAD", "--", "*.py"],
        cwd=worktree,
        timeout=120,
    )
    if diff.returncode != 0:
        return Check(
            "ruff_ratchet",
            "Lint & Typecheck",
            True,
            "skip",
            f"cannot diff against {base}: {_tail(diff.stderr, 300)}",
        )

    changed = [f for f in diff.stdout.splitlines() if f.strip()]
    if not changed:
        return Check("ruff_ratchet", "Lint & Typecheck", True, "pass", "no changed Python files")

    res = _run([ruff, "check", *changed], cwd=worktree, timeout=600)
    if res.returncode == 0:
        return Check(
            "ruff_ratchet",
            "Lint & Typecheck",
            True,
            "pass",
            f"{len(changed)} changed file(s) clean",
            output=_tail(res.stdout),
        )
    return Check(
        "ruff_ratchet",
        "Lint & Typecheck",
        True,
        "fail",
        f"{len(changed)} changed file(s) with lint errors",
        exit_code=res.returncode,
        output=_tail(res.stdout + res.stderr),
    )


def gate_pytest(worktree: Path) -> Check:
    res = _run(
        [str(PYTHON), "-m", "pytest", "tests/", "-q", "--no-header"],
        cwd=worktree,
        timeout=1800,
        env=_worktree_env(worktree),
    )
    out = res.stdout + res.stderr
    tail_line = ""
    for line in reversed(out.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            tail_line = line.strip()
            break
    status = "pass" if res.returncode == 0 else "fail"
    return Check(
        "pytest",
        "Tests",
        True,
        status,
        tail_line or f"pytest exit {res.returncode}",
        exit_code=res.returncode,
        output=_tail(out),
    )


def gate_gitleaks(worktree: Path) -> Check:
    """Secret scan in git-aware mode so gitignored artifacts are not noise."""
    gitleaks = _tool("gitleaks")
    if not gitleaks:
        return Check("gitleaks", "Security Scan", True, "skip", "gitleaks not installed")
    cfg = worktree / ".gitleaks.toml"
    cmd = [
        gitleaks,
        "detect",
        "--redact",
        "--report-format",
        "json",
        "--report-path",
        "/dev/stdout",
    ]
    if cfg.exists():
        cmd += ["--config", ".gitleaks.toml"]
    res = _run(cmd, cwd=worktree, timeout=600)
    if res.returncode == 0:
        return Check("gitleaks", "Security Scan", True, "pass", "no secrets in tracked content")
    leaks: list[Any] = []
    try:
        leaks = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        leaks = []
    files = sorted({str(leak.get("File", "?")) for leak in leaks})
    return Check(
        "gitleaks",
        "Security Scan",
        True,
        "fail",
        f"{len(leaks)} potential secret(s) in {len(files)} file(s)",
        exit_code=res.returncode,
        output=_tail("\n".join(files[:20])),
    )


def gate_board(worktree: Path) -> Check:
    script = worktree / "scripts" / "board" / "review.py"
    if not script.exists():
        return Check(
            "board", "Virtual Board Governance", True, "skip", "scripts/board/review.py absent"
        )
    res = _run(
        [str(PYTHON), "scripts/board/review.py"],
        cwd=worktree,
        timeout=900,
        env=_worktree_env(worktree),
    )
    out = res.stdout + res.stderr
    status = "pass" if res.returncode == 0 else "fail"
    failed = [ln for ln in out.splitlines() if ln.strip().startswith("❌")]
    summary = (
        "all 8 governance checks passed"
        if status == "pass"
        else f"{len(failed)} governance check(s) failed"
    )
    return Check(
        "board",
        "Virtual Board Governance",
        True,
        status,
        summary,
        exit_code=res.returncode,
        output=_tail(out),
    )


def gate_compileall(worktree: Path) -> Check:
    res = _run(
        [str(PYTHON), "-m", "compileall", "-q", "app/"],
        cwd=worktree,
        timeout=600,
        env=_worktree_env(worktree),
    )
    status = "pass" if res.returncode == 0 else "fail"
    summary = "all modules compile" if status == "pass" else "syntax errors present"
    return Check(
        "compileall",
        "Build",
        True,
        status,
        summary,
        exit_code=res.returncode,
        output=_tail(res.stdout + res.stderr),
    )


def gate_mypy(worktree: Path) -> Check:
    """ENFORCED CEILING — mypy --strict app/ may not get worse (RISK-005).

    This used to be `blocking=False` with the rationale "mypy stays CI-only
    until burn-down, CI flips to hard-enforce per sprint". Two problems with
    that, both raised by the owner:

      1. "Per sprint" was not a date. There is no dated sprint schedule in this
         repo, so the promise could never lapse, never be checked, and never
         fail. An accepted risk with an unverifiable deadline is an ignored risk.

      2. Reported-only means a PR could ADD type errors and still go green. The
         number only ever went up.

    A ratchet is the honest middle: the ceiling lives in
    `.governance/mypy_baseline.txt`, and this gate fails when the count RISES.
    Fixing the 494 legacy errors is NOT required here and is not the point --
    not adding to them is. Lower the baseline when you fix some (that is the
    only direction it may be edited without a recorded decision).

    If the baseline file is absent the gate degrades to reported-only rather
    than blocking every PR on a file someone forgot to commit.
    """
    mypy = _tool("mypy")
    if not mypy:
        return Check("mypy", "Lint & Typecheck", False, "skip", "mypy not installed")

    res = _run([mypy, "--strict", "app/"], cwd=worktree, timeout=1800, env=_worktree_env(worktree))
    out = res.stdout + res.stderr
    last = out.strip().splitlines()[-1] if out.strip() else ""

    m = re.search(r"Found (\d+) error", out)
    current = int(m.group(1)) if m else (0 if res.returncode == 0 else None)

    baseline_path = worktree / ".governance" / "mypy_baseline.txt"
    ceiling = None
    if baseline_path.is_file():
        for line in baseline_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ceiling = int(line)
                break

    if ceiling is None:
        return Check(
            "mypy",
            "Lint & Typecheck",
            False,
            "pass" if res.returncode == 0 else "fail",
            f"no baseline file; reported only. {last}",
            exit_code=res.returncode,
            output=_tail(out),
        )

    if current is None:
        return Check(
            "mypy",
            "Lint & Typecheck",
            True,
            "fail",
            f"mypy produced no parseable count (exit {res.returncode}): {last}",
            exit_code=res.returncode,
            output=_tail(out),
        )

    if current > ceiling:
        return Check(
            "mypy",
            "Lint & Typecheck",
            True,
            "fail",
            f"REGRESSION: {current} strict errors, ceiling is {ceiling} "
            f"(+{current - ceiling}). Fix the new ones, or record the raise in RISK-005.",
            exit_code=res.returncode,
            output=_tail(out),
        )

    detail = f"{current} strict errors (ceiling {ceiling})"
    if current < ceiling:
        detail += " — DOWN, lower the baseline to lock the gain"
    return Check("mypy", "Lint & Typecheck", True, "pass", detail, output=_tail(out))


def gate_bandit(worktree: Path) -> Check:
    """REPORTED ONLY — SAST signal, not yet a merge gate."""
    bandit = _tool("bandit")
    if not bandit:
        return Check("bandit", "Security Scan", False, "skip", "bandit not installed")
    res = _run(
        [bandit, "-r", "app/", "-q", "-f", "txt"],
        cwd=worktree,
        timeout=900,
        env=_worktree_env(worktree),
    )
    out = res.stdout + res.stderr
    status = "pass" if res.returncode == 0 else "fail"
    highs = out.count("Severity: High")
    summary = "no issues" if status == "pass" else f"{highs} high-severity issue(s)"
    return Check(
        "bandit",
        "Security Scan",
        False,
        status,
        summary,
        exit_code=res.returncode,
        output=_tail(out),
    )


def gate_pip_audit(worktree: Path) -> Check:
    """REPORTED ONLY — policy lives in docs/ACCEPTED_RISKS.md."""
    tool = _tool("pip-audit")
    if not tool:
        return Check("pip_audit", "Security Scan", False, "skip", "pip-audit not installed")
    res = _run(
        [tool, "-r", "requirements.txt", "-f", "json"],
        cwd=worktree,
        timeout=900,
        env=_worktree_env(worktree),
    )
    vuln: list[str] = []
    try:
        data = json.loads(res.stdout or "{}")
        vuln = [
            f"{d.get('name')}=={d.get('version')}"
            for d in data.get("dependencies", [])
            if d.get("vulns")
        ]
    except json.JSONDecodeError:
        pass
    if not vuln:
        return Check(
            "pip_audit",
            "Security Scan",
            False,
            "pass",
            "no known vulnerabilities",
            output=_tail(res.stdout),
        )
    return Check(
        "pip_audit",
        "Security Scan",
        False,
        "fail",
        f"{len(vuln)} vulnerable package(s)",
        exit_code=res.returncode,
        output=_tail(", ".join(vuln)),
    )


def gate_evals(worktree: Path) -> Check:
    """Run the eval suite (opt-in via --with-evals)."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/run_evals.py"],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return Check("evals", "Test", False, "pass", "eval suite passed", exit_code=0)
    return Check(
        "evals",
        "Test",
        False,
        "fail",
        f"eval suite failed:\n{result.stdout[:500]}",
        exit_code=result.returncode,
    )


def gate_coverage(worktree: Path) -> Check:
    """REPORTED ONLY — the gate reports 86% against the 80% floor (RISK-004 closed).

    Measured by running this gate with `--with-coverage` at HEAD on 2026-09-30:
    `coverage 86% (floor 80%)`. Branch measurement was added in the same change,
    so that figure is line+branch. For comparison, on the same tree: statement-only
    in the gate's worktree was 87%, and locally 88% statement-only / 86-87%
    line+branch. Quote a figure from a gate run, not from memory — this docstring
    previously claimed 98% and had drifted 11 points from the live command.

    Historically this reported ~36% and was tracked as RISK-004. That figure was
    stale; RISK-004 now carries the same 88% the gate measures. Still
    non-blocking on purpose: coverage moves as new code lands, and a floor
    breach should surface as a reported failure, not a build break.
    """
    res = _run(
        [
            str(PYTHON),
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--no-header",
            "--cov=app",
            "--cov-branch",
            "--cov-report=term",
        ],
        cwd=worktree,
        timeout=1800,
        env=_worktree_env(worktree),
    )
    out = res.stdout + res.stderr
    pct = 0
    for line in out.splitlines():
        if line.strip().startswith("TOTAL"):
            parts = line.split()
            for tok in reversed(parts):
                if tok.endswith("%"):
                    pct = int(tok.rstrip("%"))
                    break
            break
    status = "pass" if pct >= 80 else "fail"
    return Check(
        "coverage", "Tests", False, status, f"coverage {pct}% (floor 80%)", output=_tail(out)
    )


# ── Conventional Commits (mirrors commitlint.config.cjs + the Actions job) ─────
# commitlint.config.cjs pins type-enum=[feat, fix, docs, style, refactor, perf, test,
# chore, revert], header-max-length=100, and subject-case=never[sentence-case,
# start-case, pascal-case, upper-case]. Implemented in Python so the gate needs no Node.
CONVENTIONAL_TYPES = frozenset(
    {
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "chore",
        "revert",
    }
)
_CONVENTIONAL_HEADER = re.compile(r"^(\w+)(?:\(([^)]+)\))?(!)?:\s(\S.*)$")
_HEADER_MAX = 100


def _conventional_problems(subject: str) -> list[str]:
    """Rule violations for a single commit subject ([] means compliant)."""
    s = subject.strip()
    if s.startswith("Merge "):
        return []  # merge commits are exempt, as in the upstream lint action
    problems: list[str] = []
    if len(s) > _HEADER_MAX:
        problems.append(f"header is {len(s)} chars (max {_HEADER_MAX})")
    match = _CONVENTIONAL_HEADER.match(s)
    if match is None:
        problems.append("header must read `type(scope): subject`")
        return problems
    ctype, body = match.group(1), match.group(4)
    if ctype not in CONVENTIONAL_TYPES:
        allowed = ", ".join(sorted(CONVENTIONAL_TYPES))
        problems.append(f"type '{ctype}' is not allowed (allowed: {allowed})")
    if body.upper() == body and any(c.isalpha() for c in body):
        problems.append("subject is UPPER-CASE")
    elif body[:1].isupper():
        problems.append("subject starts capitalised (sentence/start/pascal-case)")
    if body.endswith("."):
        problems.append("subject must not end with a full stop")
    return problems


def gate_commitlint(worktree: Path, base: str) -> Check:
    """Blocking: every commit in base..HEAD must be a Conventional Commit."""
    res = _run(
        ["git", "log", "--no-merges", "--format=%H%x1f%s", "--max-count=250", f"{base}..HEAD"],
        cwd=worktree,
        timeout=120,
    )
    if res.returncode != 0:
        return Check(
            "commitlint",
            "Conventional Commits",
            True,
            "skip",
            f"cannot list commits: {_tail(res.stderr, 300)}",
        )
    entries = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if not entries:
        return Check(
            "commitlint", "Conventional Commits", True, "pass", "no non-merge commits in range"
        )
    offenders: list[str] = []
    for line in entries:
        sha, _, subject = line.partition("\x1f")
        problems = _conventional_problems(subject)
        if problems:
            offenders.append(f"{sha[:10]}  {subject[:70]}\n    - " + "\n    - ".join(problems))
    if offenders:
        return Check(
            "commitlint",
            "Conventional Commits",
            True,
            "fail",
            f"{len(offenders)}/{len(entries)} commit(s) not Conventional Commits",
            exit_code=1,
            output=_tail("\n".join(offenders)),
        )
    return Check(
        "commitlint",
        "Conventional Commits",
        True,
        "pass",
        f"{len(entries)} commit(s) Conventional Commits",
    )


def gate_docker_build(worktree: Path) -> Check:
    """REPORTED ONLY: mirrors the `docker build` step of the Actions Build job.

    Opt-in (`--with-docker`): a cold image build costs minutes per PR and the gate is
    polled, so the compileall + worktree checks stay the blocking Build gates.
    """
    if not (worktree / "Dockerfile").is_file():
        return Check("docker_build", "Build", False, "skip", "no Dockerfile in tree")
    docker = shutil.which("docker")
    if docker is None:
        return Check("docker_build", "Build", False, "skip", "docker not on PATH")
    res = _run([docker, "build", "-t", "jarvis-ci-gate:local", "."], cwd=worktree, timeout=1800)
    if res.returncode != 0:
        return Check(
            "docker_build",
            "Build",
            False,
            "fail",
            "docker build failed (reported only)",
            exit_code=res.returncode,
            output=_tail(res.stdout + res.stderr),
        )
    return Check("docker_build", "Build", False, "pass", "docker image built (reported only)")


# ── SOTA supply-chain & static-analysis gates ─────────────────────────────────
# The gates below bring the local gate to parity with a modern supply-chain posture
# (SLSA v1.0 build levels, OpenSSF Scorecard, NIST SSDF PW.4/PW.7, CycloneDX SBOM,
# Sigstore signing, OWASP ASVS/SAMM verification). See docs/CI-GATE-SOTA.md for the
# element-by-element comparison and the evidence each gate emits.
#
# Exemptions are data-driven: docs/ACCEPTED_RISKS.md is parsed for accepted/deferred
# vulnerability IDs (CVE-*/PYSEC-*/GHSA-*) and package names, so a reviewed risk
# silences exactly that finding — and a lapsed entry resurfaces it.
_RISK_TOKEN_RE = re.compile(r"\b(CVE-\d{4}-\d{4,}|PYSEC-\d{4}-\d+|GHSA-[A-Za-z0-9-]+)\b")
_RISK_PKG_RE = re.compile(r"`([A-Za-z0-9][A-Za-z0-9_.\-]{2,})")

# Licenses that block a merge unless the package is named in the risk register.
DENIED_LICENSE_MARKERS = ("AGPL", "GPL-3", "GPL-2", "SSPL", "BUSL", "CC-BY-NC")


def _changed_files(worktree: Path, base: str) -> list[str]:
    """Files added/copied/modified/renamed by this branch (for ratchets)."""
    res = _run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        cwd=worktree,
        timeout=180,
    )
    if res.returncode != 0:
        return []
    return [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]


def _accepted_risk_tokens(worktree: Path) -> set[str]:
    """Vuln IDs + package names that docs/ACCEPTED_RISKS.md has reviewed (not resolved)."""
    path = worktree / "docs" / "ACCEPTED_RISKS.md"
    if not path.is_file():
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    tokens: set[str] = set()
    for line in text.splitlines():
        low = line.lower()
        if "|" not in line or "risk-" not in low or "resolved" in low:
            continue
        if not any(k in low for k in ("accepted", "deferred", "needs decision")):
            continue
        tokens.update(m.group(0).upper() for m in _RISK_TOKEN_RE.finditer(line))
        tokens.update(m.group(1).lower() for m in _RISK_PKG_RE.finditer(line))
    tokens.discard("risk")
    return tokens


def _missing_tool(tool: str, context: str, blocking: bool, why: str) -> Check:
    """A gate whose scanner is absent reports SKIP — never a silent pass.

    Except under ``--require-tools``, where a missing tool that the gate marked
    ``blocking=True`` becomes a FAILURE. ``Check.failed`` is
    ``status in ("fail", "error")``, so a skip contributes nothing to
    ``blocking_failures``: the run concluded ``success`` while the check made no
    claim. In CI that turns a required status check green while enforcing
    nothing, which is indistinguishable from a real pass.
    """
    if blocking and REQUIRE_TOOLS:
        return Check(
            tool,
            context,
            True,
            "fail",
            f"{tool} unavailable and --require-tools is set — {why}",
        )
    return Check(tool, context, blocking, "skip", f"{tool} unavailable — {why}")


def gate_semgrep(worktree: Path, base: str) -> Check:
    """SAST (ratchet): semgrep ERROR-severity findings in the files this PR touches."""
    exe = _tool("semgrep")
    if exe is None:
        return _missing_tool("semgrep", "SAST", True, "not installed")
    # Only scan files that still exist. ``_changed_files`` lists deletions too,
    # and semgrep answers a deleted path by aborting the whole run with
    # "Invalid scanning root" (exit 2). Because a non-zero exit is reported as
    # status="skip" and ``blocking_failures`` only counts "fail", a PR that
    # deleted any .py file silently disabled this check. Every file that still
    # exists is still scanned.
    changed = [
        f for f in _changed_files(worktree, base) if f.endswith(".py") and (worktree / f).is_file()
    ]
    if not changed:
        return Check("semgrep", "SAST", True, "pass", "no changed python files")
    res = _run(
        [
            exe,
            "scan",
            "--config=p/default",
            "--severity=ERROR",
            "--error",
            "--json",
            "--quiet",
            "--timeout=60",
            # Cap parallelism. semgrep-core uses Eio over io_uring, and each
            # worker allocates an io_uring queue that counts against RLIMIT_MEMLOCK
            # -- which is 8 MB here and cannot be raised without privilege. With
            # the default (= one worker per core, 20 on this machine) the
            # allocation fails with "Unix_error: Cannot allocate memory
            # io_uring_queue_init" and the whole scan aborts, which is what made
            # this check report "did not complete" on every run. Measured on the
            # 11-file changed set: default 1/5 runs completed, --jobs=4 3/3.
            "--jobs=4",
            *changed,
        ],
        cwd=worktree,
        timeout=1200,
        env={"SEMGREP_SEND_METRICS": "off", "SEMGREP_ENABLE_VERSION_CHECK": "0"},
    )
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    findings = data.get("results", []) or []
    errors = data.get("errors", []) or []
    if findings:
        lines = [
            f"{f.get('path')}:{(f.get('start') or {}).get('line')} "
            f"[{f.get('check_id')}] "
            f"{str((f.get('extra') or {}).get('message', ''))[:140]}"
            for f in findings[:25]
        ]
        return Check(
            "semgrep",
            "SAST",
            True,
            "fail",
            f"{len(findings)} error-severity finding(s) in changed file(s)",
            exit_code=1,
            output=_tail("\n".join(lines)),
        )
    if res.returncode == 0:
        return Check(
            "semgrep",
            "SAST",
            True,
            "pass",
            f"0 error-severity findings in {len(changed)} changed file(s)",
        )
    detail = _tail(res.stderr, 500) or f"exit {res.returncode}"
    if errors:
        detail += f"\nrule errors: {len(errors)}"
    # A blocking check that CANNOT RUN is a failure, not a skip. A skip is not
    # "failed", and Report.blocking_failures only counts failed checks, so
    # returning "skip" here meant a broken scanner silently disabled the gate:
    # this check reported PASS on origin/main with the reason "no changed python
    # files", and whenever it did find files it aborted with the io_uring error
    # and skipped instead of failing. Nothing is enforced by a gate that can
    # decide it did not run. The scanner is now capped at --jobs=4 so it
    # completes; if it still cannot, the run must stop here.
    return Check(
        "semgrep",
        "SAST",
        True,
        "fail",
        f"semgrep did not complete and cannot be skipped — {detail}",
        exit_code=res.returncode,
    )


def gate_trivy_fs(worktree: Path) -> Check:
    """SCA + IaC misconfig: trivy filesystem scan (CRITICAL/HIGH block the merge)."""
    exe = _tool("trivy")
    if exe is None:
        return _missing_tool("trivy", "Supply Chain", True, "not installed")
    res = _run(
        [
            exe,
            "fs",
            "--quiet",
            "--scanners",
            "vuln,misconfig",
            "--severity",
            "CRITICAL,HIGH",
            "--format",
            "json",
            ".",
        ],
        cwd=worktree,
        timeout=1800,
    )
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return Check(
            "trivy",
            "Supply Chain",
            True,
            "skip",
            f"trivy produced no JSON — {_tail(res.stderr, 400)}",
        )
    accepted = _accepted_risk_tokens(worktree)
    blocking_hits: list[str] = []
    accepted_hits: list[str] = []
    for result in data.get("Results") or []:
        target = result.get("Target", "?")
        for v in result.get("Vulnerabilities") or []:
            vid = (v.get("VulnerabilityID") or "").upper()
            pkg = (v.get("PkgName") or "").lower()
            line = (
                f"{target}: {vid} {v.get('PkgName')} "
                f"{v.get('InstalledVersion')} -> {v.get('FixedVersion') or 'no fix'} "
                f"[{v.get('Severity')}]"
            )
            if vid in accepted or pkg in accepted:
                accepted_hits.append(line)
            else:
                blocking_hits.append(line)
        for m in result.get("Misconfigurations") or []:
            if (m.get("Severity") or "").upper() in ("CRITICAL", "HIGH"):
                blocking_hits.append(
                    f"{target}: [{m.get('Severity')}] {m.get('ID')} {m.get('Title')}"
                )
    if blocking_hits:
        body = "\n".join(blocking_hits[:25])
        if accepted_hits:
            body += "\n\n(acknowledged in ACCEPTED_RISKS.md, not blocking:)\n" + "\n".join(
                accepted_hits[:10]
            )
        return Check(
            "trivy",
            "Supply Chain",
            True,
            "fail",
            f"{len(blocking_hits)} CRITICAL/HIGH finding(s)",
            exit_code=1,
            output=_tail(body),
        )
    note = f"0 blocking CRITICAL/HIGH (accepted: {len(accepted_hits)})"
    return Check("trivy", "Supply Chain", True, "pass", note)


def gate_licenses(worktree: Path) -> Check:
    """License compliance: deny copyleft licenses unless reviewed in the risk register."""
    exe = _tool("pip-licenses")
    if exe is None:
        return _missing_tool("licenses", "Supply Chain", True, "pip-licenses not installed")
    res = _run(
        [str(PYTHON), str(exe), "--format=json", "--with-urls"],
        cwd=worktree,
        timeout=600,
    )
    try:
        pkgs = json.loads(res.stdout or "")
    except json.JSONDecodeError:
        return Check(
            "licenses",
            "Supply Chain",
            True,
            "skip",
            f"pip-licenses produced no JSON — {_tail(res.stderr or res.stdout, 300)}",
        )
    if not pkgs:
        return Check(
            "licenses",
            "Supply Chain",
            True,
            "skip",
            "pip-licenses listed no packages — nothing was verified",
        )
    accepted = _accepted_risk_tokens(worktree)
    offenders: list[str] = []
    acknowledged: list[str] = []
    for p in pkgs:
        lic = str(p.get("License") or "")
        name = str(p.get("Name") or "")
        if not any(marker in lic.upper() for marker in DENIED_LICENSE_MARKERS):
            continue
        entry = f"{name} {p.get('Version')} — {lic}"
        if name.lower() in accepted:
            acknowledged.append(entry)
        else:
            offenders.append(entry)
    if offenders:
        body = "\n".join(offenders[:25])
        if acknowledged:
            body += "\n\n(acknowledged in ACCEPTED_RISKS.md, not blocking:)\n" + "\n".join(
                acknowledged[:10]
            )
        return Check(
            "licenses",
            "Supply Chain",
            True,
            "fail",
            f"{len(offenders)} unreviewed copyleft dependency(ies)",
            exit_code=1,
            output=_tail(body),
        )
    return Check(
        "licenses",
        "Supply Chain",
        True,
        "pass",
        f"{len(pkgs)} package(s) scanned; {len(acknowledged)} acknowledged",
    )


def gate_trufflehog(worktree: Path) -> Check:
    """Verified secret detection (second detector beside gitleaks)."""
    exe = _tool("trufflehog")
    if exe is None:
        return _missing_tool("trufflehog", "Security Scan", True, "not installed")
    res = _run(
        [
            exe,
            "git",
            f"file://{worktree}",
            "--results=verified",
            "--json",
            "--no-update",
            "--log-level=-1",
        ],
        cwd=worktree,
        timeout=900,
    )
    verified: list[str] = []
    for line in (res.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("Verified"):
            src = obj.get("SourceMetadata", {}).get("Data", {}).get("Git", {})
            verified.append(
                f"{src.get('file', '?')}:{src.get('line', '?')} "
                f"{obj.get('DetectorName', '?')} ({obj.get('DetectorType')})"
            )
    if verified:
        return Check(
            "trufflehog",
            "Security Scan",
            True,
            "fail",
            f"{len(verified)} VERIFIED secret(s) in git history",
            exit_code=1,
            output=_tail("\n".join(verified[:25])),
        )
    if res.returncode not in (0, 183):
        return Check(
            "trufflehog",
            "Security Scan",
            True,
            "skip",
            f"trufflehog did not complete — {_tail(res.stderr, 300)}",
        )
    return Check("trufflehog", "Security Scan", True, "pass", "no verified secrets")


def gate_osv(worktree: Path) -> Check:
    """OSV dependency scan (reported: pip-audit+trivy are the blocking SCA gates)."""
    exe = _tool("osv-scanner")
    if exe is None:
        return _missing_tool("osv", "Supply Chain", False, "not installed")
    res = _run([exe, "--format", "json", "--recursive", "."], cwd=worktree, timeout=1200)
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return Check(
            "osv",
            "Supply Chain",
            False,
            "skip",
            f"osv-scanner produced no JSON — {_tail(res.stderr, 300)}",
        )
    accepted = _accepted_risk_tokens(worktree)
    hits: list[str] = []
    for result in data.get("results") or []:
        for pkg in result.get("packages") or []:
            name = (pkg.get("package") or {}).get("name") or "?"
            for v in pkg.get("vulnerabilities") or []:
                vid = str(v.get("id") or "").upper()
                if vid in accepted or name.lower() in accepted:
                    continue
                hits.append(f"{name}: {vid} {str(v.get('summary') or '')[:100]}")
    status = "fail" if hits else "pass"
    return Check(
        "osv",
        "Supply Chain",
        False,
        status,
        f"{len(hits)} unreviewed OSV advisory(ies)" if hits else "no unreviewed advisories",
        exit_code=1 if hits else 0,
        output=_tail("\n".join(hits[:25])),
    )


def gate_sbom(worktree: Path) -> Check:
    """CycloneDX SBOM generation (evidence artifact; closes RISK-003)."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / f"sbom-{worktree.name}.cdx.json"
    exe = _tool("syft") or _tool("cyclonedx-py")
    if exe is None:
        return _missing_tool("sbom", "Supply Chain", False, "syft/cyclonedx not installed")
    if Path(exe).name.startswith("syft"):
        cmd = [exe, "dir:.", "-o", f"cyclonedx-json={out}", "--quiet"]
    else:
        cmd = [str(PYTHON), exe, "requirements", "--output-format", "JSON", "-o", str(out)]
    res = _run(cmd, cwd=worktree, timeout=900)
    if res.returncode != 0 or not out.is_file():
        return Check(
            "sbom",
            "Supply Chain",
            False,
            "skip",
            f"SBOM generation failed — {_tail(res.stderr or res.stdout, 300)}",
        )
    size = out.stat().st_size
    return Check(
        "sbom", "Supply Chain", False, "pass", f"CycloneDX SBOM written ({size} bytes) -> {out}"
    )


def gate_provenance(worktree: Path, sha: str) -> Check:
    """SLSA-style provenance: build an in-toto statement and sign+verify it (cosign)."""
    cosign = _tool("cosign")
    if cosign is None:
        return _missing_tool(
            "provenance", "Supply Chain", False, "cosign not installed (no signing material)"
        )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    key = TOOLS_HOME / "cosign.key"
    pub = TOOLS_HOME / "cosign.pub"
    pw = _signing_password()
    if not KEYLESS and (not key.exists() or not pub.exists()):
        return Check(
            "provenance",
            "Supply Chain",
            False,
            "skip",
            "no cosign keypair — run scripts/ci_gate.py --init-signing, or pass --keyless",
        )
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "jarvis", "digest": {"gitCommit": sha}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://jarvis.local/ci-gate@v1",
                "externalParameters": {"base": worktree.name, "sha": sha},
            },
            "runDetails": {
                "builder": {"id": "local://jarvis-ci-gate"},
                "metadata": {"invocationId": sha[:12]},
            },
        },
    }
    stmt_path = ARTIFACT_DIR / f"provenance-{sha[:12]}.intoto.json"
    stmt_path.write_text(json.dumps(statement, indent=2))
    bundle_path = ARTIFACT_DIR / f"provenance-{sha[:12]}.sigstore.json"
    sig_path = ARTIFACT_DIR / f"provenance-{sha[:12]}.sig"

    # cosign v3 requires --bundle (the detached --output-signature form is deprecated
    # and now hard-fails); fall back to the detached form for older cosign builds.
    # Keyless: cosign reads ACTIONS_ID_TOKEN_REQUEST_URL/_TOKEN from the ambient
    # environment, exchanges it for a Fulcio certificate, and records the entry in
    # the Rekor transparency log. No --key is passed -- that is what "keyless"
    # means, and passing one would defeat the identity binding.
    key_args = [] if KEYLESS else ["--key", str(key)]
    sign_res = _run(
        [
            cosign,
            "sign-blob",
            "--yes",
            *key_args,
            "--bundle",
            str(bundle_path),
            str(stmt_path),
        ],
        cwd=worktree,
        timeout=300,
        env={"COSIGN_PASSWORD": pw},
    )
    if sign_res.returncode == 0:
        verify_args = ["--bundle", str(bundle_path)]
        artifact = bundle_path.name
    else:
        sign_res = _run(
            [
                cosign,
                "sign-blob",
                "--yes",
                *key_args,
                "--output-signature",
                str(sig_path),
                str(stmt_path),
            ],
            cwd=worktree,
            timeout=300,
            env={"COSIGN_PASSWORD": pw},
        )
        verify_args = ["--signature", str(sig_path)]
        artifact = sig_path.name
    if sign_res.returncode != 0:
        return Check(
            "provenance",
            "Supply Chain",
            False,
            "fail",
            f"cosign sign-blob failed — {_tail(sign_res.stderr, 300)}",
            exit_code=sign_res.returncode,
        )
    # Keyless verification must pin BOTH the issuer and the workflow identity.
    # A bundle verified without --certificate-identity proves only that some
    # Fulcio certificate signed it, and any workflow in any repository can get
    # one. Pinning is what ties the provenance to this repository's CI.
    verify_auth = (
        [
            "--certificate-identity",
            KEYLESS_IDENTITY,
            "--certificate-oidc-issuer",
            KEYLESS_ISSUER,
        ]
        if KEYLESS
        else ["--key", str(pub)]
    )
    verify_res = _run(
        [cosign, "verify-blob", *verify_auth, *verify_args, str(stmt_path)],
        cwd=worktree,
        timeout=300,
    )
    if verify_res.returncode != 0:
        return Check(
            "provenance",
            "Supply Chain",
            False,
            "fail",
            f"signature verification FAILED — {_tail(verify_res.stderr, 300)}",
            exit_code=verify_res.returncode,
        )
    return Check(
        "provenance",
        "Supply Chain",
        False,
        "pass",
        f"SLSA provenance signed + verified ({artifact})",
    )


def gate_hadolint(worktree: Path) -> Check:
    """Dockerfile best-practice lint (blocks when a Dockerfile is present)."""
    dockerfile = worktree / "Dockerfile"
    if not dockerfile.is_file():
        return Check("hadolint", "Build", True, "skip", "no Dockerfile in tree")
    exe = _tool("hadolint")
    if exe is None:
        return _missing_tool("hadolint", "Build", True, "not installed")
    res = _run([exe, "--format", "json", "Dockerfile"], cwd=worktree, timeout=300)
    try:
        issues = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        issues = []
    if issues:
        lines = [f"{i.get('line')}: {i.get('code')} {i.get('message')}" for i in issues[:25]]
        return Check(
            "hadolint",
            "Build",
            True,
            "fail",
            f"{len(issues)} Dockerfile issue(s)",
            exit_code=1,
            output=_tail("\n".join(lines)),
        )
    return Check("hadolint", "Build", True, "pass", "Dockerfile clean")


def gate_contract(worktree: Path) -> Check:
    """Contract tests as a first-class blocking gate (interface stability)."""
    tests_dir = worktree / "tests" / "contract"
    if not tests_dir.is_dir():
        return Check("contract", "Tests", True, "skip", "no tests/contract directory")
    res = _run(
        [str(PYTHON), "-m", "pytest", "tests/contract", "-q", "-p", "no:cacheprovider"],
        cwd=worktree,
        timeout=1800,
        env={"PYTHONPATH": str(worktree)},
    )
    tail = (res.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else f"exit {res.returncode}"
    if res.returncode != 0:
        return Check(
            "contract",
            "Tests",
            True,
            "fail",
            f"contract tests failed — {summary[:160]}",
            exit_code=res.returncode,
            output=_tail(res.stdout + res.stderr),
        )
    return Check("contract", "Tests", True, "pass", summary[:160])


def gate_docs(worktree: Path) -> Check:
    """Documentation gate: structure (check_docs.py) + factual drift (sync_doc_facts.py).

    Two distinct failure modes, both blocking:

    1. **Structure** — missing status header, stub table, a path that does not
       exist, a version pinned in a living doc's title.
    2. **Drift** — a number in a doc that no longer matches the repository
       ("22 checks" after gate 23 was added, "1028 passed" after 1063). Structure
       checks cannot see this, which is why both halves exist: a document can be
       perfectly well-formed and still be lying.
    """
    script = worktree / "scripts" / "check_docs.py"
    if not script.is_file():
        return Check(
            "docs",
            "Virtual Board Governance",
            True,
            "skip",
            "scripts/check_docs.py absent",
        )
    res = _run(
        [str(PYTHON), str(script), "--strict"],
        cwd=worktree,
        timeout=300,
        env={"PYTHONPATH": str(worktree)},
    )
    out = (res.stdout or "") + (res.stderr or "")
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    summary = lines[0] if lines else f"exit {res.returncode}"
    if res.returncode != 0:
        # Surface the actual findings, not just a count.
        detail = [ln.strip() for ln in lines if ln.strip().startswith("-")]
        return Check(
            "docs",
            "Virtual Board Governance",
            True,
            "fail",
            f"documentation hygiene: {len(detail)} finding(s) — {summary[:120]}",
            exit_code=res.returncode,
            output=_tail("\n".join(detail[:40]) or out),
        )
    return Check("docs", "Virtual Board Governance", True, "pass", summary[:160])


def gate_doc_types(worktree: Path) -> Check:
    """Type contract gate: the documented contract must match the code.

    ``scripts/doc_types.py`` is the contract; ``docs/DOC-GOVERNANCE.md`` §10
    documents it. Two copies of the same table is precisely the drift this
    mechanism exists to prevent, so the table is generated and this gate fails when
    it disagrees. ``check_docs.py`` in ``gate_docs`` then enforces the contract
    against every document.
    """
    script = worktree / "scripts" / "doc_type_table.py"
    if not script.is_file():
        return Check(
            "doc_types",
            "Virtual Board Governance",
            True,
            "skip",
            "scripts/doc_type_table.py absent",
        )
    res = _run(
        [str(PYTHON), str(script), "--check"],
        cwd=worktree,
        timeout=120,
        env={"PYTHONPATH": str(worktree)},
    )
    out = ((res.stdout or "") + (res.stderr or "")).strip()
    summary = out.splitlines()[0] if out else f"exit {res.returncode}"
    if res.returncode != 0:
        return Check(
            "doc_types",
            "Virtual Board Governance",
            True,
            "fail",
            f"documented type contract is stale — {summary[:150]}",
            exit_code=res.returncode,
            output=_tail(out),
        )
    return Check("doc_types", "Virtual Board Governance", True, "pass", summary[:160])


def gate_doc_coverage(worktree: Path) -> Check:
    """Doc coverage gate: every code surface must be documented.

    ``scripts/check_doc_coverage.py`` computes three censuses from the live
    tree — module Source bindings, served routes vs API_CONTRACT.md, env vars
    vs CONFIG.md. Any finding fails, blocking the pipeline. This is the gate
    that makes "a feature with zero docs" impossible: unlike the structure
    and type gates, it measures code coverage, not doc hygiene.
    """
    script = worktree / "scripts" / "check_doc_coverage.py"
    if not script.is_file():
        return Check(
            "doc_coverage",
            "Virtual Board Governance",
            True,
            "skip",
            "scripts/check_doc_coverage.py absent",
        )
    res = _run(
        [str(PYTHON), str(script), "--strict"],
        cwd=worktree,
        timeout=180,
        env={"PYTHONPATH": str(worktree)},
    )
    out = ((res.stdout or "") + (res.stderr or "")).strip()
    summary = out.splitlines()[0] if out else f"exit {res.returncode}"
    if res.returncode != 0:
        return Check(
            "doc_coverage",
            "Virtual Board Governance",
            True,
            "fail",
            f"undocumented code surface — {summary[:150]}",
            exit_code=res.returncode,
            output=_tail(out),
        )
    return Check("doc_coverage", "Virtual Board Governance", True, "pass", summary[:160])


def gate_docs_layer2(worktree: Path) -> Check:
    """Autonomous docs Layer 2: manifest, markdown, spelling, snippets, generated.

    Runs scripts/docs/check-full.py (offline full-tree). Fails loudly with the
    first findings so authors see exactly which doc/line to fix. Network checks
    (external links) stay on the 15-day scheduled sweep by design.
    """
    script = worktree / "scripts" / "docs" / "check-full.py"
    if not script.is_file():
        return Check(
            "docs_layer2",
            "Virtual Board Governance",
            True,
            "skip",
            "scripts/docs/check-full.py absent",
        )
    res = _run(
        [str(PYTHON), str(script)],
        cwd=worktree,
        timeout=300,
        env={"PYTHONPATH": str(worktree)},
    )
    out = ((res.stdout or "") + (res.stderr or "")).strip()
    summary = out.splitlines()[-1] if out else f"exit {res.returncode}"
    if res.returncode != 0:
        detail = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("error:")]
        return Check(
            "docs_layer2",
            "Virtual Board Governance",
            True,
            "fail",
            f"layer2 docs: {len(detail)} error(s) — {summary[:120]}",
            exit_code=res.returncode,
            output=_tail("\n".join(detail[:40]) or out),
        )
    return Check("docs_layer2", "Virtual Board Governance", True, "pass", summary[:160])


def gate_doc_facts(worktree: Path, report: GateReport) -> Check:
    """Doc facts gate: every number a doc asserts must match the repository.

    Separate from gate_docs on purpose — this one is about *truth*, not form, and
    it fails when a doc is well-formed but wrong.

    Uses the authoritative fact snapshot from the gate's pytest/coverage results
    when available, avoiding a redundant pytest run. Falls back to
    ``--check --run-tests`` when invoked standalone.
    """
    script = worktree / "scripts" / "sync_doc_facts.py"
    if not script.is_file():
        return Check(
            "doc_facts",
            "Virtual Board Governance",
            True,
            "skip",
            "scripts/sync_doc_facts.py absent",
        )
    # Use stored facts from the gate's pytest/coverage results if available.
    if report.facts:
        res = _run(
            [
                str(PYTHON),
                str(script),
                "--check",
                "--facts-json",
                json.dumps(report.facts),
            ],
            cwd=worktree,
            timeout=300,
            env={"PYTHONPATH": str(worktree)},
        )
    else:
        res = _run(
            [str(PYTHON), str(script), "--check", "--run-tests"],
            cwd=worktree,
            timeout=300,
            env={"PYTHONPATH": str(worktree)},
        )
    out = (res.stdout or "") + (res.stderr or "")
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    summary = lines[0] if lines else f"exit {res.returncode}"
    if res.returncode != 0:
        detail = [ln.strip() for ln in lines if ln.strip().startswith("-")]
        return Check(
            "doc_facts",
            "Virtual Board Governance",
            True,
            "fail",
            f"documentation contradicts the code: {len(detail)} finding(s)",
            exit_code=res.returncode,
            output=_tail("\n".join(detail[:40]) or out),
        )
    return Check("doc_facts", "Virtual Board Governance", True, "pass", summary[:160])


def gate_mutation(worktree: Path) -> Check:
    """Mutation testing (opt-in `--with-mutation`): reported, and slow by design."""
    exe = _tool("mutmut")
    if exe is None:
        return _missing_tool("mutation", "Mutation Testing", False, "mutmut not installed")
    res = _run(
        [str(PYTHON), str(exe), "run", "--paths-to-mutate", "app/domain"],
        cwd=worktree,
        timeout=3600,
    )
    out = (res.stdout or "") + (res.stderr or "")
    killed = survived = None
    m = re.search(r"killed\s+(\d+).*?survived\s+(\d+)", out, re.S | re.I)
    if m:
        killed, survived = int(m.group(1)), int(m.group(2))
    if res.returncode != 0 and killed is None:
        return Check(
            "mutation",
            "Mutation Testing",
            False,
            "skip",
            f"mutmut did not complete — {_tail(out, 300)}",
        )
    if killed is not None and survived is not None:
        total = killed + survived
        score = 100.0 * killed / total if total else 0.0
        return Check(
            "mutation",
            "Mutation Testing",
            False,
            "pass",
            f"mutation score {score:.1f}% ({killed} killed / {survived} survived)",
        )
    return Check("mutation", "Mutation Testing", False, "pass", "mutmut completed")


def gate_checkov(worktree: Path) -> Check:
    """IaC / config misconfiguration scan (reported). Skips when there is no IaC."""
    iac_globs = ("*.tf", "*.yaml", "*.yml", "Dockerfile", "docker-compose*.yml")
    candidates: list[str] = []
    for glob in iac_globs:
        for p in sorted(worktree.glob(glob)):
            rel = str(p.relative_to(worktree))
            if rel.startswith((".git/", ".venv/", "node_modules/")):
                continue
            candidates.append(rel)
    if not candidates:
        return Check("checkov", "Supply Chain", False, "skip", "no IaC files in tree")
    exe = _tool("checkov")
    if exe is None:
        return _missing_tool("checkov", "Supply Chain", False, "not installed")
    res = _run(
        [str(PYTHON), str(exe), "-d", ".", "--compact", "--quiet", "--output", "json"],
        cwd=worktree,
        timeout=1800,
    )
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return Check(
            "checkov",
            "Supply Chain",
            False,
            "skip",
            f"checkov produced no JSON — {_tail(res.stderr, 300)}",
        )
    failed = 0
    if isinstance(data, dict):
        summary = data.get("summary", {}) or {}
        failed = int(summary.get("failed", 0) or 0)
    elif isinstance(data, list):
        for entry in data:
            failed += int((entry.get("summary") or {}).get("failed", 0) or 0)
    status = "fail" if failed else "pass"
    return Check(
        "checkov",
        "Supply Chain",
        False,
        status,
        f"{failed} IaC check(s) failed" if failed else "no IaC misconfigurations",
        exit_code=1 if failed else 0,
    )


def _signing_password() -> str:
    """Password for the local cosign key: env var, else the 0600 file beside the key."""
    pw = os.environ.get("COSIGN_PASSWORD", "")
    if pw:
        return pw
    path = TOOLS_HOME / "cosign.password"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _init_signing() -> int:
    """Create the local cosign keypair (private material stays OUTSIDE the repo)."""
    cosign = _tool("cosign")
    if cosign is None:
        print("FATAL: cosign not installed", file=sys.stderr)
        return 2
    TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    key = TOOLS_HOME / "cosign.key"
    pub = TOOLS_HOME / "cosign.pub"
    if key.exists() and pub.exists():
        print(f"keypair already present: {pub}")
        return 0
    pw = os.environ.get("COSIGN_PASSWORD") or secrets.token_urlsafe(24)
    res = _run(
        [cosign, "generate-key-pair", "--output-key-prefix", str(TOOLS_HOME / "cosign")],
        cwd=REPO_ROOT,
        timeout=180,
        env={"COSIGN_PASSWORD": pw},
    )
    if res.returncode != 0 or not key.exists():
        print(
            f"FATAL: key generation failed — {_tail(res.stderr or res.stdout, 400)}",
            file=sys.stderr,
        )
        return 2
    pw_file = TOOLS_HOME / "cosign.password"
    pw_file.write_text(pw)
    pw_file.chmod(0o600)
    print(
        f"created {key}\n        {pub}\npassword stored in {pw_file} (mode 0600, outside the repo)"
    )
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


def run_gates(
    sha: str,
    base: str,
    keep: bool = False,
    with_coverage: bool = False,
    with_docker: bool = False,
    with_mutation: bool = False,
    with_evals: bool = False,
) -> GateReport:
    started = time.time()
    report = GateReport(
        sha=sha,
        base=base,
        repo="Er-Sajan-PLG/JARVIS",
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    worktree, err = _prepare_worktree(sha)
    if worktree is None:
        report.checks.append(
            Check(
                "worktree",
                "Build",
                True,
                "error",
                err,
                exit_code=1,
            )
        )
        report.duration_ms = int((time.time() - started) * 1000)
        return report

    report.worktree = str(worktree)
    try:
        report.app_resolved_to = _resolve_app(worktree)
        report.merge_base = _resolve_merge_base(worktree, base)

        # ── static analysis & types ──────────────────────────────────────────
        report.checks.append(gate_ruff_ratchet(worktree, report.merge_base))
        report.checks.append(gate_semgrep(worktree, report.merge_base))
        report.checks.append(gate_mypy(worktree))
        # ── tests ────────────────────────────────────────────────────────────
        report.checks.append(gate_pytest(worktree))
        report.checks.append(gate_contract(worktree))
        # ── secrets & application security ───────────────────────────────────
        report.checks.append(gate_gitleaks(worktree))
        report.checks.append(gate_trufflehog(worktree))
        report.checks.append(gate_bandit(worktree))
        # ── supply chain (SCA / SBOM / licences / provenance) ────────────────
        report.checks.append(gate_pip_audit(worktree))
        report.checks.append(gate_trivy_fs(worktree))
        report.checks.append(gate_osv(worktree))
        report.checks.append(gate_licenses(worktree))
        report.checks.append(gate_sbom(worktree))
        report.checks.append(gate_provenance(worktree, sha))
        # ── governance & build ──────────────────────────────────────────────
        report.checks.append(gate_board(worktree))
        report.checks.append(gate_docs(worktree))
        report.checks.append(gate_doc_types(worktree))
        report.checks.append(gate_doc_coverage(worktree))
        report.checks.append(gate_docs_layer2(worktree))
        # Persist facts from pytest/coverage results BEFORE gate_doc_facts so it can reuse them.
        _persist_doc_facts(report)
        report.checks.append(gate_doc_facts(worktree, report))
        report.checks.append(gate_compileall(worktree))
        report.checks.append(gate_hadolint(worktree))
        report.checks.append(gate_checkov(worktree))
        report.checks.append(gate_commitlint(worktree, report.merge_base))
        # ── opt-in (heavy / ratcheted) ───────────────────────────────────────
        if with_coverage:
            report.checks.append(gate_coverage(worktree))
        if with_docker:
            report.checks.append(gate_docker_build(worktree))
        if with_mutation:
            report.checks.append(gate_mutation(worktree))
        if with_evals:
            report.checks.append(gate_evals(worktree))
    finally:
        if not keep:
            _teardown_worktree(worktree)

    report.duration_ms = int((time.time() - started) * 1000)
    _persist_doc_facts(report)
    return report


def _persist_doc_facts(report: GateReport) -> None:
    """Extract measured facts from the gate report and store them.

    `pytest` and `coverage` numbers are already measured by this gate. Persisting
    them means `scripts/sync_doc_facts.py` can resolve `test_count`/`coverage`
    without re-running the suite — so a doc can state "1063 passed" and stay true
    without anyone remembering to update it.

    The facts are stored both in the report (for gate_doc_facts to reuse) and in
    the ephemeral cache file (for local tooling optimization).
    """
    facts: dict[str, str] = {}
    for c in report.checks:
        text = f"{c.summary}\n{c.output or ''}"
        if c.name == "pytest":
            m = re.search(r"(\d+) passed", text)
            if m:
                facts["test_count"] = m.group(1)
        elif c.name == "coverage":
            m = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", text, re.M)
            if m:
                facts["coverage"] = m.group(1)
    if not facts:
        return
    # Store facts in the report for gate_doc_facts to reuse.
    report.facts.update(facts)
    # Also write to the ephemeral cache for local tooling.
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from doc_facts import _write_cache  # noqa: PLC0415

        _write_cache(facts)
    except Exception:  # noqa: BLE001 - never let bookkeeping break the gate
        pass


def _print_human(report: GateReport) -> None:
    print(f"CI gate — {report.sha[:12]} (base {report.base})")
    print(f"worktree: {report.worktree}")
    print(f"app resolves to: {report.app_resolved_to}")
    print("-" * 68)
    icons = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "error": "ERR "}
    for c in report.checks:
        flag = "blocking" if c.blocking else "reported"
        print(f"  {icons.get(c.status, '?'):<4} [{flag:<8}] " f"{c.name:<14} {c.summary}")
    print("-" * 68)
    print(
        f"conclusion: {report.concluded.upper()}  "
        f"({len(report.blocking_failures)} blocking failure(s), "
        f"{report.duration_ms} ms)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", default="", help="commit SHA to verify")
    parser.add_argument(
        "--base", default="origin/main", help="base ref for the ruff ratchet (default origin/main)"
    )
    parser.add_argument("--json", action="store_true", help="emit machine JSON on stdout")
    parser.add_argument("--out", help="also write the JSON report to this path")
    parser.add_argument("--keep-worktree", action="store_true")
    parser.add_argument(
        "--with-coverage", action="store_true", help="add the (non-blocking) coverage gate"
    )
    parser.add_argument(
        "--with-docker", action="store_true", help="add the (non-blocking) docker-build gate"
    )
    parser.add_argument(
        "--with-mutation", action="store_true", help="add the (non-blocking, slow) mutation gate"
    )
    parser.add_argument("--with-evals", action="store_true", help="add the eval suite gate")
    parser.add_argument(
        "--init-signing", action="store_true", help="create the local cosign keypair"
    )
    parser.add_argument(
        "--keyless",
        action="store_true",
        help="sign provenance keylessly via the ambient OIDC token (Fulcio + "
        "Rekor) instead of the local cosign keypair; used by CI",
    )
    parser.add_argument(
        "--require-tools",
        action="store_true",
        help="a BLOCKING gate whose scanner is absent fails instead of skipping; "
        "used by CI so a missing tool cannot turn a required check green",
    )

    args = parser.parse_args()

    if args.init_signing:
        return _init_signing()

    if not args.sha:
        parser.error("--sha is required (unless --init-signing is used)")

    if not PYTHON.exists():
        print(f"FATAL: {PYTHON} missing", file=sys.stderr)
        return 2

    global REQUIRE_TOOLS, KEYLESS
    REQUIRE_TOOLS = args.require_tools
    # An env var is accepted too: the workflow sets it once for every step, so a
    # future step that forgets --keyless cannot silently fall back to keyed mode.
    KEYLESS = args.keyless or os.environ.get("JARVIS_COSIGN_KEYLESS") == "1"

    report = run_gates(
        args.sha,
        args.base,
        keep=args.keep_worktree,
        with_coverage=args.with_coverage,
        with_docker=args.with_docker,
        with_mutation=args.with_mutation,
        with_evals=args.with_evals,
    )

    payload = asdict(report)
    payload["conclusion"] = report.concluded
    text = json.dumps(payload, indent=2)

    if args.out:
        Path(args.out).write_text(text)
    if args.json:
        print(text)
    else:
        _print_human(report)

    return 1 if report.blocking_failures else 0


if __name__ == "__main__":
    sys.exit(main())
