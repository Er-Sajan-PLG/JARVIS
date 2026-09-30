#!/usr/bin/env python3
"""Single source of truth for every machine-derivable fact cited in the docs.

Documents do not get to remember numbers. They cite a **fact name**, and the
value is derived from the repository at sync time::

    The gate runs <!--fact:gate_count-->23<!--/fact--> checks.

`scripts/sync_doc_facts.py --apply` rewrites the value between the markers;
`--check` fails when the committed value disagrees with reality. That is what
stops "22 checks" from being copied into six documents and staying there after
gate 23 is added.

Facts are split into two costs:

* **cheap** — derived from git, the filesystem and grep. Always computed.
* **expensive** — require running the test suite. Read from
  `.governance/doc_facts.json` when present (the CI gate writes it on every
  gated commit), otherwise reported as ``unknown`` and skipped rather than
  guessed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FACTS_CACHE = REPO_ROOT / ".governance" / "doc_facts.json"

# `<--fact:name-->value<--/fact-->` (real form uses HTML comment delimiters).
MARKER_RE = re.compile(r"<!--fact:([a-z_]+)-->(.*?)<!--/fact-->", re.DOTALL)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=300)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _latest_tag() -> str:
    out = _run(["git", "tag", "--sort=-v:refname"])
    for ln in out.splitlines():
        if re.fullmatch(r"v\d+\.\d+\.\d+", ln.strip()):
            return ln.strip()
    return "unknown"


def collect_cheap() -> dict[str, str]:
    """Facts derivable in well under a second. Never guess — return ``unknown``."""
    facts: dict[str, str] = {}

    facts["version"] = _latest_tag()
    facts["commit"] = _run(["git", "rev-parse", "--short", "HEAD"]) or "unknown"

    gate_file = REPO_ROOT / "scripts" / "ci_gate.py"
    facts["gate_count"] = (
        str(len(re.findall(r"^def gate_", gate_file.read_text(), re.M)))
        if gate_file.is_file()
        else "unknown"
    )

    bridge_file = REPO_ROOT / "scripts" / "ci_bridge.py"
    if bridge_file.is_file():
        src = bridge_file.read_text()
        m = re.search(r"CONTEXT_ORDER\s*=\s*[([](.*?)[)\]]", src, re.S)
        facts["context_count"] = (
            str(len(re.findall(r'^\s*"', m.group(1), re.M))) if m else "unknown"
        )
    else:
        facts["context_count"] = "unknown"

    adr_dir = REPO_ROOT / "docs" / "adr"
    facts["adr_count"] = str(len(list(adr_dir.glob("ADR-*.md")))) if adr_dir.is_dir() else "unknown"

    board = REPO_ROOT / "scripts" / "board" / "review.py"
    facts["board_count"] = (
        str(len(re.findall(r"^def check_", board.read_text(), re.M)))
        if board.is_file()
        else "unknown"
    )

    facts["doc_count"] = str(
        len([p for p in (REPO_ROOT / "docs").rglob("*.md") if "archive" not in p.parts])
    )

    # Review windows, read from the script that enforces them, so the cadence
    # table in DOC-GOVERNANCE.md cannot drift from the code either.
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from doc_review_due import CADENCE_DAYS, DEFAULT_CADENCE  # noqa: PLC0415

        all_windows = sorted({*CADENCE_DAYS.values(), DEFAULT_CADENCE})
        facts["cadence_fast"] = str(min(all_windows))
        facts["cadence_default"] = str(DEFAULT_CADENCE)
        facts["cadence_quarterly"] = "90"
        facts["cadence_historical"] = str(max(all_windows))
    except Exception:  # noqa: BLE001
        for k in ("cadence_fast", "cadence_default", "cadence_quarterly", "cadence_historical"):
            facts[k] = "unknown"

    py = REPO_ROOT / "pyproject.toml"
    if py.is_file():
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', py.read_text())
        facts["python_requires"] = m.group(1) if m else "unknown"
    else:
        facts["python_requires"] = "unknown"

    return facts


def _head_commit() -> str | None:
    """The commit these facts describe.

    Resolved from the tree the module is *running in*, not from the main checkout.
    That distinction matters: ``ci_gate.py`` measures a detached worktree at
    ``--sha`` and invokes this module with that worktree as cwd, so asking the
    directory that merely contains the script would answer with the wrong commit.
    ``REPO_ROOT`` is derived from ``__file__``, which under the gate is the file
    inside the worktree, so git is asked about that path explicitly.
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - git absent
        return None
    commit = r.stdout.strip()
    return commit or None


