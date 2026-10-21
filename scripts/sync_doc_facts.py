#!/usr/bin/env python3
"""Keep machine-derivable numbers in the docs true to the code.

Two jobs:

``--apply``
    Rewrite every ``<!--fact:name-->value<!--/fact-->`` marker with the value
    derived from the repository. Use this after changing the code so the docs
    catch up in the same commit.

``--check`` (CI gate)
    Fail when any marker's committed value disagrees with reality, and fail when
    a **bare** (unmarked) numeric claim is recognised as a stale fact. The second
    part is what catches numbers written before markers existed — otherwise the
    convention only protects claims added after it.

Why markers instead of prose rewriting: "22 checks" in six documents cannot be
safely regex-replaced in arbitrary prose ("the 22 checks of the pipeline"). A
marker is unambiguous, greppable and diffable.

Who may write a marker value (the scope rule)
---------------------------------------------
A marker value is a function of the working tree, so a branch's value differs
from the default branch's the moment the branch changes a count. Because this
script used to run ``--apply`` on *every* commit, every branch rewrote lines the
default branch had also rewritten, and git reported a conflict on both sides —
structurally, on every test-adding PR, every dependency PR and every ADR.

So the rule is now:

    **A branch must never modify a fact marker line. Only the default branch may.**

A branch that leaves the line alone receives the default branch's change as a
clean one-sided merge, so the conflict is impossible by construction rather than
resolved by hand. Keeping the published values on a branch is also the accurate
thing to write: the documents describe the published repository, not a proposal.

The modes that enforce it:

``--check-vs-base REF``
    Fail when this tree modifies (or deletes) a marker line that ``REF`` has.
    This is the gate's PR-side check and the pre-commit hook's branch-side check.

``--status``
    Report which marker values are stale relative to this tree, and write
    nothing. Advisory: it never fails a build, because on a branch a stale value
    is the *expected* state, not a defect.

``--pre-commit``
    The hook's entry point. On the default branch it behaves as ``--apply`` plus
    ``--check`` (unchanged). On any other branch it never writes: it enforces
    ``--check-vs-base`` and reports staleness. The refresh branch is the single
    exception, and it is resolved by ``resolve_fact_scope`` (see
    ``REFRESH_BRANCH_PREFIX``) — it is the default branch's designated writer of
    those lines, and it is held to the *stricter* rule, not a weaker one.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_facts import (  # noqa: E402
    MARKER_RE,
    REPO_ROOT,
    collect,
    collect_cheap,
    marker_drift_vs_base,
    marker_value_conflicts,
    markers_in,
    resolve_fact_scope,
)

EXPENSIVE_FACTS = (
    "test_count",
    "coverage",
)  # historical grouping; see reconcile for per-fact rules


def _full_head() -> str:
    """Full HEAD sha of the tree being described (empty when unavailable)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip()


