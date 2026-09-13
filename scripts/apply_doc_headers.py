#!/usr/bin/env python3
"""Apply the required status header to every doc (docs/DOC-GOVERNANCE.md §2).

This is a migration tool for the 2026-09-13 documentation pass. It is
**idempotent**: running it twice produces the same bytes, because it strips any
existing canonical header lines and re-emits them in a fixed shape.

Fixed shape, immediately after the H1::

    # Title

    **Status**: ACTIVE
    **Last Updated**: 2026-09-13

    Body...

`PLAN` carries the status, date and optional source line per document. Documents
not listed in `PLAN` are left untouched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# rel path -> (status, last_updated, source_line_or_None)
PLAN: dict[str, tuple[str, str, str | None]] = {
    # ── root ────────────────────────────────────────────────────────────────
    "README.md": ("ACTIVE", "2026-09-13", None),
    "CONTRIBUTING.md": ("ACTIVE", "2026-09-13", None),
    "SECURITY.md": ("ACTIVE", "2026-09-13", None),
    "CODE_OF_CONDUCT.md": ("ACTIVE", "2026-09-13", None),
    "AGENTS.md": ("ACTIVE", "2026-09-13", None),
    # ── docs/ living ────────────────────────────────────────────────────────
    "docs/README.md": ("ACTIVE", "2026-09-13", None),
    "docs/DOC-GOVERNANCE.md": ("ACTIVE", "2026-09-13", None),
    "docs/GOVERNANCE.md": ("ACTIVE", "2026-09-13", "`AGENTS.md`, `docs/adr/`"),
    "docs/DEVELOPMENT.md": ("ACTIVE", "2026-09-13", None),
    "docs/ARCHITECTURE.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/` at HEAD (this document describes HEAD, not a pinned commit)",
    ),
    "docs/ROADMAP.md": ("ACTIVE", "2026-09-13", None),
    "docs/ACCEPTED_RISKS.md": ("ACTIVE", "2026-09-13", None),
    "docs/CI-GATE-SOTA.md": ("ACTIVE", "2026-09-13", None),
    "docs/CI-TOKEN-PERMISSIONS.md": ("ACTIVE", "2026-09-13", None),
    "docs/API_CONTRACT.md": ("ACTIVE", "2026-09-13", None),
    "docs/CAPABILITY-CONTRACT.md": ("ACTIVE", "2026-09-13", None),
    "docs/CAPABILITY_TRACKER.md": ("ACTIVE", "2026-09-13", None),
    "docs/CHANGELOG.md": ("ACTIVE", "2026-09-13", None),
    "docs/CONFIG.md": ("ACTIVE", "2026-09-13", None),
    "docs/DATABASE.md": ("ACTIVE", "2026-09-13", None),
    "docs/DEBUGGING.md": ("ACTIVE", "2026-09-13", None),
    "docs/GITHUB-APP-SETUP.md": ("ACTIVE", "2026-09-13", None),
    "docs/LLM.md": ("ACTIVE", "2026-09-13", None),
    "docs/MEMORY.md": ("ACTIVE", "2026-09-13", None),
    "docs/N8N-HANDOVER.md": ("ACTIVE", "2026-09-13", None),
    "docs/N8N-SETUP.md": ("ACTIVE", "2026-09-13", None),
    "docs/SPRINT_1_2_COMPLETION.md": ("ACTIVE", "2026-09-13", None),
    "docs/TOOLS.md": ("ACTIVE", "2026-09-13", None),
    "docs/VERSIONING.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/config/version.py`, `scripts/version_bump.py`",
    ),
    "docs/AGENTS.md": ("ACTIVE", "2026-09-13", "`AGENTS.md` at the repo root"),
    # ── snapshots ───────────────────────────────────────────────────────────
    "docs/AUDIT-USAT.md": ("SNAPSHOT", "2026-09-10", None),
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md": ("SNAPSHOT", "2026-09-10", None),
    "docs/timelines/evolution_timeline.md": ("SNAPSHOT", "2026-09-13", None),
    "docs/timelines/symbol_timeline.md": ("SNAPSHOT", "2026-09-13", None),
    # ── reference / module ──────────────────────────────────────────────────
    "docs/architecture/cognitive_brain.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/brain/`, `app/guardrails/` at HEAD",
    ),
    "docs/architecture/components.md": ("ACTIVE", "2026-09-13", "`app/` at HEAD"),
    "docs/architecture/data_flow.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/domain/`, `app/brain/`, `app/adapters/` at HEAD",
    ),
    "docs/architecture/memory_subsystem.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/memory/`, `app/integrations/vector/` at HEAD",
    ),
    "docs/architecture/model_routing.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/models/`, `app/resources/` at HEAD",
    ),
    "docs/architecture/startup_flow.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/bootstrap.py`, `app/main.py` at HEAD",
    ),
    "docs/modules/adapters.md": ("ACTIVE", "2026-09-13", "`app/adapters/` at HEAD"),
    "docs/modules/brain.md": ("ACTIVE", "2026-09-13", "`app/brain/` at HEAD"),
    "docs/modules/domain.md": ("ACTIVE", "2026-09-13", "`app/domain/` at HEAD"),
    "docs/modules/guardrails.md": ("ACTIVE", "2026-09-13", "`app/guardrails/` at HEAD"),
    "docs/modules/integrations.md": ("ACTIVE", "2026-09-13", "`app/integrations/` at HEAD"),
    "docs/modules/memory.md": ("ACTIVE", "2026-09-13", "`app/memory/` at HEAD"),
    "docs/modules/models.md": ("ACTIVE", "2026-09-13", "`app/models/` at HEAD"),
    "docs/migrations/tombstones.md": ("ACTIVE", "2026-09-13", None),
    "docs/migrations/v2_to_v3_migration.md": ("ACTIVE", "2026-09-13", None),
    # ── ADRs: historical decisions, each frozen on its own date ─────────────
    "docs/adr/ADR-001-ollama-cli-integration.md": ("HISTORICAL", "2026-06-27", None),
    "docs/adr/ADR-002-json-file-persistent-memory.md": ("HISTORICAL", "2026-06-28", None),
    "docs/adr/ADR-003-multi-model-task-router.md": ("HISTORICAL", "2026-07-03", None),
    "docs/adr/ADR-004-chromadb-semantic-memory.md": ("HISTORICAL", "2026-07-05", None),
    "docs/adr/ADR-005-fastapi-web-server-and-ui.md": ("HISTORICAL", "2026-07-18", None),
    "docs/adr/ADR-006-pragmatic-hybrid-architecture.md": ("ACTIVE", "2026-07-28", None),
    "docs/adr/ADR-007-domain-purity-and-dataclasses.md": ("ACTIVE", "2026-07-28", None),
    "docs/adr/ADR-008-tiered-tool-safety-policy.md": ("ACTIVE", "2026-07-28", None),
    "docs/adr/ADR-009-multi-provider-circuit-breaker-failover.md": ("ACTIVE", "2026-07-28", None),
    "docs/adr/ADR-010-adapters-and-integrations-isolation.md": ("ACTIVE", "2026-07-28", None),
    "docs/adr/ADR-011-tool-wiring-and-hitl-gate.md": ("ACTIVE", "2026-09-10", None),
    "docs/adr/ADR-012-github-auth-identity-per-function.md": ("ACTIVE", "2026-09-11", None),
    "docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md": ("ACTIVE", "2026-09-12", None),
    # ── archive: frozen, never edited again ─────────────────────────────────
    "docs/archive/CHANGELOG_v3.0.0.md": ("HISTORICAL", "2026-07-26", None),
    "docs/archive/DEVLOG_v3.0.0.md": ("HISTORICAL", "2026-07-26", None),
    "docs/archive/API_SIGNATURE_HISTORY.md": ("HISTORICAL", "2026-07-28", None),
    "docs/archive/DEVLOG.md": ("HISTORICAL", "2026-07-28", None),
    "docs/archive/HISTORY.md": ("HISTORICAL", "2026-09-10", None),
    "docs/archive/HEALTH_REPORT_2026-07-28.md": ("HISTORICAL", "2026-07-28", None),
    # ── other trees ─────────────────────────────────────────────────────────
    "n8n/README.md": ("ACTIVE", "2026-09-13", None),
}

# Canonical header lines. `^\s*` does NOT match a leading "- ", so an ADR's own
# "- **Status**: Approved" bullet is left alone — that is decision history, not
# this header.
STATUS_RE = re.compile(r"^\s*\*\*Status\*\*\s*:.*$", re.M)
UPDATED_RE = re.compile(r"^\s*\*\*(Last Updated|Last Sync|Last reviewed)\*\*\s*:.*$", re.M | re.I)
SOURCE_RE = re.compile(r"^\s*\*\*Source( of Truth)?\*\*\s*:.*$", re.M)


def render(text: str, status: str, updated: str, source: str | None) -> str:
    """Return `text` with exactly one canonical header, placed after the H1."""
    lines = text.splitlines()
    h1 = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
    if h1 is None:
        return text

    # Drop every existing canonical header line, wherever it sits. This is what
    # makes the operation idempotent and independent of where the previous pass
    # happened to leave things.
    cleaned = [
        ln
        for ln in lines
        if not (STATUS_RE.match(ln) or UPDATED_RE.match(ln) or SOURCE_RE.match(ln))
    ]
    h1 = next(i for i, ln in enumerate(cleaned) if ln.startswith("# "))

    block = [f"**Status**: {status}", f"**Last Updated**: {updated}"]
    if source:
        block.append(f"**Source**: {source}")

    # Preserve an immediately-following blockquote banner (some docs open with
    # one), placing the header below it.
    j = h1 + 1
    while j < len(cleaned) and cleaned[j].startswith(">"):
        j += 1

    out = cleaned[:j] + [""] + block + [""] + cleaned[j:]

    # Exactly one blank line between every block: collapse blank runs.
    final: list[str] = []
    for ln in out:
        if ln.strip() == "" and (not final or final[-1].strip() == ""):
            continue
        final.append(ln)
    while final and final[0].strip() == "":
        final.pop(0)
    return "\n".join(final) + "\n"


def main() -> int:
    touched, missing = [], []
    for rel, (status, updated, source) in PLAN.items():
        p = REPO / rel
        if not p.exists():
            missing.append(rel)
            continue
        before = p.read_text(encoding="utf-8", errors="replace")
        after = render(before, status, updated, source)
        if before != after:
            p.write_text(after, encoding="utf-8")
            touched.append(rel)
    print(f"updated {len(touched)} file(s)")
    for rel in touched:
        print(f"  {rel}")
    if missing:
        print("\nmissing (skipped):")
        for rel in missing:
            print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
