# MACP INDEX — Session Log

One row per session. Newest first. Use this to find prior work by keyword or file
path **before** reading session files — reading all of them wastes context.

| Session ID | Agent | Date | Title | Files touched | Status | Branch |
|---|---|---|---|---|---|---|
| `20261001-0500-MACP-bootstrap-audit` | MACP | 2026-10-01 | Bootstrap MACP + repository audit; CI/CD platform enforcement | `state/**`, `.github/**`, `scripts/ci_gate.py`, `scripts/setup_branch_protection.py`, `scripts/pin-actions.mjs`, `scripts/install_ci_tools.sh`, `tests/unit/test_gate_*.py`, `tests/unit/test_provenance_keyless.py` | IN-PROGRESS | `test/assertion-defects` |

---

## Searching

- **By file**: grep this table's *Files touched* column.
- **By area**: the titles name the subsystem, not the tool.
- **By outcome**: `COMPLETED` / `PARTIAL` / `BLOCKED` / `PIVOTED`.

## Status vocabulary

| Status | Means |
|---|---|
| `COMPLETED` | Objective met, verification run, merged or merged-ready |
| `PARTIAL` | Some objective met; remainder documented with next steps |
| `BLOCKED` | Cannot proceed; the blocker is in `BLOCKERS.md` |
| `PIVOTED` | Approach changed; the original and the reason are in the session file |
| `IN-PROGRESS` | Live. Do not take over its claims without coordinating. |
