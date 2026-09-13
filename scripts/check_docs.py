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
# The type contract lives beside this script (scripts/doc_types.py). Make the
# script importable however it is invoked — as `python scripts/check_docs.py`, as
# a module loaded by path from the tests, or from a different working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_links import (  # noqa: E402
    check_heading_numbers,
    check_index_coverage,
    check_links,
)

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

# Documents exempt from the type contract (§10). Keep empty unless a document
# genuinely cannot declare a type; every exemption is a hole in the contract.
TYPE_EXEMPT: set[str] = set()

# Documents exempt from link/anchor checking: frozen archaeology that links to a
# tree this repository no longer has. Resolving their links would be meaningless.
LINK_CHECK_EXEMPT = {
    "docs/archive/API_SIGNATURE_HISTORY.md",
    "docs/archive/CHANGELOG_v3.0.0.md",
    "docs/archive/DEVLOG.md",
    "docs/archive/DEVLOG_v3.0.0.md",
    "docs/archive/HISTORY.md",
    "docs/archive/HEALTH_REPORT_2026-07-28.md",
    "docs/SYMBOL_LINEAGE.md",
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
    """Every file the rules apply to.

    Scope is deliberately narrow: ``docs/**`` plus markdown at the repo root.
    Files under ``prompts/`` are runtime prompt templates, not documentation —
    a status header on them would be meaningless — and cache dirs are skipped
    via ``SKIP_DIRS``.
    """
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


def classify_status(text: str) -> str:
    """Return the document's declared status, or '' when it has none."""
    m = STATUS_RE.search(text)
    if not m:
        return ""
    value = m.group(1).strip().upper()
    for s in ALLOWED_STATUSES:
        if value.startswith(s):
            return s
    return value


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


# ── Rule 10: the type contract (docs/DOC-GOVERNANCE.md §10) ──────────────────
#
# A type is declared per document as `**Type**: <name>`. The type decides which
# elements the document must carry, and — more importantly — it tells the author
# which drift trap they are walking into. The single highest-value requirement is
# `**Source**`: it binds an ACTIVE document to the code it describes, so a
# refactor turns the document red instead of turning it into a quiet lie.
#
# Deliberately locked to ACTIVE documents. A HISTORICAL or SNAPSHOT document is a
# record of the past; requiring maintained structure from it would be incoherent,
# and it must still declare its status and type.

TYPE_RE = re.compile(r"^\s*\*\*Type\*\*\s*:\s*([A-Za-z_-]+)\s*$", re.MULTILINE)
ADR_NUMBER_RE = re.compile(r"^docs/adr/ADR-(\d{3})-")
SECTION_MATCH_CACHE: dict[str, re.Pattern[str]] = {}

# Header field patterns, each paired with the exact text an author must write. The
# label is used verbatim in the failure message, so the checker never asks for a
# field spelled differently from the one it looks for.
FIELD_PATTERNS: dict[str, str] = {
    "status": r"^\s*\*\*Status\*\*\s*:",
    "type": r"^\s*\*\*Type\*\*\s*:",
    "updated": r"^\s*\*\*(Last Updated|Last Sync)\*\*\s*:",
    "source": r"^\s*\*\*Source\*\*\s*:",
    "reviewed": r"^\s*\*\*Reviewed\*\*\s*:",
    "generated_by": r"^\s*\*\*Generated by\*\*\s*:",
}
FIELD_LABELS: dict[str, str] = {
    "status": "**Status**",
    "type": "**Type**",
    "updated": "**Last Updated**",
    "source": "**Source**",
    "reviewed": "**Reviewed**",
    "generated_by": "**Generated by**",
}


def _section_matches(text: str, pattern: str) -> bool:
    rx = SECTION_MATCH_CACHE.setdefault(pattern, re.compile(pattern, re.I))
    return any(rx.search(ln) for ln in text.splitlines() if ln.startswith("#"))


def _has_data_table(text: str) -> bool:
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        line, nxt = lines[i].strip(), lines[i + 1].strip()
        is_header = line.startswith("|") and line.count("|") >= 3
        is_sep = bool(re.fullmatch(r"\|?[\s:|-]+\|?", nxt)) and nxt.startswith("|")
        has_row = i + 2 < len(lines) and lines[i + 2].strip().startswith("|")
        if is_header and is_sep and has_row:
            return True
    return False


def _field_present(text: str, name: str) -> bool:
    return bool(re.search(FIELD_PATTERNS[name], text, re.MULTILINE | re.IGNORECASE))


def check_types(rel: Path, text: str) -> list[str]:
    from doc_types import (  # noqa: PLC0415
        ADR_ALTERNATIVES_SINCE,
        ALLOWED_STATUSES,
        TYPES,
        required_for,
    )

    if str(rel) in TYPE_EXEMPT or str(rel).startswith("docs/templates/"):
        return []

    findings: list[str] = []
    m = TYPE_RE.search(text)
    if not m:
        return [
            f"{rel}: missing '**Type**:' header; declare one of "
            f"{', '.join(sorted(TYPES))} (see docs/DOC-GOVERNANCE.md §10)"
        ]
    type_name = m.group(1).strip().lower()
    typ = TYPES.get(type_name)
    if typ is None:
        return [
            f"{rel}: Type '{type_name}' is not one of "
            f"{', '.join(sorted(TYPES))} (see docs/DOC-GOVERNANCE.md §10)"
        ]

    if str(rel).startswith("docs/archive/"):
        return []

    # An ADR may only live where an ADR belongs, numbered.
    if type_name == "adr" and not ADR_NUMBER_RE.match(str(rel)):
        findings.append(
            f"{rel}: type 'adr' must live at docs/adr/ADR-NNN-slug.md; "
            f"a decision outside that path will not be found or numbered"
        )

    status = classify_status(text) or "ACTIVE"
    if status not in ALLOWED_STATUSES:  # already reported by check_status
        return findings

    for field_name in required_for(status, typ):
        if not _field_present(text, field_name):
            # Display names are spelled out: `field.title()` produced "Generated By"
            # while the document actually writes "Generated by", so the error told
            # authors to add a field that did not match what the checker looks for.
            label = FIELD_LABELS[field_name]
            hint = {
                "source": (
                    " — name the code this document describes, "
                    "e.g. a source line of `app/x/` at HEAD"
                ),
                "generated_by": " — name the script that regenerates it",
            }.get(field_name, "")
            findings.append(f"{rel}: type '{type_name}' ({status}) requires '{label}'{hint}")

    # Structure is only demanded of a living document.
    if status == "ACTIVE":
        for pattern in typ.sections:
            if not _section_matches(text, pattern):
                findings.append(
                    f"{rel}: type '{type_name}' requires a section matching /{pattern}/ — "
                    f"omit it and the document stops covering what the type promises"
                )
        if typ.needs_table and not _has_data_table(text):
            findings.append(
                f"{rel}: type '{type_name}' requires at least one populated table "
                f"(a header row and no data rows is a stub, not a register)"
            )

    # An ADR that rejects nothing teaches nothing. Enforced from the cutover
    # recorded in doc_types.ADR_ALTERNATIVES_SINCE.
    if type_name == "adr":
        date_m = re.search(r"^\s*[-*]?\s*\*\*Date\*\*\s*:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
        needs_alternatives = bool(date_m and date_m.group(1) >= ADR_ALTERNATIVES_SINCE)
        if needs_alternatives and not _section_matches(text, r"alternativ|rejected"):
            findings.append(
                f"{rel}: ADR dated {date_m.group(1)} must record 'Alternatives considered' "
                f"(docs/DOC-GOVERNANCE.md §10) — the rejected options are what a future "
                f"reader needs, and they are unrecoverable later"
            )

    return findings


VERSION_BANNER_RE = re.compile(r"v\d+\.\d+\.\d+")


def check_stale_version_banner(rel: Path, text: str) -> list[str]:
    """Rule 5 (docs/DOC-GOVERNANCE.md §8): an ACTIVE doc must not pin a version.

    Scoped to the level-1 heading, on purpose. A living document that is edited
    across releases cannot honestly carry "v3.0.0" in its *title* — that is a
    frozen label on a moving target, and it is how ARCHITECTURE.md came to be
    read as a v3.0.0 artefact while describing v3.3.x code. version numbers in
    the *body* are usually legitimate (they cite releases, tags or changelog
    rows), so they are not flagged.

    Only HISTORICAL/SNAPSHOT documents may pin a version in their title, and
    those live in docs/archive/.
    """
    if str(rel) in PATH_CHECK_EXEMPT or str(rel).startswith("docs/archive/"):
        return []
    status = classify_status(text)
    if status in {"HISTORICAL", "SNAPSHOT"}:
        return []
    title = next((ln for ln in text.splitlines() if ln.startswith("# ")), "")
    if VERSION_BANNER_RE.search(title):
        return [
            f"{rel}: active document pins a version in its title ({title.strip()!r}); "
            f"living docs are versioned by git + release tag (rule 5)"
        ]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit non-zero when findings exist")
    args = ap.parse_args()

    docs = iter_docs()
    findings: list[str] = []
    anchor_cache: dict[str, set[str]] = {}
    texts: dict[Path, str] = {}
    for rel in docs:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - unreadable file
            findings.append(f"{rel}: unreadable ({exc})")
            continue
        texts[rel] = text
        findings += check_status(rel, text)
        findings += check_stub_tables(rel, text)
        findings += check_paths(rel, text)
        findings += check_single_map(rel, text)
        findings += check_stale_version_banner(rel, text)
        findings += check_types(rel, text)

    # Cross-document checks run after every file is read, so an anchor may resolve
    # against a document later in the walk order.
    for rel, text in texts.items():
        if str(rel) in LINK_CHECK_EXEMPT:
            continue
        findings += check_links(rel, text, REPO_ROOT, anchor_cache)
        findings += check_heading_numbers(rel, text)
        findings += check_index_coverage(rel, text, REPO_ROOT)

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
