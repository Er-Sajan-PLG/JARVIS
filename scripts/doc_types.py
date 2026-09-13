#!/usr/bin/env python3
"""The document type contract — one source of truth for the taxonomy.

Every document in this repository declares a ``**Type**``, and each type has a
set of required elements. Those requirements exist for exactly one reason: to
make the document **structurally incapable of drifting quietly**.

The distinction matters. ``check_docs.py`` can only catch a document that is
already wrong. A type contract catches it at *authoring* time, by insisting on
the fields that force the author to name the thing the document can drift away
from — above all ``**Source**``, which binds a claim to a real file so that
moving the file turns the document red instead of turning it into a lie.

This module is imported by ``check_docs.py`` (enforcement), ``new_doc.py``
(scaffolding) and ``check_doc_types.py`` (self-check). Because the doc type table
in ``docs/DOC-GOVERNANCE.md`` is generated from ``TYPES`` below and verified
against it, the contract cannot drift from its own documentation.

Requirements apply to **ACTIVE** documents. A HISTORICAL or SNAPSHOT document is
frozen by definition, so it must declare its status and type and nothing more —
demanding maintained structure from a record of the past would be incoherent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The cutover after which an ADR must record what it rejected. Recorded
# alternatives are cheap at decision time and irrecoverable afterwards; ADR-011
# is the first decision taken under this rule.
ADR_ALTERNATIVES_SINCE = "2026-09-10"

ALLOWED_STATUSES = ("ACTIVE", "SNAPSHOT", "HISTORICAL", "DRAFT")


@dataclass(frozen=True)
class DocType:
    """One document type and the elements a living instance of it must carry."""

    name: str
    summary: str
    #: statuses a document of this type may plausibly hold
    statuses: tuple[str, ...]
    #: header fields required on an ACTIVE doc: any of
    #: status | type | updated | source | reviewed | generated_by
    header: tuple[str, ...]
    #: regexes; each must match at least one heading in an ACTIVE doc
    sections: tuple[str, ...] = ()
    #: at least one markdown table with data rows
    needs_table: bool = False
    #: the single "drift trap" this type falls into, stated once
    drift_trap: str = ""
    #: the authoring rules that prevent that trap
    how_to_write: tuple[str, ...] = ()
    #: extra free-text note for the governance table
    note: str = ""


TYPES: dict[str, DocType] = {
    "architecture": DocType(
        name="architecture",
        summary="How the system is put together at HEAD — topology, boundaries, data flow.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated", "source"),
        sections=(r"overview|topology|system",),
        needs_table=False,
        drift_trap=(
            "Describes a design that was once true. Nothing in the document points at "
            "code, so a refactor leaves it confidently wrong."
        ),
        how_to_write=(
            "Name the code you describe in `**Source**` — for example a source line of "
            "`app/` at HEAD. It must resolve, so moving the code reddens this document "
            "instead of silently invalidating it.",
            "Describe what exists at HEAD. Never describe a plan — plans belong in the roadmap.",
            "Link the ADRs that constrain the design. A rule with no ADR behind it is an "
            "opinion and will be 'corrected' by the next author.",
            "Prefer a diagram plus the invariants over prose that restates code. Prose "
            "duplicates code and loses the race.",
        ),
    ),
    "reference": DocType(
        name="reference",
        summary="What a subsystem, config surface or API *is*, bound to the code that defines it.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated", "source"),
        needs_table=False,
        drift_trap=(
            "The fastest-rotting type. Every default, field and endpoint is duplicated from "
            "code, so every code change makes it stale."
        ),
        how_to_write=(
            "`**Source**` is mandatory and must point at the module or file that implements "
            "the described surface. This is the whole anti-drift mechanism for this type.",
            "Never hand-write a number: a count, a version, a limit or a default is a fact "
            "marker (see §8) or it is a future lie.",
            "Where the code is clearer than prose, quote it in a fenced block and say which "
            "file it came from, rather than paraphrasing it.",
            "State defaults as the code states them, and mark anything that is planned as "
            "planned — an aspirational value in a reference doc is read as current fact.",
        ),
    ),
    "governance": DocType(
        name="governance",
        summary="Who decides what, the rules that bind contributors, and how they are enforced.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated", "source"),
        needs_table=False,
        drift_trap=(
            "Names a process, workflow or authority that does not exist — eroding trust in "
            "every other rule, because a reader who finds one false rule stops believing all "
            "of them."
        ),
        how_to_write=(
            "Every rule must name its enforcement point: a gate, a hook, a test or an owner. "
            "An unenforced rule is a wish, and wishes drift.",
            "Name real workflows, real scripts and real people/roles. Do not describe a "
            "process you have not verified exists.",
            "When a rule changes, record the decision (ADR) and the date it took effect in "
            "the same change.",
            "Separate 'required' from 'recommended' explicitly. Anything ambiguous will be "
            "read as optional.",
        ),
    ),
    "adr": DocType(
        name="adr",
        summary="A dated, immutable record of one decision and what it rejected.",
        statuses=("ACTIVE", "HISTORICAL"),
        header=("status", "type", "updated"),
        sections=(r"decision", r"consequences"),
        needs_table=False,
        drift_trap=(
            "Being *edited* to look correct in hindsight. An ADR that is rewritten to match "
            "current reality destroys the only record of why the decision was made."
        ),
        how_to_write=(
            "Never edit a Decision once Accepted. Supersede it: write a new ADR and mark this "
            "one superseded, with a pointer.",
            "Keep the filename `ADR-NNN-slug.md` with the next free number. Numbers are "
            "permanent; do not renumber.",
            "Record the date, the context as it was *at the time*, the decision, and the "
            "consequences — including the bad ones.",
            "From " + ADR_ALTERNATIVES_SINCE + " onward, record what you rejected and why. "
            "That is the section a future reader actually needs.",
        ),
    ),
    "runbook": DocType(
        name="runbook",
        summary="A procedure an operator executes, with a way to tell whether it worked.",
        statuses=("ACTIVE", "HISTORICAL"),
        header=("status", "type", "updated", "source"),
        sections=(r"troubleshoot|verify|verification|diagnos",),
        needs_table=False,
        drift_trap=(
            "The command or endpoint changes and the runbook keeps instructing the old one, "
            "so following it fails at the worst moment."
        ),
        how_to_write=(
            "Include a verification section: how the operator confirms the step actually "
            "worked. A runbook without one teaches guessing.",
            "Give exact copy-pasteable commands. Paraphrased commands are run wrong.",
            "State the expected output next to the command, so a mismatch is visible.",
            "Point at the code that performs the action (`**Source**`), so the runbook can be "
            "checked against reality rather than against memory.",
        ),
    ),
    "guide": DocType(
        name="guide",
        summary="Teaching prose: onboarding, handover, and how to work with a subsystem.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated"),
        needs_table=False,
        drift_trap=(
            "Teaches a workflow that the reader then finds does not exist, which is worse for "
            "a beginner than no guide at all."
        ),
        how_to_write=(
            "Write for the reader's actual level. If it is a beginner guide, say what the tool "
            "*is* before what to type.",
            "Every command shown must have been run. Paste real output.",
            "Name the honest gaps: what does not work yet, and who does it. A guide that "
            "implies everything works loses the reader at the first failure.",
            "Link to the authoritative document for anything you summarise; do not restate it.",
        ),
    ),
    "roadmap": DocType(
        name="roadmap",
        summary="Forward plan: what is next, in what order, and the debt owed.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated"),
        sections=(r"sprint|phase|milestone", r"debt"),
        needs_table=False,
        drift_trap=(
            "Becomes a wish list. Items are marked done by intent, or never marked at all, "
            "and the document slowly describes a plan nobody is following."
        ),
        how_to_write=(
            "Mark completion only with evidence (a commit, a passing test, a merged PR), never "
            "from intention.",
            "Keep an explicit debt register. Debt that is not written down is debt that is "
            "hidden.",
            "Move finished sprints to a summary line and keep the detail in the completion "
            "record — the roadmap is for what is *next*.",
            "Record roadmap changes in a decision log inside the document, with dates.",
        ),
    ),
    "register": DocType(
        name="register",
        summary="A table of items kept under review: risks, capabilities, deviations.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated"),
        needs_table=True,
        drift_trap=(
            "Rows are added and never re-reviewed, so it becomes a list of things that were "
            "true once, presented as things that are true now."
        ),
        how_to_write=(
            "Every row carries an owner and a review date. A row nobody owns is a row nobody "
            "will ever close.",
            "Write the measurement, not the feeling: '2 critical, 2 high, measured 2026-09-13' "
            "can be re-derived; 'mostly fine' cannot.",
            "State accepted risk as accepted, with the reason and the date — never silently "
            "drop a finding.",
            "Do not use this type for a table of facts that code could generate; that is a "
            "generated document.",
        ),
    ),
    "generated": DocType(
        name="generated",
        summary="Machine-written output. Nobody edits it; a script regenerates it.",
        statuses=("SNAPSHOT", "HISTORICAL"),
        header=("status", "type", "updated", "generated_by"),
        needs_table=False,
        drift_trap=(
            "Being hand-edited. The edit is lost at the next generation, or worse, the file "
            "stops matching its generator and nobody notices."
        ),
        how_to_write=(
            "Never edit by hand. Change the generator and regenerate.",
            "`**Generated by**` must name a script that exists in the repository.",
            "Keep the status SNAPSHOT or HISTORICAL. A generated file is a dated measurement, "
            "never a living authority.",
            "A generated document may name deleted files and symbols — that is its purpose — "
            "so it is exempt from the path rule.",
        ),
    ),
    "changelog": DocType(
        name="changelog",
        summary="Append-only release history.",
        statuses=("ACTIVE", "HISTORICAL"),
        header=("status", "type", "updated"),
        needs_table=False,
        drift_trap=(
            "Being rewritten. Old entries describe what shipped; editing them falsifies the "
            "record."
        ),
        how_to_write=(
            "Append only. Correct an old entry with a new entry, never by editing history.",
            "One section per released version, newest first, dated.",
            "Derive the entries from real tags and commits; a changelog entry with no release "
            "behind it is fiction.",
            "Audience is a user, not a committer: say what changed for them.",
        ),
    ),
    "index": DocType(
        name="index",
        summary="The navigation map. Exactly one exists.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated"),
        needs_table=True,
        drift_trap=("A second map appears, the two disagree, and readers lose trust in both."),
        how_to_write=(
            "There is exactly one index: `docs/README.md`. Add a row; never create a rival map.",
            "Every row links to a document that exists. The path rule enforces this.",
            "Keep it a map, not a summary: a table of links with one-line purposes.",
            "Update it in the same change that adds or removes a document.",
        ),
    ),
    "policy": DocType(
        name="policy",
        summary="A standing commitment to the outside world: security, conduct, licensing.",
        statuses=("ACTIVE",),
        header=("status", "type", "updated"),
        needs_table=False,
        drift_trap=(
            "Promises a response time, a supported version or a contact that is no longer real."
        ),
        how_to_write=(
            "Every commitment must be one the project can keep and that someone owns. Name "
            "the owner or the channel.",
            "Cite the policy you implement (e.g. Contributor Covenant) rather than paraphrasing "
            "it, so the meaning cannot drift.",
            "Keep the contact/reporting path current — a dead reporting channel is a failed "
            "policy.",
        ),
    ),
    "snapshot": DocType(
        name="snapshot",
        summary="A dated measurement or audit. True on its date, not maintained.",
        statuses=("SNAPSHOT", "HISTORICAL"),
        header=("status", "type", "updated"),
        needs_table=False,
        drift_trap=("Being read as current. Its numbers were true once and are quoted long after."),
        how_to_write=(
            "Carry the date in the title and in a banner under it, above all other content.",
            "State plainly that it is a point-in-time record and not maintained.",
            "Do not correct it later. If the finding still matters, raise it in the risk "
            "register and leave the snapshot alone.",
            "When it stops being useful it moves to `docs/archive/` — it is never silently "
            "deleted if anything ever cited it.",
        ),
    ),
}

#: Types that may appear on a document inside docs/templates/.
TEMPLATE_TYPE = "template"


def template_doc_types() -> list[str]:
    return sorted(TYPES)


@dataclass
class TypeFinding:
    rel: str
    message: str


def required_for(status: str, typ: DocType) -> tuple[str, ...]:
    """Header fields required of a document, given its status and type.

    A frozen document only declares itself and its provenance; a living one carries
    the full contract. This is why the type rules apply to ACTIVE docs only.

    ``generated_by`` is deliberately required even of a frozen document: a
    `generated` type is *always* SNAPSHOT or HISTORICAL, so exempting frozen docs
    from it would mean the field was never required of the one type that needs it.
    Provenance is not maintained structure — it is part of what the document is.
    """
    base = ("status", "type")
    if status in {"HISTORICAL", "SNAPSHOT", "DRAFT"}:
        return base + (("generated_by",) if "generated_by" in typ.header else ())
    return ("status", "type", *[f for f in typ.header if f not in {"status", "type"}])


__all__ = [
    "ADR_ALTERNATIVES_SINCE",
    "ALLOWED_STATUSES",
    "DocType",
    "TEMPLATE_TYPE",
    "TYPES",
    "TypeFinding",
    "field",
    "required_for",
    "template_doc_types",
]
