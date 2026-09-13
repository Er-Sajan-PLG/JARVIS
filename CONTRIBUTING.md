# Contributing to JARVIS

**Status**: ACTIVE
**Type**: governance
**Source**: `AGENTS.md`, `githooks/pre-commit` at HEAD
**Last Updated**: 2026-09-13

Thanks for contributing. This project follows strict governance — read
`AGENTS.md` at the repo root **before** making any change. Key rules are
summarized below; `AGENTS.md` is authoritative.

## Prerequisites

- Python 3.11 (do NOT use 3.14 — ML deps don't build)
- A working `.venv` (see `docs/DEVELOPMENT.md`)

```bash
cd /home/sajan/Projects/JARVIS
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Workflow

1. **Read** `AGENTS.md`, `docs/ARCHITECTURE.md`, relevant `docs/adr/*`.
2. **Branch** — never commit to `main`. `git checkout -b <type>/<desc>`.
3. **Test-first** — write the failing test, then implement.
4. **Verify** — run the full gate before committing:

```bash
.venv/bin/ruff check app/ tests/
.venv/bin/ruff format --check app/ tests/
.venv/bin/mypy --strict app/
.venv/bin/pytest tests/ -q
.venv/bin/python scripts/board/review.py
.venv/bin/python scripts/sota_governance.py
```

5. **Commit** — conventional commits (`feat:`, `fix:`, `chore:`, etc.), small scope.
6. **PR** — describe what/why; CI runs all <!--fact:gate_count-->25<!--/fact--> gates.

## Standards

| Concern | Tool | Config |
|---------|------|--------|
| Lint/format | `ruff` | `pyproject.toml` |
| Types | `mypy --strict` | `pyproject.toml` |
| Tests | `pytest` | `pyproject.toml` |
| Architecture | `scripts/board/review.py` | package boundaries |
| SOTA governance | `scripts/sota_governance.py` | security/SLSA/SBOM |

## Architecture boundaries (enforced)

```
app.adapters   → app.bootstrap, app.brain
app.bootstrap  → brain/models/resources/memory/session/workspace/telemetry/prompt/guardrails/artifacts
app.brain      → app.domain, app.events, app.guardrails
app.models     → app.resources
app.memory     → app.integrations
app.telemetry  → app.events
```

`app/domain/` is pure dataclasses (stdlib only). Violating a boundary fails CI.

## Commit convention

```
<type>(<scope>): <description>
```

Types: `feat` `fix` `chore` `docs` `refactor` `test` `breaking`.

## Questions

Open an issue, or read the ADRs (`docs/adr/`) for why decisions were made.
