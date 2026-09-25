"""Tests for the autonomous documentation system (Layer 1+2 + manifest)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_SCRIPTS = REPO_ROOT / "scripts" / "docs"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_manifest = _load("test_docs_manifest", DOCS_SCRIPTS / "manifest-validate.py")
_generate = _load("test_docs_generate", DOCS_SCRIPTS / "generate.py")
_check_full = _load("test_docs_check_full", DOCS_SCRIPTS / "check-full.py")


def test_manifest_covers_whole_tree() -> None:
    assert _manifest.validate() == []


def test_manifest_expected_docs_nonempty() -> None:
    docs = _manifest.expected_docs()
    assert len(docs) > 100
    assert "docs/TOOLS.md" in docs
    assert "app/modes/README.md" in docs


def test_generate_is_deterministic_and_clean() -> None:
    assert _generate.targets() == _generate.targets()
    assert _generate.check_all() == []


def test_snippet_checker_catches_syntax_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("# T\n\n```python\ndef broken(:\n```\n", encoding="utf-8")
    errors: list[str] = []
    _check_full.check_snippets(bad, errors)
    assert len(errors) == 1
    assert "bad.md" in errors[0]

    good = tmp_path / "good.md"
    good.write_text("# T\n\n```python\nawait fetch(url)\n```\n", encoding="utf-8")
    errors.clear()
    _check_full.check_snippets(good, errors)
    assert errors == []


def test_spelling_checker_flags_typo(tmp_path: Path) -> None:
    doc = tmp_path / "typo.md"
    doc.write_text("# T\n\nTeh quick brown fox.\n", encoding="utf-8")
    errors: list[str] = []
    _check_full.check_spelling(doc, errors)
    assert len(errors) == 1
    assert "Teh" in errors[0]
