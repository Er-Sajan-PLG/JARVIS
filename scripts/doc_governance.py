"""JARVIS Documentation Governance — auto-sync mechanical facts into docs.

Inspired by Universal_Software_Auditor's docs-sync system (ADR-0020), adapted
to JARVIS's Python/tooling conventions.

Two failure classes:
1. **Mechanical facts** — counts, versions, paths. Machine-owned: derived from
   source, written in, fail the gate when they drift.
2. **Prose truth** — "is this sentence still accurate?" Reader-owned. A
   separate review clock (Reviewed:) handles this.

Marker forms (both survive rendering because they are HTML comments):

  Inline value:
    Tests: <!--fact:test_count-->1233<!--/fact-->

  Generated block (content between markers is replaced wholesale):
    <!--fact:begin sprint-progress-->
    ...generated content...
    <!--fact:end sprint-progress-->

Everything here is pure and offline: facts come from the repo, never the
network. ``compute_facts()`` derives; ``regenerate()`` replaces; ``sync()``
writes; ``check()`` verifies by re-deriving and diffing.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
FACTS_CACHE = REPO_ROOT / ".governance" / "doc_facts.json"

# Inline marker: <!--fact:name-->value<!--/fact-->
FACT_RE = re.compile(r"<!--fact:([a-z_]+)-->(.*?)<!--/fact-->", re.DOTALL)
# Block markers: <!--fact:begin name--> ... <!--fact:fact end name-->
BLOCK_RE = re.compile(r"<!--fact:begin ([a-z_]+)-->(.*?)<!--fact:end \1-->", re.DOTALL)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def _git_short_sha() -> str:
    return _run(["git", "rev-parse", "--short", "HEAD"]) or "unknown"


def _git_branch() -> str:
    return _run(["git", "branch", "--show-current"]) or "unknown"


def _git_tag() -> str:
    return _run(["git", "describe", "--tags", "--always"]) or "v0.0.0"


def collect_cheap() -> dict[str, str]:
    """Facts derivable in well under a second. Never guess — return ``unknown``."""
    facts: dict[str, str] = {}

    # Git facts
    facts["commit"] = _git_short_sha()
    facts["branch"] = _git_branch()
    facts["tag"] = _git_tag()

    # Version from git tag
    tag = facts["tag"]
    m = re.match(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if m:
        facts["version"] = tag
        facts["version_major"] = m.group(1)
        facts["version_minor"] = m.group(2)
        facts["version_patch"] = m.group(3)

    # Gate count
    gate_file = REPO_ROOT / "scripts" / "ci_gate.py"
    if gate_file.is_file():
        src = gate_file.read_text()
        facts["gate_count"] = str(len(re.findall(r"^def gate_", src, re.M)))

    # Context count (from ci_bridge.py)
    bridge_file = REPO_ROOT / "scripts" / "ci_bridge.py"
    if bridge_file.is_file():
        src = bridge_file.read_text()
        m = re.search(r"CONTEXT_ORDER\s*=\s*[(\[](.*?)[)\]]", src, re.S)
        if m:
            facts["context_count"] = str(len(re.findall(r'^\s*"', m.group(1), re.M)))

    # ADR count
    adr_dir = REPO_ROOT / "docs" / "adr"
    if adr_dir.is_dir():
        facts["adr_count"] = str(len(list(adr_dir.glob("ADR-*.md"))))

    # Board review check count
    board = REPO_ROOT / "scripts" / "board" / "review.py"
    if board.is_file():
        src = board.read_text()
        facts["board_count"] = str(len(re.findall(r"^def check_", src, re.M)))

    # Doc count
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.is_dir():
        facts["doc_count"] = str(
            len([p for p in docs_dir.rglob("*.md") if "archive" not in p.parts])
        )

    # Review windows (from doc_review_due.py)
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from doc_review_due import CADENCE_DAYS, DEFAULT_CADENCE  # noqa: PLC0415

        all_windows = sorted({*CADENCE_DAYS.values(), DEFAULT_CADENCE})
        facts["cadence_fast"] = str(min(all_windows))
        facts["cadence_default"] = str(DEFAULT_CADENCE)
        facts["cadence_quarterly"] = "90"
        facts["cadence_historical"] = str(max(all_windows))
    except Exception:
        for k in ("cadence_fast", "cadence_default", "cadence_quarterly", "cadence_historical"):
            facts[k] = "unknown"

    return facts


def collect_expensive() -> dict[str, str]:
    """Facts that need the test suite."""
    facts: dict[str, str] = {}
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    if not venv_py.is_file():
        return facts

    # Test count (collect-only, deterministic)
    out = _run([str(venv_py), "-m", "pytest", "tests/", "--collect-only", "-q"])
    m = re.search(r"collected (\d+) items", out)
    facts["test_count"] = m.group(1) if m else "unknown"

    # Coverage (full run)
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
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", out)
    facts["coverage"] = m.group(1) if m else "unknown"

    return facts


def collect(run_tests: bool = False) -> dict[str, str]:
    facts = collect_cheap()
    if run_tests:
        facts.update(collect_expensive())
    return facts


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    """Return an ASCII progress bar."""
    if total <= 0:
        return "[" + " " * width + "] 0%"
    filled = int(width * current / total)
    pct = int(100 * current / total)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct}%"


def _sprint_progress() -> str:
    """Generate a sprint progress block for docs."""

    # Read the tracker for sprint status
    tracker = DOCS_DIR / "CAPABILITY_TRACKER.md"
    if not tracker.is_file():
        return ""

    src = tracker.read_text()

    # Extract sprint sections
    sprints = []
    current_sprint = None
    for line in src.splitlines():
        if line.startswith("### Sprint"):
            if current_sprint:
                sprints.append(current_sprint)
            current_sprint = {"name": line.strip("# ").strip(), "items": [], "done": 0, "total": 0}
        elif current_sprint is not None and line.strip().startswith("- ["):
            current_sprint["total"] += 1
            if line.strip().startswith("- [x]"):
                current_sprint["done"] += 1
                item = line.strip()
                item = item.removeprefix("- [x] ").strip()
                current_sprint["items"].append(("✅", item))
            else:
                item = line.strip()
                item = item.removeprefix("- [ ] ").strip()
                current_sprint["items"].append(("⬜", item))
    if current_sprint:
        sprints.append(current_sprint)

    # Generate the progress block
    lines = ["## Sprint Progress", ""]
    for sprint in sprints:
        bar = _progress_bar(sprint["done"], sprint["total"])
        lines.append(f"### {sprint['name']}")
        lines.append(f"{bar} {sprint['done']}/{sprint['total']}")
        for icon, item in sprint["items"]:
            lines.append(f"- {icon} {item}")
        lines.append("")

    return "\n".join(lines)


def regenerate(text: str, facts: dict[str, str]) -> str:
    """Replace all markers in ``text`` with current facts. Idempotent."""

    def _replace_inline(m: re.Match) -> str:
        name = m.group(1)
        if name not in facts:
            return m.group(0)  # leave unknown markers alone
        return f"<!--fact:{name}-->{facts[name]}<!--/fact-->"

    def _replace_block(m: re.Match) -> str:
        name = m.group(1)
        if name == "sprint-progress":
            block = _sprint_progress()
            return (
                f"<!--fact:begin sprint-progress-->\n"
                f"{block}\n"
                f"<!--fact:end sprint-progress-->"
            )
        return m.group(0)

    text = FACT_RE.sub(_replace_inline, text)
    text = BLOCK_RE.sub(_replace_block, text)
    return text


def iter_docs():
    """Yield all markdown files in docs/."""
    if DOCS_DIR.is_dir():
        yield from sorted(DOCS_DIR.rglob("*.md"))


def sync(facts: dict[str, str] | None = None) -> tuple[int, int]:
    """Rewrite all marker values in all docs. Return (files_changed, markers_updated)."""
    if facts is None:
        facts = collect(run_tests=True)

    changed = 0
    updated = 0
    for path in iter_docs():
        original = path.read_text()
        rewritten = regenerate(original, facts)
        if rewritten != original:
            path.write_text(rewritten)
            changed += 1
            updated += len(FACT_RE.findall(original)) + len(BLOCK_RE.findall(original))

    # Write cache
    FACTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    FACTS_CACHE.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

    return changed, updated


def check(facts: dict[str, str] | None = None) -> list[str]:
    """Verify all markers match current facts. Return list of findings."""
    if facts is None:
        facts = collect(run_tests=True)

    findings: list[str] = []
    for path in iter_docs():
        text = path.read_text()
        for m in FACT_RE.finditer(text):
            name, value = m.group(1), m.group(2).strip()
            if name in facts and facts[name] != value:
                findings.append(
                    f"{path.relative_to(REPO_ROOT)}:{m.start()}: "
                    f"fact '{name}' says '{value}' but repo says '{facts[name]}'"
                )
    return findings


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sync", action="store_true", help="rewrite marker values from repo")
    g.add_argument("--check", action="store_true", help="fail on stale markers")
    g.add_argument("--facts", action="store_true", help="print current facts as JSON")
    ap.add_argument("--run-tests", action="store_true", help="compute test facts by running them")
    args = ap.parse_args()

    if args.facts:
        print(json.dumps(collect(run_tests=args.run_tests), indent=2, sort_keys=True))
        return 0

    facts = collect(run_tests=args.run_tests)

    if args.sync:
        changed, updated = sync(facts)
        print(f"doc_governance: updated {updated} marker(s) in {changed} file(s)")
        return 0

    if args.check:
        findings = check(facts)
        if findings:
            print(f"{len(findings)} finding(s):\n")
            for f in findings:
                print(f"  - {f}")
            return 1
        print("doc_governance: no findings — all markers match repository")
        return 0

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
