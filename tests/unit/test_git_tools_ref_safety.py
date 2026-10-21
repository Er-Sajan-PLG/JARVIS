"""Ref-safety tests for ``app/tools/git_tools.py`` (S0 hardening).

Before this fix every ref-taking git tool forwarded a caller-supplied revision
straight into ``subprocess.run(["git", ...])``. A revision such as
``--output=/tmp/pwned`` is therefore parsed by git as an *option*, and
``git_diff_stat`` wrote an attacker-chosen absolute path — reachable
unauthenticated through the MCP server.

These tests pin the fix:

  * option-like, reflog and traversal revisions are refused before git runs
  * legitimate revisions (HEAD, HEAD~1, ``^`` ancestry, tags, remote branches,
    full and abbreviated SHAs) still work — and still produce real output
  * the ref arguments handed to git are shielded by ``--end-of-options`` and a
    trailing ``--``

Everything runs against a throwaway repository built under ``tmp_path``; no
file is written outside it.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.tools import git_tools
from app.tools.git_tools import GIT_TOOLS, git_diff_full, git_diff_stat, git_show

TOOL_FUNCS: dict[str, Any] = {
    "git_diff_stat": git_diff_stat,
    "git_diff_full": git_diff_full,
    "git_show": git_show,
}

# Every ref-carrying parameter of every ref-taking tool.
REF_PARAMS: list[tuple[str, str]] = [
    ("git_diff_stat", "from_ref"),
    ("git_diff_stat", "to_ref"),
    ("git_diff_full", "from_ref"),
    ("git_diff_full", "to_ref"),
    ("git_show", "ref"),
]
REF_PARAM_IDS = [f"{name}-{param}" for name, param in REF_PARAMS]

# Revisions that git would read as an option rather than as a revision.
OPTION_LIKE_REFS = [
    "--output=/tmp/pwned",  # the live exploit: arbitrary absolute-path write
    "-n1",
    "-p",
    "-c",
    "--upload-pack=/bin/sh",
    "--",
    "-",
]

# Revisions that smuggle reflog syntax, ranges, paths or shell metacharacters.
INJECTION_LIKE_REFS = [
    "HEAD@{1}",
    "@{now}",
    "HEAD~1..HEAD",
    "main..origin/main",
    "../../etc/passwd",
    "HEAD:../../etc/passwd",
    "HEAD:alpha.txt",
    "/etc/passwd",
    "refs/heads/x/../../../../tmp/x",
    "HEAD\n--stat",
    "HEAD; touch /tmp/pwned",
    "HEAD$(touch /tmp/pwned)",
    "HEAD`touch /tmp/pwned`",
    "HEAD --output=/tmp/pwned",
    "",
]

# A hermetic git environment: neither the developer's global/system config
# (hooks, commit.gpgsign, init.defaultBranch) nor an inherited repository
# pointer may decide the outcome.
#
# The GIT_* variables below must be *dropped*, not merely overridden. An
# inherited GIT_DIR takes precedence over the cwd this helper passes, so the
# ``git_repo`` fixture's add/commit calls operate on whichever repository
# GIT_DIR names instead of the scratch one. Reproduced by setting
# ``GIT_DIR=<this repo>/.git``: the fixture's writes created "first commit" and
# "second commit" on whatever branch was checked out -- two such commits were
# observed on an unrelated branch during this session -- and with GIT_DIR set
# this file went from passing to 15 errors before the environment was sanitised.
#
# What does NOT set this, contrary to the obvious guess: **git does not export
# GIT_DIR to hooks.** A hook receives GIT_INDEX_FILE, GIT_PREFIX, GIT_EDITOR and
# GIT_AUTHOR_*, but no GIT_DIR. GIT_DIR arrives from the invoking environment
# instead -- a shell or tool working against a bare repository, or a wrapper
# that exported it. That is precisely why these helpers must not depend on it.
_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}

_GIT_ENV_DROP = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def _git_env() -> dict[str, str]:
    """Environment for scratch-repo git calls, with no inherited repository."""
    inherited = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    return {**inherited, **_GIT_ENV}


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside ``repo`` with a hermetic environment."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    )
    return completed.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A throwaway repo: two commits, a branch, a tag and a remote-tracking ref."""
    # The app's git tools (app.tools.git_tools) shell out without sanitising
    # their own environment, so an inherited pointer has to be removed from
    # os.environ and not only from this module's helper env -- otherwise those
    # calls read whichever repository GIT_DIR names. Verified: with GIT_DIR set,
    # exactly the three tests that call app.tools.git_tools failed while the
    # rest passed.
    for var in _GIT_ENV_DROP:
        monkeypatch.delenv(var, raising=False)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    ident = ("-c", "user.name=Ref Safety", "-c", "user.email=refsafety@example.invalid")

    (repo / "alpha.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "alpha.txt")
    _git(repo, *ident, "commit", "-qm", "first commit")

    (repo / "beta.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "beta.txt")
    _git(repo, *ident, "commit", "-qm", "second commit")

    _git(repo, "branch", "feature/x")
    _git(repo, "tag", "v1.0.0")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    monkeypatch.chdir(repo)
    yield repo


def _invoke(tool: str, param: str, value: str) -> str:
    """Call a ref-taking tool with ``value`` in the named ref parameter."""
    if tool == "git_show":
        return git_show(**{param: value})
    kwargs = {"from_ref": "HEAD~1", "to_ref": "HEAD", param: value}
    return TOOL_FUNCS[tool](**kwargs)


def _record_subprocess(monkeypatch: pytest.MonkeyPatch, captured: list[list[str]]) -> None:
    """Capture git argv without running git."""

    def _fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(git_tools.subprocess, "run", _fake_run)


# ─── The exploit must be refused ───────────────────────────────────────────────


def test_option_like_ref_is_refused_before_git_runs(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live S0 payload is refused and git is never spawned."""
    attack_dir = tmp_path / "attack"
    attack_dir.mkdir()
    spawned: list[list[str]] = []
    _record_subprocess(monkeypatch, spawned)

    for tool, param in REF_PARAMS:
        target = attack_dir / f"pwned-{tool}-{param}"
        with pytest.raises(ValueError, match="git ref"):
            _invoke(tool, param, f"--output={target}")
        assert spawned == [], f"{tool}({param}=...) reached git with an option-like ref"

    assert list(attack_dir.iterdir()) == [], "an option-like ref wrote a file"


@pytest.mark.parametrize(("tool", "param"), REF_PARAMS, ids=REF_PARAM_IDS)
def test_option_and_injection_refs_are_rejected(tool: str, param: str, git_repo: Path) -> None:
    """Option-like and reflike revisions are refused on every ref parameter."""
    for bad in [*OPTION_LIKE_REFS, *INJECTION_LIKE_REFS]:
        try:
            result = _invoke(tool, param, bad)
        except ValueError as exc:
            assert "git ref" in str(exc)
        else:
            pytest.fail(f"{tool}({param}={bad!r}) was not refused; returned {result!r}")


def test_registered_tool_handlers_enforce_the_same_rules(git_repo: Path, tmp_path: Path) -> None:
    """The registered tool surface (what the executor and prompts see) is fixed too."""
    handlers = {tool.name: tool.handler for tool in GIT_TOOLS}
    attack_dir = tmp_path / "attack"
    attack_dir.mkdir()

    for name, param in REF_PARAMS:
        with pytest.raises(ValueError, match="git ref"):
            handlers[name](**{param: f"--output={attack_dir / f'{name}-{param}'}"})

    assert list(attack_dir.iterdir()) == [], "a registered handler wrote a file"
    assert "second commit" in handlers["git_show"](ref="HEAD")


# ─── Legitimate revisions must keep working ────────────────────────────────────


def test_legitimate_refs_still_resolve(git_repo: Path) -> None:
    """Hardening must not over-block: every real ref spelling still works."""
    sha = _git(git_repo, "rev-parse", "HEAD")

    for ref in ["HEAD", sha, sha[:7], "main", "origin/main", "feature/x", "v1.0.0"]:
        assert "1 file changed" in git_diff_stat(from_ref="HEAD~1", to_ref=ref), ref
        assert "beta.txt" in git_diff_full(from_ref="HEAD~1", to_ref=ref), ref
        assert "second commit" in git_show(ref=ref), ref

    # Ancestry operators survive too.
    assert "first commit" in git_show(ref="HEAD~1")
    assert "first commit" in git_show(ref="HEAD^")
    assert "1 file changed" in git_diff_stat(from_ref="HEAD^", to_ref="HEAD")

    # Defaults are untouched.
    assert "1 file changed" in git_diff_stat()
    assert "second commit" in git_show()


def test_refs_are_not_degraded_to_pathspecs(git_repo: Path) -> None:
    """A ``--`` placed *before* the refs makes git read them as paths and go silent."""
    assert "1 file changed" in git_diff_stat(from_ref="HEAD~1", to_ref="HEAD")
    assert "beta.txt" in git_diff_full(from_ref="HEAD~1", to_ref="HEAD")
    assert "second commit" in git_show(ref="HEAD")


def test_wellformed_missing_ref_still_fails_like_before(git_repo: Path) -> None:
    """A well-formed but unknown revision still reaches git and raises RuntimeError."""
    with pytest.raises(RuntimeError):
        git_diff_stat(from_ref="nonexistent-branch-xyz", to_ref="HEAD")


# ─── Arguments handed to git ───────────────────────────────────────────────────


@pytest.mark.parametrize(("tool", "param"), REF_PARAMS, ids=REF_PARAM_IDS)
def test_ref_arguments_are_terminated_in_git_argv(
    tool: str, param: str, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refs sit after ``--end-of-options`` and before a trailing ``--``."""
    sha = _git(git_repo, "rev-parse", "HEAD")
    captured: list[list[str]] = []
    _record_subprocess(monkeypatch, captured)

    _invoke(tool, param, sha)

    assert len(captured) == 1
    argv = captured[0]
    assert argv[0] == "git"
    assert "--end-of-options" in argv, argv
    guard = argv.index("--end-of-options")
    assert argv[-1] == "--", argv
    assert [arg for arg in argv[2:guard] if not arg.startswith("-")] == [], argv
    assert sha in argv[guard + 1 : -1], argv


def test_scratch_repo_is_not_redirected_by_an_inherited_git_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inherited ``GIT_DIR`` must not redirect these writes.

    Git exports ``GIT_DIR`` into the environment of every hook it runs, and
    ``githooks/pre-push`` runs this suite. ``GIT_DIR`` takes precedence over the
    ``cwd`` the helper passes, so before the environment was sanitised the
    ``git_repo`` fixture's ``add``/``commit`` calls operated on the *real*
    repository and created ``first commit`` and ``second commit`` on whatever
    branch was checked out. Two such commits were observed on an unrelated
    branch while the suite ran from a hook.

    A decoy repository stands in for the real one, so a regression fails this
    test instead of writing to somebody's repository.
    """
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(decoy, "init", "-q", "-b", "main")
    (decoy / "decoy.txt").write_text("d\n", encoding="utf-8")
    _git(decoy, "add", "decoy.txt")
    _git(
        decoy,
        "-c",
        "user.name=Decoy",
        "-c",
        "user.email=decoy@example.invalid",
        "commit",
        "-qm",
        "decoy base",
    )
    decoy_head = _git(decoy, "rev-parse", "HEAD")

    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    _git(scratch, "init", "-q", "-b", "main")
    (scratch / "only-here.txt").write_text("x\n", encoding="utf-8")
    _git(scratch, "add", "only-here.txt")
    _git(
        scratch,
        "-c",
        "user.name=Ref Safety",
        "-c",
        "user.email=refsafety@example.invalid",
        "commit",
        "-qm",
        "scratch commit",
    )

    # The commit exists in the scratch repo...
    assert _git(scratch, "rev-parse", "HEAD") != decoy_head
    assert "only-here.txt" in _git(scratch, "show", "--stat", "--format=", "HEAD")

    # ...and the decoy is untouched: still unborn, still no new commit.
    assert _git(decoy, "rev-parse", "HEAD") == decoy_head
    assert "only-here" not in _git(decoy, "ls-tree", "-r", "--name-only", "HEAD~0")
