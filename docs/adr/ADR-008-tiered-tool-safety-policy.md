# ADR-008: Tiered Tool Safety Policy & HITL Approval Gates

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-07-28

- **Status**: Approved
- **Date**: 2026-07-28
- **Version Tag**: `v3.0.0 Refactored`
- **Commit**: `f4d5e01`
- **Confidence**: `VERIFIED`

## Context
Tool execution in autonomous AI agents poses security risks if destructive tools (file deletion, directory creation, shell execution) run without user oversight.

## Decision
Establish a **Tiered Tool Safety Policy**:
1. **SAFE**: Automated pass-through for read-only tools (`read_file`, `git_log`, `git_diff_full`).
2. **SENSITIVE**: Policy-checked operations (`write_file`, `append_file`).
3. **DESTRUCTIVE**: Mandatory Human-In-The-Loop (HITL) approval gate (`create_directory`, file deletion, shell execution).
4. All tool functions are decorated with `@safety_gate(tier=...)`. When a destructive tool is called without explicit client approval, execution pauses with status `AWAITING_APPROVAL`.

## Consequences
- **Positive**: Protects workspace and user filesystem against unauthorized destructive actions; enforces explicit confirmation flow.
- **Negative**: Multi-step plans with destructive steps require interactive client confirmation before completing.
