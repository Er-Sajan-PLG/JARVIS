"""Tests for scripts/publish_release.py — the release half of release automation.

Context: the pre-push hook creates tags, but a tag is not a release. GitHub held
21 tags and 0 releases, so changelogs/compare links/"Latest" never existed.
``.github/workflows/release.yml`` can't fix it (Actions billing-blocked), so the
release has to be published locally via ``gh``.

These tests pin the behaviour that matters: tag selection (only well-formed
SemVer tags), idempotency (never re-publish an existing release), backfill
selection, and changelog note generation from conventional commits. They do not
touch the network; ``gh`` invocation is stubbed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "publish_release.py"


def _load():
    spec = importlib.util.spec_from_file_location("publish_release_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_release_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_tag_regex_accepts_semver_and_rejects_noise():
    mod = _load()
    assert mod.TAG_RE.match("v3.1.2")
    assert mod.TAG_RE.match("v0.1.0")
    assert not mod.TAG_RE.match("v3.1")
    assert not mod.TAG_RE.match("3.1.2")
    assert not mod.TAG_RE.match("v3.1.2-rc1")
    assert not mod.TAG_RE.match("release-notes")


def test_local_tags_filters_non_semver(monkeypatch):
    mod = _load()

    def fake_run(cmd, timeout=120):
        if cmd[:2] == ["git", "tag"]:
            return 0, "v1.0.0\nnot-a-tag\nv2.0.0\nv2.0\n", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    assert mod.local_tags() == ["v1.0.0", "v2.0.0"]


def test_released_tags_parses_gh_tabular_output(monkeypatch):
    mod = _load()

    def fake_run(cmd, timeout=120):
        if cmd[:3] == ["gh", "release", "list"]:
            return 0, "v3.1.2\tLatest\tv3.1.2\t2026-09-13T00:47:14Z", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    assert mod.released_tags() == {"v3.1.2"}


def test_already_released_tag_is_a_noop(monkeypatch, capsys):
    mod = _load()

    def fake_run(cmd, timeout=120):
        if cmd == ["gh", "--version"]:
            return 0, "gh version 2.98.0", ""
        if cmd[:2] == ["gh", "auth"]:
            return 0, "logged in", ""
        if cmd[:3] == ["gh", "release", "list"]:
            return 0, "v3.1.2\tLatest\tv3.1.2\t2026-09-13T00:47:14Z", ""
        if cmd[:3] == ["git", "describe", "--tags"]:
            return 0, "v3.1.2", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    rc = mod.main([])

    assert rc == 0
    assert "already exists" in capsys.readouterr().out


def test_backfill_selects_only_unreleased_tags(monkeypatch):
    mod = _load()
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=120):
        calls.append(cmd)
        if cmd == ["gh", "--version"]:
            return 0, "gh version 2.98.0", ""
        if cmd[:2] == ["gh", "auth"]:
            return 0, "logged in", ""
        if cmd[:3] == ["gh", "release", "list"]:
            return 0, "v1.0.0\tLatest\tv1.0.0\t2026-01-01T00:00:00Z", ""
        if cmd[:2] == ["git", "tag"]:
            return 0, "v1.0.0\nv2.0.0", ""
        if cmd[:2] == ["git", "log"]:
            return 0, "feat(x): thing", ""
        if cmd[:3] == ["gh", "release", "create"]:
            return 0, "https://example.invalid/rel", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    rc = mod.main(["--backfill"])

    assert rc == 0
    created = [c for c in calls if c[:3] == ["gh", "release", "create"]]
    assert len(created) == 1, "only the unreleased tag should be published"
    assert "v2.0.0" in created[0]


def test_missing_gh_reports_clean_error(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "gh_available", lambda: False)

    rc = mod.main([])

    assert rc == 1
    assert "gh CLI is not installed" in capsys.readouterr().err


def test_unauthenticated_gh_reports_clean_error(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "gh_available", lambda: True)
    monkeypatch.setattr(mod, "gh_authenticated", lambda: False)

    rc = mod.main([])

    assert rc == 1
    err = capsys.readouterr().err
    assert "not authenticated" in err
    assert "contents:write" in err, "the error should explain the token-scope pitfall"


def test_release_notes_bucket_conventional_commits(monkeypatch):
    mod = _load()

    def fake_run(cmd, timeout=120):
        if cmd[:2] == ["git", "tag"]:
            return 0, "v1.0.0\nv2.0.0", ""
        if cmd[:2] == ["git", "log"]:
            return (
                0,
                "feat(api): add endpoint\nfix(db): handle null\ndocs: note the change\nchore: tidy",
                "",
            )
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    notes = mod.release_notes("v2.0.0")

    assert "### Features" in notes
    assert "### Fixes" in notes
    assert "### Documentation" in notes
    assert "feat(api): add endpoint" in notes
    assert "fix(db): handle null" in notes
    assert "chore: tidy" in notes  # falls into Other, never dropped


def test_dry_run_publishes_nothing(monkeypatch):
    mod = _load()
    seen: list[list[str]] = []

    def fake_run(cmd, timeout=120):
        seen.append(cmd)
        if cmd == ["gh", "--version"]:
            return 0, "gh version 2.98.0", ""
        if cmd[:2] == ["gh", "auth"]:
            return 0, "logged in", ""
        if cmd[:3] == ["gh", "release", "list"]:
            return 0, "", ""
        if cmd[:3] == ["git", "describe", "--tags"]:
            return 0, "v9.9.9", ""
        if cmd[:2] == ["git", "tag"]:
            return 0, "v9.9.9", ""
        if cmd[:2] == ["git", "log"]:
            return 0, "feat: x", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", fake_run)
    rc = mod.main(["--dry-run"])

    assert rc == 0
    assert not [c for c in seen if c[:3] == ["gh", "release", "create"]]
