#!/usr/bin/env python3
"""Doc-to-code manifest validation (autonomous docs system, Layer 1+2).

Every human-readable doc in the repo must be classified exactly once in
``docs.manifest.yaml`` — or carry an explicit ``standalone, reviewed <date>``
header — so nothing is silently untracked. Fails loudly; used by
``check-changed.py`` (staged scope), ``check-full.py`` (whole tree), and the
``gate_docs_layer2`` CI gate.

Schema (``docs.manifest.yaml``):
    version: 1
    sections:
      - doc: docs/TOOLS.md            # repo-relative path, exactly once
        covers: [app/tools/]          # code paths it describes (may be [])
        kind: hand                    # hand | generated
        staleness: content            # facts | content | semantic | snapshot
        owner: tools                  # area owner label (free text)
        # generated sections also carry:
        generator: scripts/docs/generate.py:module_readmes

A doc with empty ``covers`` must justify itself in ``notes`` (e.g. ADRs record
decisions; snapshots freeze history). ``standalone`` docs declare it inline:

    > standalone, reviewed 2026-09-26: <one-line reason>

Usage:
    python scripts/docs/manifest-validate.py            # full tree
    python scripts/docs/manifest-validate.py --files a b # subset (Layer 1)
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any


def _yaml() -> Any:
    """PyYAML via importlib (no static import: stub availability varies)."""
    try:
        return importlib.import_module("yaml")
    except ImportError:  # pragma: no cover - PyYAML is a hard requirement
        return None


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs.manifest.yaml"

KINDS = {"hand", "generated"}
STALENESS = {"facts", "content", "semantic", "snapshot"}
STANDALONE_RE = re.compile(r"standalone,\s*reviewed\s+(\d{4}-\d{2}-\d{2})", re.I)

# Human-readable files that participate. Machine files (requirements.txt,
# package-lock.json) are out of scope by design.
DOC_EXTENSIONS = (".md",)
DOC_DIRS = ("docs",)
DOC_ROOT_FILES = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "DEVLOG.md",
    "DOCS_AUDIT_REPORT.md",
    "DOCS_SYSTEM_DESIGN.md",
    "DOCS_VERIFICATION_LOG.md",
)
EXTRA_DOCS = (
    "n8n/README.md",
    "tgcall/README.md",
    ".env.example",
)


def _load_manifest() -> dict[str, Any]:
    mod = _yaml()
    if mod is None:
        return {"_error": "pyyaml not installed; manifest cannot be validated"}
    try:
        text = MANIFEST.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"_error": f"manifest missing: {MANIFEST}"}
    try:
        data = mod.safe_load(text)
    except Exception as err:  # noqa: BLE001 - report, don't crash
        return {"_error": f"manifest is not valid YAML: {err}"}
    return data if isinstance(data, dict) else {"_error": "manifest root must be a mapping"}


def expected_docs() -> list[str]:
    """All in-scope doc paths, repo-relative, sorted."""
    found: list[str] = []
    for doc_dir in DOC_DIRS:
        root = REPO_ROOT / doc_dir
        if root.is_dir():
            found.extend(
                str(p.relative_to(REPO_ROOT))
                for p in sorted(root.rglob("*"))
                if p.is_file() and p.suffix in DOC_EXTENSIONS
            )
    for name in DOC_ROOT_FILES:
        if (REPO_ROOT / name).is_file():
            found.append(name)
    for name in EXTRA_DOCS:
        if (REPO_ROOT / name).is_file():
            found.append(name)
    # Generated module READMEs (may not exist yet — generate.py creates them).
    app_root = REPO_ROOT / "app"
    if app_root.is_dir():
        for pkg in sorted(app_root.iterdir()):
            if pkg.is_dir() and not pkg.name.startswith(("_", ".")):
                found.append(f"app/{pkg.name}/README.md")
    found.extend(["app/README.md"])
    return sorted(set(found))


def _standalone_ok(doc: str) -> bool:
    path = REPO_ROOT / doc
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(STANDALONE_RE.search(text))


def validate(files: list[str] | None = None) -> list[str]:
    """Return findings (empty = clean). ``files`` restricts scope (Layer 1)."""
    findings: list[str] = []
    data = _load_manifest()
    if "_error" in data:
        return [f"manifest: {data['_error']}"]
    if data.get("version") != 1:
        findings.append("manifest: version must be 1")
    sections = data.get("sections", [])
    if not isinstance(sections, list):
        return findings + ["manifest: sections must be a list"]
    seen: dict[str, int] = {}
    for i, section in enumerate(sections):
        where = f"manifest sections[{i}]"
        if not isinstance(section, dict):
            findings.append(f"{where}: must be a mapping")
            continue
        doc = section.get("doc", "")
        if not doc:
            findings.append(f"{where}: missing doc")
            continue
        seen[doc] = seen.get(doc, 0) + 1
        if section.get("kind") not in KINDS:
            findings.append(f"{where} ({doc}): kind must be one of {sorted(KINDS)}")
        if section.get("staleness") not in STALENESS:
            findings.append(f"{where} ({doc}): staleness must be one of {sorted(STALENESS)}")
        covers = section.get("covers", [])
        if not isinstance(covers, list):
            findings.append(f"{where} ({doc}): covers must be a list")
        elif not covers and not section.get("notes"):
            findings.append(f"{where} ({doc}): empty covers needs notes (why is this doc kept?)")
        if section.get("kind") == "generated" and not section.get("generator"):
            findings.append(f"{where} ({doc}): generated sections need a generator")
        for path in covers if isinstance(covers, list) else []:
            if path and not (REPO_ROOT / path).exists():
                findings.append(f"{where} ({doc}): covers missing path: {path}")
    for doc, count in seen.items():
        if count > 1:
            findings.append(f"manifest: {doc} listed {count} times (exactly once required)")
    scope = set(files) if files is not None else None
    for doc in expected_docs():
        if scope is not None and doc not in scope:
            continue
        if doc not in seen and not _standalone_ok(doc):
            findings.append(
                f"unclassified doc: {doc} — add it to docs.manifest.yaml or mark "
                f"it 'standalone, reviewed <date>'"
            )
    return findings


def main(argv: list[str]) -> int:
    files: list[str] | None = None
    if argv and argv[0] == "--files":
        files = argv[1:]
    findings = validate(files)
    for finding in findings:
        print(f"  - {finding}")
    print(f"manifest-validate: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
