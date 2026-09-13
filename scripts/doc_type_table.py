#!/usr/bin/env python3
"""Keep the type table in docs/DOC-GOVERNANCE.md identical to the code.

The type contract lives in ``scripts/doc_types.py`` and is *documented* in the
governance document. Two copies of the same table is exactly the drift this whole
mechanism exists to prevent — the doc would describe types the checker does not
know, or miss types it does.

So the table is generated, and ``--check`` fails when the committed table differs
from what ``TYPES`` produces. Same principle as ``sync_doc_facts.py``: the
document does not store the truth, it renders it.

Usage:
    python scripts/doc_type_table.py --check    # exit 1 if the table is stale
    python scripts/doc_type_table.py --write    # regenerate the table in place
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_types import TYPES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
GOV_DOC = REPO_ROOT / "docs" / "DOC-GOVERNANCE.md"

BEGIN = "<!-- BEGIN GENERATED: doc types (scripts/doc_type_table.py) -->"
END = "<!-- END GENERATED: doc types -->"
RULES_BEGIN = "<!-- BEGIN GENERATED: doc type rules (scripts/doc_type_table.py) -->"
RULES_END = "<!-- END GENERATED: doc type rules -->"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_table() -> str:
    out = [
        BEGIN,
        "| Type | What it is | Required on an ACTIVE doc | Drift trap it prevents |",
        "|---|---|---|---|",
    ]
    for name, typ in sorted(TYPES.items()):
        req = ", ".join(f"`{f}`" for f in typ.header)
        if typ.sections:
            req += "; sections: " + ", ".join(f"`/{s}/`" for s in typ.sections)
        if typ.needs_table:
            req += "; a populated table"
        out.append(f"| `{name}` | {_cell(typ.summary)} | {req} | {_cell(typ.drift_trap)} |")
    out.append(END)
    return "\n".join(out)


def render_rules() -> str:
    """The per-type authoring rules, as prose an author reads before writing."""
    out = [RULES_BEGIN]
    for name, typ in sorted(TYPES.items()):
        out.append(f"\n#### `{name}` — {typ.summary}\n")
        statuses = ", ".join(f"`{s}`" for s in typ.statuses)
        out.append(f"- **Status**: {statuses}")
        out.append(f"- **Required header fields**: {', '.join(f'`{f}`' for f in typ.header)}")
        if typ.sections:
            out.append(
                "- **Required sections**: "
                + ", ".join(f"a heading matching `/{s}/`" for s in typ.sections)
            )
        if typ.needs_table:
            out.append("- **Required**: at least one populated table")
        out.append(f"- **The trap this type falls into**: {typ.drift_trap}")
        out.append("- **How to write it so that cannot happen:**")
        for n, rule in enumerate(typ.how_to_write, 1):
            out.append(f"  {n}. {rule}")
    out.append("\n" + RULES_END)
    return "\n".join(out)


def _block(text: str, begin: str, end: str) -> str | None:
    m = re.search(re.escape(begin) + r".*?" + re.escape(end), text, re.S)
    return m.group(0) if m else None


def current_block(text: str) -> str | None:
    return _block(text, BEGIN, END)


def current_rules_block(text: str) -> str | None:
    return _block(text, RULES_BEGIN, RULES_END)


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = ap.parse_args()

    text = GOV_DOC.read_text(encoding="utf-8")
    block = current_block(text)
    rules = current_rules_block(text)
    wanted = render_table()
    wanted_rules = render_rules()

    if args.write:
        if block is None or rules is None:
            print(
                f"error: generated markers not found in {GOV_DOC.relative_to(REPO_ROOT)}.\n"
                f"Expected:\n{BEGIN}\n{END}\nand\n{RULES_BEGIN}\n{RULES_END}",
                file=sys.stderr,
            )
            return 1
        changed = 0
        new_text = text
        if block != wanted:
            new_text = new_text.replace(block, wanted)
            changed += 1
        if rules != wanted_rules:
            new_text = new_text.replace(rules, wanted_rules)
            changed += 1
        if not changed:
            print("doc_type_table: tables already current (0 change(s))")
            return 0
        GOV_DOC.write_text(new_text, encoding="utf-8")
        print(f"doc_type_table: rewrote {changed} block(s) in {GOV_DOC.relative_to(REPO_ROOT)}")
        return 0

    problems: list[str] = []
    if block is None:
        problems.append("the generated type table markers are missing")
    elif block != wanted:
        names = ", ".join(sorted(TYPES))
        problems.append(
            f"the documented type table does not match scripts/doc_types.py "
            f"({len(TYPES)} types: {names})"
        )
    if rules is None:
        problems.append("the generated per-type rules markers are missing")
    elif rules != wanted_rules:
        problems.append("the documented per-type authoring rules do not match scripts/doc_types.py")
    if problems:
        print(
            "doc_type_table: FAIL — " + "; ".join(problems) + ".\n"
            "   Fix with: .venv/bin/python scripts/doc_type_table.py --write",
            file=sys.stderr,
        )
        return 1
    print(
        f"doc_type_table: {len(TYPES)} type(s) documented — table and authoring rules "
        f"both in sync with the code"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
