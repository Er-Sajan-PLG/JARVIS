"""
Tool infrastructure for JARVIS

Three classes:
- ToolResult:     what a tool returns (success/failure + output)
- ToolDefinition: a tool's metadata + handler + schema
- ToolRegistry:   holds all registered tools, formats them for the model

Designed to support future agent runtime expansions.
The schema format is already OpenAI function-calling compatible.
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ToolResult:
    """
    What every tool returns — success or failure, never an exception.
    The executor catches exceptions and wraps them here.
    The agent loop never has to handle raw exceptions from tools.
    """

    success: bool
    output: str
    error: str = ""

    def __str__(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error}"

    def __bool__(self) -> bool:
        return self.success


@dataclass
class ToolDefinition:
    """
    Everything the system needs to know about a tool:
    - What to tell the model (description, schema)
    - How to call it (handler)
    - Whether to be careful with it (risk_level, requires_confirmation)

    risk_level:
        "none"   — read-only, no side effects (git_log, git_diff)
        "low"    — reads files, no modifications (read_file)
        "medium" — writes files or external state (write_file)
        "high"   — executes code or shell commands (run_python) — v3.0+
    """

    name: str
    description: str
    parameters: dict  # JSON Schema for parameters
    handler: Callable
    risk_level: str = "low"
    requires_confirmation: bool = False

    def execute(self, **kwargs) -> ToolResult:
        """Call the handler, wrapping any exception into ToolResult."""
        try:
            result = self.handler(**kwargs)
            return ToolResult(success=True, output=str(result))
        except PermissionError as e:
            return ToolResult(success=False, output="", error=f"Permission denied: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def to_openai_schema(self) -> dict:
        """
        OpenAI-compatible tool schema.
        Ready to pass directly to model.generate(tools=[...]) in v3.0
        when native function calling is available.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """
    Holds all registered tools.
    Provides two views:
    - to_openai_schemas(): for native function calling (v3.0)
    - format_for_prompt(): for prompt-based tool calling (v2.4, current)
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: list[ToolDefinition]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def to_openai_schemas(self) -> list[dict]:
        """For v3.0 native function calling."""
        return [t.to_openai_schema() for t in self._tools.values()]

    def format_for_prompt(self) -> str:
        """
        Human-readable tool list for prompt-based calling (current approach).
        Injected into the agent's system prompt.
        """
        lines = ["Available tools:"]
        for tool in self._tools.values():
            props = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])
            params = []
            for k, v in props.items():
                type_str = v.get("type", "any")
                default = v.get("default", None)
                req = (
                    ""
                    if k in required
                    else f" = {default}"
                    if default is not None
                    else " (optional)"
                )
                params.append(f"{k}: {type_str}{req}")
            param_str = ", ".join(params)
            risk = f" [{tool.risk_level} risk]" if tool.risk_level not in ("none", "low") else ""
            lines.append(f"  {tool.name}({param_str}){risk}")
            lines.append(f"    → {tool.description}")
        return "\n".join(lines)
