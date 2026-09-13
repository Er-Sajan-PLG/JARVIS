# Documentation Governance

**Status**: ACTIVE
**Type**: governance
**Source**: `scripts/check_docs.py`, `scripts/doc_types.py` at HEAD
**Last Updated**: 2026-09-13

**Created**: 2026-09-13
**Authority**: `docs/GOVERNANCE.md`; repo-root `AGENTS.md` §Documentation
**Reviewed**: 2026-09-13

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
8. **No version pinning in a living document's title** (§9). A doc edited across
   releases cannot honestly carry "v3.0.0"; the release tag *is* the version.
9. **No hand-written numbers** (§8). Counts, versions and paths are fact markers
   derived from the repository; a typed number is a future lie.

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

`scripts/check_docs.py` enforces rules 1-5, and `scripts/sync_doc_facts.py`
enforces rule 6 (§8). Both run in CI.

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
- no ACTIVE document pins a version in its **title** (rule 5 / §9) — version
  numbers in the body are legitimate and are not flagged;

Adding a new exception is a code change with a rationale in the script, not a
silent skip.

---

## 7. Review cadence

There are two kinds of drift, and only one of them can be automated.

**Machine-checkable drift is already automated and needs no human action.** A
number, version, path or count that disagrees with the code fails
`scripts/sync_doc_facts.py --check` / `scripts/check_docs.py`, which run in both
`githooks/pre-commit` and the CI gate (`gate_docs`, `gate_doc_facts`). Those
values live in `<!--fact:` + fact-name + `-->`…`<!--/fact-->` markers and are re-derived from the
repository, so they cannot silently go stale. Nothing in this section is needed
for them.

**Semantic drift is what a human or agent must catch.** A document can be
structurally valid and numerically exact while no longer describing how the
system works. That is what the cadence below is for, and it is driven by
`scripts/doc_review_due.py`, which is the single source of truth for these
windows — the table is a readable mirror of `CADENCE_DAYS` in that script.

| Cadence | Documents | Trigger |
|---|---|---|
| **<!--fact:cadence_fast-->30<!--/fact--> days** | `ROADMAP.md`, `ACCEPTED_RISKS.md` | These move fastest and drive decisions |
| **<!--fact:cadence_quarterly-->90<!--/fact--> days** | `ARCHITECTURE.md`, `GOVERNANCE.md`, `API_CONTRACT.md`, `CAPABILITY-CONTRACT.md`, `CAPABILITY_TRACKER.md`, `CI-GATE-SOTA.md`, `CI-TOKEN-PERMISSIONS.md`, `DOC-GOVERNANCE.md` | Architectural, API, CI or process change |
| **<!--fact:cadence_default-->180<!--/fact--> days** (default) | `DEVELOPMENT.md`, `CONFIG.md`, `DATABASE.md`, `LLM.md`, `MEMORY.md`, `TOOLS.md`, and any unlisted living doc | Reference material that changes slowly |
| **<!--fact:cadence_historical-->365<!--/fact--> days** | `DEBUGGING.md` | Historical symptom log, kept for searchability |
| **Never** | `docs/archive/`, `docs/adr/`, `docs/timelines/`, `CHANGELOG.md`, `AUDIT-USAT.md`, `SPRINT_1_2_COMPLETION.md`, `DECISIONS-AUTONOMOUS-*.md`, `SYMBOL_LINEAGE.md` | Frozen by definition — a cadence here would only create noise |

**How the clock is measured.** From the explicit `**Reviewed**: YYYY-MM-DD` line
only — deliberately **not** from git history and **not** from the `**Last Updated**`
field. Both `git log` and a hand-maintained `Last Updated` record that *something*
changed, which is not the same as a re-read: a typo fix, a formatting pass, or an
automatic marker sync (`sync_doc_facts.py --apply` rewrites prose whenever a count
moves) all touch the file without anyone having judged whether it is still true.
Treating any of those as review evidence would let mechanical edits silently reset a
document's clock — the exact failure this cadence exists to prevent. Only
`**Reviewed**:` is a claim that a semantic re-read happened, so only it resets the
clock. Git activity is reported alongside it as *context* (`last_modified`,
`edits_since_review`): a document mechanically edited many times since its last
review is the strongest re-read candidate, but the count never moves the date. A
future-dated `**Reviewed**:` is rejected — it cannot evidence a review that has not
happened, and accepting it would let a typo park a document out of the queue
indefinitely.

