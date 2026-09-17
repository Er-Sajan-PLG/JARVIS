"""
Documentation Agent for JARVIS

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

from app.models.client import ModelClient
from app.tools.base import ToolRegistry
from app.tools.executor import ToolExecutor
from app.tools.file_tools import FILE_TOOLS
from app.tools.git_tools import GIT_TOOLS

# ─── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are JARVIS's documentation agent. Your job is to generate accurate,
well-structured CHANGELOG and DEVLOG entries for the JARVIS project.

You are reading JARVIS's own history. Write entries that JARVIS itself
can read later to understand its own evolution.

{tools_section}

TOOL CALL FORMAT — output EXACTLY this, one call per line:
<tool_call>{{"name": "tool_name", "args": {{"param": "value"}}}}</tool_call>

Wait for each tool result before making the next call.
Never call a tool inside prose. Never skip waiting for results.

ENTRY FORMAT RULES:
- CHANGELOG: What changed and why it matters.
  Sections: Added, Changed, Fixed, Known Issues.
  Be specific: "Added token-by-token streaming via on_token callback — made
  stream/on_token explicit named params to prevent kwarg leakage into OpenAI client"
  is good. "Added streaming" is not.
- DEVLOG: Why decisions were made.
  Cover: the problem, options considered, decision taken, trade-off accepted.
  Written for two readers: the developer AND JARVIS reading its own history later.
- Every bug found belongs in the entry, even bugs introduced in that same release.
- Use append_file to add entries. Never use write_file on existing docs.

FILE WRITING RULES:
- append_file → adds new content at end of existing file. Use this always.
- write_file  → overwrites entire file. Never use on existing docs.
- Always confirm the file exists with read_file before appending.

WORKFLOW FOR FULL HISTORY:
1. git_log(n=30)                          → get all commits, newest first
2. Work oldest to newest — commits are at the BOTTOM of git_log output
3. For each commit: git_show(ref=<hash>)  → see exactly what changed
4. read_file("docs/CHANGELOG_recovered.md") → early version notes (v0.1-v0.8)
5. read_file("docs/DEVLOG_recovered.md")    → early decision context
6. read_file("docs/CHANGELOG.md")           → learn current format
7. read_file("docs/DEVLOG.md")              → learn current format
8. Generate entries for each version
9. append_file("docs/CHANGELOG.md", ...)    → append, never overwrite
10. append_file("docs/DEVLOG.md", ...)      → append, never overwrite

VERSIONING NOTES:
- Early versions: 2-digit format (v0.1, v0.2, v0.3...)
- 3-digit format started at v2.0.0
- Jump from v1.x to v2.0.0 was a complete architecture rewrite
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
            require_confirmation=True,  # always confirm writes
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
            {"role": "user", "content": task},
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
            messages.append(
                {
                    "role": "user",
                    "content": "\n\n".join(result_blocks),
                }
            )

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
        "Document JARVIS complete history from first commit to now. "
        "FIRST call git_log with n=30 to get ALL commits. "
        "Then work from OLDEST commit (bottom of list) to newest. "
        "Call git_show for EACH commit hash individually. "
        "Call read_file on docs/CHANGELOG_recovered.md and docs/DEVLOG_recovered.md for early context. "
        "Write a CHANGELOG entry for every version found. "
        "Write a DEVLOG entry for every version found. "
        "Use append_file for both files. "
        "Do not stop until entries are written for ALL commits.",
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
