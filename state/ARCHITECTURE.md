# MACP ARCHITECTURE — JARVIS (as audited 2026-10-01)

**Status**: ACTIVE
**Type**: architecture
**Source**: `app/`, `scripts/`, `.github/` at `test/assertion-defects`
**Last Updated**: 2026-10-01

---

## 1. Runtime shape

```
                       ┌──────────────────────────┐
  HTTP / WebSocket ───▶ │  app/adapters (FastAPI)  │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │  app/bootstrap (root DI)  │  composition root
                       └────────────┬─────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌────────────────┐          ┌────────────────┐
│  app/brain    │          │  app/memory    │          │  app/models    │
│ intent→plan→  │          │ BM25 + Chroma  │          │ provider       │
│ execute→synth │          │ (hybrid)       │          │ routing        │
└───────┬───────┘          └───────┬────────┘          └───────┬────────┘
        │                          │                           │
        ▼                          ▼                           ▼
   app/domain               app/integrations              app/resources
   (pure dataclasses)       (Chroma, OCR)                 (budget, health)
```

Allowed import directions are declared in `AGENTS.md` §2.2 and enforced by
`scripts/board/review.py` (`architecture` check). `app/domain` is pure
dataclasses only — no framework imports, no I/O (`domain_purity` check).

**28 packages under `app/`.** The ones that matter for orientation:
`adapters, bootstrap, brain, memory, models, domain, events, guardrails, tools,
telemetry, resources, session, workspace, config, integrations, security`.

---

## 2. CI/CD — the area that changed most recently

### The gate is one script with two runners

```
                      scripts/ci_gate.py   ← ONE definition of "green"
                              │              29 checks
              ┌───────────────┴───────────────┐
              ▼                               ▼
   .github/workflows/ci-gate.yml      n8n → scripts/ci_bridge.py
   (GitHub Actions, required check)   (local automation plane)
```

This matters. Before 2026-10-01 there were **two divergent definitions of green**:
a six-job `ci.yml` on GitHub and the local `ci_gate.py`. They disagreed, and the
GitHub one was weaker — `bandit` and `pip-audit` ended in `|| true` (always
pass), `mypy` was `continue-on-error: true` (never blocking), and coverage was
line-only.

**`ci.yml` was deleted, not fixed.** `ci-gate.yml` now runs `ci_gate.py` directly,
so the runners cannot drift.

### How the workflow invokes it

```
.venv/bin/python scripts/ci_gate.py \
    --sha "$GITHUB_SHA" --require-tools --keyless --with-coverage
```

Three flags carry the enforcement:

| Flag | Why |
|---|---|
| `--require-tools` | A **missing blocking scanner becomes a failure, not a skip.** Without it, a tool that failed to install reports `skip`, and since `blocking_failures` only counts `fail`, the required check would go **green while enforcing nothing**. |
| `--keyless` | Sign provenance with the job's OIDC token (Fulcio + Rekor) instead of a local keypair, which cannot exist on a runner. Verification pins `--certificate-identity` and `--certificate-oidc-issuer` to this repo's own workflow. |
| `--with-coverage` | Adds the branch-aware coverage gate (non-blocking; floor 80%, currently 86%). |

Tool installation is `scripts/install_ci_tools.sh` — **one installer, used by both
the developer machine and CI**. It exits non-zero if a blocking scanner is
missing, so a partial install fails loudly.

### Enforcement is platform-level now

`scripts/setup_branch_protection.py` installs a ruleset on `main`:

| Rule | Effect |
|---|---|
| `pull_request` | No direct push to `main` |
| `required_status_checks` | **`ci-gate`** must pass. Exactly one context. |
| `strict_required_status_checks_policy` | Branch must be current with `main` |
| `required_signatures` | Unsigned commits rejected |
| `required_linear_history` | **No merge commits — squash or rebase only** |
| `non_fast_forward`, `deletion` | No force-push, no branch deletion |

`allowed_merge_methods: [squash, rebase]` follows from linear history.

> **Trap that was live until this session.** The previous
> `setup_branch_protection.py` required **six contexts** from `ci.yml`, which had
> never run. A required check that never reports never passes — `main` would have
> been permanently unmergeable. There is exactly one required check by design.

---

## 3. Data & storage

| Store | Path | Notes |
|---|---|---|
| ChromaDB (vectors) | `data/` | FTS5 index currently **corrupt** — see `BLOCKERS.md` B-002 |
| SQLite (sessions) | `data/` | |
| Postgres (checkpointer) | via `JARVIS_TEST_DATABASE_URL` | 2 tests skip when unset |
| Uploads | `data/uploads/` | contains real personal documents — **never commit, never upload** |

**Privacy is a hard constraint.** Sensitive data must never leave this machine.
`data/` is gitignored; `tests/` is verified free of personal identifiers.

---

## 4. Known structural gaps

These are documented rather than hidden — see `DEBT.md` and
`docs/architecture/DEAD-CODE-REGISTER.md`.

- **Four subsystems are unreachable**: `DocumentationAgent`, `MCPClientManager`,
  `MCPServer`, `ModelSwitcher`. Real and tested, but nothing in `app/` calls them.
  `ModelRouter` is excluded from that register because
  `tests/unit/test_router_call_sites.py` asserts the stronger prohibition.
- **`app/agents/` is not imported by `app/` at all.** `main.py` has no `docs`
  command. `AGENTS.md`'s isolation table calls MCP "missing" — the components
  exist and are *unwired*, which is a different thing.
- **`external/Unlimited-OCR`** is a 94 MB gitlink with no `.gitmodules`, unused.

---

## 5. Where the drift traps are

This repository's recurring failure mode is **a claim that outlives the thing it
describes**. Three live examples found this session, all fixed:

1. `AGENTS.md` §4.3 said branch protection was "NOT available" — true only while
   the repo was private.
2. **`ci.yml`'s own header** claimed it enforced 22 checks. It ran nothing.
3. Three docs claimed Cloudflare Pages deploy was "DONE". It has no secrets, used
   a deleted action, and never created the venv it invoked.

The defences in place: `scripts/check_docs.py --strict` (doc-type contract),
`sync_doc_facts.py` (machine-synced counts), and `tests/unit/test_*` tests that
assert behavioural facts rather than source text.