**Enforcement and operation.**

```
.venv/bin/python scripts/doc_review_due.py            # what is due
.venv/bin/python scripts/doc_review_due.py --packet   # bounded review task
```

A scheduled job (`JARVIS doc staleness review`, monthly) runs the packet and
performs the re-read; automated drift is already covered by the gate, so the job
does only the part machinery cannot judge. A document past its window without a
re-read is a governance failure and belongs in `docs/ACCEPTED_RISKS.md`, not
quietly ignored.

---

## 8. Facts: numbers are derived, never remembered

Structural rules cannot catch a document that is well-formed and wrong. Before
this section existed, six documents asserted a gate count of 22 while the gate had grown to 24,
and `ACCEPTED_RISKS.md` still claimed a test count of 1028 and coverage of ~36%
after the real numbers were 1063 and 98%. Every one of those documents passed the
structural checker.

A number in a document is therefore not text — it is a **fact reference**:

```markdown
The gate runs <!--fact:gate_count-->25<!--/fact--> checks.
```

`scripts/doc_facts.py` derives the value from the repository;
`scripts/sync_doc_facts.py` writes it between the markers (`--apply`) and fails
when a committed value disagrees (`--check`).

**Facts come in two costs.** Cheap facts (git, filesystem, grep) are always
computable. Expensive facts need the test suite, so they are read from
`.governance/doc_facts.json`, which `ci_gate.py` writes after running pytest and
coverage. When no measurement exists the fact resolves to `unknown` and the
marker is **left alone** — an admitted gap is always better than a guessed
number, and `sync_doc_facts.py` will never write an invented value.

| Fact | Source |
|---|---|
| `version` | latest `vX.Y.Z` tag |
| `commit` | `git rev-parse --short HEAD` |
| `gate_count` | count of `def gate_*` in `scripts/ci_gate.py` |
| `context_count` | entries in `ci_bridge.CONTEXT_ORDER` |
| `adr_count` | `docs/adr/ADR-*.md` |
| `board_count` | `check_*` functions in `scripts/board/review.py` |
| `cadence_*` | `CADENCE_DAYS` / `DEFAULT_CADENCE` in `scripts/doc_review_due.py` |
| `doc_count` | living markdown files under `docs/` |
| `test_count`, `coverage` | written by the gate from a real pytest run |

**Bare claims are checked too.** The checker also flags an *unmarked* number that
contradicts reality. A sentence such as the following is a claim, not prose:

```
The gate runs 22 checks.
```

That is what found the six stale gate-count claims: they were written long
before markers existed, and the bare-claim rule is what reaches backwards and
catches them. It is deliberately narrow — a small explicit list of patterns
in `scripts/sync_doc_facts.py` — so it stays a drift alarm rather than a style
linter. Section numbers (`### 5.2 ADR Template`) are explicitly not claims.

**Exempt.** `docs/archive/`, `CHANGELOG.md`, `AUDIT-USAT.md`,
`SPRINT_1_2_COMPLETION.md`, `DECISIONS-AUTONOMOUS-*.md` and `DEBUGGING.md` carry
historical numbers on purpose; rewriting them would destroy the record.

