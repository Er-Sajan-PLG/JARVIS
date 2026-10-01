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
./scripts/setup.sh   # venv + deps + ALL hooks (framework and native) + API key
```

Manual equivalent (must include BOTH hook installs — skipping either leaves
commits unenforced on your machine):

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install "pre-commit==4.6.2"   # NOT in requirements.txt (runtime set)
.venv/bin/pre-commit install                # framework hooks (or rely on native path below)
.venv/bin/python scripts/bump_version.py install-hooks  # native githooks via core.hooksPath
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
6. **PR** — describe what/why; CI runs all <!--fact:gate_count-->29<!--/fact--> gates.

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

## Documentation system (autonomous, enforced)

Every code change must keep its docs true. Three layers enforce this:

- **Layer 1 — pre-commit** (`.venv/bin/python scripts/docs/check-changed.py`, wired
  in `.pre-commit-config.yaml`): staged-scope only, seconds. Blocks the commit when
  staged code changes public surface without its manifest-mapped doc, when new
  defs lack docstrings, or when staged markdown has broken fences/links/paths.
- **Layer 2 — pre-push + local CI** (`scripts/docs/check-full.py`, `gate_docs_layer2`
  in `scripts/ci_gate.py`): whole tree — manifest completeness, markdown, spelling,
  snippet compile checks, generated-vs-committed diff, live fact cross-validation.
  Fails the push/gate.
- **Scheduled** (`scripts/scheduled_doc_maintenance.py`, 15-day): external links +
  semantic-review packets, auto-opens a GitHub issue.

Rules: no `--no-verify` culture — the local CI plane (`ci_gate.py` via n8n) is the
backstop even if a hook is bypassed. New docs go in `docs.manifest.yaml`
(classify every doc, or mark it `standalone, reviewed <date>`); new modules get a
generated `app/<pkg>/README.md` via `scripts/docs/generate.py --apply` (hand notes
go below the marked block — the generator only replaces marked content).
Run checks locally:

```bash
.venv/bin/python scripts/docs/manifest-validate.py
.venv/bin/python scripts/docs/check-changed.py
.venv/bin/python scripts/docs/check-full.py
.venv/bin/python scripts/docs/generate.py --apply  # then stage the result
```

Rule of thumb: never hardcode volatile counts (tests, gates, files) in prose;
cite them via fact markers (auto-synced; see `sync_doc_facts.py` for the list)
or omit the number — stale numbers in prose are the exact drift this system
exists to kill.

When GitHub billing returns, mirror Layer 2 as a required PR check (exact recipe
in `DOCS_SYSTEM_DESIGN.md` §7).

## Questions

Open an issue, or read the ADRs (`docs/adr/`) for why decisions were made.