def _live_test_count() -> str:
    """Count tests via --collect-only (seconds, deterministic, no execution)."""
    # Prefer the repository interpreter, but fall back to the one already
    # running this script. REPO_ROOT is a *worktree* whenever the CI gate runs
    # (ci_gate.py checks out the commit under test), and a worktree has no
    # .venv -- so hardcoding REPO_ROOT/.venv made this return "unknown" in
    # exactly the environment the gate uses, which failed
    # test_docs_system.py and test_doc_facts.py there while passing in a
    # developer's checkout.
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    if not venv_py.is_file():
        venv_py = Path(sys.executable)
    if not venv_py.is_file():
        return "unknown"
    try:
        proc = subprocess.run(
            [
                str(venv_py),
                "-m",
                "pytest",
                "tests/",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    m = re.search(r"(\d+) tests? collected", proc.stdout) or re.search(
        r"collected (\d+) items", proc.stdout
    )
    return m.group(1) if m else "unknown"


def reconcile_injected_facts(injected: object) -> dict[str, str]:
    """Merge an externally supplied snapshot with live cheap facts.

    The ``--facts-json`` fast path exists to skip pytest, but a snapshot is a
    claim about a PAST tree. Applying it blindly writes stale numbers as
    current truth (observed twice in the wild: ``test_count`` 1694 written
    while the suite collected 1746, then 1703 written while it collected
    1751 — the second time the cache commit even MATCHED head, because at
    pre-commit time HEAD is the parent, not the tree being committed).
    So the rule is:
    - cheap facts: always recomputed live (milliseconds);
    - ``test_count``: ALWAYS recomputed live via --collect-only (seconds,
      deterministic) — caching it buys nothing and risks everything, so the
      snapshot's value is never trusted;
    - ``coverage``: survives ONLY when the snapshot's commit matches HEAD
      (prefix either way: cheap=short, caches=full), else ``"unknown"``.
    ``apply_facts`` skips ``"unknown"`` markers and ``check_facts`` reports
    explicit cannot-verify findings instead of passing on a lie.
    """
    facts: dict[str, str] = {}
    if isinstance(injected, dict):
        facts = {str(k): str(v) for k, v in injected.items()}
    snapshot_commit = facts.get("commit", "")
    facts.update(collect_cheap())  # cheap facts always live, including commit
    # NOTE: collect_cheap reports a SHORT commit while caches carry the full
    # sha — compare by prefix in either direction, never by equality.
    head = _full_head()
    if (
        not snapshot_commit
        or not head
        or not (head.startswith(snapshot_commit) or snapshot_commit.startswith(head))
    ):
        facts["coverage"] = "unknown"
    facts["test_count"] = _live_test_count()
    return facts


BACKTICK_FACT_RE = re.compile(r"<!--fact:([a-z_]+)-->(.*?)<!--/fact-->", re.DOTALL)

# Bare, unmarked claims that should carry a marker. Kept narrow and explicit so
# this stays a drift alarm, not a style linter.
# (regex, fact name) — the regex must capture the NUMBER in group 1.
#
# The negative lookbehind on `[.\d]` matters: "### 5.2 ADR Template" is a section
# number, not a claim about how many ADRs exist.
BARE_CLAIMS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+(?:CI\s+)?(?:checks|gates)\b"), "gate_count"),
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+ADRs?\b"), "adr_count"),
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+(?:published\s+)?contexts\b"), "context_count"),
    (re.compile(r"(?<![\d.])\b(\d{3,4})\s+(?:tests?\s+)?passed\b"), "test_count"),
    (re.compile(r"(?<![\d.])\b(\d{3,4})\s+tests?\b"), "test_count"),
]

# Documents that are allowed to contain historical numbers without markers:
# they describe a past state on purpose and must NOT be rewritten.
EXEMPT_PREFIXES = (
    "docs/archive/",
    # An ADR is the one place a stale number is *correct*. Its Context section
    # records what was true when the decision was taken — ADR-014 quotes "22 checks"
    # precisely because that was the value that drifted. Rewriting it would falsify
    # the record the ADR exists to keep, and an ADR must never be edited to look
    # right in hindsight (docs/DOC-GOVERNANCE.md §10, type `adr`).
    "docs/adr/",
)
EXEMPT_FILES = {
    "docs/CHANGELOG.md",  # release notes are a historical record
    "docs/DEBUGGING.md",  # historical symptom log
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md",  # dated decision snapshot
    "docs/AUDIT-USAT.md",  # dated audit snapshot
    "docs/SPRINT_1_2_COMPLETION.md",  # dated sprint record
    "docs/ACCEPTED_RISKS.md",  # risk rows carry dated measurements
}

# An author must be able to *quote* a stale claim to explain the rule — this very
# document explains what the detector catches. A fenced code block, or a line
# carrying this escape, is quoted material rather than a claim.
ESCAPE = "<!--doc-facts:quoted-->"
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _line_is_quoted(lines: list[str], idx: int) -> bool:
    """True when the line at ``idx`` is illustrative, not an assertion.

    Two principled cases: inside a fenced code block (code is illustrative), or
    carrying the explicit ESCAPE comment (the author is quoting an anti-pattern).
    """
    if ESCAPE in lines[idx]:
        return True
    open_fence: str | None = None
    for i in range(idx):
        m = FENCE_RE.match(lines[i])
        if not m:
            continue
        if open_fence is None:
            open_fence = m.group(1)
        elif m.group(1) == open_fence:
            open_fence = None
    return open_fence is not None


def iter_docs() -> list[Path]:
    out = list((REPO_ROOT / "docs").rglob("*.md"))
    out += list(REPO_ROOT.glob("*.md"))
    return sorted(out)


# Facts a document is allowed to cite. Anything else is a typo, and a typo'd
# marker name would silently never be checked (the value would resolve to
# `unknown` and be skipped forever).
KNOWN_FACTS = frozenset(
    {
        "version",
        "commit",
        "gate_count",
        "context_count",
        "adr_count",
        "board_count",
        "cadence_fast",
        "cadence_default",
        "cadence_quarterly",
        "cadence_historical",
        "doc_count",
        "python_requires",
        "test_count",
        "coverage",
    }
)


def is_exempt(p: Path) -> bool:
    rel = str(p.relative_to(REPO_ROOT))
    return rel.startswith(EXEMPT_PREFIXES) or rel in EXEMPT_FILES


def apply_facts(facts: dict[str, str]) -> tuple[int, int, list[str]]:
    """Rewrite marker values. Returns (files_changed, markers_updated, unknown)."""
    changed = updated = 0
    unknown: list[str] = []
    for path in iter_docs():
        if is_exempt(path):
            continue
        text = original = path.read_text(encoding="utf-8", errors="replace")
        for name in dict.fromkeys(MARKER_RE.findall(text)):
            name = name[0] if isinstance(name, tuple) else name
            value = facts.get(name, "unknown")
            if value == "unknown":
                unknown.append(f"{path.relative_to(REPO_ROOT)}:{name}")
                continue
            for marker in MARKER_RE.finditer(text):
                if marker.group(1) != name:
                    continue
                if marker.group(2) == value:
                    # Already correct — not a rewrite, not a change reported.
                    continue
                before = marker.group(0)
                after = f"<!--fact:{name}-->{value}<!--/fact-->"
                text = text[: marker.start()] + after + text[marker.end() :]
                if before != after:
                    updated += 1
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed, updated, unknown


def check_facts(facts: dict[str, str]) -> list[str]:
    """Every number a doc asserts must be verifiable against the repository.

    The rule that matters, and the one this function previously got wrong: an
    **unresolvable** fact is a finding, not a pass. If a document cites
    `test_count` and the fact cannot be derived, the checker cannot say the
    document is true — it can only say it does not know. Reporting that silence
    as "no findings" is the worst possible outcome, because it *looks* like
    verification while the number underneath may be arbitrarily stale.

    That is not hypothetical. `coverage`/`test_count` are expensive and read from
    a gate-written cache; when the cache was unprovenanced or absent they resolved
    to `unknown`, `check_facts` skipped them, and `docs/ROADMAP.md` asserted a
    test count 84 lower than the suite's real count while this checker printed
    "no findings — every marked fact matches the repository". A blind spot that
    reports clean is worse than no check, so an unresolved *cited* fact is now a
    blocking finding naming the marker and why it is unresolvable.
    """
    findings: list[str] = []
    cited_unknown: list[str] = []
    for path in iter_docs():
        rel = str(path.relative_to(REPO_ROOT))
        if is_exempt(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        # 0. a marker naming a fact that does not exist is a typo, and a typo would
        #    otherwise resolve to `unknown` and be skipped forever.
        for m in MARKER_RE.finditer(text):
            if m.group(1) not in KNOWN_FACTS:
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    f"{rel}:{line}: marker '{m.group(1)}' is not a known fact "
                    f"— see scripts/doc_facts.py for the list"
                )

        # 1. marked values must match
        for m in MARKER_RE.finditer(text):
            name, committed = m.group(1), m.group(2).strip()
            if name not in facts:
                # Fact not in the provided snapshot; skip (caller chose not to verify this fact).
                continue
            actual = facts[name]
            if actual == "unknown":
                # The document asserts a value we cannot verify. That is a finding,
                # not a silence — unless the line is quoting the anti-pattern.
                line = text[: m.start()].count("\n") + 1
                if _line_is_quoted(lines, line - 1):
                    continue
                cited_unknown.append(f"{rel}:{line}: fact '{name}'")
                continue
            if committed != actual:
                line = text[: m.start()].count("\n") + 1
                if _line_is_quoted(lines, line - 1):
                    continue
                findings.append(
                    f"{rel}:{line}: fact '{name}' says {committed!r} but the repo says {actual!r} "
                    f"— run scripts/sync_doc_facts.py --apply"
                )

        # 2. bare claims that contradict reality must be marked
        for rx, name in BARE_CLAIMS:
            if name not in facts:
                # Fact not in the provided snapshot; skip.
                continue
            actual = facts[name]
            if actual == "unknown":
                continue
            for m in rx.finditer(text):
                if m.group(1) == actual:
                    continue
                # ignore a number that is already inside a fact marker
                line = text[: m.start()].count("\n") + 1
                if any(fm.start() <= m.start() < fm.end() for fm in MARKER_RE.finditer(text)):
                    continue
                # ignore quoted/illustrative material (fenced code, or an explicit
                # escape) — prose explaining the rule must be able to show the
                # anti-pattern without tripping the rule itself.
                if _line_is_quoted(lines, line - 1):
                    continue
                findings.append(
                    f"{rel}:{line}: unmarked stale claim {m.group(0)!r} (repo says {actual}) "
                    f"— wrap it in <!--fact:{name}-->{actual}<!--/fact-->"
                )

    # Unresolvable cited facts are reported as a single grouped finding. They mean
    # the checker could not verify the document — not that the document is wrong —
    # and the fix is to produce the measurement (run the gate), not to edit prose.
    if cited_unknown:
        findings.append(
            f"{len(cited_unknown)} citation(s) could not be verified because the fact(s) "
            f"are unresolvable — the checker cannot certify a document it cannot measure. "
            f"Run the gate (`scripts/ci_gate.py --with-coverage`) so "
            f"`.governance/doc_facts.json` carries a measurement for this commit: "
            + ", ".join(cited_unknown[:10])
            + (" …" if len(cited_unknown) > 10 else "")
        )
    return findings


def _base_text(ref: str, rel: str) -> str | None:
    """The base branch's version of a document, or ``None`` when it is new there.

    ``None`` means the document has no lines on the base, so none of its marker
    lines can conflict — a brand-new file merges cleanly whatever it contains.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{rel}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - git absent
        return None
    return proc.stdout if proc.returncode == 0 else None


def check_vs_base(ref: str) -> tuple[list[str], int]:
    """Enforce the invariant: this tree must not modify a fact marker line.

    Returns ``(findings, markers_compared)``. The count is returned rather than
    dropped because a check that compared nothing must never be reported as a
    pass — the failure mode this whole system exists to avoid.
    """
    findings: list[str] = []
    compared = 0
    for path in iter_docs():
        if is_exempt(path):
            continue
        rel = str(path.relative_to(REPO_ROOT))
        head_text = path.read_text(encoding="utf-8", errors="replace")
        findings += marker_value_conflicts(rel, head_text)
        base_text = _base_text(ref, rel)
        if base_text is None:
            continue
        compared += len(markers_in(base_text))
        findings += marker_drift_vs_base(rel, base_text, head_text)
    return findings, compared


def stale_markers(facts: dict[str, str]) -> list[str]:
    """Markers that disagree with ``facts`` — a report, never a verdict.

    On a branch this is the expected state: the values are the published ones and
    the branch has moved a count. So it is reported and nothing is written; the
    default branch's refresh path owns the correction.
    """
    out: list[str] = []
    for path in iter_docs():
        if is_exempt(path):
            continue
        rel = str(path.relative_to(REPO_ROOT))
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for m in MARKER_RE.finditer(text):
            name, committed = m.group(1), m.group(2).strip()
            actual = facts.get(name, "unknown")
            if actual == "unknown" or committed == actual:
                continue
            line = text[: m.start()].count("\n") + 1
            if _line_is_quoted(lines, line - 1):
                continue
            out.append(f"{rel}:{line}: {name} is {committed!r} here; this tree derives {actual!r}")
    return out


def _facts_for_branch(injected: object | None) -> dict[str, str]:
    """Facts for the advisory branch report: cheap always, snapshot when given.

    Deliberately never runs pytest. On a branch the numbers are informational —
    the authoritative measurement belongs to the default branch, which is the
    only place a value is written — so paying for a test collection here would
    slow every commit to report something that is going to be stale anyway.
    """
    facts = collect_cheap()
    if isinstance(injected, dict):
        facts.update(reconcile_injected_facts(injected))
    return facts


def pre_commit(injected: object | None) -> int:
    """The hook's entry point. Writes only where writing is allowed.

    This is where the structural conflict was created: ``--apply`` ran on every
    commit, so every branch rewrote marker lines the default branch had also
    rewritten. A branch now never writes them, and its markers are instead
    *checked* against the base branch — which is what makes the merge a clean
    one-sided change. The refresh branch is the one exception, and it is resolved
    by ``resolve_fact_scope`` rather than decided here.
    """
    scope = resolve_fact_scope(REPO_ROOT)
    if not scope.frozen:
        facts = (
            reconcile_injected_facts(injected)
            if isinstance(injected, dict)
            else collect(run_tests=True)
        )
        changed, updated, unknown = apply_facts(facts)
        print(f"doc facts: {scope.reason} — rewrote {updated} marker value(s) in {changed} file(s)")
        if unknown:
            print(f"  skipped {len(unknown)} marker(s) with no derivable value (unknown)")
        findings = check_facts(facts)
        if findings:
            print(f"\n{len(findings)} finding(s):\n")
            for f in findings:
                print("  -", f)
            return 1
        print("no findings — documentation is consistent with the repository")
        return 0

    # ── a branch: frozen markers, enforced rather than assumed ───────────────
    print(f"doc facts: {scope.reason} — markers are frozen at the base branch's values.")
    print("   A branch must never modify a fact marker line; only the default branch may")
    print("   (state/DECISIONS.md ADR-008). This hook will not rewrite them.")
    findings: list[str] = []
    if scope.base:
        findings, compared = check_vs_base(scope.base)
        print(f"   checked {compared} base marker line(s) against {scope.base[:12]}")
    else:
        print("   no base branch ref resolves locally, so the unchanged-marker check is skipped")
    stale = stale_markers(_facts_for_branch(injected))
    if stale:
        print(f"   {len(stale)} value(s) are stale here and are left as-is (advisory):")
        for s in stale[:15]:
            print("     -", s)
        if len(stale) > 15:
            print(f"     … and {len(stale) - 15} more")
    if findings:
        print(f"\n{len(findings)} finding(s):\n")
        for f in findings:
            print("  -", f)
        print(
            "\nRestore the base branch's marker lines (do not re-sync them):\n"
            f"    git checkout {scope.base or '<base>'} -- <the files named above>"
        )
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="rewrite marker values from the repo")
    g.add_argument("--check", action="store_true", help="fail on stale markers/bare claims")
    g.add_argument(
        "--sync",
        action="store_true",
        help="compute facts once, apply to docs, verify, and write cache (one pytest run)",
    )
    g.add_argument(
        "--check-vs-base",
        metavar="REF",
        help="fail when this tree modifies a fact marker line that REF has — the "
        "branch-side rule (a branch must never modify a marker; only the default branch may)",
    )
    g.add_argument(
        "--status",
        action="store_true",
        help="report stale marker values without writing them; never fails (a branch's "
        "markers are expected to be stale, because they are the published values)",
    )
    g.add_argument(
        "--pre-commit",
        action="store_true",
        help="hook mode: sync markers on the default branch, and on any other branch "
        "enforce --check-vs-base and report staleness without writing",
    )
    ap.add_argument("--run-tests", action="store_true", help="compute test facts by running them")
    ap.add_argument(
        "--facts-json",
        help="use the provided JSON fact snapshot instead of computing (for CI reuse)",
    )
    args = ap.parse_args()

    if args.pre_commit:
        try:
            injected = json.loads(args.facts_json) if args.facts_json else None
        except json.JSONDecodeError:
            injected = None
        return pre_commit(injected)

    if args.check_vs_base:
        findings, compared = check_vs_base(args.check_vs_base)
        print(
            f"sync_doc_facts: compared {compared} base marker line(s) against "
            f"{args.check_vs_base[:12]}"
        )
        if findings:
            print(f"\n{len(findings)} finding(s):\n")
            for f in findings:
                print("  -", f)
            print(
                "\nA branch must never modify a fact marker line; only the default branch may "
                "(state/DECISIONS.md ADR-008).\nRestore the base value rather than re-syncing it."
            )
            return 1
        if compared == 0:
            print("  note: no base marker lines were comparable — nothing was verified")
        print("no findings — this tree leaves every base marker line unchanged")
        return 0

    if args.status:
        facts = collect_cheap()
        if args.facts_json:
            with contextlib.suppress(json.JSONDecodeError):
                facts.update(reconcile_injected_facts(json.loads(args.facts_json)))
        stale = stale_markers(facts)
        if stale:
            print(f"sync_doc_facts: {len(stale)} stale marker value(s) (not written):")
            for s in stale[:20]:
                print("  -", s)
            if len(stale) > 20:
                print(f"  … and {len(stale) - 20} more")
        else:
            print("sync_doc_facts: no stale marker values")
        return 0

    if args.sync:
        facts = collect(run_tests=True)
        changed, updated, unknown = apply_facts(facts)
        print(f"sync_doc_facts: rewrote {updated} marker value(s) in {changed} file(s)")
        if unknown:
            print(f"  skipped {len(unknown)} marker(s) with no derivable value (unknown):")
            for u in unknown[:15]:
                print(f"    {u}")
        findings = check_facts(facts)
        print(f"sync_doc_facts: checked {len(iter_docs())} markdown file(s)")
        if findings:
            print(f"\n{len(findings)} finding(s):\n")
            for f in findings:
                print("  -", f)
            return 1
        print("no findings — documentation is consistent with the repository")
        return 0

    if args.facts_json:
        facts = reconcile_injected_facts(json.loads(args.facts_json))
    else:
        facts = collect(run_tests=args.run_tests)

    if args.apply:
        changed, updated, unknown = apply_facts(facts)
        print(f"sync_doc_facts: rewrote {updated} marker value(s) in {changed} file(s)")
        if unknown:
            print(f"  skipped {len(unknown)} marker(s) with no derivable value (unknown):")
            for u in unknown[:15]:
                print(f"    {u}")
        return 0

    findings = check_facts(facts)
    print(f"sync_doc_facts: checked {len(iter_docs())} markdown file(s)")
    if findings:
        print(f"\n{len(findings)} finding(s):\n")
        for f in findings:
            print("  -", f)
        return 1
    print("no findings — every marked fact matches the repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
