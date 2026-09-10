# Coding Standards

- Python 3.11/3.12 only
- `ruff` for lint; `mypy --strict` for type check
- `.pre-commit-config.yaml` + `githooks/pre-commit`
- Tests: `tests/unit/` (pure, fast); `tests/contract/` (verifiable); `tests/e2e/` (verified before deploy)
- One increment per logical change; commit per logical change; never batch
