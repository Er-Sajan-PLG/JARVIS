#!/usr/bin/env python3
"""Documentation hygiene checker — enforces the rules in docs/DOC-GOVERNANCE.md.

Checks, for every ``*.md`` under ``docs/`` plus the root-level markdown files:

1. **Status header** (§2). The file must contain a ``**Status**:`` line whose
   value begins with one of ACTIVE / SNAPSHOT / HISTORICAL / DRAFT.
2. **No stub tables** (§3, rule 3). A markdown table that has a header row and a
   separator row but zero data rows is a stub.
3. **Referenced paths resolve** (§4, rule 4). Every repo-relative path written in
   backticks with a known code/config extension must exist on disk. URLs,
   absolute paths, globs, template placeholders and known runtime-data paths are
   skipped.
4. **One navigation map** (§4, rule 1). Only ``docs/README.md`` may carry a
   "Documentation Guide"/"Documentation Index" H1.

Usage:
    python scripts/check_docs.py            # report only, always exit 0
    python scripts/check_docs.py --strict   # exit 1 when findings exist

Rationale for every allowance lives next to the constant that declares it, so a
new exception is a reviewed code change rather than a silent skip.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Rule 2: allowed status values ────────────────────────────────────────────
ALLOWED_STATUSES = ("ACTIVE", "SNAPSHOT", "HISTORICAL", "DRAFT")

# ── Rule 4 (paths): which extensions are worth resolving ─────────────────────
# Only source/config extensions. Prose, prose-ish paths and directories are not
# checked, because a document may legitimately name a *concept* ("app/memory")
# rather than a file.
CHECKED_EXTENSIONS = (
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".js",
    ".ts",
    ".toml",
    ".txt",
    ".sh",
    ".cjs",
    ".mjs",
    ".html",
    ".css",
    ".cfg",
    ".ini",
    ".sql",
    ".dockerfile",
)

# Paths that exist only at runtime (created by the app or the gate, never
# committed). A document may cite them; they are not repo artifacts.
RUNTIME_PREFIXES = (
    "data/",  # app runtime state: memories.json, chroma/, conversations/
    "artifacts/",  # gate outputs: sbom-<sha>.cdx.json, provenance, coverage
    "logs/",  # service logs
    ".governance/ci_bridge_state.json",  # bridge state, regenerated per run
    "server.pid",
    "n8n/.n8n/",
    "external/",  # third-party checkouts, not our code
)

# Explicit, individually justified allowances. Keep this list short; each entry
# is a documented false positive, not a blanket mute.
ALLOWED_MISSING = {
    # docs/DOC-GOVERNANCE.md §5 is a *deletion ledger*: it must name the files it
    # records as deleted, so those paths are correct by being absent. Removing
    # them from the ledger would destroy the audit trail.
    "docs/INDEX.md",
    "docs/CODING_STANDARDS.md",
    "docs/BRANCH_PROTECTION_SETUP.md",
    "docs/STARTUP_FLOW.md",
    "docs/modules/config.md",
    "docs/modules/githooks.md",
    "docs/modules/scripts.md",
    "docs/modules/frontend.md",
    "docs/modules/tests.md",
    "docs/HEALTH_REPORT.md",
    "docs/HISTORY.md",
    "docs/API.md",
    "docs/DEVLOG.md",
    "docs/CHANGELOG_recovered.md",
    "docs/DEVLOG_recovered.md",
    "docs/V3_ROADMAP.md",
    "docs/ECOSYSTEM-TARGET-ARCHITECTURE.md",
    "docs/changelog.md",
    "frontend/app.js",
    "tests/stress_test.py",
    # Placeholder forms that appear in templates and prose.
    "docs/adr/ADR-XXX.md",
    # Superseded modules referenced only as historical context.
    "app/api/server.py",
    "app/web_api_server.py",
    "app/prompt/builder.py",
    "app/knowledge/extract.py",
    "conversation/manager.py",
    "conversations/default.json",
    # Tooling referenced in workflow prose that is not vendored into the repo.
    "tests/conftest.py",
    "scripts/setup_dev_env.sh",
    # ADR-012 names a script that was never created under that name; the
    # correction note under it explains this and points at the real file. The
    # reference is intentional and must stay for the record.
    "scripts/mint_app_token.py",
}

# Documents exempt from the *path* rule, because their whole purpose is to record
# code that no longer exists. Resolving their paths would defeat the document.
PATH_CHECK_EXEMPT = {
    # Auto-generated symbol registry: by design it names symbols and files that
    # were DELETED, so its paths are historical facts, not claims about HEAD.
    "docs/SYMBOL_LINEAGE.md",
    # Frozen historical material (docs/DOC-GOVERNANCE.md §3, status HISTORICAL).
    "docs/archive/CHANGELOG_v3.0.0.md",
    "docs/archive/DEVLOG_v3.0.0.md",
    "docs/archive/API_SIGNATURE_HISTORY.md",
    "docs/archive/DEVLOG.md",
    "docs/archive/HISTORY.md",
    "docs/archive/HEALTH_REPORT_2026-07-28.md",
    # Migration notes describe the pre-migration tree.
    "docs/migrations/tombstones.md",
    "docs/migrations/v2_to_v3_migration.md",
}

# Documents exempt from the status-header rule, with a reason.
STATUS_EXEMPT = {
    # (none — every doc in this repo now carries a status header)
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "external",
    ".archaeology",
}


def iter_docs() -> list[Path]:
    files: list[Path] = []
    for p in REPO_ROOT.rglob("*.md"):
        rel = p.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.parts[0] == "docs" or len(rel.parts) == 1:
            files.append(rel)
    return sorted(files)


def rel_exists(rel: str, doc: Path | None = None) -> bool:
    """Resolve ``rel`` as repo-relative, then doc-relative.

    Documents legitimately cite both forms: ``app/memory/store.py`` (repo
    relative) and ``ARCHITECTURE.md`` (sibling, from inside ``docs/``).
    """
    if rel.startswith(RUNTIME_PREFIXES):
        # A runtime path is never committed; accept it without a disk check.
        return True
    if rel in ALLOWED_MISSING:
        return True
    if (REPO_ROOT / rel).exists():
        return True
    return bool(doc is not None and (REPO_ROOT / doc.parent / rel).exists())


PATH_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9]+)`")
STATUS_RE = re.compile(r"^\s*\*\*Status\*\*\s*:\s*(.+?)\s*$", re.MULTILINE)


def check_status(rel: Path, text: str) -> list[str]:
    if str(rel) in STATUS_EXEMPT:
        return []
    m = STATUS_RE.search(text)
    if not m:
        return [f"{rel}: missing '**Status**:' header (see docs/DOC-GOVERNANCE.md §2)"]
    value = m.group(1).strip().upper()
    if not any(value.startswith(s) for s in ALLOWED_STATUSES):
        return [f"{rel}: Status '{m.group(1).strip()}' is not one of {', '.join(ALLOWED_STATUSES)}"]
    return []


def check_stub_tables(rel: Path, text: str) -> list[str]:
    lines = text.splitlines()
    findings: list[str] = []
    i = 0
    while i < len(lines) - 1:
        line, nxt = lines[i].strip(), lines[i + 1].strip()
        is_header = line.startswith("|") and line.count("|") >= 3
        is_sep = bool(re.fullmatch(r"\|?[\s:|-]+\|?", nxt)) and "-" in nxt and nxt.startswith("|")
        if is_header and is_sep:
            j = i + 2
            rows = 0
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows += 1
                j += 1
            if rows == 0:
                findings.append(f"{rel}:{i + 1}: empty table (header with zero data rows)")
            i = j
        else:
            i += 1
    return findings


def check_paths(rel: Path, text: str) -> list[str]:
    if str(rel) in PATH_CHECK_EXEMPT:
        return []
    findings: list[str] = []
    for candidate in dict.fromkeys(PATH_RE.findall(text)):
        c = candidate.strip()
        if c.startswith(("http://", "https:///", "https://", "/", "~", "@")):
            continue
        if any(ch in c for ch in ("<", ">", "*", "{", "}", "$", "\\")):
            continue  # template/glob, not a literal path
        if not c.lower().endswith(CHECKED_EXTENSIONS):
            continue
        # A *bare basename* (``store.py``) in prose names a file loosely and is
        # not a path claim — resolving it would require guessing the directory.
        # Only directory-qualified paths (``app/memory/store.py``) are claims.
        if "/" not in c:
            continue
        if not rel_exists(c, rel):
            findings.append(f"{rel}: referenced path does not exist: {c}")
    return findings


def check_single_map(rel: Path, text: str) -> list[str]:
    first_h1 = next((ln for ln in text.splitlines() if ln.startswith("# ")), "")
    looks_like_map = bool(re.search(r"documentation (guide|index)", first_h1, re.I))
    if looks_like_map and str(rel) != "docs/README.md":
        return [
            f"{rel}: claims to be a documentation map ('{first_h1.strip()}'); "
            f"docs/README.md is the only map (rule 1)"
        ]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit non-zero when findings exist")
    args = ap.parse_args()

    docs = iter_docs()
    findings: list[str] = []
    for rel in docs:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - unreadable file
            findings.append(f"{rel}: unreadable ({exc})")
            continue
        findings += check_status(rel, text)
        findings += check_stub_tables(rel, text)
        findings += check_paths(rel, text)
        findings += check_single_map(rel, text)

    print(f"check_docs: scanned {len(docs)} markdown file(s)")
    if findings:
        print(f"\n{len(findings)} finding(s):\n")
        for f in findings:
            print("  -", f)
    else:
        print("no findings — documentation headers, tables and paths are clean")

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
