# ADR-014 — Documentation facts are machine-synced and machine-checked

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-13
**Reviewed**: 2026-09-14

- **Date**: 2026-09-13
- **Related**: `docs/DOC-GOVERNANCE.md` (§4 rules, §6 checker, §7 cadence, §8 facts,
  §10 types), `docs/ACCEPTED_RISKS.md`, `docs/CI-GATE-SOTA.md`
- **Supersedes**: nothing. Extends the 2026-09-13 documentation pass recorded in
  `docs/DOC-GOVERNANCE.md` §5, which fixed the documents *by hand*.

## Context

On 2026-09-13 a full pass read all 86 documents, deleted 9, archived 4 and corrected
12. It was necessary and it did not hold. Within the same day the tree had drifted
again, measurably:

- Six documents asserted the CI gate ran "22 checks" while `scripts/ci_gate.py`
  executed 23. One of them was a new ADR written *during* the pass.
- `docs/ACCEPTED_RISKS.md` claimed "1028 passing, coverage ~36%" long after the
  suite reached 1063 passing at 98%.
- Every structural check passed on all of them. The documents were well-formed and
  factually wrong.

The failure mode is specific and worth naming. Documentation drift is not one
problem but two, and they need different machinery:

| Kind | Example | Can a regex catch it? |
|---|---|---|
| **Mechanical** | a count, version, path, or link that no longer matches the repo | **Yes**, if the value is derived rather than typed |
| **Semantic** | a governance doc describing a practice nobody follows | **No** — needs a judgment re-read |

A hand-fix addresses neither durably: the numbers were typed by a human who
remembered them, so the next change re-created the same lie. At 86 documents this is
annoying; at the 1,000–10,000 documents this repository is expected to reach, "read
everything periodically" stops being possible at all.

Two further facts shaped the design:

- **GitHub Actions are disabled on this repository** (billing-blocked; see
  `docs/CI-GATE-SOTA.md`). "CI" here means the local gate — `scripts/ci_gate.py`
  driven by `n8n` via `scripts/ci_bridge.py`. Any mechanism that only works in a
  hosted CI runner would not run at all.
- **The audit path must stay offline.** A gate that depends on the network is a gate
  that fails for reasons unrelated to the change under review.

## Decision

**Documentation facts are derived from the repository, written into documents by
machine, and verified by machine. Prose that cannot be derived stays human-written
and is surfaced for review on a cadence instead.**

Seven parts.

### 1. Facts are derived, never typed

`scripts/doc_facts.py` computes every shared fact by parsing the real files — the
gate's own function count, the test count and coverage from the gate's cache, the ADR
count, the git tag, the doc count, the release count. Nothing is hardcoded and
nothing touches the network.

Cheap facts (filesystem, git, grep) are computed on every run. Expensive facts (test
count, coverage) are read from a cache that `scripts/ci_gate.py` writes when it
already runs the suite, so the documentation never triggers a second test run.

**When a fact cannot be resolved, it stays `unknown`.** The writer refuses to emit
`unknown` into a document. This is deliberate: an admitted gap is recoverable, an
invented number is not, and a fabricated value in a governance document is worse than
a blank one.

### 2. Values live in markers

A document does not contain a number. It contains a claim that a number belongs there:

```markdown
The gate runs <!--fact:gate_count-->26<!--/fact--> checks.
```

HTML comments are chosen so that no markdown formatter, linter or renderer touches
them. `scripts/sync_doc_facts.py --apply` rewrites the interior; `--check` fails when
the interior disagrees with the derived value.

### 3. Unmarked claims are failures, not suggestions

Markers only protect a value that has one. The dangerous case is the bare number a
human typed before markers existed — "22 checks" with no marker at all, which no
marker check can see.

So `sync_doc_facts.py --check` also scans prose for a short, explicit list of
claim patterns (a count of checks, ADRs, tests; a coverage figure) and fails when the
number disagrees with the repository. This is the half that reaches *backwards* and
found the stale claims listed in the Context.

The pattern list is deliberately short. A general "any number is suspicious" rule
would become a style linter that authors route around, which is worse than no rule.

### 4. Four enforcement layers, ordered by when they act

| Layer | When it acts | Mechanism |
|---|---|---|
| Scaffold | before the author writes | `scripts/new_doc.py` emits the correct shape |
| Contract | at authoring time | `scripts/doc_types.py` — per-type required fields, stated drift trap |
| Local hook | at commit time | `githooks/pre-commit` syncs facts, re-stages, regenerates the type tables |
| Gate | before merge | `scripts/check_docs.py`, `scripts/doc_type_table.py`, `gate_docs` + `gate_doc_facts` + `gate_doc_types` |

The ordering is the point. A check that fires after the work is done is the weakest
of the four; a scaffold that makes the correct shape the path of least resistance is
the strongest.

### 5. The `**Source**` binding is the load-bearing element

Every ACTIVE document that describes code must name it:

```markdown
**Source**: `app/memory/` at HEAD
```

It must resolve, so it is checked by the same path rule as any other reference. This
is the only requirement in the whole system that converts a *future* code change into
a *present* gate failure: move `app/memory/` and `docs/MEMORY.md` stops resolving, so
the document goes red instead of going quietly stale. Everything else keeps a
document well-formed; this keeps it honest.

### 6. Semantic drift gets a clock, not a checker

No regex can decide whether a governance document still describes how the project
actually works. `scripts/doc_review_due.py` assigns a review window per document class
(strategy 30 days; governance and architecture 90; references 180; historical 365;
`docs/archive/` and ADRs never) and measures it from the explicit
`**Reviewed**: YYYY-MM-DD` marker — deliberately **not** from git history.

