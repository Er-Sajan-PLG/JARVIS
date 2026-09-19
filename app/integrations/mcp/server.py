"""MCP Server for JARVIS — exposes the capability surface to the mesh.

External agents (PROFESSOR-J, OpenCode, Hermes, and any MCP client) connect
and get access to the same JARVIS tools the cognitive loop uses: workspace
ops, git, session, memory, plus (Sprint 8.5 mesh) chat, brief, notify, email
and sub-agent spawning. Every tool call is routed through the same
ToolSafetyPolicy the local loop enforces.

MCP 2.2 lowlevel API: on_list_tools / on_call_tool are constructor callbacks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import warnings
from typing import Any

# MCP stdio is JSON-only on stdout: any stray stderr/warning text corrupts the
# protocol. The `fitz` (pymupdf) deprecation warning fires on lazy import
# inside tool handlers; silence it here so a chat/brief/email call cannot
# corrupt the stdio stream.
warnings.filterwarnings("ignore", message=r".*fitz.*deprecated.*", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=r".*`fitz`.*", category=DeprecationWarning)

from app.domain import SafetyTier  # noqa: E402
from app.guardrails import ToolSafetyPolicy  # noqa: E402

logger = logging.getLogger(__name__)


def _schema(**props) -> dict:
    """Build an object JSON schema from {name: {type, ...}} props."""
    required = [k for k, v in props.items() if v.pop("required", False)]
    return {"type": "object", "properties": props, "required": required}


# Tool definitions exposed to external agents.
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
    # ── Sprint 8.5 mesh tools: external agents subcontract to JARVIS ──────────
    {
        "name": "jarvis_chat",
        "description": "Ask JARVIS a question through its chat pipeline (memory + comms context).",
        "inputSchema": _schema(
            message={"type": "string", "required": True},
            session_id={"type": "string"},
        ),
    },
    {
        "name": "jarvis_brief",
        "description": "Generate JARVIS's morning brief (memory, approvals, activity).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "jarvis_notify",
        "description": "Send a notification via push and/or telegram (comma-separated channels).",
        "inputSchema": _schema(
            title={"type": "string", "required": True},
            body={"type": "string", "required": True},
            channels={"type": "string"},
        ),
    },
    {
        "name": "jarvis_read_emails",
        "description": "Read JARVIS's email inbox (unread or a folder).",
        "inputSchema": _schema(
            limit={"type": "integer"},
            unread_only={"type": "boolean"},
        ),
    },
    {
        "name": "jarvis_send_email",
        "description": "Send an email from JARVIS.",
        "inputSchema": _schema(
            to={"type": "string", "required": True},
            subject={"type": "string", "required": True},
            body={"type": "string", "required": True},
        ),
    },
    {
        "name": "jarvis_spawn_subagent",
        "description": "Spawn an OpenCode sub-agent worker (delegation). Returns a worker receipt.",
        "inputSchema": _schema(
            goal={"type": "string", "required": True},
            agent={"type": "string"},
            workdir={"type": "string"},
            timeout_s={"type": "integer"},
        ),
    },
    {
        "name": "jarvis_spawn_worker",
        "description": "Spawn a worker on a bridged backend (opencode|hermes|deepseek).",
        "inputSchema": _schema(
            goal={"type": "string", "required": True},
            backend={"type": "string"},
            agent={"type": "string"},
            workdir={"type": "string"},
            timeout_s={"type": "integer"},
        ),
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

    # Auth: stdio has no HTTP headers, so the client must present the shared
    # key via the server environment (JARVIS_MCP_KEY). Fail closed when set
    # but missing/mismatched. Unset disables the check (local dev).
    expected = os.environ.get("JARVIS_MCP_KEY", "").strip()
    if expected:
        presented = (os.environ.get("JARVIS_API_KEY", "") or "").strip()
        if presented != expected:
            logger.error("MCP call without matching JARVIS_MCP_KEY")
            return CallToolResult(
                content=[TextContent(type="text", text="Error: unauthorized")],
                is_error=True,
            )

    try:
        policy = get_global_policy()
        policy.evaluate_tool_call(name, SafetyTier.SENSITIVE, args, f"MCP tool: {name}")
        from app.telemetry.trace_new import traced_call

        result = await traced_call(f"mcp.{name}", lambda: _dispatch(name, args))
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
        # ── Sprint 8.5 mesh ────────────────────────────────────────────────
        "jarvis_chat": lambda: _jarvis_chat(args),
        "jarvis_brief": lambda: _jarvis_brief(),
        "jarvis_notify": lambda: _jarvis_notify(args),
        "jarvis_read_emails": lambda: _jarvis_read_emails(args),
        "jarvis_send_email": lambda: _jarvis_send_email(args),
        "jarvis_spawn_subagent": lambda: _jarvis_spawn_subagent(args),
        "jarvis_spawn_worker": lambda: _jarvis_spawn_worker(args),
    }

    if name not in dispatch_map:
        raise ValueError(f"Unknown tool: {name}")

    result = dispatch_map[name]()
    if asyncio.iscoroutine(result):
        return await result
    return result


# ── Sprint 8.5 mesh handlers ───────────────────────────────────────────────────


async def _jarvis_chat(args: dict[str, Any]) -> str:
    """Route a question through JARVIS's chat pipeline."""
    from app.adapters.web.router import chat as web_chat

    result = await web_chat(
        {
            "message": args["message"],
            "session_id": args.get("session_id") or "mcp",
            "memory_enabled": True,
        }
    )
    if isinstance(result, dict):
        return result.get("response") or result.get("error") or "…"
    return str(result)


