"""mtime-Cached Prompt Loader & Jinja2 Template Engine.

Loads externalized prompt templates from /prompts/*.md and caches compiled templates
by file modification timestamp (mtime), ensuring live hot-reloading without server restarts.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.meta import find_undeclared_variables

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loader and manager for externalized Jinja2 prompt templates."""

    def __init__(self, prompts_dir: str | Path = "prompts") -> None:
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._cache: dict[str, tuple[float, Template]] = {}

    def get_template(self, template_name: str) -> Template:
        """Retrieve a compiled Jinja2 template, refreshing cache if mtime changed.

        Args:
            template_name: Filename of template (e.g. 'system_base.md').

        Returns:
            Jinja2 Template instance.

        Raises:
            FileNotFoundError: If template file does not exist.
        """
        file_path = self.prompts_dir / template_name
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template missing: {file_path}")

        mtime = file_path.stat().st_mtime
        if template_name in self._cache:
            cached_mtime, cached_template = self._cache[template_name]
            if cached_mtime == mtime:
                return cached_template

        logger.info("Loading/refreshing prompt template: %s (mtime: %f)", template_name, mtime)
        template = self._env.get_template(template_name)
        self._cache[template_name] = (mtime, template)
        return template

    def get_required_variables(self, template_name: str) -> set[str]:
        """Extract set of required template variables from template source code.

        Args:
            template_name: Filename of template.

        Returns:
            Set of variable name strings required by template.
        """
        file_path = self.prompts_dir / template_name
        source = file_path.read_text(encoding="utf-8")
        parsed_content = self._env.parse(source)
        return find_undeclared_variables(parsed_content)

    def render(self, template_name: str, **kwargs: str | int | float | bool | list[str] | dict[str, str]) -> str:
        """Render prompt template with keyword arguments.

        Args:
            template_name: Filename of template.
            **kwargs: Template context variables.

        Returns:
            Rendered prompt string.
        """
        template = self.get_template(template_name)
        return template.render(**kwargs)
