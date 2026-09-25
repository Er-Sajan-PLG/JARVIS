# Autonomous Documentation System — Design

**Status**: ACTIVE
**Type**: architecture
**Last Updated**: 2026-09-26
**Reviewed**: 2026-09-26
**Source**: `DOCS_AUDIT_REPORT.md` (Phase 1), `scripts/docs/` at HEAD

**Date**: 2026-09-26 · **Status**: design → implementing · **Source**: `DOCS_AUDIT_REPORT.md` (Phase 1), live repo inspection
**Non-goals**: replacing `check_docs.py`, `check_doc_coverage.py`, `sync_doc_facts.py`, the board, or the n8n plane. This system *closes the gaps around them* (Layer-1 co-change detection, manifest, markdown/style, snippet checks, generated-vs-hand separation).

---

## 1. Architecture

```
                ┌──────────────────────── docs.manifest.yaml ────────────────────────┐
                │ section → code paths (+ generated | hand, owner, staleness class) │
                └──────────────┬───────────────────────────────┬───────────────────┘
                               │                               │
              LAYER 1 (pre-commit, seconds, staged-only)        │  LAYER 2 (pre-push/ci_gate/n8n, full tree)
                               │                               │
           scripts/docs/check-changed.py ◄────────────► scripts/docs/check-full.py
             - staged py ↔ manifest reverse index                 - Layer-1 rules over ALL files
             - docstring presence (new defs)                     - markdownlint-core + codespell-lite
             - md lint + internal links (staged)                 - full internal-link graph + orphans
             - manifest completeness                             - snippet compile check (py blocks)
             - facts regen (changed scope)                       - generated-vs-committed diff
                               │                               │
              manifest-validate.py (both layers: every doc classified or fails)
```

**Single sources of truth**: routes → `app/adapters/*` (already censused); env → `os.getenv` reads (already censused); facts → `sync_doc_facts.py` (already synced); ADRs → `docs/adr/`; **new**: module READMEs ← package docstrings (generated, marked); CLI reference ← `--help` (generated, marked); manifest ← `**Source**` bindings (seeded once, then enforced).

**Generated vs hand**: generated blocks delimited by `<!-- generated:<name> begin -->` / `<!-- generated:<name> end -->`; Layer-2 diffs regenerated output against committed blocks. Hand prose outside markers is never touched by generators.

## 2. Layer 1 — `scripts/docs/check-changed.py` (pre-commit, staged-only)