def collect_expensive(run_tests: bool = False, allow_cache: bool = False) -> dict[str, str]:
    """Facts that need the test suite.

    Preference order: run them (`run_tests=True`), else read the gate's cache **when
    that cache is proven to describe this commit**, else ``unknown``. Never invent a
    number.

    Provenance is the whole point of the cache check. The cache is written by the CI
    gate after it runs pytest, and a gate run is expensive, so reusing it is right.
    But a cache is a *claim about a past tree*: consuming it against a newer checkout
    would report a test count and coverage that describe code which no longer exists,
    and the documentation would then assert a stale measurement as current truth.

    So the cache carries the commit it measured, and is only trusted when that commit
    is the one being described. A mismatch, a missing field, or a malformed file all
    fall back to ``unknown`` — an admitted gap is recoverable, an invented number in
    a governance document is not.

    CRITICAL: When called from inside a running pytest session (e.g. from
    `test_real_repository_has_no_doc_drift`), this uses `--collect-only` to count
    tests without executing them. Executing tests here would cause infinite
    recursion (the test runs pytest which runs the test which runs pytest...).
    Collection is deterministic and fast; execution is neither.
    """
    # Prefer the repository interpreter, else the one running this script.
    # REPO_ROOT is a *worktree* whenever ci_gate.py measures a commit, and a
    # worktree has no .venv -- so testing REPO_ROOT/.venv made this skip
    # collection entirely there and report "unknown", which failed
    # test_real_repository_has_no_doc_drift under the gate while passing in a
    # developer's checkout. The guard was reporting "cannot verify" in exactly
    # the environment that is supposed to verify.
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    if not venv_py.is_file():
        venv_py = Path(sys.executable)
    if run_tests and venv_py.is_file():
        # Detect if we're inside a running pytest session to avoid recursion.
        inside_pytest = "pytest" in sys.modules

        # The test count must be DERIVED ONE WAY and one way only, or the doc
        # marker will flap between "N collected" and "M passed" depending on
        # where (and whether) the suite happened to run. ``--collect-only`` is
        # the sole authority: it is deterministic and independent of pass/fail,
        # so "tests = 1180" means exactly one thing everywhere.
        collect_cmd = [
            str(venv_py),
            "-m",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
        ]
        out = _run(collect_cmd)
        facts: dict[str, str] = {}
        m = re.search(r"collected (\d+) items", out)
        facts["test_count"] = m.group(1) if m else "unknown"
        facts["coverage"] = "unknown"

        # Coverage is only meaningful from a real execution, which we must not
        # do here (it would recurse inside pytest, and double-run in pre-commit).
        # It is measured by the CI gate and written to the cache; the doc check
        # treats an unresolved coverage as an explicit "cannot verify" finding,
        # never a silent pass.
        if not inside_pytest:
            cov_cmd = [
                str(venv_py),
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--no-header",
                "--cov=app",
                "--cov-report=term",
            ]
            cov_out = _run(cov_cmd)
            cm = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", cov_out, re.M)
            if cm and facts.get("test_count") != "unknown":
                facts["coverage"] = cm.group(1)

        if facts.get("test_count") != "unknown":
            _write_cache(facts)
        return facts

    # No implicit cache loading: the cache file is untracked scratch whose
    # provenance no caller has verified at this point. A commit-matching cache
    # can still describe the wrong tree (written pre-commit, when HEAD is the
    # parent). Expensive facts load ONLY via explicit paths: run_tests (live),
    # --facts-json through reconcile_injected_facts (provenance-checked), or
    # allow_cache=True passed deliberately by the caller.
    if allow_cache:
        return _read_cache()
    return {"test_count": "unknown", "coverage": "unknown"}


def _read_cache() -> dict[str, str]:
    """Read the gate's measured facts, but only for the commit they measured."""
    unknown = {"test_count": "unknown", "coverage": "unknown"}
    if not FACTS_CACHE.is_file():
        return unknown
    try:
        data = json.loads(FACTS_CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return unknown
    if not isinstance(data, dict):
        return unknown

    cached_commit = data.get("commit")
    head = _head_commit()
    if not cached_commit or not head or cached_commit != head:
        # The cache describes a different tree. Reporting it as current would be
        # exactly the silent staleness this system exists to catch.
        return unknown

    return {
        "test_count": str(data.get("test_count", "unknown")),
        "coverage": str(data.get("coverage", "unknown")),
    }


def _write_cache(facts: dict[str, str]) -> None:
    """Record measured facts together with the commit they describe."""
    FACTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if FACTS_CACHE.is_file():
        try:
            loaded = json.loads(FACTS_CACHE.read_text())
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(facts)
    head = _head_commit()
    if head:
        existing["commit"] = head
    FACTS_CACHE.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")


def collect(run_tests: bool = False, allow_cache: bool = False) -> dict[str, str]:
    facts = collect_cheap()
    facts.update(collect_expensive(run_tests=run_tests, allow_cache=allow_cache))
    return facts


if __name__ == "__main__":
    print(json.dumps(collect(run_tests="--run-tests" in sys.argv), indent=2, sort_keys=True))
