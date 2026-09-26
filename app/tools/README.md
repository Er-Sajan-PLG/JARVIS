# app/tools

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Tools Package. | — |
| `base.py` | Tool infrastructure for JARVIS | `ToolDefinition`, `ToolRegistry`, `ToolResult` |
| `comms_tools.py` | Comms tools for the ExecutionRunner: email, notifications, brief. | `_dump()`, `comms_brief()`, `comms_notify()`, `comms_read_emails()`, `comms_reply_email()`, `comms_search_emails()`, `comms_send_email()` |
| `executor.py` | ToolExecutor for JARVIS | `ParsedCall`, `ToolExecutor` |
| `file_tools.py` | File tools for JARVIS Documentation Agent. | `_require_allowed()`, `append_file()`, `create_directory()`, `list_dir()`, `read_file()`, `write_file()` |
| `git_tools.py` | Git tools for JARVIS Documentation Agent (v2.4.0) | `_run_git()`, `git_diff_full()`, `git_diff_stat()`, `git_log()`, `git_show()`, `git_status()`, `git_tags()` |
| `subagent_tools.py` | Sub-agent runner: JARVIS spawns OpenCode workers and collects receipts. | `_parse_events()`, `_resolve_workdir()`, `_run_plain()`, `_spawn_worker_inner()`, `spawn_subagent()`, `spawn_worker()` |
| `web_search_tool.py` | Web-search runner tool (Migration Plan Step 2). | `_excerpt()`, `_format_results()`, `web_search()` |
| `workspace_tools.py` | Workspace-scoped file tools for the ExecutionRunner. | `_allowed_roots()`, `_check_sandbox()`, `_resolve()`, `_workspace_root()`, `workspace_append_file()`, `workspace_create_directory()`, `workspace_list_dir()`, `workspace_read_file()` |

<!-- generated:module_readmes end -->
