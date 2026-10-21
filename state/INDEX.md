# MACP INDEX — Session Log

One row per session. Newest first. Use this to find prior work by keyword or file
path **before** reading session files — reading all of them wastes context.

| Session ID | Agent | Date | Title | Files touched | Status | Branch |
|---|---|---|---|---|---|---|
| `20261021-0430-HERM` | HERM | 2026-10-21 | Clear the real merge blocker (trivy findings, not the signature rule); merge #137/#147/#164; drain the Dependabot queue; correct the B-007 record | `state/**`, `.github/dependabot.yml`, `requirements.txt`, `package-lock.json`, `docs/ACCEPTED_RISKS.md` | IN-PROGRESS | `docs/state-record-correction` |
| `20261001-0500-MACP-bootstrap-audit` | MACP | 2026-10-01 | Bootstrap MACP + repository audit; CI/CD platform enforcement (GitHub Actions, ruleset, keyless provenance, action pinning, requirements.txt repair) | `state/**`, `.github/**`, `scripts/ci_gate.py`, `scripts/setup_branch_protection.py`, `scripts/pin-actions.mjs`, `scripts/install_ci_tools.sh`, `requirements.txt`, `tests/unit/test_gate_*.py`, `tests/unit/test_provenance_keyless.py`, `tests/unit/test_tokenizer.py`, `tests/unit/test_context.py` | **PARTIAL** — B-007 (since cleared; both artefacts merged via #147) | `fix/ruleset-helper-payload-v2` |

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
