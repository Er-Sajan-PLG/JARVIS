"""MCP Server for JARVIS — exposes the capability surface to PROFESSOR-J.

PROFESSOR-J connects as an MCP client (stdio or Streamable HTTP) and gets
access to the same JARVIS tools the cognitive loop uses: workspace ops,
git, session, memory. Every tool call is routed through the same
ToolSafetyPolicy the local loop enforces.

MCP 2.2 lowlevel API: on_list_tools / on_call_tool are constructor callbacks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.domain import SafetyTier
from app.guardrails import ToolSafetyPolicy

logger = logging.getLogger(__name__)

# Tool definitions exposed to PROFESSOR-J
_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the workspace (sandboxed to allowed roots).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace (sandboxed).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files in a workspace directory.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "create_directory",
        "description": "Create a new directory in the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "git_log",
        "description": "Show recent git log entries.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer"}},
        },
    },
    {
        "name": "git_diff_stat",
        "description": "Show git diff stat between two refs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_ref": {"type": "string"},
                "to_ref": {"type": "string"},
            },
        },
    },
    {
        "name": "git_diff_full",
        "description": "Show full git diff between two refs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_ref": {"type": "string"},
                "to_ref": {"type": "string"},
            },
        },
    },
    {
        "name": "session_get",
        "description": "Get the current session state.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
        },
    },
    {
        "name": "session_fork",
        "description": "Fork a session into a new independent session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "new_session_id": {"type": "string"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "memory_retrieve",
        "description": "Retrieve relevant memories for a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "workspace_git_state",
        "description": "Get current git state (HEAD, branch, dirty files).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


async def _on_list_tools(ctx: Any = None, params: Any = None) -> Any:
    from mcp.types import ListToolsResult, Tool

    return ListToolsResult(tools=[Tool(**t) for t in _TOOLS])


async def _on_call_tool(ctx: Any, request: Any) -> Any:
    """Execute a JARVIS tool by name, routed through ToolSafetyPolicy."""
    from mcp.types import CallToolResult, TextContent

    name = request.name
    args = request.arguments or {}

    try:
        policy = get_global_policy()
        policy.evaluate_tool_call(name, SafetyTier.SENSITIVE, args, f"MCP tool: {name}")
        result = await _dispatch(name, args)
        return CallToolResult(content=[TextContent(type="text", text=str(result))])
    except Exception as e:
        logger.error("MCP tool %s failed: %s", name, e)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            is_error=True,
        )


async def _dispatch(name: str, args: dict[str, Any]) -> str:
    """Dispatch a tool call to the correct implementation."""
    from app.tools import (
        create_directory,
        git_diff_full,
        git_diff_stat,
        git_log,
        list_dir,
        read_file,
        write_file,
    )

    dispatch_map = {
        "read_file": lambda: read_file(**args),
        "write_file": lambda: write_file(**args),
        "list_dir": lambda: list_dir(**args),
        "create_directory": lambda: create_directory(**args),
        "git_log": lambda: git_log(**args),
        "git_diff_stat": lambda: git_diff_stat(**args),
        "git_diff_full": lambda: git_diff_full(**args),
        "session_get": lambda: _session_get(args),
        "session_fork": lambda: _session_fork(args),
        "memory_retrieve": lambda: _memory_retrieve(args),
        "workspace_git_state": lambda: _workspace_git_state(args),
    }

    if name not in dispatch_map:
        raise ValueError(f"Unknown tool: {name}")

    result = dispatch_map[name]()
    if asyncio.iscoroutine(result):
        return await result
    return result


def _session_get(args: dict[str, Any]) -> str:
    """Get session state (sync wrapper)."""
    from app.session.manager import SessionManager
    from app.session.persistence import SessionPersistence

    mgr = SessionManager(SessionPersistence())
    session = mgr.get_or_create_session_sync(args.get("session_id", "default"))
    return (
        f"session_id={session.session_id}\n"
        f"user_id={session.user_id}\n"
        f"preferences={session.preferences}\n"
    )


def _session_fork(args: dict[str, Any]) -> str:
    """Fork a session (sync wrapper)."""
    from app.session.manager import SessionManager
    from app.session.persistence import SessionPersistence

    mgr = SessionManager(SessionPersistence())
    forked = mgr.fork_session_sync(args["session_id"], args.get("new_session_id"))
    return f"forked_session_id={forked.session_id}"


def _memory_retrieve(args: dict[str, Any]) -> str:
    """Retrieve memories (sync wrapper)."""
    from app.memory.manager import MemoryManager

    mgr = MemoryManager()
    results = mgr.retrieve(args["query"], limit=args.get("limit", 10))
    if not results:
        return "No relevant memories found."
    return "\n".join(f"- [{r.score:.2f}] {r.memory.value}" for r in results)


def _workspace_git_state(args: dict[str, Any]) -> str:
    from app.workspace.manager import WorkspaceManager

    mgr = WorkspaceManager()
    state = mgr.get_git_state()
    lines = [
        f"head={state['head']}",
        f"branch={state['branch']}",
        f"dirty={state['dirty']}",
    ]
    if state["dirty_files"]:
        lines.append("dirty_files:")
        for f in state["dirty_files"]:
            lines.append(f"  {f}")
    return "\n".join(lines)


def get_global_policy() -> ToolSafetyPolicy:
    """Get the global ToolSafetyPolicy, creating default if needed."""
    from app.guardrails.decorator import _global_policy

    if _global_policy is None:
        from app.guardrails import set_global_policy

        set_global_policy(ToolSafetyPolicy(auto_approve_sensitive=True))
    return _global_policy


def create_server() -> Any:
    """Create and return the MCP server."""
    from mcp.server.lowlevel import Server

    return Server(
        "jarvis-capability-server",
        version="1.0.0",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


async def run_stdio_server() -> None:
    """Run the MCP server over stdio."""
    from mcp.server.stdio import stdio_server

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for scripts/run_mcp_server.py."""
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
