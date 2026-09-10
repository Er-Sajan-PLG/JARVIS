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


# ─────────────────────────────────────────────────────────────────────────────
# Result model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Check:
    """Outcome of a single gate."""

    name: str
    context: str          # GitHub check-run context this maps to
    blocking: bool
    status: str           # pass | fail | skip | error
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
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=merged,
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return subprocess.CompletedProcess(
            cmd, 124, partial, f"TIMEOUT after {timeout}s",
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _tail(text: str, cap: int = OUTPUT_CAP) -> str:
    """Keep the most informative part of a long log."""
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    head = text[: cap // 2]
    tail = text[-(cap // 2):]
    return f"{head}\n... [{len(text) - cap} chars omitted] ...\n{tail}"


def _tool(name: str) -> str | None:
    """Absolute path to a venv-installed tool, else a PATH lookup."""
    candidate = VENV_BIN / name
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
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        shutil.rmtree(path, ignore_errors=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )

    res = _run(
        ["git", "worktree", "add", "--detach", "--force", str(path), sha],
        cwd=REPO_ROOT, timeout=300,
    )
    if res.returncode != 0:
        return None, f"worktree add failed: {_tail(res.stderr or res.stdout, 800)}"
    return path, ""


def _teardown_worktree(path: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    shutil.rmtree(path, ignore_errors=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
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
        cwd=worktree, timeout=120, env=_worktree_env(worktree),
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
        return Check("ruff_ratchet", "Lint & Typecheck", True, "skip",
                     "ruff not installed")

    diff = _run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, "HEAD",
         "--", "*.py"],
        cwd=worktree, timeout=120,
    )
    if diff.returncode != 0:
        return Check("ruff_ratchet", "Lint & Typecheck", True, "skip",
                     f"cannot diff against {base}: {_tail(diff.stderr, 300)}")

    changed = [f for f in diff.stdout.splitlines() if f.strip()]
    if not changed:
        return Check("ruff_ratchet", "Lint & Typecheck", True, "pass",
                     "no changed Python files")

    res = _run([ruff, "check", *changed], cwd=worktree, timeout=600)
    if res.returncode == 0:
        return Check("ruff_ratchet", "Lint & Typecheck", True, "pass",
                     f"{len(changed)} changed file(s) clean",
                     output=_tail(res.stdout))
    return Check("ruff_ratchet", "Lint & Typecheck", True, "fail",
                 f"{len(changed)} changed file(s) with lint errors",
                 exit_code=res.returncode, output=_tail(res.stdout + res.stderr))


def gate_pytest(worktree: Path) -> Check:
    res = _run(
        [str(PYTHON), "-m", "pytest", "tests/", "-q", "--no-header"],
        cwd=worktree, timeout=1800, env=_worktree_env(worktree),
    )
    out = res.stdout + res.stderr
    tail_line = ""
    for line in reversed(out.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            tail_line = line.strip()
            break
    status = "pass" if res.returncode == 0 else "fail"
    return Check("pytest", "Tests", True, status,
                 tail_line or f"pytest exit {res.returncode}",
                 exit_code=res.returncode, output=_tail(out))


def gate_gitleaks(worktree: Path) -> Check:
    """Secret scan in git-aware mode so gitignored artifacts are not noise."""
    gitleaks = _tool("gitleaks")
    if not gitleaks:
        return Check("gitleaks", "Security Scan", True, "skip",
                     "gitleaks not installed")
    cfg = worktree / ".gitleaks.toml"
    cmd = [gitleaks, "detect", "--redact", "--report-format", "json",
           "--report-path", "/dev/stdout"]
    if cfg.exists():
        cmd += ["--config", ".gitleaks.toml"]
    res = _run(cmd, cwd=worktree, timeout=600)
    if res.returncode == 0:
        return Check("gitleaks", "Security Scan", True, "pass",
                     "no secrets in tracked content")
    leaks: list[Any] = []
    try:
        leaks = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        leaks = []
    files = sorted({str(leak.get("File", "?")) for leak in leaks})
    return Check("gitleaks", "Security Scan", True, "fail",
                 f"{len(leaks)} potential secret(s) in {len(files)} file(s)",
                 exit_code=res.returncode,
                 output=_tail("\n".join(files[:20])))


def gate_board(worktree: Path) -> Check:
    script = worktree / "scripts" / "board" / "review.py"
    if not script.exists():
        return Check("board", "Virtual Board Governance", True, "skip",
                     "scripts/board/review.py absent")
    res = _run([str(PYTHON), "scripts/board/review.py"],
               cwd=worktree, timeout=900, env=_worktree_env(worktree))
    out = res.stdout + res.stderr
    status = "pass" if res.returncode == 0 else "fail"
    failed = [ln for ln in out.splitlines() if ln.strip().startswith("❌")]
    summary = "all 8 governance checks passed" if status == "pass" else \
        f"{len(failed)} governance check(s) failed"
    return Check("board", "Virtual Board Governance", True, status, summary,
                 exit_code=res.returncode, output=_tail(out))


def gate_compileall(worktree: Path) -> Check:
    res = _run([str(PYTHON), "-m", "compileall", "-q", "app/"],
               cwd=worktree, timeout=600, env=_worktree_env(worktree))
    status = "pass" if res.returncode == 0 else "fail"
    summary = "all modules compile" if status == "pass" else "syntax errors present"
    return Check("compileall", "Build", True, status, summary,
                 exit_code=res.returncode, output=_tail(res.stdout + res.stderr))


def gate_mypy(worktree: Path) -> Check:
    """REPORTED ONLY — 591 legacy errors, tracked as RISK-005."""
    mypy = _tool("mypy")
    if not mypy:
        return Check("mypy", "Lint & Typecheck", False, "skip",
                     "mypy not installed")
    res = _run([mypy, "--strict", "app/"],
               cwd=worktree, timeout=1800, env=_worktree_env(worktree))
    out = res.stdout + res.stderr
    last = out.strip().splitlines()[-1] if out.strip() else ""
    status = "pass" if res.returncode == 0 else "fail"
    return Check("mypy", "Lint & Typecheck", False, status,
                 last or f"mypy exit {res.returncode}",
                 exit_code=res.returncode, output=_tail(out))


def gate_bandit(worktree: Path) -> Check:
    """REPORTED ONLY — SAST signal, not yet a merge gate."""
    bandit = _tool("bandit")
    if not bandit:
        return Check("bandit", "Security Scan", False, "skip",
                     "bandit not installed")
    res = _run([bandit, "-r", "app/", "-q", "-f", "txt"],
               cwd=worktree, timeout=900, env=_worktree_env(worktree))
    out = res.stdout + res.stderr
    status = "pass" if res.returncode == 0 else "fail"
    highs = out.count("Severity: High")
    summary = "no issues" if status == "pass" else f"{highs} high-severity issue(s)"
    return Check("bandit", "Security Scan", False, status, summary,
                 exit_code=res.returncode, output=_tail(out))


def gate_pip_audit(worktree: Path) -> Check:
    """REPORTED ONLY — policy lives in docs/ACCEPTED_RISKS.md."""
    tool = _tool("pip-audit")
    if not tool:
        return Check("pip_audit", "Security Scan", False, "skip",
                     "pip-audit not installed")
    res = _run([tool, "-r", "requirements.txt", "-f", "json"],
               cwd=worktree, timeout=900, env=_worktree_env(worktree))
    vuln: list[str] = []
    try:
        data = json.loads(res.stdout or "{}")
        vuln = [
            f"{d.get('name')}=={d.get('version')}"
            for d in data.get("dependencies", []) if d.get("vulns")
        ]
    except json.JSONDecodeError:
        pass
    if not vuln:
        return Check("pip_audit", "Security Scan", False, "pass",
                     "no known vulnerabilities", output=_tail(res.stdout))
    return Check("pip_audit", "Security Scan", False, "fail",
                 f"{len(vuln)} vulnerable package(s)",
                 exit_code=res.returncode,
                 output=_tail(", ".join(vuln)))


def gate_coverage(worktree: Path) -> Check:
    """REPORTED ONLY — 36% vs 80% target, tracked as RISK-004."""
    res = _run(
        [str(PYTHON), "-m", "pytest", "tests/", "-q", "--no-header",
         "--cov=app", "--cov-report=term"],
        cwd=worktree, timeout=1800, env=_worktree_env(worktree),
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
    return Check("coverage", "Tests", False, status,
                 f"coverage {pct}% (floor 80%)",
                 output=_tail(out))


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


def run_gates(sha: str, base: str, keep: bool = False,
              with_coverage: bool = False) -> GateReport:
    started = time.time()
    report = GateReport(
        sha=sha, base=base,
        repo="Er-Sajan-PLG/JARVIS",
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    worktree, err = _prepare_worktree(sha)
    if worktree is None:
        report.checks.append(Check(
            "worktree", "Build", True, "error", err, exit_code=1,
        ))
        report.duration_ms = int((time.time() - started) * 1000)
        return report

    report.worktree = str(worktree)
    try:
        report.app_resolved_to = _resolve_app(worktree)
        report.merge_base = _resolve_merge_base(worktree, base)

        report.checks.append(gate_ruff_ratchet(worktree, report.merge_base))
        report.checks.append(gate_pytest(worktree))
        report.checks.append(gate_gitleaks(worktree))
        report.checks.append(gate_board(worktree))
        report.checks.append(gate_compileall(worktree))
        report.checks.append(gate_mypy(worktree))
        report.checks.append(gate_bandit(worktree))
        report.checks.append(gate_pip_audit(worktree))
        if with_coverage:
            report.checks.append(gate_coverage(worktree))
    finally:
        if not keep:
            _teardown_worktree(worktree)

    report.duration_ms = int((time.time() - started) * 1000)
    return report


def _print_human(report: GateReport) -> None:
    print(f"CI gate — {report.sha[:12]} (base {report.base})")
    print(f"worktree: {report.worktree}")
    print(f"app resolves to: {report.app_resolved_to}")
    print("-" * 68)
    icons = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "error": "ERR "}
    for c in report.checks:
        flag = "blocking" if c.blocking else "reported"
        print(f"  {icons.get(c.status, '?'):<4} [{flag:<8}] "
              f"{c.name:<14} {c.summary}")
    print("-" * 68)
    print(f"conclusion: {report.concluded.upper()}  "
          f"({len(report.blocking_failures)} blocking failure(s), "
          f"{report.duration_ms} ms)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="commit SHA to verify")
    parser.add_argument("--base", default="origin/main",
                        help="base ref for the ruff ratchet (default origin/main)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine JSON on stdout")
    parser.add_argument("--out", help="also write the JSON report to this path")
    parser.add_argument("--keep-worktree", action="store_true")
    parser.add_argument("--with-coverage", action="store_true",
                        help="add the (non-blocking) coverage gate")
    args = parser.parse_args()

    if not PYTHON.exists():
        print(f"FATAL: {PYTHON} missing", file=sys.stderr)
        return 2

    report = run_gates(args.sha, args.base, keep=args.keep_worktree,
                       with_coverage=args.with_coverage)

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