async def _jarvis_brief() -> str:
    """Generate the morning brief."""
    from app.integrations.brief import BriefConfig, BriefService

    service = BriefService(BriefConfig.from_env())
    brief = await service.generate_brief()
    return service._format_brief_text(brief)


async def _jarvis_notify(args: dict[str, Any]) -> str:
    """Send a notification via the configured channels."""
    from app.integrations.push import PushMessage, PushService

    wanted = [c.strip() for c in (args.get("channels") or "push").split(",") if c.strip()]
    results: dict[str, Any] = {}
    if "push" in wanted:
        results["push"] = await PushService().send(
            PushMessage(title=args["title"], body=args["body"])
        )
    if "telegram" in wanted:
        from app.integrations.telegram import send_message

        results["telegram"] = {"success": await send_message(f"{args['title']}\n{args['body']}")}
    return str(results)


async def _jarvis_read_emails(args: dict[str, Any]) -> str:
    """Read email, returning a compact digest."""
    from app.integrations.email.tools import summarize_unread

    return await summarize_unread(limit=args.get("limit", 10))


async def _jarvis_send_email(args: dict[str, Any]) -> str:
    """Send an email."""
    from app.integrations.email.tools import send_email

    return str(await send_email(to=args["to"], subject=args["subject"], body=args["body"]))


async def _jarvis_spawn_subagent(args: dict[str, Any]) -> str:
    """Spawn an OpenCode worker and return the receipt."""
    from app.tools.subagent_tools import spawn_subagent

    return await spawn_subagent(
        goal=args["goal"],
        agent=args.get("agent", "build"),
        workdir=args.get("workdir", "."),
        timeout_s=int(args.get("timeout_s", 600)),
    )


async def _jarvis_spawn_worker(args: dict[str, Any]) -> str:
    """Spawn a worker on any bridged backend and return the receipt."""
    from app.tools.subagent_tools import spawn_worker

    return await spawn_worker(
        goal=args["goal"],
        backend=args.get("backend", "opencode"),
        agent=args.get("agent", "build"),
        workdir=args.get("workdir", "."),
        timeout_s=int(args.get("timeout_s", 600)),
    )


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
    """Entry point for scripts/run_mcp_server.py.

    Loads the JARVIS .env so tools (email, brief, telegram) see full config
    even when the server is spawned by an MCP client that only passes the
    auth keys. Auth keys are NOT overridden here — they stay fail-closed.
    """
    from pathlib import Path

    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
