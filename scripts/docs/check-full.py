#!/usr/bin/env python3
"""Layer 2: full-tree documentation check (autonomous docs system).

Runs pre-push (subset), in ci_gate.py::gate_docs_layer2 (offline full), and on
the scheduled sweep (this script + scheduled_doc_maintenance.py for network).
Rules (see DOCS_SYSTEM_DESIGN.md):
  F1 manifest over the whole tree (errors).
  F2 markdown over ALL docs: headings, fences, internal links, path claims (errors).
  F3 codespell-lite over docs (errors; tiny unambiguous wordlist).
  F4 python snippet compile check over fenced blocks (errors).
  F5 generated-block diff via scripts/docs/generate.py (errors).
  F6 orphan report: docs with zero inbound links (warnings in v1 — ratchet
     philosophy: 27 pre-existing orphans must not red-day-one new code; the
     remaining-work list in the final report tracks the index fix).

Exit 1 on any error. No network.

Usage:
    python scripts/docs/check-full.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "scripts" / "docs"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_check_docs = _load("docs_check_docs_full", SCRIPTS / "check_docs.py")
_manifest = _load("docs_manifest_validate_full", DOCS_DIR / "manifest-validate.py")

HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
FENCE_START_RE = re.compile(r"^```(\w*)\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")

# Unambiguous typos only (word-boundary). Domain terms never included.
TYPO_RE = re.compile(
    r"\b(teh|recieve|seperate|seperator|occured|occurance|neccessary|"
    r"accomodate|definately|goverance|maintanance|existant|wich|adn|fro)\b",
    re.IGNORECASE,
)

DOC_EXTENSIONS = (".md",)


def all_docs() -> list[Path]:
    """In-scope docs = the manifest universe (existing files only).

    Third-party, scratch, and runtime dirs (external/, data/, .archaeology/,
    .hermes/, frontend build output) are out of scope by design — their docs
    describe other projects' trees, so path claims cannot resolve here.
    """
    docs = []
    for doc in _manifest.expected_docs():
        path = REPO_ROOT / doc
        if path.is_file() and path.suffix in DOC_EXTENSIONS:
            docs.append(path)
    return sorted(docs)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _prose_lines(lines: list[str]) -> list[str]:
    """Lines outside fenced blocks. Fences hold examples, not path/link claims."""
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def check_markdown(path: Path, errors: list[str]) -> None:
    rel = _rel(path)
    # Frozen history is do-not-cite by policy; links/paths inside it pin the
    # past and must not be "fixed" to HEAD.
    frozen = "/archive/" in rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        errors.append(f"F2 read: {rel}: {err}")
        return
    lines = text.splitlines()
    # NOTE: no single-H1 / no-skipped-levels rules — house style uses repeated
    # `# path` file-marker headings (see check-changed.py R3 note).
    if sum(1 for ln in lines if ln.startswith("```")) % 2:
        errors.append(f"F2 markdown: {rel} has unbalanced fenced blocks")
    prose = "\n".join(_prose_lines(text.splitlines()))
    for target in dict.fromkeys(LINK_RE.findall(prose)):
        if frozen:
            break
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not target.endswith((".md", ".py", ".json", ".yaml", ".yml")):
            continue
        try:
            ok = (path.parent / target).is_file() or (REPO_ROOT / target).is_file()
        except OSError:
            ok = False
        if not ok:
            errors.append(f"F2 links: {rel} links missing file: {target}")
    # Deletion ledgers and frozen history name absent files on purpose —
    # same exemption check_docs.py applies (shared rule, cannot disagree).
    if not frozen and rel not in _check_docs.PATH_CHECK_EXEMPT:
        for candidate in dict.fromkeys(_check_docs.PATH_RE.findall(prose)):
            c = candidate.strip()
            if "/" not in c:
                continue
            if not _check_docs.rel_exists(c, path):
                errors.append(f"F2 paths: {rel} references missing path: {c}")


def check_spelling(path: Path, errors: list[str]) -> None:
    rel = _rel(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in TYPO_RE.finditer(line):
            errors.append(f"F3 spelling: {rel}:{lineno}: '{m.group(1)}'")
            break  # one per file keeps output actionable


def check_snippets(path: Path, errors: list[str]) -> None:
    rel = _rel(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    lang: str | None = None
    buf: list[str] = []
    start = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = FENCE_START_RE.match(line)
        if m is None:
            if lang is not None:
                buf.append(line)
            continue
        if lang is None:
            lang, start, buf = (m.group(1) or "text").lower(), lineno, []
        else:
            if lang in ("python", "py"):
                source = "\n".join(buf)
                try:
                    compile(source, f"{rel}:{start}", "exec")
                except SyntaxError:
                    # Illustrative fragments often show bare `await`/indented
                    # bodies; retry wrapped so syntax (not packaging) is checked.
                    wrapped = "async def _snippet():\n" + "\n".join(
                        "    " + ln if ln.strip() else ln for ln in buf
                    )
                    try:
                        compile(wrapped, f"{rel}:{start}", "exec")
                    except SyntaxError as err:
                        errors.append(f"F4 snippet: {rel}:{start}: {err}")
            lang, buf = None, []


def check_generated(errors: list[str]) -> None:
    try:
        generate = _load("docs_generate", DOCS_DIR / "generate.py")
    except Exception as err:  # noqa: BLE001 - report, don't crash
        errors.append(f"F5 generated: cannot load generate.py: {err}")
        return
    try:
        diffs = generate.check_all()
    except Exception as err:  # noqa: BLE001 - report, don't crash
        errors.append(f"F5 generated: generator raised: {err}")
        return
    for doc, hint in diffs:
        errors.append(f"F5 generated: {doc} differs from generator output ({hint})")


def orphan_warnings(docs: list[Path]) -> list[str]:
    inbound: dict[str, int] = {str(p.relative_to(REPO_ROOT)): 0 for p in docs}
    for path in docs:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in dict.fromkeys(LINK_RE.findall(text)):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                rel = str(resolved.relative_to(REPO_ROOT))
            except ValueError:
                continue
            if rel in inbound:
                inbound[rel] += 1
    warnings = []
    for doc, count in sorted(inbound.items()):
        if count == 0 and "/archive/" not in doc:
            warnings.append(f"F6 orphan: {doc} has no inbound doc links")
    return warnings


def main() -> int:
    errors: list[str] = []
    for finding in _manifest.validate():
        errors.append(f"F1 manifest: {finding}")
    docs = all_docs()
    for path in docs:
        check_markdown(path, errors)
        check_spelling(path, errors)
        check_snippets(path, errors)
    check_generated(errors)
    warnings = orphan_warnings(docs)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"check-full: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
