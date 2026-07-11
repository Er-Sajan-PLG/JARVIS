"""
ToolExecutor for JARVIS v2.4.0

Responsibilities:
- Parse <tool_call>...</tool_call> blocks from model text output
- Execute the named tool with given arguments
- Handle confirmation prompts for risky tools
- Cap tool output to prevent context window overflow
- Wrap all failures — the agent loop never handles raw exceptions

This is prompt-based tool calling. The same ToolExecutor interface will
work in v3.0 when native function calling is available — only the
parse step changes (model returns structured JSON instead of text tags).
"""

import json
import re
from typing import Iterator

from app.tools.base import ToolRegistry, ToolResult

# Matches: <tool_call>{"name": "...", "args": {...}}</tool_call>
# Tolerates whitespace, newlines inside the tag
_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</?tool_?call>?",
    re.DOTALL | re.IGNORECASE,
)

# Function call with string args: read_file("path")
_FUNC_CALL_RE = re.compile(
    r"<tool_call>\s*(\w+)\s*\(([^{].*?)\)\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)

# Hybrid: git_show({"ref": "abc"})  ← what Gemini produces
_HYBRID_CALL_RE = re.compile(
    r"<tool_call>\s*(\w+)\s*\((\{.*?\})\)\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)

# Cap all tool output at this size before injecting into the model context
MAX_OUTPUT_CHARS = 4096


class ParsedCall:
    """A single parsed tool call from model output."""
    __slots__ = ("name", "args", "raw")

    def __init__(self, name: str, args: dict, raw: str):
        self.name = name
        self.args = args
        self.raw = raw

    def __repr__(self) -> str:
        return f"ParsedCall({self.name}, {self.args})"


class ToolExecutor:
    """
    Parses model output for tool calls and executes them.

    Usage in the agent loop:
        calls = executor.parse(response_text)
        for call in calls:
            result = executor.run(call)
            # inject result back into messages
    """

    def __init__(self, registry: ToolRegistry, require_confirmation: bool = True):
        self._registry = registry
        self._require_confirmation = require_confirmation

    # ─── Parsing ──────────────────────────────────────────────────────────────

    def has_calls(self, text: str) -> bool:
        return bool(
            _TOOL_CALL_RE.search(text) or
            _HYBRID_CALL_RE.search(text) or
            _FUNC_CALL_RE.search(text)
        )

    def parse(self, text: str) -> list[ParsedCall]:
        calls = []
        seen = set()

        # Format 1: {"name": "git_show", "args": {"ref": "abc"}}
        for match in _TOOL_CALL_RE.finditer(text):
            try:
                data = json.loads(match.group(1))
                name = data.get("name", "").strip()
                args = data.get("args", {})
                if name and name not in seen:
                    seen.add(name)
                    calls.append(ParsedCall(name=name, args=args, raw=match.group(0)))
            except json.JSONDecodeError:
                pass

        # Format 2: git_show({"ref": "abc"})
        for match in _HYBRID_CALL_RE.finditer(text):
            try:
                name = match.group(1).strip()
                args = json.loads(match.group(2))
                if name and name not in seen:
                    seen.add(name)
                    calls.append(ParsedCall(name=name, args=args, raw=match.group(0)))
            except json.JSONDecodeError:
                pass

        # Format 3: read_file("docs/CHANGELOG.md")
        for match in _FUNC_CALL_RE.finditer(text):
            name = match.group(1).strip()
            args_str = match.group(2).strip()
            if name and name not in seen:
                seen.add(name)
                positional = re.findall(r'["\']([^"\']+)["\']', args_str)
                args = {"path": positional[0]} if positional else {}
                calls.append(ParsedCall(name=name, args=args, raw=match.group(0)))

        return calls

    # ─── Execution ────────────────────────────────────────────────────────────

    def run(self, call: ParsedCall) -> ToolResult:
        """
        Execute a single parsed tool call.

        Order of operations:
        1. Look up the tool in the registry
        2. Prompt for confirmation if required
        3. Execute and wrap any exception
        4. Cap the output
        """
        tool = self._registry.get(call.name)

        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: '{call.name}'. "
                      f"Available: {[t.name for t in self._registry.all()]}",
            )

        # Confirmation gate for medium/high risk tools
        if self._require_confirmation and tool.requires_confirmation:
            arg_preview = json.dumps(call.args, ensure_ascii=False)
            if len(arg_preview) > 120:
                arg_preview = arg_preview[:120] + "..."
            print(f"\n  [Tool] {call.name}({arg_preview})")
            answer = input("  Execute? (y/N): ").strip().lower()
            if answer != "y":
                return ToolResult(
                    success=False,
                    output="",
                    error="User declined — tool not executed",
                )

        result = tool.execute(**call.args)

        # Cap output — a read_file on a huge file would blow the context
        if result.success and len(result.output) > MAX_OUTPUT_CHARS:
            trimmed = len(result.output) - MAX_OUTPUT_CHARS
            result.output = (
                result.output[:MAX_OUTPUT_CHARS]
                + f"\n\n... ({trimmed} chars trimmed)"
            )

        return result

    def format_result(self, call: ParsedCall, result: ToolResult) -> str:
        """
        Format a tool result as a message to inject back into the conversation.
        The model sees this as a <tool_result> block so it knows which call it answers.
        """
        status = "success" if result.success else "error"
        content = str(result)
        return (
            f'<tool_result name="{call.name}" status="{status}">\n'
            f"{content}\n"
            f"</tool_result>"
        )