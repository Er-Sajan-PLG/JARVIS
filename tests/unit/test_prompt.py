"""Unit tests for app/prompt/loader.py (PromptLoader)."""

import time
from pathlib import Path

import pytest

from app.prompt.loader import PromptLoader


def test_prompt_loader_missing_template(tmp_path: Path) -> None:
    loader = PromptLoader(prompts_dir=tmp_path)
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.get_template("non_existent.md")
    assert "Prompt template missing" in str(exc_info.value)


def test_prompt_loader_render_and_cache(tmp_path: Path) -> None:
    prompt_file = tmp_path / "greeting.md"
    prompt_file.write_text("Hello {{ name }}, welcome to {{ place }}!", encoding="utf-8")

    loader = PromptLoader(prompts_dir=tmp_path)

    # First load
    t1 = loader.get_template("greeting.md")
    assert "greeting.md" in loader._cache

    # Second load hits cache
    t2 = loader.get_template("greeting.md")
    assert t1 is t2

    # Render
    result = loader.render("greeting.md", name="Alice", place="Wonderland")
    assert result == "Hello Alice, welcome to Wonderland!"


def test_prompt_loader_mtime_invalidation(tmp_path: Path) -> None:
    prompt_file = tmp_path / "dynamic.md"
    prompt_file.write_text("Version 1: {{ val }}", encoding="utf-8")

    loader = PromptLoader(prompts_dir=tmp_path)
    t1 = loader.get_template("dynamic.md")
    assert loader.render("dynamic.md", val="A") == "Version 1: A"

    # Update template file with new content and bumped mtime
    time.sleep(0.01)
    new_mtime = prompt_file.stat().st_mtime + 2.0
    prompt_file.write_text("Version 2: {{ val }}", encoding="utf-8")
    import os

    os.utime(prompt_file, (new_mtime, new_mtime))

    t2 = loader.get_template("dynamic.md")
    assert t2 is not t1
    assert loader.render("dynamic.md", val="B") == "Version 2: B"


def test_prompt_loader_get_required_variables(tmp_path: Path) -> None:
    prompt_file = tmp_path / "complex.md"
    content = """
    {% for item in items %}
      {{ item }}
    {% endfor %}
    {% if flag %}
      {{ special_value }}
    {% endif %}
    Constant text
    """
    prompt_file.write_text(content, encoding="utf-8")

    loader = PromptLoader(prompts_dir=tmp_path)
    vars_found = loader.get_required_variables("complex.md")

    assert "items" in vars_found
    assert "flag" in vars_found
    assert "special_value" in vars_found


def test_prompt_loader_default_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    PromptLoader()
    assert (tmp_path / "prompts").is_dir()
