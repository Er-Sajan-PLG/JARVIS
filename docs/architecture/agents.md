# JARVIS — Agents & Tools

> Modules: `app/agents/`, `app/tools/`. The only concrete agent is
> `DocumentationAgent` — a **mini agentic loop** using prompt-based
> `<tool_call>` parsing. The design is intentionally forward-compatible with the
> planned v3.0 full runtime (native function calling): only the parse step and
> the `model.generate()` call are expected to change.

---

## 1. Agent & Tools Overview

```mermaid
flowchart TB
    subgraph AGENT["app/agents/doc_agent.py"]
        DA["DocumentationAgent(model: ModelClient)"]
        RI["run_interactive(agent)<br/>menu: 1 changelog / 2 devlog / 3 both / 4 custom"]
    end

    subgraph TOOLS["app/tools"]
        REG["ToolRegistry<br/>register / format_for_prompt / to_openai_schemas"]
        EXE["ToolExecutor<br/>parse / run / has_calls / format_result"]
        BASE["ToolDefinition + ToolResult<br/>(OpenAI-compatible schema)"]
    end

    subgraph IMPL["Tool implementations"]
        GIT["GIT_TOOLS<br/>git_log / git_diff_stat / git_diff_full / git_show / git_tags"]
        FILE["FILE_TOOLS<br/>read_file / write_file"]
    end

    subgraph EXT["External"]
        REPO["Local Git repo"]
        DOCS["docs/CHANGELOG.md · docs/DEVLOG.md"]
    end

    DA --> REG
    DA --> EXE
    REG --> BASE
    EXE --> BASE
    REG --> GIT
    REG --> FILE
    EXE --> GIT
    EXE --> FILE
    GIT --> REPO
    FILE --> DOCS
    RI --> DA
```

> `append_file` is defined in `file_tools.py` but sits **dead-code inside** the
> `append_file()` function body (after its `return`), so it is **not** in
> `FILE_TOOLS`. The agent's system prompt tells the model to use `append_file`,
> but only `write_file` (overwrite) is actually registered.

---

## 2. Agentic Loop (sequence)

`DocumentationAgent.run(task)` loops until no tool calls remain or
`MAX_ITERATIONS = 12` is hit.

```mermaid
sequenceDiagram
    participant U as User
    participant A as DocumentationAgent
    participant M as ModelClient
    participant E as ToolExecutor
    participant T as Tools (git/file)

    U->>A: run(task)
    A->>A: build system (registry.format_for_prompt) + user(task)
    loop up to 12 iterations
        A->>M: generate(messages)  [non-streaming]
        M-->>A: response.content
        A->>E: has_calls(text)?
        alt no tool calls
            E-->>A: false
            A-->>U: return text (done)
        else tool calls present
            A->>E: parse(text) -> list[ParsedCall]
            A->>A: append assistant message
            loop each call
                A->>E: run(call)
                E->>T: tool.execute(**args)
                T-->>E: ToolResult (success/error)
                E-->>A: format_result -> tool_result block
            end
            A->>A: append tool_result user message
        end
    end
```

---

## 3. ToolExecutor Parse/Run

`ToolExecutor` (`app/tools/executor.py`) understands three `<tool_call>` formats
and wraps every failure.

```mermaid
flowchart TB
    TXT["model output text"] --> HC{"has_calls?"}
    HC -->|"no"| DONE["agent finished"]
    HC -->|"yes"| PARSE["parse()<br/>3 regex formats:<br/>{json} / name({json}) / name('str')"]
    PARSE --> DEDUP["dedupe by tool name (seen set)"]
    DEDUP --> LOOP["for each ParsedCall"]
    LOOP --> LOOKUP{"tool in registry?"}
    LOOKUP -->|"no"| UNK["ToolResult(success=False,<br/>'Unknown tool')"]
    LOOKUP -->|"yes"| CONF{"requires_confirmation<br/>and enabled?"}
    CONF -->|"yes"| ASK["input('Execute? (y/N)')"]
    ASK -->|"not y"| DECL["ToolResult(success=False,<br/>'User declined')"]
    ASK -->|"y"| EXEC["tool.execute(**args)"]
    CONF -->|"no"| EXEC
    EXEC --> WRAP["wrap exception -> ToolResult"]
    WRAP --> CAP["cap output at 4096 chars"]
    CAP --> RET["ToolResult"]
```

---

## 4. Tool Safety Model (v2.4)

Blast radius is enforced **inside** the tool functions, not by the caller.

```mermaid
flowchart LR
    subgraph READ["ALLOWED_READ"]
        R1["docs/CHANGELOG.md"]
        R2["docs/DEVLOG.md"]
        R3["README.md / config.yaml / etc."]
    end
    subgraph WRITE["ALLOWED_WRITE"]
        W1["docs/CHANGELOG.md"]
        W2["CHANGELOG.md / DEVLOG.md"]
    end
    RF["read_file(path)"] -->|"not in ALLOWED_READ"| PERM["PermissionError"]
    WF["write_file(path, content)"] -->|"not in ALLOWED_WRITE"| PERM
    RF -->|"allowed + missing"| PLACE["'(file not found)' placeholder"]
```

| Tool | risk_level | requires_confirmation |
|------|-----------|------------------------|
| `git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags` | none | no |
| `read_file` | low | no |
| `write_file` | medium | **yes** |

> `git_branch` and `git_status` exist as functions but are **not** in `GIT_TOOLS`,
> so the agent cannot call them. Git diff output is additionally capped at 8000
> chars inside the git tools.
