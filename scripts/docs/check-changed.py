#!/usr/bin/env python3
"""Layer 1: staged-scope documentation check (autonomous docs system).

Runs in seconds on `git diff --cached` only. Rules (see DOCS_SYSTEM_DESIGN.md):
  R1 co-change: staged code with changed public surface requires its manifest-
     mapped doc staged too (block). Body-only changes warn.
  R2 docstrings: new def/class in staged app/*.py needs a docstring (block).
  R3 markdown: staged *.md get heading/fence/link/path checks (block).
  R4 manifest: staged docs must be classifiable (block).
  R5 facts: sync_doc_facts --check over the tree would rewrite → block with fix.

Exit 1 blocks the commit. No network. Reuses check_docs.py + manifest-validate.py
so Layer 1 and Layer 2 can never disagree on shared rules.

Usage:
    python scripts/docs/check-changed.py
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
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


_check_docs = _load("docs_check_docs", SCRIPTS / "check_docs.py")
_manifest = _load("docs_manifest_validate", DOCS_DIR / "manifest-validate.py")

CODE_DIRS = ("app/", "scripts/", "evals/")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
FENCE_RE = re.compile(r"^```")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
NEW_DEF_RE = re.compile(r"^\+(?:async\s+)?def\s+(\w+)|^\+class\s+(\w+)")


def _git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout if proc.returncode == 0 else ""


def staged_files() -> list[str]:
    out = _git(["diff", "--cached", "--name-only", "-z"])
    return sorted(p for p in out.split("\0") if p)


def _show(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout if proc.returncode == 0 else None


def _top_level_defs(source: str) -> dict[str, tuple[str, ...]]:
    """Map top-level def/class name → arg names (methods folded to classes)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    result: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            result[node.name] = tuple(a.arg for a in node.args.args)
        elif isinstance(node, ast.ClassDef):
            result[node.name] = ()
    return result


def public_surface_changes(path: str) -> tuple[list[str], list[str]]:
    """Return (breaking, notes) for staged .py vs HEAD. Empty = body-only."""
    old = _show("HEAD", path) or ""
    new = _show("", path) or ""
    old_defs, new_defs = _top_level_defs(old), _top_level_defs(new)
    breaking: list[str] = []
    for name in sorted(set(old_defs) - set(new_defs)):
        breaking.append(f"removed {name}()")
    for name in sorted(set(new_defs) - set(old_defs)):
        breaking.append(f"added {name}()")
    for name in sorted(set(old_defs) & set(new_defs)):
        if old_defs[name] != new_defs[name]:
            breaking.append(f"signature changed: {name}{old_defs[name]} -> {new_defs[name]}")
    return breaking, []


def manifest_reverse_index() -> dict[str, list[str]]:
    """Map code path → manifest docs covering it."""
    data = _manifest._load_manifest()  # noqa: SLF001 - same system, shared loader
    index: dict[str, list[str]] = {}
    for section in data.get("sections", []) if isinstance(data, dict) else []:
        if not isinstance(section, dict):
            continue
        for cover in section.get("covers", []) or []:
            index.setdefault(cover, []).append(section.get("doc", ""))
    return index


def is_code(path: str) -> bool:
    return (
        path.endswith(".py")
        and path.startswith(CODE_DIRS)
        and "/tests/" not in path
        and not path.startswith("tests/")
    )


