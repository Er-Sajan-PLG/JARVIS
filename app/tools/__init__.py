"""JARVIS Tools Package.

Provides atomic tool definitions and execution functions wrapped with @safety_gate policy
enforcement.

``DEFAULT_TOOLSET`` is the composition-root wiring table (ADR-011): the ExecutionRunner
executes tools *by name*, so ``app.bootstrap`` registers this mapping at boot. Without
it every plan step reported COMPLETED without executing anything (RISK-014).
"""

from collections.abc import Callable

from app.tools.file_tools import (
    append_file,
    create_directory,
    list_dir,
    read_file,
    write_file,
)
from app.tools.git_tools import git_diff_full, git_diff_stat, git_log

DEFAULT_TOOLSET: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "create_directory": create_directory,
    "list_dir": list_dir,
    "git_log": git_log,
    "git_diff_stat": git_diff_stat,
    "git_diff_full": git_diff_full,
}

__all__ = [
    "DEFAULT_TOOLSET",
    "append_file",
    "create_directory",
    "git_diff_full",
    "git_diff_stat",
    "git_log",
    "list_dir",
    "read_file",
    "write_file",
]
