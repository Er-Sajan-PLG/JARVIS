"""
Documentation Agent for JARVIS v2.4.0

This is JARVIS documenting its own evolution.

The agent:
1. Reads git history and diffs to understand what changed
2. Reads existing CHANGELOG.md and DEVLOG.md to learn the established format
3. Generates new entries that match the format exactly
4. Writes them to the files (with confirmation)

Architecture: mini agentic loop (prompt-based tool calling)
- Same pattern as v3.0's full agentic runtime, narrower scope
- When v3.0 ships with native function calling, only the model.generate()
  call changes — ToolExecutor, ToolRegistry, and this loop stay the same

Why prompt-based instead of waiting for v3.0 native calling:
- Not all local models support tool_calls in responses
- Prompt-based works on any model that can follow instructions
- The <tool_call> tag format is unambiguous and easy to parse
- Same interface — v3.0 upgrade is one method change in ModelClient
"""

from app.models.client import ModelClient, ModelResponse
from app.tools.base import ToolRegistry
from app.tools.executor import ToolExecutor
from app.tools.git_tools import GIT_TOOLS
from app.tools.file_tools import FILE_TOOLS


# ─── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are JARVIS's documentation agent. Your job is to generate accurate, \
well-structured CHANGELOG and DEVLOG entries for the JARVIS project.

You are reading JARVIS's own history. Write entries that JARVIS itself \
can read later to understand its own evolution.

{tools_section}

To call a tool, output EXACTLY this format on its own line:
<tool_call>{{"name": "tool_name", "args": {{"param": "value"}}}}</tool_call>

Wait for the tool result before continuing. After receiving results, \
keep reasoning until you have everything you need.

ENTRY FORMAT RULES:
- Read the existing CHANGELOG.md and DEVLOG.md FIRST to match their format exactly
- CHANGELOG: What changed and why it matters. Include: Added, Changed, Fixed, Known Issues
- DEVLOG: Why decisions were made. Cover: the problem, the options considered, \
  the decision taken, the trade-off accepted. Written for two readers: \
  the developer AND JARVIS reading its own history.
- Be specific. "Added streaming" is weak. \
  "Added token-by-token streaming via on_token callback parameter \
  — made stream/on_token explicit named params to prevent kwarg leakage into the API" is strong.
- Every bug found belongs in the entry, even bugs introduced in that same release.
- When writing files: write the COMPLETE file content, not just the new section. \
  Prepend the new version entry, keep all existing content below it.

WORKFLOW:
1. git_log(15)                          → what commits were made?
2. git_diff_stat("HEAD~N", "HEAD")      → which files changed?
3. git_diff_full("HEAD~N", "HEAD")      → what actually changed in the code?
4. read_file("docs/CHANGELOG.md")       → learn the established format
5. read_file("docs/DEVLOG.md")          → learn the established format
6. Generate the entries
7. write_file("docs/CHANGELOG.md", ...) → full file with new entry prepended
8. write_file("docs/DEVLOG.md", ...)    → full file with new entry prepended
"""

MAX_ITERATIONS = 12  # safety ceiling — should never be reached in normal use


# ─── Agent ─────────────────────────────────────────────────────────────────────

class DocumentationAgent:
    """
    Mini agentic loop for documentation generation.

    Pattern (same as v3.0 full runtime, scoped):
        while iterations < MAX:
            response = model.generate(messages)
            if no tool calls → done, return response
            parse tool calls → execute → inject results → loop
    """

    def __init__(self, model: ModelClient):
        self._model = model

        # Build registry from documentation-relevant tools only
        self._registry = ToolRegistry()
        self._registry.register_many(GIT_TOOLS)
        self._registry.register_many(FILE_TOOLS)

        self._executor = ToolExecutor(
            registry=self._registry,
            require_confirmation=True,   # always confirm writes
        )

    def run(self, task: str, verbose: bool = True) -> str:
        """
        Run the agent for a given documentation task.

        Args:
            task:    Natural language description of what to document.
            verbose: Print iteration headers and tool call status.

        Returns:
            The agent's final text response (after all tool calls complete).
        """
        tools_section = self._registry.format_for_prompt()
        system = _SYSTEM.format(tools_section=tools_section)

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": task},
        ]

        for iteration in range(1, MAX_ITERATIONS + 1):
            if verbose:
                print(f"\n  [Agent] Step {iteration}/{MAX_ITERATIONS}")

            response = self._model.generate(messages)
            text = response.content

            # No tool calls → agent has finished
            if not self._executor.has_calls(text):
                if verbose:
                    print("  [Agent] Done — no more tool calls")
                return text

            # Parse all tool calls from this response
            calls = self._executor.parse(text)

            if verbose:
                for call in calls:
                    print(f"  [Tool] → {call.name}({call.args})")

            # Add assistant message to conversation history
            messages.append({"role": "assistant", "content": text})

            # Execute all calls and collect results
            result_blocks = []
            for call in calls:
                result = self._executor.run(call)
                status = "✅" if result.success else "❌"
                preview = str(result)[:80].replace("\n", " ")
                if verbose:
                    print(f"  {status} {call.name}: {preview}...")
                result_blocks.append(self._executor.format_result(call, result))

            # Inject all results as a single user message
            messages.append({
                "role": "user",
                "content": "\n\n".join(result_blocks),
            })

        # Fell through max iterations — shouldn't happen in practice
        if verbose:
            print(f"  [Agent] Warning: reached MAX_ITERATIONS ({MAX_ITERATIONS})")
        return "[Documentation agent reached iteration limit without completing]"


# ─── Interactive entry point ───────────────────────────────────────────────────

_TASKS = {
    "1": (
        "changelog",
        "Generate a CHANGELOG.md entry for the most recent changes. "
        "Use git_log and git_diff to understand what changed. "
        "Read docs/CHANGELOG.md first to match the exact format. "
        "Write the complete updated file with the new entry prepended.",
    ),
    "2": (
        "devlog",
        "Generate a DEVLOG.md entry for the most recent changes. "
        "Focus on WHY decisions were made, what was considered, what trade-offs were accepted. "
        "Read docs/DEVLOG.md first to match the exact format and voice. "
        "Write the complete updated file with the new entry prepended.",
    ),
    "3": (
        "both",
        "Generate both a CHANGELOG.md entry and a DEVLOG.md entry for the most recent changes. "
        "Do changelog first (what changed), then devlog (why decisions were made). "
        "Read both existing files first to match their formats exactly. "
        "Write both complete updated files.",
    ),
}


def run_interactive(agent: DocumentationAgent) -> None:
    """
    Menu-driven entry point. Called from main.py when user types 'docs'.
    """
    print("\n╔══════════════════════════════╗")
    print("║   JARVIS Documentation Agent  ║")
    print("╚══════════════════════════════╝")
    print("\nWhat should I document?")
    print("  1. Changelog entry  (what changed)")
    print("  2. Devlog entry     (why decisions were made)")
    print("  3. Both")
    print("  4. Custom task")
    print("  q. Cancel\n")

    choice = input("Choice: ").strip().lower()

    if choice == "q":
        print("Cancelled.")
        return

    if choice in _TASKS:
        label, task = _TASKS[choice]
        print(f"\nRunning: {label}")
    elif choice == "4":
        task = input("Describe the task: ").strip()
        if not task:
            print("No task entered. Cancelled.")
            return
    else:
        print("Invalid choice.")
        return

    print("\n" + "─" * 50)
    final = agent.run(task, verbose=True)
    print("\n" + "─" * 50)
    print("\n[Agent summary]")
    print(final)