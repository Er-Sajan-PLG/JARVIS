# Documentation Governance

**Status**: ACTIVE
**Last Updated**: 2026-09-13

**Created**: 2026-09-13
**Authority**: `docs/GOVERNANCE.md`; repo-root `AGENTS.md` §Documentation
**Reviewed**: 2026-12-13

---

## 1. Why this document exists

On 2026-09-13 every file under `docs/` (82 markdown files) was read end-to-end and
compared against the code. The audit found four classes of defect that had been
surviving review for weeks:

| Defect | Example found |
|---|---|
| **Two competing navigation maps** | `docs/README.md` **and** `docs/INDEX.md`, both claiming to be "the master map", disagreeing on document counts and on which files existed |
| **Frozen snapshots presented as current** | `docs/HEALTH_REPORT.md` listed the *same* `HEAD` row three times with three different test counts (108 / 109 / 110) and no "historical" banner |
| **Auto-generated stubs with empty tables** | `docs/modules/config.md`, `githooks.md`, `scripts.md` — a title, `[Auto-generated from repository tree scan]`, and a header row with zero data rows |
| **Docs describing files that do not exist** | `docs/modules/frontend.md` (→ `frontend/app.js`), `docs/modules/tests.md` (→ `tests/stress_test.py`), `docs/CONFIG.md` (→ `paths` that moved), `docs/STARTUP_FLOW.md` (→ a CLI loop that was deleted), `docs/BRANCH_PROTECTION_SETUP.md` (→ a UI action that the GitHub plan blocks) |

Each one is a bug by the rule in `docs/README.md`: *if a document and the code
disagree, the code wins — and the document is a bug.* This file makes that rule
mechanically checkable instead of aspirational.

---

## 2. Required status header

Every file under `docs/` **must** begin with a level-1 heading followed by a
status block containing at least:

```markdown
# Title

**Status**: ACTIVE
**Last Updated**: 2026-09-13

Body…
```

Documents that assert behaviour **must** additionally name their source, e.g.
`**Source**: app/brain/runner.py at HEAD`.

### The four statuses

| Status | Promise | May a reader act on it? |
|---|---|---|
| **ACTIVE** | Describes the system as it exists at `HEAD`. Reviewed within its cadence. | **Yes** |
| **SNAPSHOT** | A dated measurement. True on its date, not maintained. | Only with the date in hand |
| **HISTORICAL** | Describes a past state on purpose (archaeology, release notes). | **No** — it is history |
| **DRAFT** | Not yet reviewed. Never binds. | **No** |

A file with **no** status header is treated as **DRAFT** by default. That is the
safe failure direction: an unlabelled document can never be cited as authority.

---

## 3. Where a document belongs

| Directory | Holds | Migration rule |
|---|---|---|
| `docs/` (top level) | Living documents a contributor reads to do work | — |
| `docs/adr/` | Numbered decisions, immutable once Accepted | Superseded decisions stay, marked superseded |
| `docs/architecture/`, `docs/modules/`, `docs/timelines/` | Structural diagrams and per-subsystem histories | Must name the code paths they describe |
| `docs/migrations/` | Migration notes and the tombstone registry | — |
| `docs/archive/` | Superseded snapshots and frozen release cycles | **Move here, never silently delete** a document that was ever cited as current |

**Deletion is the exception, and it has a bar.** A document may be deleted
outright only if it is (a) an auto-generated stub with no content, (b) an exact
duplicate of a surviving document, or (c) verifiably wrong about a file that does
not exist and has no historical value. Anything that was ever authoritative moves
to `docs/archive/` instead. The 2026-09-13 pass deleted nine files and moved four,
recorded in §5.

---

## 4. Rules that keep it from drifting again

1. **One navigation map.** `docs/README.md` is the only index. Do not create a
   second one; add a row to the existing tables instead.
2. **No doc without a status header** (§2). This is the single highest-value rule:
   it makes "is this current?" answerable without reading the body.
3. **No empty tables.** A table with a header row and zero data rows is a stub,
   not a document. Write it against real code or delete it.
4. **Every referenced path must resolve.** Before committing, run the checker in
   §6. A path in backticks that does not exist in the repo is a bug.
5. **Historical documents get a banner** immediately under the title, above all
   other content, stating the snapshot date and what superseded it.
6. **Never edit a document to make a claim true.** Edit the code, or record the
   gap in `docs/ACCEPTED_RISKS.md`. This is the rule that RISK-012 (branch
   protection) and the 2026-09-13 token correction both turn on.
7. **Update the doc in the same change as the code.** A PR that changes behaviour
   without touching its document is incomplete.
8. **No version pinning in a living document's title** (§8). A doc edited across
   releases cannot honestly carry "v3.0.0"; the release tag *is* the version.

---

## 5. The 2026-09-13 pass, recorded

**Deleted (9)** — reasons per §3:

