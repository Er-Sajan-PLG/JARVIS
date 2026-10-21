# MACP REGISTRY — Active Agents

**Updated**: 2026-10-01T05:00Z

An agent is **ACTIVE** if it has a session file dated within 24 h. Anything older
is **INACTIVE** and its file claims may be taken over — document the takeover in
your own session file and add a `[COORDINATION]` note to theirs.

---

## Active

| Agent ID | Type | Branch | Task | Since (UTC) | Status | Claims |
|---|---|---|---|---|---|---|
| `MACP` | DeepSeek Harness agent | `test/assertion-defects` | Bootstrap MACP; then CI/CD platform enforcement | 2026-10-01T05:00Z | IN-PROGRESS | see below |

### `MACP` file claims

Owned exclusively for the duration of this session:

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
