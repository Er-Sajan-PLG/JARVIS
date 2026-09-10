# JARVIS Coding Standards (Sprint 3)

- Python 3.11/3.12 only; `.pre-commit-config.yaml` + `githooks/pre-commit`
- `ruff` lint (ratchet: changed files only); `mypy --strict` (non-blocking, per RISK-005)
- Tests: `tests/unit/` (pure, fast); `tests/contract/` (verifiable); `tests/sprint3/` (Sprint-3 contract targets)
- Docs sync: `docs/CHANGELOG.md` (v1.2.0.dirty); `docs/AUDIT-USAT.md` (76.2/100); `docs/AGENTS.md` (frozen reference, not edited by Sprint 3)
- Version tracking: `bump_version.py` (patch/minor/major + install-hooks); `.env.example` (26 provider keys)
- Incremental commits only (AGENTS.md §1.2 loop); one logical change per commit; never batch
- Sprint 4 deferred (`tests/sprint4/` verified absent)
