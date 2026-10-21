"""The pre-push hook must verify only the commits a push INTRODUCES.

Why this exists
---------------
`githooks/pre-push` required a verifiable signature (`%G?` in ``G``/``U``) on
every commit in the pushed range. For an existing branch that range is
``remote_sha..local_sha``, so as soon as a PR branch merged ``main`` into
itself, every commit ``main`` had gained since the branch was cut entered the
range -- including GitHub's own commits.

Those verify as ``%G? = E`` locally: *cannot check*, not *unsigned*. This
repository signs with ``gpg.format=ssh`` and verifies against
``gpg.ssh.allowedsignersfile``, so it holds no PGP keyring able to check a
GitHub signature (Dependabot bumps and API squash-merges are PGP-signed by
GitHub). The hook therefore refused the push outright:

    ❌ commit 4cf9f5a is not signed (GPG/SSH signature required)

and the branch was unrecoverable, because Stage 0b refuses the force-push that
would have kept it linear instead. Two branches had to be rebuilt.

The fix is to stop re-verifying what is already published. Two properties must
hold, and both are asserted below:

  1. a commit already on the remote is NOT re-verified (the bug is gone), and
  2. a genuinely new unsigned commit IS still refused (the check is not weakened)

Property 2 is the one that matters most. A fix that made the hook stop
complaining would be indistinguishable from deleting the check, so the negative
control below is not decoration -- it is the test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_PUSH = REPO_ROOT / "githooks" / "pre-push"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _repo_with_a_merged_main(tmp_path: Path) -> tuple[Path, str, str]:
    """Build the exact shape that broke: a branch that merged an advanced main.

    Returns (worktree, sha_of_published_main_commit, sha_of_new_merge_commit).
    """
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "--initial-branch=main")

    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=main")
    # No hooks, no signing: this test is about which commits are selected.
    _git(work, "config", "core.hooksPath", str(tmp_path / "nohooks"))
    _git(work, "config", "commit.gpgsign", "false")
    _git(work, "config", "user.email", "test@example.invalid")
    _git(work, "config", "user.name", "Test")
    _git(work, "remote", "add", "origin", str(origin))

    # A: main's first commit, published.
    (work / "a.txt").write_text("a\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "A: initial")

    # A feature branch, cut here and pushed -- so its remote tip is B.
    _git(work, "checkout", "-q", "-b", "feat")
    (work / "b.txt").write_text("b\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "B: feature work")
    _git(work, "push", "-q", "-u", "origin", "feat")

    # main advances while the branch is open. C is the published commit that
    # ends up inside the branch's pushed range after the merge.
    _git(work, "checkout", "-q", "main")
    (work / "c.txt").write_text("c\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "C: main advances")
    _git(work, "push", "-q", "origin", "main")
    sha_c = _git(work, "rev-parse", "HEAD")

    # The merge that used to make the branch unpushable.
    _git(work, "checkout", "-q", "feat")
    _git(work, "fetch", "-q", "origin")
    _git(work, "merge", "--no-edit", "-q", "origin/main")
    sha_merge = _git(work, "rev-parse", "HEAD")

    return work, sha_c, sha_merge


def _range_for_existing_branch(work: Path) -> str:
    """The range the hook computes: remote_sha..local_sha."""
    remote_sha = _git(work, "rev-parse", "origin/feat")
    return f"{remote_sha}..HEAD"


def _rev_list(work: Path, rev: str, *extra: str) -> list[str]:
    out = _git(work, "rev-list", rev, *extra)
    return out.split() if out else []


def test_the_hook_excludes_published_commits_from_the_signature_check() -> None:
    """The hook must not re-verify what origin already accepted.

    Asserted on the hook's own rev-list invocation rather than by running it:
    executing the hook would run the full test suite and recurse. The companion
    test below proves the expression this asserts on actually behaves as
    claimed, so this is not a bare string match.
    """
    text = PRE_PUSH.read_text(encoding="utf-8")
    rev_list_lines = [
        line.strip()
        for line in text.splitlines()
        if "rev-list" in line and "%G?" in text and not line.strip().startswith("#")
    ]
    signature_stage = [
        line for line in rev_list_lines if "--not --remotes=origin" in line
    ]
    assert signature_stage, (
        "the signature stage no longer excludes published commits -- "
        "a branch that merged main would become unpushable again"
    )


def test_published_commits_are_excluded_and_new_ones_are_not(tmp_path: Path) -> None:
    """The semantics the hook relies on, exercised against a real repository."""
    work, sha_c, sha_merge = _repo_with_a_merged_main(tmp_path)
    rev = _range_for_existing_branch(work)

    # Precondition: the bug is real. C is published on origin/main AND inside
    # the branch's pushed range, which is why the hook saw it at all.
    plain = _rev_list(work, rev)
    assert sha_c in plain, (
        "test setup is wrong: the published commit is not in the pushed range, "
        "so this would not have reproduced the original failure"
    )

    # The fix: it is excluded.
    filtered = _rev_list(work, rev, "--not", "--remotes=origin")
    assert sha_c not in filtered, (
        "a commit already published on origin is still being re-verified"
    )

    # The negative control: the new merge commit is NOT excluded, so the hook
    # still has to verify it. Without this, the change would be indistinguishable
    # from switching the signature check off.
    assert sha_merge in filtered, (
        "the new commit is excluded too -- the signature check has been weakened"
    )
