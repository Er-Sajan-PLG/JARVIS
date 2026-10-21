"""A branch must never be able to conflict with the default branch over a fact marker.

Why this exists
---------------
Derived numbers live in the documents as HTML-comment markers
(``<!--fact:test_count-->2161<!--/fact-->``), and ``githooks/pre-commit`` used to
rewrite those interiors on **every** commit. A marker value is a function of the
working tree, so a branch's value differs from the default branch's the moment the
branch changes a count -- and the default branch advances on its own. Both sides
then changed the same lines, so git reported a conflict. Not occasionally:
structurally, on every test-adding PR, every dependency PR and every ADR. It
happened for real (a PR went ``DIRTY`` with conflicts in ``docs/FINAL_STATE.md``,
``docs/GOVERNANCE.md`` and ``state/DECISIONS.md`` and had to be rebuilt).

No ``.gitattributes`` driver can fix that. GitHub computes mergeability itself and
does not run merge drivers; measured on a probe repository that declared
``merge=union`` for one file and ``merge=ours`` for another and changed the same
line on both sides, the server still answered ``mergeable=false`` /
``mergeable_state=dirty`` and refused the merge with "Pull Request has merge
conflicts". ``merge=union`` does apply locally and emits BOTH values into the
document, which is worse than the conflict.

So the fix is an invariant, not a driver:

    **A branch must never modify a fact marker line. Only the default branch may.**

A branch that leaves the line alone receives the default branch's change as a
clean one-sided merge, and the conflict becomes impossible by construction.

What is asserted here
---------------------
The *shape* of the defect, built with real git rather than mocked
(``test_a_branch_that_rewrites_a_marker_conflicts_...``), the clean merge that
replaces it (``..._leaves_the_marker_alone_merges_cleanly``), and the mechanism
that keeps the shape from coming back: the checker that refuses a branch which
changes a marker, the advisory report that replaces the rewrite, and the hook
that no longer writes on a branch.

The three tests that carry the fix -- ``test_check_vs_base_rejects_...``,
``test_check_vs_base_accepts_...`` and
``test_the_hook_leaves_a_branch_s_markers_alone`` -- fail on the pre-fix tree
(no ``--check-vs-base`` mode exists, and the hook rewrites the marker) and pass
after it. The two merge tests and the default-branch hook test are controls: they
document the defect and prove the write path was not simply deleted.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
PRE_COMMIT = REPO_ROOT / "githooks" / "pre-commit"

# Every test below builds a real repository and runs real git; there is no mock to
# fall back to, so on a machine without git there is nothing honest to assert.
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="needs git and bash to build the merge shape",
)

MARKER_LINE = "ADRs: <!--fact:adr_count-->1<!--/fact--> in this fixture.\n"
DOC = (
    "# DOC\n\n**Status**: ACTIVE\n**Type**: reference\n"
    "**Source**: `scripts/` at HEAD\n\n" + MARKER_LINE
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_allow_failure(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _init_repo(path: Path) -> Path:
    """A scratch repository shaped like the real one, minus everything irrelevant.

    No hooks (so the host repository's hook cannot fire), no signing, and a
    ``main`` default branch. The two fact scripts are copied in at test time, so
    the code under test is always the code in the tree, never a mock.
    """
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "core.hooksPath", str(path / "no-hooks"))
    (path / "scripts").mkdir(exist_ok=True)
    for name in ("doc_facts.py", "sync_doc_facts.py", "refresh_doc_facts.py"):
        shutil.copy(SCRIPTS / name, path / "scripts" / name)
    # The hook requires an executable repository interpreter at this exact path.
    # Only `python` is provided, so the pre-commit framework stage stays out of
    # the way -- this test is about the fact stage.
    (path / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    (path / ".venv" / "bin" / "python").symlink_to(sys.executable)
    return path


def _write_doc(repo: Path, text: str = DOC) -> Path:
    doc = repo / "docs" / "DOC.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(text, encoding="utf-8")
    return doc


def _write_adr(repo: Path, number: int) -> Path:
    adr = repo / "docs" / "adr" / f"ADR-{number:03d}-fixture.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text(f"# ADR-{number:03d} — fixture\n\n## Decision\n\nFixture.\n", encoding="utf-8")
    return adr


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _run_script(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "sync_doc_facts.py"), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _run_hook(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(PRE_COMMIT)],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _marker(text: str) -> str:
    """The marker line itself, so assertions are about the line, not the prose."""
    for line in text.splitlines():
        if "<!--fact:" in line:
            return line.strip()
    raise AssertionError(f"no marker line in {text!r}")


# ── the defect, built with real git ──────────────────────────────────────────


def _two_sided_marker_change(tmp_path: Path) -> tuple[Path, str]:
    """Both sides rewrite the same marker line: the shape that broke.

    Returns the repository, sitting on the branch with ``main`` advanced.
    """
    repo = _init_repo(tmp_path / "repo")
    _write_doc(repo)
    _write_adr(repo, 1)
    _commit(repo, "main: the published marker value")

    _git(repo, "checkout", "-q", "-b", "fix/x")
    _write_doc(repo, DOC.replace("-->1<!--", "-->2<!--"))
    _commit(repo, "fix/x: the branch rewrites the marker (the old hook's behaviour)")

    _git(repo, "checkout", "-q", "main")
    _write_doc(repo, DOC.replace("-->1<!--", "-->3<!--"))
    _commit(repo, "main: the default branch rewrites the same marker")
    _git(repo, "checkout", "-q", "fix/x")
    return repo, "main"


def test_a_branch_that_rewrites_a_marker_conflicts_with_the_default_branch(
    tmp_path: Path,
) -> None:
    """The reproduction: a real ``git merge`` that cannot be completed.

    This is the defect stated as a property of git rather than as prose, and it
    is why the fix cannot be a merge driver: the conflict is in the *lines*, and
    both sides legitimately changed them.
    """
    repo, base = _two_sided_marker_change(tmp_path)
    merge = _git_allow_failure(repo, "merge", "--no-edit", base)

    assert merge.returncode != 0, "both sides changed the marker; git must conflict"
    assert "CONFLICT" in (merge.stdout + merge.stderr)
    conflicted = (repo / "docs" / "DOC.md").read_text(encoding="utf-8")
    assert "<<<<<<<" in conflicted and ">>>>>>>" in conflicted
    assert "-->2<!--" in conflicted and "-->3<!--" in conflicted
    _git_allow_failure(repo, "merge", "--abort")


def test_a_branch_that_leaves_the_marker_alone_merges_cleanly(tmp_path: Path) -> None:
    """The fix, as a property of git: one-sided changes cannot conflict.

    The branch adds an ADR (so the marker is stale *relative to the branch*) and
    never touches the marker line. The default branch rewrites it. The merge is
    clean and the published value wins -- which is also the accurate outcome,
    because the documents describe the published repository.
    """
    repo = _init_repo(tmp_path / "repo")
    _write_doc(repo)
    _write_adr(repo, 1)
    _commit(repo, "main: the published marker value")

    _git(repo, "checkout", "-q", "-b", "fix/x")
    _write_adr(repo, 2)  # the branch changes a count, and only that
    _commit(repo, "fix/x: add an ADR, leaving the marker line untouched")

    _git(repo, "checkout", "-q", "main")
    _write_doc(repo, DOC.replace("-->1<!--", "-->3<!--"))
    _commit(repo, "main: the default branch rewrites the marker")
    _git(repo, "checkout", "-q", "fix/x")

    merge = _git_allow_failure(repo, "merge", "--no-edit", "main")

    assert merge.returncode == 0, f"merge must be clean, got:\n{merge.stdout}{merge.stderr}"
    merged = (repo / "docs" / "DOC.md").read_text(encoding="utf-8")
    assert _marker(merged) == _marker(DOC.replace("-->1<!--", "-->3<!--"))
    assert (repo / "docs" / "adr" / "ADR-002-fixture.md").is_file()


# ── the invariant, enforced (the negative control) ───────────────────────────


def test_check_vs_base_rejects_a_branch_that_changed_a_marker(tmp_path: Path) -> None:
    """The negative control. A fix that only stopped the hook writing would be
    indistinguishable from deleting the check, so this asserts the check has
    teeth: a branch that changes a marker line FAILS, and is told which one.
    """
    repo, base = _two_sided_marker_change(tmp_path)

    result = _run_script(repo, "--check-vs-base", base)

    assert result.returncode == 1, f"expected a refusal, got:\n{result.stdout}{result.stderr}"
    assert "adr_count" in result.stdout
    # Names both sides: the base branch's value and the value this branch wrote.
    assert "'3'" in result.stdout and "'2'" in result.stdout
    assert "must never modify a fact marker line" in result.stdout
    assert "ADR-008" in result.stdout


def test_check_vs_base_accepts_a_branch_whose_marker_is_stale_but_unchanged(
    tmp_path: Path,
) -> None:
    """A branch's own counts are not facts about the project.

    The branch adds an ADR, so ``adr_count`` is 2 in its tree while the marker
    says 1. That must PASS: the marker is the published value, and demanding the
    branch's own count is exactly what forced the rewrite that conflicted.
    """
    repo = _init_repo(tmp_path / "repo")
    _write_doc(repo)
    _write_adr(repo, 1)
    _commit(repo, "main: the published marker value")
    _git(repo, "checkout", "-q", "-b", "fix/x")
    _write_adr(repo, 2)
    _commit(repo, "fix/x: add an ADR")

    result = _run_script(repo, "--check-vs-base", "main")

    assert result.returncode == 0, f"a stale-but-unchanged marker must pass:\n{result.stdout}"
    assert "leaves every base marker line unchanged" in result.stdout
    # ...and the staleness is still REPORTED, just not written. Advisory, never
    # blocking: on a branch this is the expected state, not a defect.
    status = _run_script(repo, "--status")
    assert status.returncode == 0
    assert "adr_count" in status.stdout


def test_the_hook_leaves_a_branch_s_markers_alone_and_reports_them(tmp_path: Path) -> None:
    """The cause, removed. The hook used to rewrite the marker here.

    A branch that moves a count must get a report, not a rewrite: the rewrite is
    what put both sides on the same line and made every branch conflict with the
    default branch.
    """
    repo = _init_repo(tmp_path / "repo")
    _write_doc(repo)
    _write_adr(repo, 1)
    _commit(repo, "main: the published marker value")
    _git(repo, "checkout", "-q", "-b", "fix/x")
    _write_adr(repo, 2)
    before = (repo / "docs" / "DOC.md").read_text(encoding="utf-8")

    result = _run_hook(repo)

    assert result.returncode == 0, f"the hook must not refuse this:\n{result.stdout}"
    after = (repo / "docs" / "DOC.md").read_text(encoding="utf-8")
    assert after == before, "the hook rewrote a marker line on a branch"
    assert _marker(after) == _marker(DOC)
    # It says what it did not do, and why -- and names the stale value.
    assert "markers are frozen at the base branch's values" in result.stdout
    assert "adr_count" in result.stdout
    assert "advisory" in result.stdout


def test_the_hook_still_writes_markers_on_the_default_branch(tmp_path: Path) -> None:
    """The control for the test above: the write path was not deleted.

    On the default branch the documents ARE the published repository, so the
    hook must still correct them -- otherwise this "fix" would be an amnesty for
    stale documentation, which is the drift ADR-014 was written to end.
    """
    repo = _init_repo(tmp_path / "repo")
    _write_doc(repo)
    _write_adr(repo, 1)
    _commit(repo, "main: the published marker value")
    _write_adr(repo, 2)  # the count moves on the default branch itself

    result = _run_hook(repo)

    assert result.returncode == 0, result.stdout
    after = (repo / "docs" / "DOC.md").read_text(encoding="utf-8")
    assert "<!--fact:adr_count-->2<!--/fact-->" in after, after
    assert "rewrote 1 marker value(s)" in result.stdout


def test_the_hook_refuses_a_branch_that_modified_a_marker(tmp_path: Path) -> None:
    """The invariant is enforced at commit time, not only in the gate.

    Otherwise the failure surfaces after the push, on a PR the author has already
    finished with -- and the remedy (restore the base line) is cheapest here.
    """
    repo, _ = _two_sided_marker_change(tmp_path)
    # A fresh, uncommitted marker change on the branch: the hook must refuse it.
    _write_doc(repo, DOC.replace("-->1<!--", "-->7<!--"))

    result = _run_hook(repo)

    assert result.returncode == 1, result.stdout
    assert "adr_count" in result.stdout
    assert "Commit refused" in result.stdout


# ── the rules themselves, without a repository ───────────────────────────────


def _load(name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def facts_mod():
    return _load("merge_conflicts_doc_facts", SCRIPTS / "doc_facts.py")


def test_drift_vs_base_is_multiset_not_membership(facts_mod) -> None:
    """Changing ONE of two identical base lines is still a modified line.

    Set membership would miss it: the value is still "present" in the file, so a
    branch could edit a line and keep a copy elsewhere and pass.
    """
    base = "a <!--fact:gate_count-->29<!--/fact-->\nb <!--fact:gate_count-->29<!--/fact-->\n"
    head = "a <!--fact:gate_count-->29<!--/fact-->\nb <!--fact:gate_count-->30<!--/fact-->\n"
    findings = facts_mod.marker_drift_vs_base("docs/X.md", base, head)
    assert len(findings) == 1 and "gate_count" in findings[0]


def test_drift_vs_base_allows_an_added_marker_line(facts_mod) -> None:
    """A line the base does not have cannot conflict, so it is allowed.

    It is still checked for coherence by ``marker_value_conflicts`` below, and by
    the default branch's own ``--check`` once it merges.
    """
    base = "<!--fact:gate_count-->29<!--/fact-->\n"
    head = "<!--fact:gate_count-->29<!--/fact-->\n<!--fact:adr_count-->19<!--/fact-->\n"
    assert facts_mod.marker_drift_vs_base("docs/X.md", base, head) == []


def test_drift_vs_base_flags_a_deleted_marker_line(facts_mod) -> None:
    """Deleting a line the default branch changed is a modify/delete conflict."""
    base = "<!--fact:gate_count-->29<!--/fact-->\n"
    findings = facts_mod.marker_drift_vs_base("docs/X.md", base, "")
    assert len(findings) == 1 and "gate_count" in findings[0]


def test_drift_vs_base_flags_a_renamed_fact(facts_mod) -> None:
    """A typo'd fact name is not a marker-interior rewrite."""
    base = "<!--fact:gate_count-->29<!--/fact-->\n"
    head = "<!--fact:gate_countt-->29<!--/fact-->\n"
    assert facts_mod.marker_drift_vs_base("docs/X.md", base, head)


def test_marker_value_conflicts_flags_two_values_in_one_document(facts_mod) -> None:
    """A branch may add a marker line, but not a second value for one fact."""
    text = "<!--fact:gate_count-->29<!--/fact-->\n<!--fact:gate_count-->30<!--/fact-->\n"
    findings = facts_mod.marker_value_conflicts("docs/X.md", text)
    assert len(findings) == 1 and "exactly one value" in findings[0]


def test_scope_precedence(facts_mod) -> None:
    """The resolution order, asserted as a table.

    Each rung exists because the environment above it is unavailable: a pull
    request has no local branch, a runner has no remote HEAD, and a developer's
    checkout has neither ``GITHUB_*`` variable. The one convention that selects
    the *stricter* scope is the refresh branch, which is the default branch's
    designated writer of those lines.
    """
    assert facts_mod.resolve_fact_scope(REPO_ROOT, env={"DOC_FACTS_SCOPE": "default"}).scope == (
        "default"
    )
    refresh = facts_mod.resolve_fact_scope(
        REPO_ROOT, env={"GITHUB_HEAD_REF": "chore/doc-facts-refresh-20261021"}
    )
    assert refresh.scope == "default" and "refresh" in refresh.reason
    pr = facts_mod.resolve_fact_scope(REPO_ROOT, env={"GITHUB_BASE_REF": "main"})
    assert pr.scope == "branch" and pr.base
    pushed_main = facts_mod.resolve_fact_scope(REPO_ROOT, env={"GITHUB_REF": "refs/heads/main"})
    assert pushed_main.scope == "default"
    pushed_branch = facts_mod.resolve_fact_scope(REPO_ROOT, env={"GITHUB_REF": "refs/heads/fix/x"})
    assert pushed_branch.scope == "branch" and pushed_branch.base


def test_scope_in_the_real_repository_is_branch_scoped_or_strict() -> None:
    """Whatever this checkout is, the scope must be one of the two defined kinds.

    A third value would silently disable every marker check downstream.
    """
    facts_mod = _load("merge_conflicts_doc_facts_scope", SCRIPTS / "doc_facts.py")
    scope = facts_mod.resolve_fact_scope(REPO_ROOT)
    assert scope.scope in (facts_mod.SCOPE_DEFAULT, facts_mod.SCOPE_BRANCH)
    if scope.frozen:
        assert scope.base, "a frozen scope without a base compares against nothing"


def test_marker_only_rewrites_guard(tmp_path: Path) -> None:
    """The refresh guard: only marker interiors may change.

    This is what makes "the refresh PR merges cleanly" a fact rather than a hope
    -- and what stops the refresh path becoming a way to smuggle prose edits into
    a commit that is allowed to touch lines nobody else may.
    """
    refresh_mod = _load("merge_conflicts_refresh", SCRIPTS / "refresh_doc_facts.py")
    base = "The count is <!--fact:gate_count-->29<!--/fact-->.\nSecond line.\n"
    assert refresh_mod.marker_only_rewrites(base, base.replace("-->29<!--", "-->31<!--")) == []
    prose = refresh_mod.marker_only_rewrites(base, base.replace("Second line.", "Rewritten."))
    assert len(prose) == 1 and "not a marker rewrite" in prose[0]
    renamed = refresh_mod.marker_only_rewrites(
        base, base.replace("<!--fact:gate_count-->", "<!--fact:gate_countt-->")
    )
    assert len(renamed) == 1
    added = refresh_mod.marker_only_rewrites(base, base + "A new line.\n")
    assert len(added) == 1 and "line count changed" in added[0]
