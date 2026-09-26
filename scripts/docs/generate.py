#!/usr/bin/env python3
"""Regenerate derived docs from source of truth (autonomous docs system).

Generators (deterministic output — never timestamps, paths-absolute, or
versions — so committed output only diffs when the source changes):
  module_readmes: app/README.md + app/*/README.md from package structure,
     module docstrings, and top-level def/class names.
  cli_reference: docs/CLI_REFERENCE.md from argparse declarations in
     scripts/*.py (AST-extracted; scripts are never executed).

Hand-written notes live BELOW the marked block; the generator only replaces
the block between markers. check_all() powers check-full.py F5.

Usage:
    python scripts/docs/generate.py --apply    # write files
    python scripts/docs/generate.py --check    # exit 1 if any diff
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"
SCRIPTS_ROOT = REPO_ROOT / "scripts"

BEGIN = "<!-- generated:{name} begin -->"
END = "<!-- generated:{name} end -->"


def _module_doc(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return "(unparseable)"
    doc = ast.get_docstring(tree)
    if not doc:
        return "(no module docstring)"
    return doc.strip().splitlines()[0][:120]


def _top_level_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.append(f"{node.name}()")
        elif isinstance(node, ast.ClassDef):
            names.append(node.name)
    return sorted(names)


def _package_dirs() -> list[Path]:
    return sorted(p for p in APP_ROOT.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


def render_module_readme(pkg: Path | None) -> str:
    """Render README for app/ itself (pkg=None) or one app/<pkg>/ dir."""
    if pkg is None:
        title, target = "app", APP_ROOT
    else:
        title, target = f"app/{pkg.name}", pkg
    lines = [f"# {title}", "", BEGIN.format(name="module_readmes"), ""]
    modules = sorted(p for p in target.glob("*.py") if p.name != "__init__.py")
    inits = list(target.glob("__init__.py"))
    if not modules and not inits:
        lines.append("_Empty package (no `.py` sources — placeholder, see manifest)._")
    else:
        lines.append("| Module | Purpose | Top-level API |")
        lines.append("|---|---|---|")
        for mod in inits + modules:
            api = ", ".join(f"`{n}`" for n in _top_level_names(mod)[:8])
            lines.append(f"| `{mod.name}` | {_module_doc(mod)} | {api or '—'} |")
    lines += ["", END.format(name="module_readmes"), ""]
    return "\n".join(lines)


def _argparse_flags(path: Path) -> list[tuple[str, str]]:
    """Extract (flags, help) from parser.add_argument calls via AST."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return []
    flags: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "add_argument":
            continue
        names = [
            a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        help_text = ""
        for kw in node.keywords:
            if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                help_text = str(kw.value.value)
        if names:
            first_line = help_text.splitlines()[0][:100] if help_text else "—"
            flags.append((", ".join(f"`{n}`" for n in names), first_line))
    return flags


def render_cli_reference() -> str:
    lines = [
        "# CLI Reference (generated)",
        "",
        "**Status**: ACTIVE",
        "**Type**: reference",
        "**Last Updated**: see git log (regenerated from source)",
        "**Source**: `scripts/*.py` argparse declarations at HEAD",
        "",
        BEGIN.format(name="cli_reference"),
        "",
        "_Regenerated from `argparse` declarations in `scripts/*.py`. "
        "Run `<script> --help` for full details._",
        "",
    ]
    for script in sorted(SCRIPTS_ROOT.glob("*.py")):
        flags = _argparse_flags(script)
        if not flags:
            continue
        lines.append(f"## `scripts/{script.name}`")
        lines.append("")
        lines.append("| Flags | Help |")
        lines.append("|---|---|")
        for names, help_text in flags:
            lines.append(f"| {names} | {help_text} |")
        lines.append("")
    lines.append(END.format(name="cli_reference"))
    lines.append("")
    return "\n".join(lines)


def targets() -> dict[str, str]:
    """Map doc path (repo-relative) → freshly rendered content."""
    out = {"app/README.md": render_module_readme(None)}
    for pkg in _package_dirs():
        out[f"app/{pkg.name}/README.md"] = render_module_readme(pkg)
    out["docs/CLI_REFERENCE.md"] = render_cli_reference()
    return out


def check_all() -> list[tuple[str, str]]:
    """Return [(doc, hint)] for every generated target that differs."""
    diffs = []
    for doc, fresh in targets().items():
        path = REPO_ROOT / doc
        try:
            committed = path.read_text(encoding="utf-8")
        except OSError:
            diffs.append((doc, "missing — run scripts/docs/generate.py --apply"))
            continue
        if committed != fresh:
            diffs.append((doc, "content differs — run scripts/docs/generate.py --apply"))
    return diffs


def main(argv: list[str]) -> int:
    if "--apply" in argv:
        for doc, fresh in targets().items():
            path = REPO_ROOT / doc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(fresh, encoding="utf-8")
            print(f"wrote {doc}")
        return 0
    diffs = check_all()
    for doc, hint in diffs:
        print(f"  - {doc}: {hint}")
    print(f"generate --check: {len(diffs)} diff(s)")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
