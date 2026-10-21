# MACP REGISTRY — Active Agents

**Updated**: 2026-10-01T05:00Z

An agent is **ACTIVE** if it has a session file dated within 24 h. Anything older
is **INACTIVE** and its file claims may be taken over — document the takeover in
your own session file and add a `[COORDINATION]` note to theirs.

---

## Active

| Agent ID | Type | Branch | Task | Since (UTC) | Status | Claims |
|---|---|---|---|---|---|---|
| `HERM` | Hermes Agent (`meituan/longcat-2.5-preview:free`) | `docs/state-record-correction` | Clear the real merge blocker (trivy); drain the Dependabot queue; correct the B-007 record | 2026-10-21T04:30Z | IN-PROGRESS | `state/**`, `.github/dependabot.yml` |
| `MACP` | DeepSeek Harness agent | `fix/ruleset-helper-payload-v2` | Bootstrap MACP; CI/CD platform enforcement | 2026-10-01T05:00Z | **PARTIAL → superseded** (B-007 cleared 2026-10-21; both artefacts merged via #147) | released |

### `MACP` file claims — RELEASED

This session ended at `7b8ed44` with outcome **PARTIAL** (see
`sessions/20261001-0500-MACP-bootstrap-audit.md`). **All claims are released.**

Two files still carry unmerged work on the branch `fix/ruleset-helper-payload-v2`
(PR #147): `scripts/setup_branch_protection.py` and everything under `state/`.
If you need them, coordinate through that PR rather than editing `main`.

The claims below are retained only as a record of what this session owned:

- `state/**` (bootstrap)
- `scripts/ci_gate.py`
- `scripts/setup_branch_protection.py`
- `scripts/pin-actions.mjs`
- `scripts/install_ci_tools.sh`
- `.github/**`
- `tests/unit/test_gate_action_pinning.py`
- `tests/unit/test_gate_require_tools.py`
- `tests/unit/test_provenance_keyless.py`
- `tests/unit/test_openrouter_max_tokens.py`

Shared files touched — require a `[COORDINATION]` note if another agent needs them
in the same window: `AGENTS.md`, `SECURITY.md`, `docs/ACCEPTED_RISKS.md`,
`docs/CI-GATE-SOTA.md`.

---

## Inactive

*None recorded. This is the first MACP session in this repository.*

---

## Conventions

- **Agent ID**: 4 alphanumeric characters. `MACP` is reserved for the bootstrap
  session so it is greppable as the origin of this directory.
- **One row per session**, not per agent. Two concurrent sessions by the same
  tool are two rows with distinct IDs.
- Release claims in your shutdown step. Do not leave a stale row: the next agent
  trusts this table to decide whether it may touch a file.
- If you must edit a file another ACTIVE agent has claimed, STOP and coordinate.
  Never resolve an overlap by going first and hoping.