def check(staged: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    staged_set = set(staged)
    index = manifest_reverse_index()

    for path in staged:
        if not is_code(path):
            continue
        breaking, _ = public_surface_changes(path)
        if not breaking:
            continue
        # Most-specific cover wins: docs mapped via a shallow cover (e.g. the
        # [app/] architecture overviews) warn; docs at the deepest matching
        # cover block. Otherwise every app/ change would require staging four
        # overviews — unbearable and not what the manifest means.
        hits: dict[str, int] = {}
        for cover, docs in index.items():
            if path == cover or path.startswith(cover.rstrip("/") + "/"):
                for doc in docs:
                    hits[doc] = max(hits.get(doc, -1), len(cover.rstrip("/")))
        if hits:
            deepest = max(hits.values())
            required = sorted(d for d, depth in hits.items() if depth == deepest)
            advisory = sorted(d for d, depth in hits.items() if depth < deepest)
            missing = [d for d in required if d not in staged_set]
            if missing:
                errors.append(
                    f"R1 co-change: {path} changes public surface ({'; '.join(breaking)}) "
                    f"but mapped doc(s) not staged: {', '.join(missing)} — "
                    f"stage the doc update too"
                )
            unstaged_advisory = [d for d in advisory if d not in staged_set]
            if unstaged_advisory:
                warnings.append(
                    f"R1 info: {path} also falls under broader docs "
                    f"({', '.join(unstaged_advisory)}) — update them in a follow-up"
                )
        # New files always need a doc touch (they cannot be covered by edits).
        if _show("HEAD", path) is None and not hits:
            warnings.append(f"R1 info: {path} is new; confirm manifest covers it")

    # R2: docstrings on new defs/classes in staged app code.
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for path in staged:
        if not (path.startswith("app/") and path.endswith(".py")):
            continue
        diff = _git(["diff", "--cached", "-U0", "--", path])
        added: set[int] = set()
        for line in diff.splitlines():
            if (m := hunk_re.match(line)) is not None:
                start, count = int(m.group(1)), int(m.group(2) or 1)
                added.update(range(start, start + count))
        if not added:
            continue
        try:
            tree = ast.parse(_show("", path) or "")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue
                if node.lineno in added and ast.get_docstring(node) is None:
                    errors.append(
                        f"R2 docstring: {path}:{node.lineno} "
                        f"{type(node).__name__.lower()} {node.name}() has no docstring"
                    )
                    break  # one finding per file keeps output actionable

    # R3: markdown checks on staged docs.
    for path in staged:
        if not path.endswith(".md"):
            continue
        text = _show("", path) or ""
        lines = text.splitlines()
        # NOTE: no single-H1 / no-skipped-levels rules — house style uses
        # repeated `# path` file-marker headings (e.g. docs/LLM.md:31), and
        # check_docs.py deliberately does not enforce them either.
        if sum(1 for ln in lines if FENCE_RE.match(ln)) % 2:
            errors.append(f"R3 markdown: {path} has unbalanced fenced code blocks")
        # Links/paths inside fences are examples, not claims (shared with F2).
        in_fence, prose = False, []
        for ln in lines:
            if ln.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                prose.append(ln)
        prose_text = "\n".join(prose)
        for target in dict.fromkeys(LINK_RE.findall(prose_text)):
            if target.startswith(("http://", "https://", "mailto:", "#")) or not target.endswith(
                (".md", ".py", ".json", ".yaml", ".yml")
            ):
                continue
            resolved = (REPO_ROOT / Path(path).parent / target).resolve()
            try:
                ok = resolved.is_file() or (REPO_ROOT / target).is_file()
            except OSError:
                ok = False
            if not ok:
                errors.append(f"R3 links: {path} links missing file: {target}")
        for candidate in dict.fromkeys(_check_docs.PATH_RE.findall(prose_text)):
            c = candidate.strip()
            if "/" not in c:
                continue
            if not _check_docs.rel_exists(c, REPO_ROOT / path):
                errors.append(f"R3 paths: {path} references missing path: {c}")

    # R4: manifest classification for staged docs.
    staged_docs = [
        p
        for p in staged
        if (p.endswith(".md") or p == ".env.example")
        and (p.startswith("docs/") or "/" not in p or p in ("n8n/README.md", "tgcall/README.md"))
    ]
    for finding in _manifest.validate(staged_docs or ["__none__"]):
        errors.append(f"R4 manifest: {finding}")

    # R5 (retired as a check): machine-fact verification lives in Layer 2 (F7)
    # and in the native hook's auto-apply step. Rationale: the framework stashes
    # unstaged work before hooks run, so any worktree read here evaluates a
    # Frankenstein tree (staged + HEAD) — observed to misreport during
    # verification (see DOCS_VERIFICATION_LOG.md "stash-cycle" entry). Layer 1
    # is therefore strictly index-based (staged snapshot + HEAD); it never
    # reads the worktree and never writes anything, which makes it immune to
    # stash/pop races by construction.
    return errors, warnings


def main() -> int:
    staged = staged_files()
    if not staged:
        print("check-changed: nothing staged")
        return 0
    errors, warnings = check(staged)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"check-changed: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