Git history was the first design, and it was wrong: a commit records that *something*
changed, not that anyone re-read the document against the implementation. A typo fix,
a formatting pass, or an automatic marker sync (`sync_doc_facts.py --apply` rewrites
prose on every commit that moves a count) all touch the file without anyone having
judged whether it is still true — so a git-based clock let mechanical edits silently
mark a document as reviewed, which is the exact failure this script exists to prevent.
Only the explicit `**Reviewed**` marker resets the clock, because it is the only
signal that is a *claim of a semantic re-read*. Git activity is still shown, as
advisory context (`last_modified`, `edits_since_review`): "this document has been
mechanically edited six times since it was last reviewed" is precisely the signal that
it needs reading — but it never moves the clock. A future-dated `**Reviewed**` line is
rejected, so a typo cannot park a document permanently out of the queue.

It emits a bounded review packet listing only the documents actually due, with three
questions: still true, still useful, still complete. A monthly cron job runs it. When
nothing is due the job reports that and stops.

### 7. Link integrity, and one deliberate exception to the offline rule

`scripts/doc_links.py` checks that every markdown link resolves — including
`file.md#anchor` and same-file `#anchor`, resolved against GitHub-style heading
slugs. A dead anchor is invisible to a path check and to a human skimming a diff; the
reader who clicks it is the one who pays.

External URLs are the one thing that cannot be derived offline, so they are isolated
in `scripts/check_links.py`, which is **the only file in the doc pipeline permitted to
use the network**. It is not wired into the offline gate; it runs on its own
15-day schedule. It separates hard-dead (404/410/DNS, fails) from transient (429/5xx,
warned) and from blocked-or-non-browsable (reported as unverified, never failed). A
check that cries wolf gets ignored, and then it is worth nothing.

## Alternatives considered

**A documentation linter only.** Rejected: it catches a document that is already
wrong. The problem is a document that *becomes* wrong later, and a linter that runs at
review time cannot see the future.

**GitHub Actions as the enforcement layer.** Rejected: Actions are disabled on this
repository (billing-blocked). A mechanism that only runs in a hosted runner is a
mechanism that does not run. The local gate plus `n8n` was the only executable choice.

**Periodic full re-reads ("just read all the docs again").** Rejected as the primary
mechanism: it does not scale past a few hundred documents, it is forgettable, and it
delivers an unbounded task to a human. The pass that motivated this ADR was exactly
that, and it decayed the same day. Retained only for *semantic* drift, bounded to the
documents actually due.

**Typing the value and letting review catch it.** Rejected: this is what produced both
drift incidents, because a reviewer diffs prose and a number change looks correct.

**A generator that rewrites whole documents from code.** Rejected: most documents are
prose, and generated prose reads as generated. Markers change only the values that are
actually derived and leave the writing alone.

**Failing on external link blocks (403/429).** Rejected after measurement: a real run
reported 4 "dead" links of which all 4 were local dev addresses or non-browsable API
bases. A check whose failures are mostly wrong is worse than no check.

**Reusing the type contract's required sections for history.** Rejected: demanding
maintained structure from a HISTORICAL or SNAPSHOT document is incoherent, and it
pushes authors to edit history to satisfy a checker.

## Consequences

**Good.**

- A derived value cannot drift. Changing the gate's check count changes every document
  that cites it, in the same commit, with no human edit.
- The stale claims that motivated this are now structurally impossible: the number is
  not stored, it is rendered.
- A document that describes code must name it, so a refactor reddens the document
  rather than silently invalidating it.
- The gates report *which* document and *which* line, and for an unmarked claim, the
  exact marker to add — so a contributor learns the convention from the failure.
- Nothing runs in hosted CI, so nothing depends on a service that is currently off.

**Costly, and accepted.**

- **Marker noise.** Documents contain HTML comments where a number would be. This is
  the visible price of the guarantee, and it is why the type tables and the generated
  §10 blocks exist: the alternative to a marker is a number that will be wrong.
- **Hand-editing a mirrored value is overwritten.** A contributor who edits the
  interior of a marker sees it reverted by `pre-commit`. That is intended; the sync is
  the source of truth for that value.
- **The claim regex can false-positive on prose.** Mitigated by keeping the pattern
  list short, exempting historical documents, and treating fenced code blocks and an
  explicit escape comment as illustrative — so an author can *quote* a stale claim
  while explaining the rule.
- **Prose review still exists.** It is now a scheduled, bounded prompt rather than a
  memory. That is a reduction, not an elimination, and it is stated here so nobody
  later reads the gates as a guarantee that the prose is true.
- **Legacy debt remains.** The gate ratchets: it enforces on changed files, and the
  ~88 pre-existing ruff findings in `scripts/` are tracked rather than hidden.

## Verification

Recorded per `docs/DOC-GOVERNANCE.md` §10.5: each gate was proved by deliberately
breaking it and observing the failure, then reverting.

| Break | Observed |
|---|---|
| Corrupt a marked value | `sync_doc_facts --check` fails; `--apply` repairs |
| Add a bare "999 rules" claim | `--check` fails and names the marker to use |
| Move a `**Source**` path | `check_docs` fails on the unresolved reference |
| Break a relative link | `check_docs` fails with file and line |
| Break a same-file `#anchor` | `check_docs` fails with file and line |
| Delete an index entry | `check_docs` reports the unreachable document |
| Add an unknown `**Type**` | `check_docs` names the allowed types |
| Add a dead external link | `check_links.py` exits 1 with file and line, on DNS failure |
