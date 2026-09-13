#!/usr/bin/env python3
"""Fill in the **Source** bindings the type contract demands.

The type contract (docs/DOC-GOVERNANCE.md §10) requires every ACTIVE `reference`,
`architecture`, `governance` and `runbook` document to name the code it describes.
The first run of the contract found 13 documents that do not.

That finding is correct, and it is the whole point of the rule: a document that
makes claims about code and cannot point to it has no way to be noticed when the
code moves. Each binding below was checked against the filesystem before being
written — the contract verifies them afterwards via the path rule.

Idempotent: strips an existing `**Source**` line and re-emits it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# rel -> the source binding. Chosen to name the *narrowest* set of paths that
# genuinely holds the document's claims, because a source line that names the
# whole repository catches nothing.
SOURCES: dict[str, str] = {
    "AGENTS.md": "`githooks/`, `scripts/ci_gate.py`, `scripts/check_docs.py` at HEAD",
    "CONTRIBUTING.md": "`AGENTS.md`, `githooks/pre-commit` at HEAD",
    "docs/DOC-GOVERNANCE.md": "`scripts/check_docs.py`, `scripts/doc_types.py` at HEAD",
    "docs/GOVERNANCE.md": "`scripts/ci_gate.py`, `scripts/ci_bridge.py` at HEAD",
    "docs/CAPABILITY-CONTRACT.md": (
        "`AGENTS.md`, `docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md`"
    ),
    "docs/API_CONTRACT.md": "`app/api/` at HEAD",
    "docs/CONFIG.md": "`app/config/` at HEAD",
    "docs/DATABASE.md": "`app/memory/` at HEAD",
    "docs/LLM.md": "`app/models/` at HEAD",
    "docs/MEMORY.md": "`app/memory/` at HEAD",
    "docs/TOOLS.md": "`app/tools/` at HEAD",
    "docs/CI-GATE-SOTA.md": "`scripts/ci_gate.py` at HEAD",
    "docs/CI-TOKEN-PERMISSIONS.md": "`scripts/ci_bridge.py`, `.ci-bridge.env` (not committed)",
    "docs/GITHUB-APP-SETUP.md": "`scripts/ci_bridge.py` at HEAD",
}

SOURCE_RE = re.compile(r"^\s*\*\*Source( of Truth)?\*\*\s*:.*$\n?", re.M)


def render(text: str, source: str) -> str:
    text = SOURCE_RE.sub("", text)
    m = re.search(r"^(\s*\*\*Type\*\*\s*:.*)$", text, re.M)
    if not m:
        m = re.search(r"^(\s*\*\*Status\*\*\s*:.*)$", text, re.M)
    if not m:
        return text
    line_end = text.find("\n", m.end())
    if line_end == -1:
        return text + f"\n**Source**: {source}\n"
    return text[: line_end + 1] + f"**Source**: {source}\n" + text[line_end + 1 :]


def main() -> int:
    touched, missing, absent = [], [], []
    for rel, source in SOURCES.items():
        p = REPO / rel
        if not p.exists():
            missing.append(rel)
            continue
        before = p.read_text(encoding="utf-8", errors="replace")
        after = render(before, source)
        if before != after:
            p.write_text(after, encoding="utf-8")
            touched.append(rel)
        # Fail loudly if a binding names a path that is not there: a source line
        # pointing at nothing is worse than no source line, because it looks like
        # a binding.
        for token in re.findall(r"`([A-Za-z0-9_./-]+)`", source):
            is_path_claim = token.endswith("/") or "." in Path(token).name
            missing_on_disk = not (REPO / token.rstrip("/")).exists()
            if is_path_claim and missing_on_disk and not token.startswith(".ci-bridge"):
                absent.append(f"{rel} -> {token}")
    print(f"bound {len(touched)} file(s) to their source")
    for rel in touched:
        print(f"  {rel}")
    if missing:
        print("\nmissing (skipped):", *missing, sep="\n  ")
    if absent:
        print("\nBINDING NAMES A PATH THAT DOES NOT EXIST:", *absent, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
