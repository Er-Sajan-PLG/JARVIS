# ADR-015 — Memory facts are bi-temporal, invalidated not deleted

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-15
**Reviewed**: 2026-09-15

- **Date**: 2026-09-15
- **Related**: `docs/MEMORY.md`, `docs/adr/ADR-002-json-file-persistent-memory.md`,
  `ADR-004-chromadb-semantic-memory.md`, `docs/ACCEPTED_RISKS.md`
- **Supersedes**: nothing. Extends ADR-002 (JSON-file store) with a temporal
  data model; the storage substrate is unchanged.

## Context

On 2026-09-15 the memory store was found to hold 492 records collapsing to 49
unique values (90% exact duplication), including a single identity fact
re-appended 372 times, and three competing claims about the owner's name and
profession. The write path was fixed by hand (dedup + junk rejection), and the
store was consolidated to 68 verified records.

Fixing the write path exposed a second defect that the first fix could not
address. Correcting the owner's employment history **destroyed** the prior
state:

| Action | Records affected | Recoverable? |
|---|---|---|
| Superseded LinkedIn employers (RUCHI Real Estate → RUCHI Developer) | 7 | **No** — deleted |
| Corrected university/college split | 2 | **No** — deleted |
| Replaced experience figure (2y7m → 1+ years) | 1 | **No** — overwritten |

None of this was wrong to do — the corrections were correct. The defect is that
`MemoryStore` had no way to represent *"this was believed until 2026-09-15, and
is not believed now."* It could only append or delete. A store that can only
append or delete cannot answer "what did we believe last week", cannot undo a
correction that later proves to be the mistake, and cannot show its work.

The same audit found a third gap: **no fact carried provenance.** A
`library_document` record held OCR text with no link to the file it came from,
and the 68 profile records did not record whether they came from LinkedIn, the
CV, or a direct owner statement. When two sources conflicted — exactly what
happened between LinkedIn and CV REV 7.0 — nothing in the data model said which
source won or why.

## Research

The field has converged on a specific answer, and it is worth stating what was
adopted and what was rejected.

**Bi-temporal modelling (adopted).** Zep's Graphiti models each fact with four
timestamps on two independent axes — event time (`valid_at`/`invalid_at`: when
the fact was true in the world) and system time (`created_at`/`expired_at`: when
the store learned or retracted it). Keeping the axes separate is what allows
both "what is true now" and "what did we believe then" to be answered from one
store, and it handles out-of-order ingestion: a late-arriving historical fact
can be born already invalid.

**Invalidate, don't delete (adopted).** When a new fact contradicts an old one,
Graphiti closes the old fact's interval rather than removing it. Deleting loses
time-travel queries, the audit trail, and the ability to reverse a bad
correction.

**Division of labour (adopted).** Deciding whether two facts contradict each
other is a language judgement, so an LLM does it. Deciding which came first and
what timestamps to assign is arithmetic, so deterministic code does it. Asking a
model to order dates invites a hallucinated ordering.

**Lighter alternatives (not adopted).** Typed structured records
`(entity, attribute, value, timestamp)` and versioned chains with an `isLatest`
flag (Supermemory) both give versioning without a graph. JARVIS is a
single-user, single-machine store at 68 records — a graph database, entity
resolution and community summarisation are disproportionate. The temporal
*fields* deliver most of the value; the graph substrate is deferred.

**Explicitly rejected.** A full knowledge-graph migration (Zep/Graphiti as a
dependency, Neo4j/FalkorDB). Graphiti's own documentation reports its weakness
honestly: it regresses ~17.7% on single-session questions where no temporal
reasoning is needed. Most JARVIS memory reads are single-session preference
recall, which is the case temporal graphs do not help. Revisit if the store
grows past the point where linear scans are honest.

## Alternatives considered

**Delete-on-correction (the status quo).** What the store did until today: a
correction removed the superseded record. Rejected because the history is
unrecoverable — when CV REV 7.0 corrected RUCHI's dates and dropped GUD, the
prior values were destroyed and the "why did this change?" question could no
longer be answered from the store. A memory system that cannot distinguish
"never true" from "true until September" loses the ability to answer historical
questions, which is exactly what the owner asks of it.

**Single timestamp (created_at only).** Rejected: one clock cannot express the
difference between *when we learned something* and *when it was true in the
world*. Without that split, a fact recorded today about 2023 looks as new as a
fact about today.

**Overwrite in place with a `history` array inside the record.** Rejected: it
keeps history but breaks the invariant that one record is one fact, and every
consumer (retrieval, rules, API serialization) would need to know how to read a
nested history. The temporal fields keep the store flat and the queries simple.

**A separate `memory_history.json` sidecar.** Rejected: two files that must stay
in sync is a corruption source, and the store already rewrites its whole list on
every save. It also would not survive a partial write.

**Trusting an LLM to decide which of two facts is newer.** Rejected as the sole
mechanism: the literature (Zep/Graphiti) puts the LLM on *contradiction
detection* and keeps *date arithmetic* in code. A model asked to compare
"Aug–Nov 2025" against "Aug 2025–present" will usually be right and occasionally
wrong with no audit trail. `close_interval()` is deterministic and tested.

## Decision

1. `MemoryItem` carries **four temporal fields**: `valid_at`, `invalid_at`
   (event time) and `created_at`, `expired_at` (system time). All optional;
   absent means open-ended.
2. **Corrections invalidate rather than delete.** A superseding record sets the
   prior record's `invalid_at` and `expired_at` and links it forward via
   `superseded_by`. The prior record remains readable.
3. **Every record carries provenance**: `source` (the document or statement it
   came from) and, where applicable, `derived_from` (the episode/file).
4. **Reads filter to currently-valid facts by default.** `as_of` queries take a
   timestamp and return the facts valid at that instant.
5. Contradiction detection is LLM-driven and structured; interval arithmetic is
   deterministic code and is unit-tested.

## Consequences

**Positive**: corrections become reversible and auditable; the two-source
conflict (LinkedIn vs CV) becomes a query rather than a hand-reconciliation;
"what did we believe on date X" is answerable; and a wrong correction no longer
destroys the fact it replaced.

**Negative**: the store grows monotonically — records are retired, not removed —
so retrieval must filter on validity or it will return superseded facts. This is
the main new failure mode and it is covered by tests. Each record also carries
five extra fields, so hand-editing `data/memories.json` becomes less pleasant;
the scripts are the intended interface.

**Risk accepted**: without a graph, entity resolution is string-based, so
"RUCHI Real Estate" and "RUCHI Developer" are matched by the reconciliation
logic, not by graph identity. Recorded in `docs/ACCEPTED_RISKS.md`.
