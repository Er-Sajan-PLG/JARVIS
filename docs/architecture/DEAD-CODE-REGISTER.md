# Dead-Code Register: Subsystems With No Production Call Site

**Status**: ACTIVE
**Type**: register
**Last Updated**: 2026-09-30

> Drift trap for this type: Rows are added and never re-reviewed, so it becomes a
> list of things that were true once, presented as things that are true now.

**Source**: `tests/unit/test_dead_code_register.py` at HEAD. Every row is
verified by that test — it re-derives each component's call sites from the AST on
every run, so a row that stops being true turns the build red rather than going
quietly stale.

---

## Purpose

Four subsystems in `app/` are fully implemented, tested, and **reachable from
nothing the application runs**. They are recorded here because the reason they
survived is the same in every case, and it is not laziness:

> A component with no production call site cannot fail in production. Its tests
> can only assert what their own fixtures set up, so they confirm any interface
> the author believed in — including one that does not exist.

The clearest instance: `ModelSwitcher` called `router.register(...)` and
`router.set_default(...)` on a `ModelRouter` that has never had either method.
Twelve call sites, all raising `AttributeError`, swallowed by a blanket
`except Exception`. Thirty-three tests patched `ModelRouter`, where `MagicMock`
invents any method on first access, so the suite asserted against an interface
that has never existed. It was found by asking *who calls this*, not by a test
going red (ADR-019).

This register exists so the fifth one is found by asking that question once,
deliberately, rather than by accident.

---

## Rules

1. **A row means "no call site", not "no value".** `ModelRouter` is abandoned and
   should probably be deleted. `ModelSwitcher` is correct, tested code that is one
   bootstrap line away from working. The register does not judge which.

2. **Rows are re-derived, not trusted.** `tests/unit/test_dead_code_register.py`
   walks `app/`, `scripts/` and `n8n/` with the AST and asserts zero
   `ClassName(...)` calls for each row. `legacy/` is deliberately excluded: it is
   retired, `app/` does not import it, and a construction there makes nothing
   reachable.

3. **Wiring a component is a green failure.** If a row gains a production call
   site, the test fails and names the line. That is the task completing, not the
   build breaking. Remove the row, then correct any ADR that recorded it as
   unreachable.

4. **Do not generalise the scan.** A "classes never called" sweep of `app/` returns
   **53 of 196** public classes and is unusable: enums, dataclasses, `Protocol`s,
   ABCs and settings classes are all correctly never constructed. The register is
   a hand-curated list behind a mechanical check, which is the only version that
   carries signal.

5. **The tests are not the evidence of health.** Each row has passing tests. Rule
   2 of this document's own drift check asserts they still do, because "has tests"
   is exactly what made these four look fine.

---

## Register

| Component | Module | Reachable from | What would make it live | Recorded in |
|---|---|---|---|---|
| `DocumentationAgent` | `app/agents/doc_agent.py` | tests only | a `docs` command in `main.py` | `docs/AGENTS.md` |
| `MCPClientManager` | `app/integrations/mcp/manager.py` | tests only | a bootstrap wiring that constructs the MCP client mesh | this row |
| `MCPServer` | `app/mcp/registry.py` | tests only | tool registration exposing MCP servers to the brain | this row |
| `ModelSwitcher` | `app/models/switcher.py` | `legacy/`, tests | replacing the retired `legacy/` entry points | ADR-019 |

### Detail

**`DocumentationAgent`** — `app/agents/doc_agent.py`. A prompt-based agentic loop
with a 9-tool registry, a file allowlist and a 12-iteration cap. Nothing in `app/`
imports `app.agents`; the only production mention is prose in a
`app/tools/workspace_tools.py` docstring. `run_interactive` is called only from
`tests/unit/test_agents.py`. `main.py` has no `docs` command. The documented
lifecycle in `docs/AGENTS.md` cited a `main.py` construction that does not exist,
and listed it as "AI Verified"; that claim is withdrawn there.

**`MCPClientManager`** and **`MCPServer`** — `app/integrations/mcp/` and
`app/mcp/`. Client manager, transports, registry, server and types, with four test
files. Nothing outside the two packages imports them, and neither class is
constructed under `app/`, `scripts/` or `n8n/`. AGENTS.md §7.2 lists "MCP
components missing" as an open Sprint 3 gap; the components exist and are
unwired, which is a different problem from the one recorded there.

**`ModelSwitcher`** — `app/models/switcher.py`, with
`app/utils/model_selector.py` as its companion (`_startup_model_select` is called
from nowhere, and `model_selector` references `ModelSwitcher` in a docstring
only, not an import — the pair is a closed loop with no entry point). The live
model path is `container.create_model_client(config)` in
`app/adapters/web/router.py`. Constructed in `legacy/server.py:107,409` and
`legacy/web_api_server.py:111,448`, all of which are retired.

**Not registered, and why** — `ModelRouter` (`app/models/router.py`) is also
abandoned, but it is *not* in this table because the guard in
`tests/unit/test_router_call_sites.py` asserts the stronger property: nothing in
`app/` may construct it at all. That is a prohibition, not an inventory.

---

## Open question

Whether each row should be **wired** or **deleted** is a product decision this
register deliberately does not take. Deletion is not free: `DocumentationAgent`
and the MCP packages carry real tests and real behaviour, and removing them
trades a small maintenance cost for the loss of a working implementation. Wiring
is also not free: it makes previously unreachable code live, and the point of this
document is that unreachable code has not been proven by anything except its own
fixtures.
