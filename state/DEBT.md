# MACP DEBT — JARVIS Technical Debt

Every entry is a **known, measured** liability with a location. Adding debt
without a row here is a protocol violation (log `[DEBT]` in your session file).

Severity: **S1** blocks correctness or security · **S2** slows every future change
· **S3** cosmetic or opportunistic.

---

Per **P5**, each measured count carries its reproduction command. Re-run before
acting on a number; the counts were verified 2026-10-01 and may have moved.

| ID | Sev | Debt | Location | Impact | Remediation |
|---|---|---|---|---|---|
| D-001 | S2 | **`mypy --strict` reports 504 errors in 86 files** (of 197 checked) — `.venv/bin/mypy --strict app/`, 2026-10-01 | `app/` | Types give no safety net on the majority of the codebase; the 504 figure is a ratchet ceiling, not a target | Burn down per-subsystem; start with `app/domain` (pure dataclasses, cheapest) |
| D-002 | S2 | **~519 mocks without `spec=`, 0 `create_autospec`.** ~122 stand in for JARVIS's own classes — approximate; recount with `grep -rno 'Mock()\|MagicMock()' tests/ | wc -l` before relying on it | `tests/` | A mock invents any method called on it, so a test asserting against a mock can pass while the real class lacks the method. This has already produced false confidence (F-TEST-005) | Retrofit `spec=` at boundaries first — clients, registries, repositories |
| D-003 | S3 | **`docs/snippets/` does not exist.** Fenced markdown code blocks are `compile()`-checked, never executed | `docs/` | A documented example can be syntactically valid and behaviourally wrong | Add an executable-snippet runner if docs examples grow |
| D-004 | S2 | **Four unreachable subsystems** carry tests and prose that imply they run | `app/agents/`, `app/integrations/mcp/`, `app/mcp/`, `app/models/switcher.py` | A green suite does not mean the capability works. Register exists but the code remains | Wire them or delete them; the register alone is a holding pattern |
| D-005 | S2 | **Whole-tree ruff debt**: `ruff check tests/` reports 85 errors, 40 files unformatted — 2026-10-01 | `tests/` | Only *changed* files are enforced (ratchet), so the backlog never shrinks on its own | Periodic `ruff check --fix` sweep with a review pass |
| D-006 | S3 | **`external/Unlimited-OCR` is a 94 MB gitlink** with no `.gitmodules`, unused by any code path | `external/` | Bloats every clone; `-dirty` status pollutes `git status` | Remove the gitlink (see `BLOCKERS.md` B-001) |
| D-007 | S2 | **Coverage gate is opt-in *and* non-blocking** | `scripts/ci_gate.py` `gate_coverage` | An opt-in, non-blocking gate never fails anything by itself; 86% is a measurement, not a ratchet | Decide: make it blocking at the current floor, or accept it as a report |
| D-008 | S3 | **`tests/e2e/` does not exist** though `AGENTS.md` §3.2 once implied it did | `tests/` | No end-to-end coverage of a real user journey | Either build it or remove the row (currently kept deliberately as a visible gap) |
| D-009 | S2 | **PyYAML settings deprecation warnings** in `pyproject.toml` on every ruff run | `pyproject.toml` | Noise that hides real findings | Move `select`/`ignore` under `[tool.ruff.lint]` |
| D-010 | S3 | **`artifacts/AUDIT-NOW.md` and `_audit/` carry stale prose** describing superseded state | `artifacts/`, `_audit/` | Agents reading them as current will re-derive findings that are already fixed | Mark as snapshots with a date, or regenerate |

---

## Resolved this window

| ID | Was | Fixed by |
|---|---|---|
| D-R1 | Pre-push hook ran 2011 of 2128 tests while claiming "full suite" | PR #141 |
| D-R2 | Coverage measured statements only; docstring claimed 98% | PR #139 |
| D-R3 | Two Protocols lacked `@runtime_checkable`, so `isinstance` raised | PR #135 |
| D-R4 | Two security guards passed when the guarded code was deleted | PR #140 |
| D-R5 | Missing blocking scanner reported `skip` → gate green while enforcing nothing | `--require-tools` (ADR-002) |
| D-R6 | Actions pinned to mutable tags (SUP-010) | `gate_action_pinning` (ADR-004) |
| D-R7 | `urllib3==2.7.0` carried CVE-2026-97687 / CVE-2026-97689 (both fixed in 2.8.0) | `0ec6128` |
| D-R8 | The ruff ratchet reported *checked* files as *failing* files | `59fd80c` |

---

## Adding debt

```markdown
| D-0NN | S1/S2/S3 | **What** | `path:line` | Why it matters | How to fix |
```

Prefer a measured number over an adjective. "504 errors" is actionable;
"many type errors" is not.