| File | Why |
|---|---|
| `docs/INDEX.md` | Duplicate navigation map (rule 1) |
| `docs/CODING_STANDARDS.md` | 9-line Sprint-3 stub; superseded by repo-root `AGENTS.md` and `docs/DEVELOPMENT.md` |
| `docs/BRANCH_PROTECTION_SETUP.md` | Instructed a GitHub-UI action that the plan blocks (RISK-012); the surviving record is `docs/CI-TOKEN-PERMISSIONS.md` |
| `docs/STARTUP_FLOW.md` | Duplicated `docs/architecture/startup_flow.md`; described a CLI `while True:` loop that no longer exists (`app/main.py` is FastAPI + uvicorn) |
| `docs/modules/config.md` | Empty auto-generated stub |
| `docs/modules/githooks.md` | Empty auto-generated stub |
| `docs/modules/scripts.md` | Empty stub; documented `scripts/bump_version.py`, which is **not** the authoritative version path |
| `docs/modules/frontend.md` | Referenced `frontend/app.js`, which does not exist |
| `docs/modules/tests.md` | Referenced `tests/stress_test.py`, which moved to `tests/performance/` |

**Moved to `docs/archive/` (4)** — historical, but previously cited as current:

| From | To | Why |
|---|---|---|
| `docs/HEALTH_REPORT.md` | `docs/archive/HEALTH_REPORT_2026-07-28.md` | Frozen 2026-07-28 scorecard with no banner and self-contradicting numbers |
| `docs/HISTORY.md` | `docs/archive/HISTORY.md` | Commit-by-commit archaeology of the pre-v3.0 era |
| `docs/API.md` | `docs/archive/API_SIGNATURE_HISTORY.md` | Historical signature-evolution log, not the API contract (`docs/API_CONTRACT.md` is) |
| `docs/DEVLOG.md` | `docs/archive/DEVLOG.md` | Release-cycle development log; superseded by `docs/CHANGELOG.md` for current releases |

**Corrected in place** — documents that stay authoritative but carried stale
claims: `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`,
`docs/GOVERNANCE.md`, `docs/DEVELOPMENT.md`, `docs/VERSIONING.md`,
`docs/CI-TOKEN-PERMISSIONS.md`, `docs/CHANGELOG.md`, `docs/CONFIG.md`,
`docs/DATABASE.md`, `docs/modules/*`, `docs/SPRINT_1_2_COMPLETION.md`.

---

## 6. The checker

`scripts/check_docs.py` enforces rules 1-5 mechanically and runs in CI.

```bash
.venv/bin/python scripts/check_docs.py          # report
.venv/bin/python scripts/check_docs.py --strict # non-zero exit on findings
```

It checks, for every `docs/**/*.md` plus the root-level markdown files:

- a `**Status**:` header exists and is one of the four allowed values;
- no markdown table consists only of a header row and a separator row;
- every repo-relative path written in backticks resolves on disk
  (URLs, absolute paths and glob patterns are skipped);
- `docs/README.md` is the only file whose title claims to be the navigation map;
- no ACTIVE document pins a version in its **title** (rule 5 / §8) — version
  numbers in the body are legitimate and are not flagged.

Adding a new exception is a code change with a rationale in the script, not a
silent skip.

---

## 7. Review cadence

| Document class | Cadence | Trigger |
|---|---|---|
| `ARCHITECTURE.md`, `GOVERNANCE.md` | Quarterly | Architectural or process change |
| `ROADMAP.md`, `SPRINT_*` | Per sprint | Sprint boundary |
| `API_CONTRACT.md` | Per release | API change |
| `CI-GATE-SOTA.md`, `CI-TOKEN-PERMISSIONS.md` | Quarterly, or on any CI change | Token/permission change |
| `CAPABILITY_TRACKER.md` | Quarterly | Manual review |
| Everything in `archive/` | Never | Frozen by definition |

A document past its review date without a re-read is a governance failure and
belongs in `docs/ACCEPTED_RISKS.md`, not quietly ignored.

---

## 8. Versioning documents

Documents are versioned by **git and the release tag**, not by a number in the
filename. There is exactly one exception.

**The rule.** A living document is never renamed to carry a version.
`docs/ARCHITECTURE.md` stays `docs/ARCHITECTURE.md` across every release; its
history is the file's git log, and the version a reader should assume it
describes is the latest release tag on the branch (`docs/VERSIONING.md`). This is
why the old `# JARVIS Architecture — Living Document v3.0.0` title was wrong: a
v3.0.0 banner on a document edited through v3.3.0 told readers it was frozen when
it was not.

**The exception.** A document that is *replaced* rather than updated is frozen
under a versioned name in `docs/archive/`, and its successor is created fresh:

| Pattern | Example | Meaning |
|---|---|---|
| `docs/archive/<NAME>_v<X.Y.Z>.md` | `docs/archive/CHANGELOG_v3.0.0.md`, `docs/archive/DEVLOG_v3.0.0.md` | The complete document as it stood at that release cycle. Never edited again. |
| `docs/archive/<NAME>_<YYYY-MM-DD>.md` | `docs/archive/HEALTH_REPORT_2026-07-28.md` | A dated measurement not tied to a release. |

**What this means in practice:**

1. To change a living doc, edit it in place and update `**Last Updated**`. Do not
   create `ARCHITECTURE_v3.4.0.md` — that is what the archive naming is for, and
   only when the whole document is being retired.
2. To retire a living doc, copy it to `docs/archive/` with the version suffix and
   state in the commit message what supersedes it. Never silently overwrite
   history in place.
3. `docs/CHANGELOG.md` is the single place release notes accumulate; the archived
   `CHANGELOG_v3.0.0.md` is the pre-split artefact retained for history.
4. Every release tag must have a matching GitHub Release (automated by
   `githooks/pre-push` → `scripts/publish_release.py`), so "which docs described
   release X" is answerable by checking out that tag.
