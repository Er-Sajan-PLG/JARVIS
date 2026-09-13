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

    py = REPO_ROOT / "pyproject.toml"
    if py.is_file():
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', py.read_text())
        facts["python_requires"] = m.group(1) if m else "unknown"
    else:
        facts["python_requires"] = "unknown"

    return facts


def collect_expensive(run_tests: bool = False) -> dict[str, str]:
    """Facts that need the test suite.

    Preference order: run them (`run_tests=True`), else read the gate's cache,
    else ``unknown``. Never invent a number.
    """
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    if run_tests and venv_py.is_file():
        out = _run(
            [
                str(venv_py),
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--no-header",
                "--cov=app",
                "--cov-report=term",
            ]
        )
        facts = {}
        m = re.search(r"(\d+) passed", out)
        facts["test_count"] = m.group(1) if m else "unknown"
        m = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", out, re.M)
        facts["coverage"] = m.group(1) if m else "unknown"
        if facts.get("test_count") != "unknown":
            _write_cache(facts)
        return facts

    if FACTS_CACHE.is_file():
        try:
            data = json.loads(FACTS_CACHE.read_text())
            return {
                "test_count": str(data.get("test_count", "unknown")),
                "coverage": str(data.get("coverage", "unknown")),
            }
        except (OSError, json.JSONDecodeError):
            pass
    return {"test_count": "unknown", "coverage": "unknown"}


def _write_cache(facts: dict[str, str]) -> None:
    FACTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if FACTS_CACHE.is_file():
        try:
            existing = json.loads(FACTS_CACHE.read_text())
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(facts)
    FACTS_CACHE.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")


def collect(run_tests: bool = False) -> dict[str, str]:
    facts = collect_cheap()
    facts.update(collect_expensive(run_tests=run_tests))
    return facts


if __name__ == "__main__":
    print(json.dumps(collect(run_tests="--run-tests" in sys.argv), indent=2, sort_keys=True))
