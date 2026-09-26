# JARVIS Documentation Governance

**Type**: governance
**Status**: ACTIVE
**Last Updated**: 2026-09-14
**Reviewed**: 2026-09-14
**Source**: `scripts/doc_governance.py` + `scripts/doc_review_due.py` + `scripts/doc_type_table.py` + `scripts/check_docs.py` at HEAD

Inspired by [Universal_Software_Auditor](https://github.com/Er-Sajan-PLG/Universal_Software_Auditor)'s docs-sync system (ADR-0020), adapted to JARVIS's Python conventions.

## Two failure classes

| Class | What | Who owns |
|-------|------|----------|
| **Mechanical facts** | Counts, versions, paths, numbers | Machine: derived from source, written in, gate fails when they drift |
| **Prose truth** | "Is this sentence still accurate?" | Reader: `**Reviewed**:` markers + monthly cron |

## Marker forms

**Inline value** (HTML comments, survive Prettier, render invisibly):
```markdown
Tests: <!--fact:test_count-->1703<!--/fact-->
Coverage: <!--fact:coverage-->87<!--/fact-->
Gates: <!--fact:gate_count-->28<!--/fact-->
```

**Generated block** (content between markers is replaced wholesale):
```markdown
<!--fact:begin sprint-progress-->
...ASCII progress bars per sprint, auto-generated...
<!--fact:end sprint-progress-->
```

## Tools

| Script | What | When |
|--------|------|------|
| `scripts/doc_governance.py --sync` | Compute facts, rewrite markers, write cache | Pre-commit / CI / manual |
| `scripts/doc_governance.py --check` | Verify markers match current facts | CI gate |
| `scripts/doc_governance.py --facts` | Print current facts as JSON | Debug |
| `scripts/doc_review_due.py` | Semantic staleness check (`**Reviewed**:` markers) | Monthly cron |
| `scripts/doc_type_table.py` | Regenerate §10 type tables from code | Pre-commit |
| `scripts/sync_doc_facts.py` | Legacy fact sync (kept for compatibility) | Pre-commit |
| Monthly cron | Doc staleness review + prose re-read | 1st of month 9am |

## Fact sources (cheap — computed from repo)

| Fact | Source |
|------|--------|
| `commit` | `git rev-parse --short HEAD` |
| `branch` | `git branch --show-current` |
| `tag`, `version` | `git describe --tags` |
| `gate_count` | `grep -c "^def gate_" scripts/ci_gate.py` |
| `context_count` | `len(CONTEXT_ORDER)` in `scripts/ci_bridge.py` |
| `adr_count` | `ls docs/adr/ADR-*.md \| wc -l` |
| `board_count` | `grep -c "^def check_" scripts/board/review.py` |
| `doc_count` | `find docs -name "*.md"` |
| `cadence_*` | `CADENCE_DAYS` in `scripts/doc_review_due.py` |

## Fact sources (expensive — require test run)

| Fact | Source |
|------|--------|
| `test_count` | `pytest tests/ --collect-only` |
| `coverage` | `pytest tests/ --cov=app` |

## Cache

`.governance/doc_facts.json` caches expensive facts. Pre-commit hook uses cache for fast commits, falling back to full computation only when cache is missing.

## Sprint progress block

The `<!--fact:begin sprint-progress-->` block in `docs/ROADMAP.md` is auto-regenerated with ASCII progress bars showing each sprint's completion status, derived from the checkboxes in `CAPABILITY_TRACKER.md`.

## Review clock

Documents carry `**Reviewed**: YYYY-MM-DD`. Only this marker resets the review clock — deliberately **not** git history and **not** `**Last Updated**`. `doc_review_due.py` checks cadences (30d fast, 90d default, 180d slow, 365d historical) and a monthly cron opens a prose review packet.
