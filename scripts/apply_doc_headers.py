#!/usr/bin/env python3
"""Apply/normalise the required status header on every doc (docs/DOC-GOVERNANCE.md §2).

Idempotent: re-running replaces the existing Status/Last Updated lines rather than
appending duplicates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = (
    Path(__file__).resolve().parents[1]
    if "__file__" in globals()
    else Path("/home/sajan/Projects/JARVIS")
)

PLAN: dict[str, tuple[str, str, str | None]] = {
    "README.md": ("ACTIVE", "2026-09-13", None),
    "CONTRIBUTING.md": ("ACTIVE", "2026-09-13", None),
    "SECURITY.md": ("ACTIVE", "2026-09-13", None),
    "CODE_OF_CONDUCT.md": ("ACTIVE", "2026-09-13", None),
    "AGENTS.md": ("ACTIVE", "2026-09-13", "repo-root governance standard"),
    "docs/ACCEPTED_RISKS.md": ("ACTIVE", "2026-09-13", None),
    "docs/AGENTS.md": ("ACTIVE", "2026-09-13", "`app/agents/` at HEAD"),
    "docs/API_CONTRACT.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/adapters/http/router.py`, `app/adapters/websocket/stream.py`",
    ),
    "docs/ARCHITECTURE.md": ("ACTIVE", "2026-09-13", None),
    "docs/AUDIT-USAT.md": ("SNAPSHOT", "2026-09-10", None),
    "docs/CAPABILITY-CONTRACT.md": ("ACTIVE", "2026-09-13", None),
    "docs/CAPABILITY_TRACKER.md": ("ACTIVE", "2026-09-13", None),
    "docs/CHANGELOG.md": ("ACTIVE", "2026-09-13", None),
    "docs/CI-GATE-SOTA.md": (
        "ACTIVE",
        "2026-09-13",
        "`scripts/ci_gate.py`, `scripts/ci_bridge.py`",
    ),
    "docs/CI-TOKEN-PERMISSIONS.md": ("ACTIVE", "2026-09-13", None),
    "docs/CONFIG.md": ("ACTIVE", "2026-09-13", "`app/config/settings.py` at HEAD"),
    "docs/DATABASE.md": ("ACTIVE", "2026-09-13", "`app/memory/`, `app/conversation/` at HEAD"),
    "docs/DEBUGGING.md": ("ACTIVE", "2026-09-13", None),
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md": ("HISTORICAL", "2026-09-10", None),
    "docs/DEVELOPMENT.md": ("ACTIVE", "2026-09-13", None),
    "docs/DOC-GOVERNANCE.md": ("ACTIVE", "2026-09-13", None),
    "docs/GITHUB-APP-SETUP.md": ("ACTIVE", "2026-09-13", "`scripts/github_app_token.py` at HEAD"),
    "docs/GOVERNANCE.md": ("ACTIVE", "2026-09-13", None),
    "docs/LLM.md": ("ACTIVE", "2026-09-13", "`app/models/` at HEAD"),
    "docs/MEMORY.md": ("ACTIVE", "2026-09-13", "`app/memory/` at HEAD"),
    "docs/N8N-HANDOVER.md": ("ACTIVE", "2026-09-13", None),
    "docs/N8N-SETUP.md": ("ACTIVE", "2026-09-13", None),
    "docs/ROADMAP.md": ("ACTIVE", "2026-09-13", None),
    "docs/SPRINT_1_2_COMPLETION.md": ("SNAPSHOT", "2026-09-13", None),
    "docs/SYMBOL_LINEAGE.md": ("SNAPSHOT", "2026-09-13", None),
    "docs/TOOLS.md": ("ACTIVE", "2026-09-13", "`app/tools/` at HEAD"),
    "docs/VERSIONING.md": (
        "ACTIVE",
        "2026-09-13",
        "`app/config/version.py`, `scripts/version_bump.py`",
    ),
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
    "docs/timelines/evolution_timeline.md": ("SNAPSHOT", "2026-09-13", None),
    "docs/timelines/symbol_timeline.md": ("SNAPSHOT", "2026-09-13", None),
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
    "docs/archive/CHANGELOG_v3.0.0.md": ("HISTORICAL", "2026-07-26", None),
    "docs/archive/DEVLOG_v3.0.0.md": ("HISTORICAL", "2026-07-26", None),
    "docs/archive/API_SIGNATURE_HISTORY.md": ("HISTORICAL", "2026-07-28", None),
    "docs/archive/DEVLOG.md": ("HISTORICAL", "2026-07-28", None),
    "docs/archive/HISTORY.md": ("HISTORICAL", "2026-09-10", None),
    "docs/archive/HEALTH_REPORT_2026-07-28.md": ("HISTORICAL", "2026-07-28", None),
    "n8n/README.md": ("ACTIVE", "2026-09-13", None),
}

STATUS_LINE = re.compile(r"^\s*\*\*Status\*\*\s*:.*$", re.M)
UPDATED_LINE = re.compile(r"^\s*\*\*(Last Updated|Last Sync|Last reviewed)\*\*\s*:.*$", re.M | re.I)


def insert(path: Path, status: str, updated: str, source: str | None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    # find H1
    h1 = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
    if h1 is None:
        return "no-h1"
    block = [f"**Status**: {status}", f"**Last Updated**: {updated}"]
    if source:
        block.append(f"**Source**: {source}")

    # existing Status line anywhere? replace it + adjacent Last Updated
    if STATUS_LINE.search(text):
        text2 = STATUS_LINE.sub(f"**Status**: {status}", text, count=1)
        if UPDATED_LINE.search(text2):
            text2 = UPDATED_LINE.sub(f"**Last Updated**: {updated}", text2, count=1)
        else:
            # put Last Updated right after the Status line
            text2 = text2.replace(
                f"**Status**: {status}", f"**Status**: {status}\n**Last Updated**: {updated}", 1
            )
        if source and "**Source**:" not in text2:
            text2 = text2.replace(
                f"**Last Updated**: {updated}",
                f"**Last Updated**: {updated}\n**Source**: {source}",
                1,
            )
        path.write_text(text2, encoding="utf-8")
        return "renormalised"

    # skip past the H1 and any immediately-following blockquote/banner lines,
    # inserting the header *after* the title but before the first blank-separated para.
    j = h1 + 1
    while j < len(lines) and (lines[j].startswith(">") or lines[j].strip() == ""):
        # stop after the first blockquote block ends
        if lines[j].strip() == "" and j > h1 + 1 and not lines[j - 1].startswith(">"):
            break
        j += 1
    new = lines[:j] + [""] + block + lines[j:]
    path.write_text("\n".join(new) + "\n", encoding="utf-8")
    return "inserted"


def main() -> int:
    touched, missing = [], []
    for rel, (status, updated, source) in PLAN.items():
        p = REPO / rel
        if not p.exists():
            missing.append(rel)
            continue
        before = p.read_text(encoding="utf-8", errors="replace")
        action = insert(p, status, updated, source)
        after = p.read_text(encoding="utf-8", errors="replace")
        if before != after:
            touched.append((rel, action))
    print(f"touched {len(touched)} file(s)")
    for rel, a in touched:
        print(f"  {a:14s} {rel}")
    if missing:
        print("\nmissing (skipped):", missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
