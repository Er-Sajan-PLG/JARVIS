# JARVIS — Model Layer & Routing

> Module: `app/models/`. The model layer's central contract is the
> `ModelClient` Protocol. Every concrete client (`LlamaCppClient`,
> `OllamaClient`, `OpenRouterClient`, `GoogleClient`) is interchangeable — the
> router cannot tell local from cloud.

---

## 1. Model Layer Overview

```mermaid
flowchart TB
    subgraph CONTRACT["Contract"]
        PROTO["ModelClient Protocol<br/>generate(messages, stream, on_token, **kwargs)<br/>-> ModelResponse"]
        RESP["ModelResponse<br/>content / model / tokens_used / finish_reason"]
    end

    subgraph ROUTING["Routing"]
        SW["ModelSwitcher<br/>active profile + clients cache"]
        ROUTER["ModelRouter<br/>route(prompt) -> (client, TaskType)"]
        TASK["TaskType enum<br/>AUTOCOMPLETE / CODE / REASONING / STEM / GENERAL / DOCS"]
        FACT["create_client()<br/>backend dispatch by ModelConfig"]
    end

    subgraph CLIENTS["Implementations"]
        LCPP["LlamaCppClient"]
        OLL["OllamaClient"]
        ORR["OpenRouterClient"]
        GC["GoogleClient"]
    end

    subgraph EXT["Providers"]
        LS["llama.cpp server (:8080/v1)"]
        OS["Ollama server (:11434)"]
        CR["Cloud API (OpenRouter/xAI/Google)"]
    end

    PROTO --> LCPP
    PROTO --> OLL
    PROTO --> ORR
    PROTO --> GC
    LCPP --> RESP
    OLL --> RESP
    ORR --> RESP
    GC --> RESP

    SW --> ROUTER
    SW --> FACT
    ROUTER --> TASK
    FACT -->|"llamacpp"| LCPP
    FACT -->|"ollama"| OLL
    FACT -->|"openrouter"| ORR
    FACT -->|"google"| GC

    LCPP --> LS
    OLL --> OS
    ORR --> CR
    GC --> CR
```

---

## 2. Factory Dispatch

`create_client(config: ModelConfig)` (`app/models/factory.py`) picks a client
from the `backend` field.

```mermaid
flowchart TD
    CFG["ModelConfig<br/>{name, role, backend, base_url, api_key}"] --> RESOLVE["_resolve_key(api_key)<br/>'env:VAR' -> os.environ['VAR']"]
    RESOLVE --> B{"backend?"}
    B -->|"ollama"| OLL["OllamaClient<br/>OllamaClient(host=base_url)"]
    B -->|"openrouter"| ORR["OpenRouterClient<br/>OpenAI(base_url=openrouter.ai/api/v1)"]
    B -->|"llamacpp (default)"| LCPP["LlamaCppClient<br/>OpenAI(base_url=/v1)"]
    OLL --> OUT["ModelClient"]
    ORR --> OUT
    LCPP --> OUT
```

> Google Gemini is handled by a dedicated `GoogleClient`
> (`app/models/google_client.py`), selected via `backend: "google"`.

---

## 3. Router Classification

`ModelRouter.route(prompt)` classifies the prompt into a `TaskType`, then
returns the registered client. Classification is **score-based** (not
first-match) to avoid order bias.

```mermaid
flowchart TD
    P["route(prompt)"] --> CL["_classify_prompt(prompt)"]
    CL --> SCORE["score each TaskType by keyword overlap<br/>CODE / STEM / REASONING"]
    SCORE --> MAX{"max score == 0?"}
    MAX -->|"yes"| GEN["TaskType.GENERAL"]
    MAX -->|"no"| TIE{"single top type?"}
    TIE -->|"yes"| WIN["that type"]
    TIE -->|"tie"| PREF["prefer CODE > STEM > REASONING"]
    GEN --> SEL["select(task_type)"]
    WIN --> SEL
    PREF --> SEL
    SEL --> OUT{"client found?"}
    OUT -->|"yes"| C["ModelClient"]
    OUT -->|"no default"| ERR["ValueError"]
```

> `KEYWORDS` only defines `CODE` / `STEM` / `REASONING`. `GENERAL`, `DOCS`, and
> `AUTOCOMPLETE` are only reachable via explicit profile mapping — auto-route
> never selects them.

---

## 4. Switcher Profiles

`ModelSwitcher` (`app/models/switcher.py`) builds one `ModelRouter` per profile
from the `Settings.profiles` mapping (role -> model key).

```mermaid
flowchart TB
    SET["Settings.profiles"] --> LOC["local: general->g, code->c, reasoning->r, docs->d, stem->r"]
    SET --> CLO["cloud: all roles -> cloud key"]
    LOC --> BUILD["_build_router(mapping)"]
    CLO --> BUILD
    BUILD --> REG["router.register(TaskType(role), client)"]
    REG --> DEF["router.set_default(general client)"]
    DEF --> ACTIVE["switcher.active_profile<br/>(switcher.router -> ModelRouter)"]
```

> Client load failures are caught during `__init__` (logs `⚠️ Could not load` via `logging`)
> and startup continues. Switching to a profile with no loaded models yields a
> router that raises `ValueError` on `route()`.

---

## 5. Client Transport (generate)

`LlamaCppClient`, `OllamaClient`, and `OpenRouterClient` implement the same
`generate()` shape over an OpenAI-compatible API. `GoogleClient` uses the Gemini
REST API but exposes the identical `generate()` signature. In all cases `stream`
and `on_token` are consumed by the client; `**kwargs` are forwarded.

```mermaid
sequenceDiagram
    participant R as Router/Switcher
    participant C as ModelClient
    participant P as Provider API

    R->>C: generate(messages, stream=True, on_token, **kwargs)
    alt streaming
        C->>P: chat.completions.create(stream=True)
        loop each chunk
            P-->>C: delta.content
            C->>R: on_token(delta)
        end
        C-->>R: ModelResponse(content, model)  (tokens_used=None)
    else non-streaming
        C->>P: chat.completions.create(stream=False)
        P-->>C: choice.message.content + usage
        C-->>R: ModelResponse(content, model, tokens_used, finish_reason)
    end
```

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
f9fa068|Er Sajan PLG|2026-07-18 18:05:40 +0545|feat: add web UI, FastAPI server, and fix batch of issues
1cab1b1|Er Sajan PLG|2026-07-13 08:12:24 +0545|mermaid added in docs/architecture and mermaid dependencies
```

Notes: This log was generated from the repository history for `docs/architecture/models.md`.