**An unresolvable fact is a failure, not a silence.** This is the subtlest rule
here and the one that was got wrong first. When a document cites a fact the
checker cannot derive — typically `test_count`/`coverage` with no measurement for
this commit — the checker cannot certify the document. An earlier revision
skipped such citations and printed "no findings", which was actively harmful: the
run *looked* verified while the underlying number could be arbitrarily stale, and
it was: `ROADMAP.md` asserted a test count 84 lower than the suite's real count
while `--check` reported clean. A check that reports success when it has measured
nothing is worse than no check, so a citation of an unresolvable fact is now a
blocking finding. The remedy is to produce the measurement (run the gate so
`.governance/doc_facts.json` carries this commit's numbers), never to edit prose.
A marker naming a fact that does not exist is flagged the same way, so a typo
cannot hide a claim from the checker forever. `--apply` still refuses to write
`unknown`, and leaves such markers untouched — the writer never invents a value;
only the *checker* treats the unresolvable as a defect.

**Enforcement.** `githooks/pre-commit` runs `--apply`, re-stages the corrected
documents, then runs `--check` as a backstop — so a stale number is fixed in the
same commit that made it stale. The CI gate enforces `--check` as
`gate_doc_facts`, blocking, under the Virtual Board Governance context.

---

## 9. Versioning documents

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

---

## 10. Document types: how to write each kind so it cannot drift

Sections 2–9 say *what shape* a document must have. This section says *how to
write each kind of document* so that the drift never starts. It is the part that
is meant to be read **before** typing, not after.

### 10.1 The mandatory gate: read this before writing a document

This is a blocking rule, not advice.

1. **Identify the type.** Every document declares `**Type**: <name>` in its
   header, immediately under `**Status**`. The type decides the required shape and
   tells you which drift trap you are walking into. If you cannot name the type,
   you do not yet know what you are writing.
2. **Read your type's row below**, including its drift trap and its rules.
3. **Scaffold, do not hand-write the header:**

   ```bash
   .venv/bin/python scripts/new_doc.py <type> docs/<path>.md \
       --title "<Title>" --source "<the code this describes>"
   ```

   The scaffold arrives with the correct status block, source binding and required
   sections in place, so the rules are a form you fill in rather than a list you
   must remember.
4. **Fill it against the code, not against memory.** Open the file you named in
   `**Source**` while you write. A document written from memory is the single most
   common origin of drift.
5. **Run the checker before committing:** `scripts/check_docs.py --strict`. This is
   enforced again by `githooks/pre-commit` and by the `gate_docs` CI check, so
   skipping it locally only moves the failure later.

**For agents:** the same gate applies. Before writing or editing any document, read
this section, declare the type, and run `scripts/new_doc.py`. An agent that writes
a document without a type is producing a file the gate will reject — and, worse, one
that no reader can tell is current.

### 10.2 The types

<!-- BEGIN GENERATED: doc types (scripts/doc_type_table.py) -->
| Type | What it is | Required on an ACTIVE doc | Drift trap it prevents |
|---|---|---|---|
| `adr` | A dated, immutable record of one decision and what it rejected. | `status`, `type`, `updated`; sections: `/decision/`, `/consequences/` | Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made. |
| `architecture` | How the system is put together at HEAD — topology, boundaries, data flow. | `status`, `type`, `updated`, `source`; sections: `/overview|topology|system/` | Describes a design that was once true. Nothing in the document points at code, so a refactor leaves it confidently wrong. |
| `changelog` | Append-only release history. | `status`, `type`, `updated` | Being rewritten. Old entries describe what shipped; editing them falsifies the record. |
| `generated` | Machine-written output. Nobody edits it; a script regenerates it. | `status`, `type`, `updated`, `generated_by` | Being hand-edited. The edit is lost at the next generation, or worse, the file stops matching its generator and nobody notices. |
| `governance` | Who decides what, the rules that bind contributors, and how they are enforced. | `status`, `type`, `updated`, `source` | Names a process, workflow or authority that does not exist — eroding trust in every other rule, because a reader who finds one false rule stops believing all of them. |
| `guide` | Teaching prose: onboarding, handover, and how to work with a subsystem. | `status`, `type`, `updated` | Teaches a workflow that the reader then finds does not exist, which is worse for a beginner than no guide at all. |
| `index` | The navigation map. Exactly one exists. | `status`, `type`, `updated`; a populated table | A second map appears, the two disagree, and readers lose trust in both. |
| `policy` | A standing commitment to the outside world: security, conduct, licensing. | `status`, `type`, `updated` | Promises a response time, a supported version or a contact that is no longer real. |
| `reference` | What a subsystem, config surface or API *is*, bound to the code that defines it. | `status`, `type`, `updated`, `source` | The fastest-rotting type. Every default, field and endpoint is duplicated from code, so every code change makes it stale. |
| `register` | A table of items kept under review: risks, capabilities, deviations. | `status`, `type`, `updated`; a populated table | Rows are added and never re-reviewed, so it becomes a list of things that were true once, presented as things that are true now. |
| `roadmap` | Forward plan: what is next, in what order, and the debt owed. | `status`, `type`, `updated`; sections: `/sprint|phase|milestone/`, `/debt/` | Becomes a wish list. Items are marked done by intent, or never marked at all, and the document slowly describes a plan nobody is following. |
| `runbook` | A procedure an operator executes, with a way to tell whether it worked. | `status`, `type`, `updated`, `source`; sections: `/troubleshoot|verify|verification|diagnos/` | The command or endpoint changes and the runbook keeps instructing the old one, so following it fails at the worst moment. |
| `snapshot` | A dated measurement or audit. True on its date, not maintained. | `status`, `type`, `updated` | Being read as current. Its numbers were true once and are quoted long after. |
<!-- END GENERATED: doc types -->

Generated from `scripts/doc_types.py`; `scripts/doc_type_table.py --check` fails if
this table and the code disagree, so the contract cannot drift from its own
documentation.

### 10.3 How to write each type

<!-- BEGIN GENERATED: doc type rules (scripts/doc_type_table.py) -->

#### `adr` — A dated, immutable record of one decision and what it rejected.

- **Status**: `ACTIVE`, `HISTORICAL`
- **Required header fields**: `status`, `type`, `updated`
- **Required sections**: a heading matching `/decision/`, a heading matching `/consequences/`
- **The trap this type falls into**: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.
- **How to write it so that cannot happen:**
  1. Never edit a Decision once Accepted. Supersede it: write a new ADR and mark this one superseded, with a pointer.
  2. Keep the filename `ADR-NNN-slug.md` with the next free number. Numbers are permanent; do not renumber.
  3. Record the date, the context as it was *at the time*, the decision, and the consequences — including the bad ones.
  4. From 2026-09-10 onward, record what you rejected and why. That is the section a future reader actually needs.

#### `architecture` — How the system is put together at HEAD — topology, boundaries, data flow.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`, `source`
- **Required sections**: a heading matching `/overview|topology|system/`
- **The trap this type falls into**: Describes a design that was once true. Nothing in the document points at code, so a refactor leaves it confidently wrong.
- **How to write it so that cannot happen:**
  1. Name the code you describe in `**Source**` — for example a source line of `app/` at HEAD. It must resolve, so moving the code reddens this document instead of silently invalidating it.
  2. Describe what exists at HEAD. Never describe a plan — plans belong in the roadmap.
  3. Link the ADRs that constrain the design. A rule with no ADR behind it is an opinion and will be 'corrected' by the next author.
  4. Prefer a diagram plus the invariants over prose that restates code. Prose duplicates code and loses the race.

#### `changelog` — Append-only release history.

- **Status**: `ACTIVE`, `HISTORICAL`
- **Required header fields**: `status`, `type`, `updated`
- **The trap this type falls into**: Being rewritten. Old entries describe what shipped; editing them falsifies the record.
- **How to write it so that cannot happen:**
  1. Append only. Correct an old entry with a new entry, never by editing history.
  2. One section per released version, newest first, dated.
  3. Derive the entries from real tags and commits; a changelog entry with no release behind it is fiction.
  4. Audience is a user, not a committer: say what changed for them.

#### `generated` — Machine-written output. Nobody edits it; a script regenerates it.

- **Status**: `SNAPSHOT`, `HISTORICAL`
- **Required header fields**: `status`, `type`, `updated`, `generated_by`
- **The trap this type falls into**: Being hand-edited. The edit is lost at the next generation, or worse, the file stops matching its generator and nobody notices.
- **How to write it so that cannot happen:**
  1. Never edit by hand. Change the generator and regenerate.
  2. `**Generated by**` must name a script that exists in the repository.
  3. Keep the status SNAPSHOT or HISTORICAL. A generated file is a dated measurement, never a living authority.
  4. A generated document may name deleted files and symbols — that is its purpose — so it is exempt from the path rule.

#### `governance` — Who decides what, the rules that bind contributors, and how they are enforced.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`, `source`
- **The trap this type falls into**: Names a process, workflow or authority that does not exist — eroding trust in every other rule, because a reader who finds one false rule stops believing all of them.
- **How to write it so that cannot happen:**
  1. Every rule must name its enforcement point: a gate, a hook, a test or an owner. An unenforced rule is a wish, and wishes drift.
  2. Name real workflows, real scripts and real people/roles. Do not describe a process you have not verified exists.
  3. When a rule changes, record the decision (ADR) and the date it took effect in the same change.
  4. Separate 'required' from 'recommended' explicitly. Anything ambiguous will be read as optional.

#### `guide` — Teaching prose: onboarding, handover, and how to work with a subsystem.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`
- **The trap this type falls into**: Teaches a workflow that the reader then finds does not exist, which is worse for a beginner than no guide at all.
- **How to write it so that cannot happen:**
  1. Write for the reader's actual level. If it is a beginner guide, say what the tool *is* before what to type.
  2. Every command shown must have been run. Paste real output.
  3. Name the honest gaps: what does not work yet, and who does it. A guide that implies everything works loses the reader at the first failure.
  4. Link to the authoritative document for anything you summarise; do not restate it.

#### `index` — The navigation map. Exactly one exists.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`
- **Required**: at least one populated table
- **The trap this type falls into**: A second map appears, the two disagree, and readers lose trust in both.
- **How to write it so that cannot happen:**
  1. There is exactly one index: `docs/README.md`. Add a row; never create a rival map.
  2. Every row links to a document that exists. The path rule enforces this.
  3. Keep it a map, not a summary: a table of links with one-line purposes.
  4. Update it in the same change that adds or removes a document.

#### `policy` — A standing commitment to the outside world: security, conduct, licensing.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`
- **The trap this type falls into**: Promises a response time, a supported version or a contact that is no longer real.
- **How to write it so that cannot happen:**
  1. Every commitment must be one the project can keep and that someone owns. Name the owner or the channel.
  2. Cite the policy you implement (e.g. Contributor Covenant) rather than paraphrasing it, so the meaning cannot drift.
  3. Keep the contact/reporting path current — a dead reporting channel is a failed policy.

#### `reference` — What a subsystem, config surface or API *is*, bound to the code that defines it.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`, `source`
- **The trap this type falls into**: The fastest-rotting type. Every default, field and endpoint is duplicated from code, so every code change makes it stale.
- **How to write it so that cannot happen:**
  1. `**Source**` is mandatory and must point at the module or file that implements the described surface. This is the whole anti-drift mechanism for this type.
  2. Never hand-write a number: a count, a version, a limit or a default is a fact marker (see §8) or it is a future lie.
  3. Where the code is clearer than prose, quote it in a fenced block and say which file it came from, rather than paraphrasing it.
  4. State defaults as the code states them, and mark anything that is planned as planned — an aspirational value in a reference doc is read as current fact.

#### `register` — A table of items kept under review: risks, capabilities, deviations.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`
- **Required**: at least one populated table
- **The trap this type falls into**: Rows are added and never re-reviewed, so it becomes a list of things that were true once, presented as things that are true now.
- **How to write it so that cannot happen:**
  1. Every row carries an owner and a review date. A row nobody owns is a row nobody will ever close.
  2. Write the measurement, not the feeling: '2 critical, 2 high, measured 2026-09-13' can be re-derived; 'mostly fine' cannot.
  3. State accepted risk as accepted, with the reason and the date — never silently drop a finding.
  4. Do not use this type for a table of facts that code could generate; that is a generated document.

#### `roadmap` — Forward plan: what is next, in what order, and the debt owed.

- **Status**: `ACTIVE`
- **Required header fields**: `status`, `type`, `updated`
- **Required sections**: a heading matching `/sprint|phase|milestone/`, a heading matching `/debt/`
- **The trap this type falls into**: Becomes a wish list. Items are marked done by intent, or never marked at all, and the document slowly describes a plan nobody is following.
- **How to write it so that cannot happen:**
  1. Mark completion only with evidence (a commit, a passing test, a merged PR), never from intention.
  2. Keep an explicit debt register. Debt that is not written down is debt that is hidden.
  3. Move finished sprints to a summary line and keep the detail in the completion record — the roadmap is for what is *next*.
  4. Record roadmap changes in a decision log inside the document, with dates.

#### `runbook` — A procedure an operator executes, with a way to tell whether it worked.

- **Status**: `ACTIVE`, `HISTORICAL`
- **Required header fields**: `status`, `type`, `updated`, `source`
- **Required sections**: a heading matching `/troubleshoot|verify|verification|diagnos/`
- **The trap this type falls into**: The command or endpoint changes and the runbook keeps instructing the old one, so following it fails at the worst moment.
- **How to write it so that cannot happen:**
  1. Include a verification section: how the operator confirms the step actually worked. A runbook without one teaches guessing.
  2. Give exact copy-pasteable commands. Paraphrased commands are run wrong.
  3. State the expected output next to the command, so a mismatch is visible.
  4. Point at the code that performs the action (`**Source**`), so the runbook can be checked against reality rather than against memory.

#### `snapshot` — A dated measurement or audit. True on its date, not maintained.

- **Status**: `SNAPSHOT`, `HISTORICAL`
- **Required header fields**: `status`, `type`, `updated`
- **The trap this type falls into**: Being read as current. Its numbers were true once and are quoted long after.
- **How to write it so that cannot happen:**
  1. Carry the date in the title and in a banner under it, above all other content.
  2. State plainly that it is a point-in-time record and not maintained.
  3. Do not correct it later. If the finding still matters, raise it in the risk register and leave the snapshot alone.
  4. When it stops being useful it moves to `docs/archive/` — it is never silently deleted if anything ever cited it.

<!-- END GENERATED: doc type rules -->

### 10.4 Why a type contract, and not more prose rules

Every rule above is enforceable, and enforcement is the point. The previous pass
(§5) fixed 86 documents by reading them; without a contract that fix decays, because
nothing stopped the next document from being written the same way the old ones were.
The mechanism is deliberately layered:

| Layer | What it does | Where |
|---|---|---|
| **Scaffold** | Makes the correct shape the path of least resistance | `scripts/new_doc.py` |
| **Contract** | States per type what is required and which trap it avoids | `scripts/doc_types.py` |
| **Documentation** | Generates the tables above from the contract | `scripts/doc_type_table.py` |
| **Gate** | Rejects a document that violates its type | `scripts/check_docs.py`, `githooks/pre-commit`, `gate_docs` |

The `**Source**` binding is the load-bearing element. It is the only requirement
here that converts a *future* code change into a *present* gate failure: move
`app/memory/` and `docs/MEMORY.md` stops resolving, so the document goes red instead
of going quietly out of date. Everything else keeps a document well-formed; that one
keeps it honest.

### 10.5 What this contract deliberately does not do

- **It does not demand structure from history.** A HISTORICAL or SNAPSHOT document
  must declare its status and type and nothing more. Requiring maintained sections
  from a record of the past would be incoherent — and would push authors to edit
  history to satisfy a checker.
- **It does not check whether the prose is *right*.** That is §7's cadence job. No
  regex can tell you a governance document describes a practice nobody follows.
- **It does not type-check the root of the world.** Prompts, `n8n/` workflow JSON
  and generated graphs are not documents in this taxonomy.
