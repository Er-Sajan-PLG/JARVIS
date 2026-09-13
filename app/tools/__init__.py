"""JARVIS Tools Package.

Provides atomic tool definitions and execution functions wrapped with @safety_gate policy
enforcement.

``DEFAULT_TOOLSET`` is the composition-root wiring table (ADR-011): the ExecutionRunner
executes tools *by name*, so ``app.bootstrap`` registers this mapping at boot. Without
it every plan step reported COMPLETED without executing anything (RISK-014).

Two file-tool policies exist, deliberately (see app/tools/workspace_tools.py):

* ``app.tools.file_tools``  — the DocumentationAgent's docs-only allowlist. A model
  driving the doc agent must not be able to overwrite source code or read secrets; the
  adversarial suite pins that property.
* ``app.tools.workspace_tools`` — the generic, sandboxed primitives the ExecutionRunner
  uses (workspace root + temp dir; source/test/secret paths refused).

The names re-exported below are the *runner-facing* (workspace) ones, because this package
is the composition root for the execution runner. The doc agent imports ``file_tools``
directly and is unaffected.
"""

from collections.abc import Callable

from app.tools.git_tools import git_diff_full, git_diff_stat, git_log
from app.tools.workspace_tools import (
    WORKSPACE_TOOLS,
    workspace_append_file,
    workspace_create_directory,
    workspace_list_dir,
    workspace_read_file,
    workspace_write_file,
)

# Runner-facing surface: generic sandboxed primitives, keyed by tool name.
DEFAULT_TOOLSET: dict[str, Callable[..., str]] = {
    "read_file": workspace_read_file,
    "write_file": workspace_write_file,
    "append_file": workspace_append_file,
    "create_directory": workspace_create_directory,
    "list_dir": workspace_list_dir,
    "git_log": git_log,
    "git_diff_stat": git_diff_stat,
    "git_diff_full": git_diff_full,
}

__all__ = [
    "DEFAULT_TOOLSET",
    "WORKSPACE_TOOLS",
    "append_file",
    "create_directory",
    "git_diff_full",
    "git_diff_stat",
    "git_log",
    "list_dir",
    "read_file",
    "write_file",
]

# Plain-name aliases pointing at the generic (runner-facing) implementations, so callers
# such as `from app.tools import read_file` get sandboxed workspace behaviour.
read_file = workspace_read_file
write_file = workspace_write_file
append_file = workspace_append_file
create_directory = workspace_create_directory
list_dir = workspace_list_dir
