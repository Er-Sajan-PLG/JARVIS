#!/usr/bin/env python3
"""One-shot migration: declare a **Type** on every document (docs/DOC-GOVERNANCE.md §10).

Idempotent, in the same style as ``apply_doc_headers.py``: it strips any existing
``**Type**`` line and re-emits it immediately after ``**Status**``, so a second run
changes nothing.

The mapping below is a judgement about what each document *is*, and it is recorded
here rather than inferred from the filename, because a filename cannot tell you
whether `CI-GATE-SOTA.md` is a reference or a governance document. Mis-typing a
document is the one way to weaken this contract, so the mapping is explicit and
reviewable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# rel -> type. Every document in scope must appear here or it is left untyped and
# the checker will flag it.
TYPES: dict[str, str] = {
    # ── root ────────────────────────────────────────────────────────────────
    "README.md": "guide",
    "AGENTS.md": "governance",
    "CONTRIBUTING.md": "governance",
    "SECURITY.md": "policy",
    "CODE_OF_CONDUCT.md": "policy",
    # ── docs/ living ────────────────────────────────────────────────────────
    "docs/README.md": "index",
    "docs/DOC-GOVERNANCE.md": "governance",
    "docs/GOVERNANCE.md": "governance",
    "docs/DEVELOPMENT.md": "guide",
    "docs/ARCHITECTURE.md": "architecture",
    "docs/ROADMAP.md": "roadmap",
    "docs/ACCEPTED_RISKS.md": "register",
    "docs/CI-GATE-SOTA.md": "reference",
    "docs/CI-TOKEN-PERMISSIONS.md": "reference",
    "docs/API_CONTRACT.md": "reference",
    "docs/CAPABILITY-CONTRACT.md": "governance",
    "docs/CAPABILITY_TRACKER.md": "register",
    "docs/CHANGELOG.md": "changelog",
    "docs/CONFIG.md": "reference",
    "docs/DATABASE.md": "reference",
    "docs/DEBUGGING.md": "runbook",
    "docs/GITHUB-APP-SETUP.md": "runbook",
    "docs/LLM.md": "reference",
    "docs/MEMORY.md": "reference",
    "docs/N8N-HANDOVER.md": "guide",
    "docs/N8N-SETUP.md": "guide",
    "docs/TOOLS.md": "reference",
    "docs/VERSIONING.md": "reference",
    "docs/AGENTS.md": "reference",
    "docs/SYMBOL_LINEAGE.md": "generated",
    "docs/SPRINT_1_2_COMPLETION.md": "snapshot",
    "docs/AUDIT-USAT.md": "snapshot",
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md": "snapshot",
    # ── docs/ subfolders ────────────────────────────────────────────────────
    "docs/architecture/cognitive_brain.md": "architecture",
    "docs/architecture/components.md": "architecture",
    "docs/architecture/data_flow.md": "architecture",
    "docs/architecture/memory_subsystem.md": "architecture",
    "docs/architecture/model_routing.md": "architecture",
    "docs/architecture/startup_flow.md": "architecture",
    "docs/modules/adapters.md": "reference",
    "docs/modules/brain.md": "reference",
    "docs/modules/domain.md": "reference",
    "docs/modules/guardrails.md": "reference",
    "docs/modules/integrations.md": "reference",
    "docs/modules/memory.md": "reference",
    "docs/modules/models.md": "reference",
    "docs/migrations/tombstones.md": "register",
    "docs/migrations/v2_to_v3_migration.md": "guide",
    "docs/timelines/evolution_timeline.md": "generated",
    "docs/timelines/symbol_timeline.md": "generated",
    # ── ADRs: one type, no exceptions ───────────────────────────────────────
    "docs/adr/ADR-001-ollama-cli-integration.md": "adr",
    "docs/adr/ADR-002-json-file-persistent-memory.md": "adr",
    "docs/adr/ADR-003-multi-model-task-router.md": "adr",
    "docs/adr/ADR-004-chromadb-semantic-memory.md": "adr",
    "docs/adr/ADR-005-fastapi-web-server-and-ui.md": "adr",
    "docs/adr/ADR-006-pragmatic-hybrid-architecture.md": "adr",
    "docs/adr/ADR-007-domain-purity-and-dataclasses.md": "adr",
    "docs/adr/ADR-008-tiered-tool-safety-policy.md": "adr",
    "docs/adr/ADR-009-multi-provider-circuit-breaker-failover.md": "adr",
    "docs/adr/ADR-010-adapters-and-integrations-isolation.md": "adr",
    "docs/adr/ADR-011-tool-wiring-and-hitl-gate.md": "adr",
    "docs/adr/ADR-012-github-auth-identity-per-function.md": "adr",
    "docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md": "adr",
    # ── archive: frozen records ─────────────────────────────────────────────
    "docs/archive/API_SIGNATURE_HISTORY.md": "snapshot",
    "docs/archive/CHANGELOG_v3.0.0.md": "snapshot",
    "docs/archive/DEVLOG.md": "snapshot",
    "docs/archive/DEVLOG_v3.0.0.md": "snapshot",
    "docs/archive/HEALTH_REPORT_2026-07-28.md": "snapshot",
    "docs/archive/HISTORY.md": "snapshot",
    # ── other trees ─────────────────────────────────────────────────────────
    "n8n/README.md": "guide",
}

# Documents whose status must change for their type to be honest: a point-in-time
# completion record cannot claim to be ACTIVE (docs/DOC-GOVERNANCE.md §2).
STATUS_FIXES: dict[str, str] = {
    "docs/SPRINT_1_2_COMPLETION.md": "SNAPSHOT",
}

STATUS_RE = re.compile(r"^(\s*\*\*Status\*\*\s*:\s*)(\S+)(.*)$", re.M)
TYPE_LINE_RE = re.compile(r"^\s*\*\*Type\*\*\s*:.*$\n?", re.M)


def render(text: str, type_name: str, status_fix: str | None) -> str:
    text = TYPE_LINE_RE.sub("", text)

    m: re.Match[str] | None = STATUS_RE.search(text)
    if not m:
        return text

    if status_fix:
        text = text[: m.start()] + f"{m.group(1)}{status_fix}{m.group(3)}" + text[m.end() :]
        m = STATUS_RE.search(text)
        if not m:
            return text

    # `**Type**` sits immediately under `**Status**`, so the block reads as a
    # unit and a reader learns status and kind together.
    line_end = text.find("\n", m.end())
    if line_end == -1:
        return text + f"\n**Type**: {type_name}\n"
    return text[: line_end + 1] + f"**Type**: {type_name}\n" + text[line_end + 1 :]


def main() -> int:
    touched, missing, untyped = [], [], []
    for rel, type_name in TYPES.items():
        p = REPO / rel
        if not p.exists():
            missing.append(rel)
            continue
        before = p.read_text(encoding="utf-8", errors="replace")
        after = render(before, type_name, STATUS_FIXES.get(rel))
        if before != after:
            p.write_text(after, encoding="utf-8")
            touched.append(rel)

    # Anything in scope but absent from the map is left untyped on purpose: it
    # should be reported loudly, not silently guessed.
    for p in sorted(REPO.glob("docs/**/*.md")):
        rel = str(p.relative_to(REPO))
        if rel not in TYPES:
            untyped.append(rel)

    print(f"typed {len(touched)} file(s)")
    for rel in touched:
        print(f"  {rel}")
    if missing:
        print("\nmissing (skipped):")
        for rel in missing:
            print(f"  {rel}")
    if untyped:
        print("\nIN SCOPE BUT UNMAPPED (check_docs will flag these):")
        for rel in untyped:
            print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