Inputs: `git diff --cached --name-only` (+ staged content via `git show :path`). Rules:
- R1 **co-change**: staged `app|scripts|evals/**/*.py` ∩ manifest reverse index → mapped doc section must also be staged (or the code change must carry `docs: not-needed` trailer — explicit, auditable). Block otherwise with the exact doc path.
- R2 **docstrings**: new `def/class` (added lines starting with `def |class |async def `, minus tests) without a docstring within 3 lines → block (stdlib `ast` on staged content).
- R3 **markdown**: changed `*.md` → heading-structure lint (single H1, no skipped levels, no trailing whitespace beyond pre-commit's, fenced-block balance), internal `](...)` targets resolve (repo- or doc-relative), no new backticked path that fails `rel_exists` logic.
- R4 **manifest**: every staged doc must be classifiable (in manifest or `standalone, reviewed <date>`); `docs.manifest.yaml` itself must stay valid YAML matching the schema.
- R5 **facts**: run `sync_doc_facts.py` in check mode over changed scope; if it would rewrite, block with the command to apply (same UX as the existing hook).
- Exit non-zero blocks commit. Runtime target <10s (staged-only by construction). No network.

## 3. Layer 2 — `scripts/docs/check-full.py` + `generate.py` (pre-push subset, `ci_gate` gate, n8n schedule)

- Full-tree R1–R5; full internal-link graph + orphan report (dir-linked-only files flagged, matching the audit's 27); codespell-lite (repo-local wordlist, stdlib); snippet check: fenced ` ```python ` blocks extracted and `compile()`-checked (execution only for a curated `docs/snippets/*.py` allowlist — never arbitrary exec); generated-block diff for module READMEs + CLI reference + manifest-derived index.
- Wiring: new `gate_docs_layer2` in `scripts/ci_gate.py` (offline subset: everything except external links); network checks (external links, already in `scheduled_doc_maintenance.py`) stay on the 15-day schedule reusing its auto-issue path. GitHub Actions yaml gets a mirror job marked `required: true` **documented as dormant** (billing-disabled) with exact re-enable steps.

## 4. Manifest — `docs.manifest.yaml`

```yaml
version: 1
sections:
  - doc: docs/TOOLS.md
    covers: [app/tools/, app/guardrails/policy.py]
    kind: hand
    staleness: content        # facts | content | semantic | snapshot
    owner: tools
  - doc: app/modes/README.md # generated
    covers: [app/modes/]
    kind: generated
    generator: scripts/docs/generate.py:module_readmes
```

`manifest-validate.py`: every `docs/**/*.md` + root `*.md` + `app/*/README.md` + `n8n/README.md` + `tgcall/README.md` + `prompts/*.md` must appear exactly once, or carry `standalone, reviewed <date>` in its header block. Seeded from `**Source**` bindings + audit inventory (Phase 3 populates all 100+).

## 5. Enforcement & no-bypass

- Pre-commit: new `scripts/docs/check-changed.py` repo entry (local `repo: local` hook — zero installs, works offline). Non-zero blocks.
- Pre-push: extend `githooks/pre-push` Stage 4 with Layer-1-over-range + Layer-2 offline subset (it already runs the doc gates + unit suite; we add the two scripts, not a new stage).
- CI: `gate_docs_layer2` in `ci_gate.py` (the real backstop — runs locally via n8n every 30 min and on demand). GitHub branch-protection recipe ships in `CONTRIBUTING.md` for the day billing returns (exact clicks + `gh api` commands).
- Scheduled: existing 15-day sweep keeps network checks; add manifest-drift + generated-diff to its packet source (read-only additions).
- `CONTRIBUTING.md` documents the no-bypass rule with CI/local-plane as backstop (mirroring the existing hook philosophy).

## 6. As-built deltas (decisions taken during implementation)

- **No single-H1 / no-skipped-levels rules.** House style uses repeated `# path`
  file-marker headings; `check_docs.py` deliberately omits these rules. Enforcing
  them would reformat ~15 docs for zero truth gain. Fences, links, and path claims
  are still enforced.
- **Orphans are warnings in v1** (ratchet philosophy, mirroring the ruff ratchet):
  27 pre-existing orphans must not red-day-one new code. The remaining-work list
  tracks the `docs/README.md` index fix.
- **Frozen archive excluded** from link/path/snippet rules (do-not-cite by policy).
- **Deletion ledgers reuse `PATH_CHECK_EXEMPT`** (shared rule with `check_docs.py`).
- **`sync_doc_facts.py --apply` (no `--run-tests`) writes a STALE `test_count`**
  (static estimate vs live collection). Never rely on its test_count; hand-set from
  pytest collection totals until the script is fixed (remaining work).

## 7. Branch-protection recipe (for the day billing returns)

```bash
# 1. Re-enable the workflow triggers in .github/workflows/ci.yml
#    (pull_request: opened/synchronize/reopened + push to main).
# 2. Add the Layer-2 job (or extend governance) running:
#    .venv/bin/python scripts/docs/check-full.py
# 3. Mark it required:
gh api repos/Er-Sajan-PLG/JARVIS/branches/main/protection -X PUT \
  -H Accept:application/vnd.github+json \
  -f required_status_checks[strict]=true \
  -f required_status_checks[checks][][context]='Virtual Board Governance' \
  -f enforce_admins=true \
  -f required_pull_request_reviews[required_approving_review_count]=1 \
  -f restrictions='null'
# Click path: Settings → Branches → Add rule → branch name `main` →
# Require status checks → search the Layer-2 check → Require branches up to
# date → Require 1 approval → Include administrators → Save.
```

## 8. Tool choices (justified)

No new frameworks, no daemons, no network dependencies: pure-stdlib Python scripts (repo already runs 57 scripts this way), `pre-commit` local hooks (already adopted), codespell rules vendored as a wordlist (not the package — avoids a new dependency for v1; upgrade path documented). Markdownlint/vale rejected: Node toolchain + network installs the repo deliberately avoids (root `package.json` is diagram-only). Interrogate rejected for v1: custom 20-line AST docstring check covers the rule without a new pinned dep. Mkdocs/Docusaurus rejected: no serving need; the repo's docs are GitHub-rendered.
