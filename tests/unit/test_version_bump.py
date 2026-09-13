"""Unit tests for scripts/version_bump.py — the deterministic SemVer bump.

These pin the bump-decision logic in isolation (the part that used to be a manual
human judgement), without touching the real repo's tags. They import the module
by path and monkeypatch its git surface, so they are hermetic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "version_bump.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("version_bump", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["version_bump"] = module
    spec.loader.exec_module(module)
    return module


def test_feat_means_minor():
    module = _load_module()
    assert module._classify("feat(brain): add intent analyzer") == "minor"


def test_fix_means_patch():
    module = _load_module()
    assert module._classify("fix(tools): enforce allowlist") == "patch"


def test_breaking_means_major():
    module = _load_module()
    assert module._classify("feat(api): rework the interface\n\nBREAKING CHANGE: ...") == "major"
    assert module._classify("breaking(api): drop the old route") == "major"


def test_chore_docs_not_a_bump_on_their_own():
    module = _load_module()
    # Non feat/fix/breaking commits fall through to patch in classification,
    # but the bump LEVEL is decided by the max across all commits, so a lone
    # chore commit still yields patch (it is a real code change worth a patch).
    assert module._classify("chore(deps): bump chromadb") == "patch"


def _subjects(module, *subjects):
    """Stub the commit subjects seen since the tag."""
    module._commit_subjects_since = lambda tag: list(subjects)  # noqa: E731


def test_compute_bump_minor_wins_over_patch(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "latest_tag", lambda: "v3.0.1")
    _subjects(module, "fix(a): one", "feat(b): two", "fix(c): three")

    result = module.compute_bump()
    assert result is not None
    assert result[0] == "v3.1.0"  # minor wins
    assert result[1] == "minor"


def test_compute_bump_major_wins_over_everything(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "latest_tag", lambda: "v2.5.0")
    _subjects(module, "feat(a): one", "breaking(b): big change")

    result = module.compute_bump()
    assert result is not None
    assert result[0] == "v3.0.0"
    assert result[1] == "major"


def test_compute_bump_patch_when_only_fixes(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "latest_tag", lambda: "v3.0.1")
    _subjects(module, "fix(a): one", "chore(deps): bump", "fix(b): two")

    result = module.compute_bump()
    assert result is not None
    assert result[0] == "v3.0.2"
    assert result[1] == "patch"


def test_no_commits_since_tag_returns_none(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "latest_tag", lambda: "v3.0.1")
    _subjects(module)  # empty

    assert module.compute_bump() is None
