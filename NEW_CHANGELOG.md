# NEW_CHANGELOG.md

> **Source of truth:** Git history only (`git log` / `git show`). Working-tree changes
> were intentionally ignored — this covers only the **first 26 commits**, oldest → newest.
> No direct project-file inspection was performed.
>
> **Versioning:** No Git tags exist for these commits (tags only appear later at
> `v2.0.0`, `v2.2.1`, `v2.4.0`, `v2.4.1`). The initial commit is **v0.0.0**; commits 1–10
> run v0.1.0 → v0.6.0, with the final three renumbered to **v0.6.1 / v0.6.2 / v0.6.3**
> (originally v0.7.0 / v0.8.0 / v0.9.0) by instruction. Commits 11–20:
> **v0.7.0 → v0.7.4** (Git has no version labels for 11–15 — assigned sequentially by instruction),
> then **v0.8.0** (commit 16, Git `feat(v0.8)` + `version.py` `"0.8.0"`),
> **v0.8.1** (commit 17, no Git label — user-assigned),
> **v0.9.0** (commit 18, Git DEVLOG/changelog),
> **v0.9.1** (commit 19, no Git label — user-assigned),
> **v1.1** (commit 20, Git DEVLOG/changelog/`version.py` `"v.1.1"`; this commit also authors the **v1.0.0** release notes whose code shipped in v0.9.1).
> **v1.2.0** (commit 21, no Git label — user-assigned; pre-v2.0.0 cleanup + `reasoner.py` stub).
> **v2.0.0** (commit 22, Git tag `v2.0.0` + `version.py` `"v.2.0.0"`; complete architectural overhaul).
> **v2.0.1** (commit 23, no Git label — user-assigned; v2.0.0 bug fixes + release docs).
> **v2.1.0** (commit 24, Git `version.py` `"v.2.1.0"`; Multi-Backend + Streaming + External Config).
> **v2.2.0** (commit 25, Git `version.py` `"v.2.2.0"`; Semantic Memory with chromaDB + hybrid retriever + conversation store).
> **v2.2.1** (commit 26, `HEAD` — **triple Git tag**: `v2.2.1` / `v2.4.0` / `v2.4.1`; commit message "fix: v2.2.1 — Documentation agent wired, package structure fixed". **Note:** `app/config/version.py` was NOT updated — it remains `"v.2.2.0"` at HEAD; the agent source docstrings instead reference "v2.4.0"/"v3.0". See block for the full version inconsistency).

---

## Version v0.0.0 - Initial project scaffolding
*Commit:* `1999e53` — "Initial project structure" (no parent — initial commit)

### Added
- **Repository skeleton / placeholder files** (all empty blobs in this commit):
  - `.gitignore`, `README.md`, `app/__init__.py`, `app/main.py`
  - *What:* bare tracked files establishing the repo root and the `app` Python package.
  - *Why:* lay the foundation before any real code (there is no previous version to compare against).
  - *Problem solved:* creates a version-controlled project root and an importable `app` package.
  - *How:* empty files are committed so the structure exists from commit #1.
  - *Note:* `app/main.py` is 0 bytes here; real code arrives in v0.1.0.
- **`requirements.txt`** — 117 pinned (`==`) dependencies.
  - *What:* full dependency manifest.
  - *Why:* declare the project's third-party stack up front.
  - *Problem solved:* reproducible environment.
  - *How:* exact version pins for every package.
  - Notable groups (evident from the pinned list, and later consumed by code):
    - `ollama` — local LLM client (used by `app/models/ollama_client.py` from v0.1.0)
    - `chromadb` — vector store (foundation for later semantic memory)
    - `fastapi`, `uvicorn`, `starlette` — API server (later `app/api`)
    - `torch`, `transformers`, `sentence-transformers` — ML / embedding stack
    - `pydantic`, `pydantic-settings` — config & validation (later `app/config`)
    - `PyYAML`, `typer`, `rich` — config files, CLI, terminal output

### Dependencies
- All 117 entries in `requirements.txt` are **new** in this version (full pinned list lives in the file).

### Documentation
- `README.md` exists but is empty in this commit — no content yet.

### Summary
The repo is scaffolded with an `app` package and a comprehensive dependency manifest, but contains no runnable logic yet.

### Possible Next Version
With `ollama` already declared in `requirements.txt`, v0.1.0 will most likely introduce the first runnable code that connects to a local Ollama model.

---

## Version v0.1.0 - Connect to Ollama
*Commit:* `e13ee67` — "Build Jarvis v0.1: Connect to Ollama" (parent `1999e53`)

### Added
- **`app/config/settings.py`** — central config constants:
  - `DEFAULT_MODEL = "deepseek-r1:32b"`, `OLLAMA_HOST = "http://localhost:11434"`, `APP_NAME = "Jarvis"`, `VERSION = "0.1.0"`
- **`app/models/ollama_client.py`** — `OllamaClient`:
  ```
  app/models/ollama_client.py  OllamaClient
  ├── __init__(self, model: str)
  └── ask(self, prompt: str) -> str   # single-turn call to ollama.chat
  ```
  - *What:* thin wrapper over the `ollama.chat` API.
  - *Why:* provide a single place to talk to the local model.
  - *Problem solved:* decouples the app from the Ollama SDK details.
  - *How:* builds a one-message (`user`) request and returns `response["message"]["content"]`.
- **`app/main.py`** — first runnable entry point:
  ```
  app/main.py  main()
  ├── prints a "JARVIS" banner
  ├── OllamaClient(DEFAULT_MODEL)
  └── one-shot: input("You: ") -> ask() -> print("Jarvis: ...")
  ```
- **Package directories** (each with an empty `__init__.py`): `app/agents`, `app/api`, `app/brain`, `app/config`, `app/memory`, `app/models`, `app/tools`, `app/utils` — mirroring the planned modular architecture.
- **`docs/DEVLOG.md`** — added as an empty file (content arrives in v0.2.0).

### Changed
- `app/main.py` went from empty (v0.0.0) to a working single-prompt script.

### Note (Inferred)
- This commit also adds compiled `__pycache__/*.pyc` binary artifacts. **Reason (Inferred):** the code was executed before any `.gitignore` existed (ignore rules arrive in v0.3.0). These are build artifacts, not project logic.

### Dependencies
- No changes to `requirements.txt`; the `ollama` package (already pinned in v0.0.0) is now actually imported.

### Documentation
- None new beyond the empty `DEVLOG.md` placeholder.

### Summary
JARVIS becomes runnable for the first time: a one-shot CLI that sends a single prompt to a local Ollama model. The package layout previews the future modular design.

### Possible Next Version
v0.2.0 is expected to turn the one-shot script into a continuous chat loop (matching the working-CLI-loop theme of the next commit).

---

## Version v0.2.0 - Working CLI chat loop
*Commit:* `ded44b9` — "v0.2: working CLI chat loop with Ollama integration" (parent `e13ee67`)

### Changed
- **`app/main.py`** — replaced the single `input()`/`ask()` with a persistent loop:
  ```
  app/main.py  main()
  └── while True:
        prompt = input("You: ")
        if prompt == 'quit': print("Good Bye"); break
        answer = client.ask(prompt)
        print(f"\nJarvis: {answer}")
  ```
  - *What changed:* interactive REPL-style loop instead of one-shot.
  - *Why (from Git):* commit message — "working CLI chat loop with Ollama integration".
  - *Problem solved:* enables multi-turn conversation within a single session.
  - *How behaviour changed:* the `OllamaClient` is created once before the loop (connection/model reused) and the user types `quit` to exit.
- **`docs/DEVLOG.md`** — first real content added (v0.1 and v0.2 sections documenting learnings & mistakes, e.g. "while loops are better for open-ended interaction", "client should be created once", "input/output flow must be sequential").

### Summary
JARVIS is now an interactive CLI: continuous prompt/response until `quit`. Dev learnings are captured in the devlog.

### Possible Next Version
Likely a `.gitignore` cleanup (the repo currently tracks `__pycache__`), and/or a system prompt — both thematically close in the history.

---

## Version v0.3.0 - Python .gitignore
*Commit:* `163f8a1` — "Add .gitignore for Python project" (parent `ded44b9`)

### Changed
- **`.gitignore`** — filled in (was empty in v0.0.0) with 26 lines of rules:
  - `__pycache__/`, `*.py[cod]`, `*.so`
  - `.venv/`, `.env`
  - `.vscode/`, `.idea/`
  - `*.log`, `build/`, `dist/`, `*.egg-info/`
  - `.DS_Store`, `Thumbs.db`
  - *What changed:* the empty ignore file now contains standard Python ignores.
  - *Why (Inferred):* to stop committing build/IDE/venv artifacts. **Reason (Inferred):** the previous commits already committed `__pycache__/*.pyc` because no ignore rules existed yet.
  - *Problem solved:* prevents Python bytecode, virtual envs, secrets (`.env`), and editor files from being tracked.

### Dependencies
- No changes to `requirements.txt`.

### Summary
Repository hygiene fix: standard Python ignores are now in place, addressing the accidental bytecode commits seen in v0.1.0.

### Possible Next Version
With config and a clean repo, the next step is likely documentation of the intended architecture/roadmap (matching the next commit).

---

## Version v0.4.0 - Architecture & Roadmap docs
*Commit:* `8b1d0cb` — "Added Architecture and Roadmap in docs for what to do seamless development" (parent `163f8a1`)

### Added
- **`docs/ARCHITECTURE.md`** — describes the system design:
  - Philosophy: modular AI system, single-responsibility components, replaceable parts.
  - High-level flow: `User → Input Layer → Executive Brain (Memory, Router, Planner, Tools, Models) → Output Layer`.
  - Components detailed: Main, Brain, Memory, Router, Models, Tools, Output.
  - Design/Core principles (separation of concerns, local-first, build one feature at a time, etc.).
- **`docs/ROADMAP.md`** — vision + phased plan:
  - Phase 1 Foundation (architecture, git, workflow, Ollama, CLI loop done; System prompt & Session memory pending),
  - Phase 2 Intelligence (long-term memory, knowledge base, model router, planner, conversation history),
  - Phase 3 Tools, Phase 4 Interfaces (voice/web/mobile), Phase 5 Autonomous Jarvis, plus future ideas.

### Documentation
- Both files introduce **important design decisions and roadmap** (explicitly in-scope): they define the modular target architecture and the multi-phase plan that later commits follow.

### Dependencies
- No changes to `requirements.txt`.

### Summary
The project now has a written architecture and roadmap — the north star that subsequent versions implement piece by piece.

### Possible Next Version
Phase 1 lists "System prompt" as pending, so the next version likely introduces a system prompt for the model (matching the next commit).

---

## Version v0.5.0 - System prompt introduced
*Commit:* `39b3d5b` — "Making prompt" (parent `8b1d0cb`)

### Added
- **`app/config/prompt.py`** — `SYSTEM_PROMPT` constant:
  ```
  app/config/prompt.py  SYSTEM_PROMPT
  └── "You are Jarvis. AI assistant focused on engineering, STEM,
       learning, programming, productivity, problem solving.
       Be logical. Be honest. Explain your reasoning.
       If uncertain, say so."
  ```
  - *What:* a static system-instruction string.
  - *Why (from Git / roadmap):* Phase 1 roadmap marks "System prompt" as a pending goal.
  - *Problem solved:* gives the model a consistent Jarvis identity & behavioural guardrails.
  - *How:* a module-level constant imported where needed.

### Changed
- **`app/models/ollama_client.py`** — added import `from app.config.prompts import SYSTEM_PROMPT`.
  - *Defect introduced (fact from Git):* the import path uses `prompts` (plural) while the new file is `prompt.py` (singular). This mismatch would cause an `ImportError` at runtime. (Fixed in v0.6.0.)

### Dependencies
- No changes to `requirements.txt`.

### Summary
A Jarvis system prompt is defined and wired into the client import — but the import path is wrong, so it isn't yet functional.

### Possible Next Version
The broken import must be fixed next (matching the next commit's "prompt failure" theme).

---

## Version v0.6.0 - Fix prompt import path
*Commit:* `7491e9a` — "prompt failure, prompts to prompt" (parent `39b3d5b`)

### Changed
- **`app/models/ollama_client.py`** — corrected the import:
  - `from app.config.prompts import SYSTEM_PROMPT` → `from app.config.prompt import SYSTEM_PROMPT`.
  - *What changed:* import target module name fixed to match the actual file `prompt.py`.
  - *Why (from Git):* commit message "prompt failure" indicates the previous (v0.5.0) import failed at runtime.
  - *Problem solved:* resolves the `ImportError` so the module loads.

### Dependencies
- No changes to `requirements.txt`.

### Summary
The system-prompt wiring is repaired; `SYSTEM_PROMPT` can now be imported correctly.

### Possible Next Version
With the import fixed, the next step is to actually send `SYSTEM_PROMPT` to the model in the request (matching the next commit).

---

## Version v0.6.1 - System prompt sent to model
*Commit:* `e5c6fd6` — "added SYSTEM_PROMPT in messege" (parent `7491e9a`)

### Changed
- **`app/models/ollama_client.py`** — `ask()` now prepends a `system` message to the `messages` list:
  ```
  messages=[
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user",   "content": prompt},
  ]
  ```
  - *What changed:* the system prompt is now included in the request payload.
  - *Why (from Git):* commit message — "added SYSTEM_PROMPT in messege".
  - *Problem solved:* the model finally receives Jarvis's identity/behaviour instructions (imported since v0.5.0 but unused until now).
  - *How behaviour changed:* each call now carries the system instruction alongside the user prompt.

### Dependencies
- No changes to `requirements.txt`.

### Summary
The system prompt is fully active: every request now carries Jarvis's behavioural instructions.

### Possible Next Version
So far each call is stateless (no memory of prior turns); the next version likely adds conversation history (matching the next commit).

---

## Version v0.6.2 - Conversation history
*Commit:* `94e1956` — "Implement conversation history in OllamaClient" (parent `e5c6fd6`)

### Changed
- **`app/models/ollama_client.py`** — `OllamaClient` now keeps persistent state:
  ```
  OllamaClient
  ├── __init__(model)
  │     self.conversation = [{"role":"system","content":SYSTEM_PROMPT}]
  └── ask(prompt) -> str
        self.conversation.append({"role":"user",     "content":prompt})
        response = chat(model, messages=self.conversation)
        self.conversation.append({"role":"assistant","content":answer})
        return answer
  ```
  - *What changed:* the system message moved out of the per-call payload into a persistent `self.conversation` list; user and assistant messages are appended after each turn.
  - *Why (from Git):* commit message — "Implement conversation history in OllamaClient".
  - *Problem solved:* the model now sees the full prior dialogue, enabling coherent multi-turn chat.
  - *How behaviour changed:* session memory now lives inside the client instance; each `ask()` builds on previous turns.

### Removed
- Compiled `__pycache__/*.pyc` artifacts for `app/models` were deleted in this commit (cleanup of previously tracked bytecode; ignore rules already in place since v0.3.0).

### Dependencies
- No changes to `requirements.txt`.

### Summary
JARVIS gains in-session memory: conversations are now context-aware across turns. This also satisfies the Phase 2 roadmap item "Conversation history".

### Possible Next Version
Phase 1 still lists "Session memory" and Phase 2 lists "Long-term memory / Knowledge base"; the next version likely begins persisting memory beyond a single session.

---

## Version v0.6.3 - Switch default model for speed
*Commit:* `3cc9e4b` — "change model from deepseek r1:32b to qwen3:8b for faster development" (parent `94e1956`)

### Changed
- **`app/config/settings.py`** — `DEFAULT_MODEL` updated:
  - `"deepseek-r1:32b"` → `"qwen3:8b"`
  - *What changed:* the default Ollama model used by `OllamaClient`.
  - *Why (from Git):* commit message — "for faster development".
  - *Problem solved:* a smaller/faster model reduces iteration time during development.
  - *How behaviour changed:* every run now defaults to `qwen3:8b` unless overridden.

### Dependencies
- No changes to `requirements.txt`.

### Summary
Development velocity is prioritised by switching the default local model to a lighter, faster one. The conversational core built up to v0.6.2 is preserved.

### Possible Next Version (based on Git history & roadmap)
The roadmap's pending Phase 1 "Session memory" and Phase 2 "long-term memory / Knowledge base" strongly suggest the next version introduces a persistent memory layer (e.g. saving facts/preferences and a context builder). This aligns with the direction of the subsequent commits in this repository (titled around "Persistent Memory Core", "Fact Extraction", etc.).

---

## Version v0.7.0 - Persistent Memory Core
*Commit:* `4034bf7` — "Persistent Memory Core" (parent `3cc9e4b` / v0.6.3)

### Added
- **`app/memory/manager.py`** — `MemoryManager` (JSON-file persistence):
  ```
  app/memory/manager.py  MemoryManager
  ├── __init__(self, path)
  ├── load() -> conversation        # json.load from path
  ├── save(conversation)            # json.dump to path
  └── clear()                       # resets memory
  ```
  - *What:* a small persistence layer that reads/writes the conversation to a JSON file.
  - *Why (from Git / roadmap):* the roadmap's pending "Session memory" and the DEVLOG's "Next: Session memory".
  - *Problem solved:* conversation now survives program restarts (stateful agent).
  - *How:* `main` loads the JSON at startup and saves after every turn.
- **`app/memory/conversation.json`** — seed data: a JSON **list** of role-based messages (system `"Temporary"` + a sample name/coffee dialogue).

### Changed
- **`app/main.py`** — wires in `MemoryManager`:
  ```
  app/main.py  main()
  ├── memory = MemoryManager(path="app/memory/conversation.json")
  ├── conversation = memory.load()
  ├── client = OllamaClient(model=DEFAULT_MODEL, conversation=conversation)
  └── loop: memory.save(client.conversation)   # after each answer
  ```
  - *What changed:* startup now loads the prior conversation; each reply is persisted.
  - *Problem solved:* continuity across sessions.
- **`app/models/ollama_client.py`** — `OllamaClient.__init__` now takes a `conversation` argument (dependency injection) and no longer builds the system prompt itself:
  ```
  OllamaClient.__init__(self, model: str, conversation: str)
  └── self.conversation = conversation
  ```
  - the `from app.config.prompt import SYSTEM_PROMPT` import was **removed**.

### Removed
- The `SYSTEM_PROMPT` import/usage from `ollama_client.py`; the system instruction is no longer injected by the client (it now relies on the seed conversation JSON containing the system message).

### Defect (fact from Git)
- `MemoryManager.clear()` calls `new_conversation()`, which is **not defined** anywhere in this commit. Calling `clear()` would raise `NameError`. (Resolved in v0.7.2, where `clear()` is rewritten.)

### Note (Inferred)
- Commit `4034bf7` again includes `__pycache__/*.pyc` bytecode (for `app/main.py`, `app/config/settings.py`). **Reason (Inferred):** these files were first committed in v0.1.0 *before* `.gitignore` existed (v0.3.0); Git keeps tracking already-tracked files, and `.gitignore` does not retroactively untrack them.

### Documentation
- `docs/DEVLOG.md` extended with developer notes (internally labeled v0.3 / v0.4 / v0.5) covering system prompt, conversation memory, and this persistent-memory core (learnings + known limitations: memory grows indefinitely, no structured/semantic memory yet).

### Summary
Jarvis becomes a stateful, persistent agent: a dedicated `MemoryManager` stores/loads conversation JSON, and responsibilities split cleanly (main = orchestration, OllamaClient = LLM, MemoryManager = persistence). Trade-off: the system prompt is dropped from the client, and `clear()` has a latent bug.

### Possible Next Version
The DEVLOG lists "Session memory" and notes "no structured long-term memory" — the next step is extracting structured facts/preferences from user input (matching the next commit, "Save Fact based on preferences").

---

## Version v0.7.1 - Save Fact based on preferences
*Commit:* `7a840ee` — "Save Fact based on preferences" (parent `4034bf7` / v0.7.0)

### Added
- **Fact-extraction wiring in `app/main.py`** (the *intent* to capture preferences):
  ```
  app/main.py  main()
  ├── from app.memory.fact_extractor import extract_fact
  ├── conversation, facts = memory.load()
  └── loop:
        fact = extract_fact(prompt)
        if fact: memory.add_fact(fact)
        memory.save(chat=client.conversation, facts=memory.facts)
  ```
  - *What:* after each reply, the user's message is run through `extract_fact()`; any returned fact is stored via `memory.add_fact()` and persisted.
  - *Why (from Git):* commit message — "Save Fact based on preferences".
  - *Problem solved (intent):* begin capturing long-term user facts separate from chat history.

### Changed
- **`app/main.py`** — `MemoryManager.load()` is now expected to return a **tuple** `(conversation, facts)`; the quit check changed from `'quit'` to `"quit"`; the startup banner now prints `"JARVIS v0.6"`.
  - *Note:* the in-code banner string `"JARVIS v0.6"` is the developer's own runtime label and does not match this changelog's version (v0.7.1).

### Defect / incomplete step (fact from Git)
This commit is a **build-up step** that references pieces not yet present, so it would not run as-is:
- `conversation, facts = memory.load()` — but `load()` still returns a single list until v0.7.2 → `ValueError` (not enough values to unpack).
- `from app.memory.fact_extractor import extract_fact` — but `fact_extractor.py` is **not added until v0.7.3** → `ImportError`.
- `memory.add_fact(...)` — but `MemoryManager.add_fact` is **not defined until v0.7.2** → `AttributeError`.
- `memory.save(chat=..., facts=...)` — but `MemoryManager.save` still has the single-arg `save(conversation)` signature from v0.7.0 (and even after v0.7.2 its parameter is `conversation`, not `chat`) → `TypeError`.
These are all resolved across v0.7.2 and v0.7.3.

### Summary
v0.7.1 lays down the fact-saving *flow* in `main.py` but is incomplete on its own; the supporting `MemoryManager` methods and the `fact_extractor` module arrive in the next two commits.

### Possible Next Version
v0.7.2 should extend `MemoryManager` with `add_fact()` and a two-argument `save(conversation, facts)` using a structured dict format (matching the next commit, "Fact Extraction").

---

## Version v0.7.2 - Fact Extraction (MemoryManager side)
*Commit:* `b145614` — "Fact Extraction" (parent `7a840ee` / v0.7.1)

### Changed
- **`app/memory/manager.py`** — substantially reworked to support facts + a structured format:
  ```
  MemoryManager
  ├── __init__(self, path): self.facts = []
  ├── load()  -> (conversation, facts)   # reads {"conversation":[], "facts":[]}; FileNotFoundError -> default system msg + []
  ├── save(conversation, facts)          # writes {"conversation":[], "facts":[]}
  ├── clear()                            # resets to default system msg (no more new_conversation())
  └── add_fact(fact)                     # appends to self.facts
  ```
  - *What changed:* `load()`/`save()` now use a **dict** `{"conversation", "facts"}`; `load()` gains `FileNotFoundError` handling returning a default system message; `clear()` no longer calls the undefined `new_conversation()` (fixes the v0.7.0 defect); new `add_fact()` supports the v0.7.1 flow.
  - *Why (from Git):* commit message — "Fact Extraction".
  - *Problem solved:* structured long-term memory (facts) alongside conversation; robust load with defaults; removes the `clear()` crash.
  - *How behaviour changed:* facts persist in the same JSON file under a `facts` key.

### Defect still present (fact from Git)
- `main.py` (from v0.7.1) still calls `memory.save(chat=client.conversation, facts=memory.facts)`. Even with the new `save(conversation, facts)` signature, the keyword is `chat`, which does **not** match the parameter name `conversation` → `TypeError` at runtime. (Fixed in v0.7.3, where `main.py` switches to `conversation=`.)
- The `from app.memory.fact_extractor import extract_fact` line in `main.py` still fails because `fact_extractor.py` is added only in v0.7.3 → `ImportError`.

### Dependencies
- No changes to `requirements.txt`.

### Summary
The persistence layer now stores facts in a structured dict with safe defaults and a working `add_fact()`/`clear()`. The end-to-end fact flow is still blocked by a keyword mismatch in `main.py` (resolved next commit).

### Possible Next Version
v0.7.3 should add the `fact_extractor` module and fix the `chat=` → `conversation=` keyword so facts actually get extracted and saved (matching the next commit, "JARVIS MEMORY SEPERATION...").

---

## Version v0.7.3 - Memory separation: conversation vs facts
*Commit:* `9aa2fb2` — "JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS" (parent `b145614` / v0.7.2)

### Added
- **`app/memory/fact_extractor.py`** — `extract_fact(message)` (rule-based):
  ```
  app/memory/fact_extractor.py  extract_fact(message) -> str | None
  └── if "i like"         -> "user likes "   + rest
     if "i am"            -> "user is "      + rest
     if "i prefer"        -> "user prefers " + rest
     if "remember that"   -> replace "remember that" with "user"
     else                 -> None
  ```
  - *What:* a tiny keyword-triggered fact parser.
  - *Why (from Git):* commit theme — separate facts from conversation.
  - *Problem solved:* turns user statements ("i like…", "i am…") into stored long-term facts.

### Changed
- **`app/main.py`** — fixed the save call: `memory.save(conversation=client.conversation, facts=memory.facts)` (keyword `conversation=`, matching `MemoryManager.save`). This resolves the v0.7.1/v0.7.2 `TypeError`.
- **`app/memory/manager.py`** — now imports `SYSTEM_PROMPT`; `load()` handles **both** the old list format and the new dict format (backward compatibility); default/clear system messages use the real `SYSTEM_PROMPT` constant instead of the literal string `"SYSTEM_PROMPT"`.
- **`app/memory/conversation.json`** — **migrated** from a JSON list to a JSON dict `{"conversation": [...], "facts": [...]}`, and extended with a new dialogue (football, guitar, civil engineer, STEM, tuition teacher) plus a stored `facts` entry.

### Renamed / Moved
- *Data-format migration* (not a file rename): memory-file content changed shape from `[...messages]` (list) to `{"conversation": [...], "facts": [...]}` (dict). `MemoryManager.load()` was explicitly updated to keep reading the old list format for backward compatibility.

### Documentation
- `docs/DEVLOG.md` extended (internally "v0.06") documenting fact-extraction features, the conversation-vs-facts separation, architecture, and lessons learned (schema evolution needs backward compatibility; separating responsibilities aids extensibility).

### Summary
The fact system becomes fully functional: `fact_extractor` exists, `main.py`'s save keyword matches, and memory now cleanly separates short-term conversation from long-term facts with backward-compatible loading. This realizes the roadmap's "Session memory" / structured-memory goal.

### Possible Next Version
The DEVLOG's stated next goal is to make Jarvis **use** remembered facts in conversation (not just store them) — matching the next commit, "Context Builder & Long-Term Memory Integration".

---

## Version v0.7.4 - Context Builder & Long-Term Memory Integration
*Commit:* `7803a93` — "Context Builder & Long-Term Memory Integration" (parent `9aa2fb2` / v0.7.3)

### Added
- **`OllamaClient.build_messages()`** — a Context Builder:
  ```
  OllamaClient.build_messages() -> list
  ├── append system: SYSTEM_PROMPT
  ├── if self.facts: append system: "Here are some known facts:\n- <fact>\n..."
  └── extend with self.conversation
  ```
  - *What:* assembles the full LLM context = system prompt + persistent facts + conversation history.
  - *Why (from Git / DEVLOG goal):* "Teach Jarvis to use remembered facts during conversation."
  - *Problem solved:* long-term facts are now injected into every request.
  - *How:* `ask()` calls `build_messages()` and sends that (instead of raw `self.conversation`).

### Changed
- **`app/config/prompt.py`** — `SYSTEM_PROMPT` gained one line: *"Do not repeat previous answers. If similar question appears, rephrase or extend."*
- **`app/models/ollama_client.py`** — `OllamaClient.__init__(self, model, conversation: list, facts: list)` now also stores `self.facts` (and re-imports `SYSTEM_PROMPT`, which was dropped back in v0.7.0); `ask()` builds messages via `build_messages()`.
- **`app/main.py`** — passes `facts=facts` into `OllamaClient(...)`.

### Dependencies
- No changes to `requirements.txt`.

### Documentation
- `docs/DEVLOG.md` extended (internally "v0.7") documenting the Context Builder, long-term memory injection, and the final separation of responsibilities (MemoryManager / OllamaClient / main). Notes next steps: intelligent memory retrieval, memory categories, conversation trimming.

### Summary
Jarvis now combines system prompt + long-term facts + conversation history into every request via `build_messages()`. Facts are no longer just stored — they actively shape responses. This completes the persistence + structured-memory arc begun at v0.7.0.

### Possible Next Version (based on Git history & roadmap)
The DEVLOG's next goals (intelligent/filtered memory retrieval, memory categories, conversation trimming) and the later commit titles in this repo (e.g. "implement structured memory pipeline", "multi-fact extraction", and ultimately "JARVIS v2.0.0 - Complete architectural overhaul") strongly suggest the next versions move toward richer, retrieved, and categorized memory — and eventually a major architectural rewrite.

---

## Version v0.8.0 - Structured memory pipeline
*Commit:* `d43f6e9` — "feat(v0.8): implement structured memory pipeline" (parent `7803a93` / v0.7.4)

### Added
- **`app/config/version.py`** (new) — `VERSION = "0.8.0"`.
  - *What:* single source of truth for the app version, imported by `main.py`.
  - *Why (from Git):* commit message `feat(v0.8)` — first commit to carry an explicit version string in code.
  - *Problem solved:* the banner no longer hardcodes a stale label.
- **`app/memory/rules.py`** (new) — `RULES`: a list of ~19 trigger dicts across categories `identity`, `preferences`, `skills`, `goals`, `plans`, `tasks`, `location`, `profession`. Each rule = `{"trigger", "category", "type"}`.
  - *What:* declarative extraction rules replacing hardcoded `if` chains.
  - *Why (from Git / DEVLOG):* "Rule-Based Extraction" — central, extensible place for extraction logic.
  - *Problem solved:* adding a new fact type no longer requires editing `extract_fact()`.

### Changed
- **`app/memory/fact_extractor.py`** — `extract_fact()` rewritten to import `RULES` and loop over them, returning a **dict** `{"category", "type", "value"}` (previously returned a plain string or `None`). Hardcoded string branches removed.
- **`app/models/ollama_client.py`** — `build_messages()` reformatted fact rendering to `Known user facts:` then `- [{category}] {type} → {value}`. Conversation extension (`messages.extend(self.conversation)`) was **commented out** for an Ollama-statelessness experiment, leaving a `print("Conversation extension is DISABLED")` debug line; added `pprint` debug output of the sent messages.
- **`app/main.py`** — banner changed from hardcoded `"JARVIS v0.6"` to `f"JARVIS {VERSION}"` (reads `from app.config.version import VERSION`).
- **`app/memory/conversation.json`** — appended more seed dialogue; the `facts` array was **reset to `[]`** (old string-format facts cleared).

### Removed
- The legacy string-based facts in `conversation.json` (replaced by the empty `facts: []` list compatible with the new dict-based builder).

### Defect / experiment state (fact from Git)
- `build_messages()` runs with conversation extension **disabled** (debugging whether Ollama retains memory). Net effect in this commit: only system prompt + facts are sent, not history. DEVLOG concludes "Ollama is stateless" — all memory comes from Jarvis' own architecture.
- Old v0.7 string facts were incompatible with the new dict-based builder and caused `TypeError: string indices must be integers`; resolved by clearing `facts` to `[]`.

### Note (Inferred)
- Commit `d43f6e9` again updates `__pycache__/*.pyc` (for `app/main.py`, `app/config/settings.py`, `app/config/__init__.py`). **Reason (Inferred):** these were first tracked before `.gitignore` (v0.3.0) and Git keeps tracking already-tracked files.

### Documentation
- **`docs/DEVLOG.md`** — added `## v0.8 -` section: objective (structured memory), major changes (dict memory, rule-based extraction, updated pipeline), bugs (variable scope, missing `RULES` import, old-format `TypeError`, Ollama-stateless experiment), limitations (only one fact per prompt), result.
- **`docs/changelog.md`** (new) — `# v0.8.0` with Added / Changed / Fixed / Verified / Known Issues.

### Dependencies
- No changes to `requirements.txt`.

### Summary
Memory is rebuilt as structured dicts (`category`/`type`/`value`) driven by a declarative `RULES` table, and a dedicated `version.py` makes the app self-versioning. The extraction pipeline is now extensible, but only one fact per message is extracted and conversation history is temporarily disabled while proving Ollama has no memory of its own.

### Possible Next Version
The DEVLOG's "Current Limitations" and the new `docs/project_notes.md` (added next commit) name **v0.9.0** as the multi-fact-extraction mission — splitting a message into sentences and extracting many facts.

---

## Version v0.8.1 - Multi-fact extraction pipeline
*Commit:* `2922129` — "feat(memory): implement multi-fact extraction pipeline" (parent `d43f6e9` / v0.8.0)

> *Version note:* Git carries **no release label** for this commit (`version.py` still `"0.8.0"`; the only version token is `docs/project_notes.md` "JARVIS v0.9.0 Mission"). The label **v0.8.1** is assigned by instruction (user), keeping the sequence monotonic after v0.8.0.

### Added
- **`extract_facts()`** + helper **`_split_into_sentences()`** in `app/memory/fact_extractor.py`:
  ```
  app/memory/fact_extractor.py
  └── extract_facts(message) -> list[dict]
        _split_into_sentences(message)  # split on . ! ?
        for sentence: match first RULES trigger -> append {"category","type","value"}
        return facts  (empty list if none)
  ```
  - *What:* replaces the single-fact `extract_fact()` with a sentence-aware multi-fact extractor.
  - *Why (from Git / project_notes):* the stated v0.9.0 mission — "One Message → Many Sentences → Many Facts".
  - *Problem solved:* a message like "I like football. I can swim." now yields two facts instead of one.
  - *How:* split into sentences, check each independently against `RULES`, collect all matches.

### Changed
- **`app/memory/fact_extractor.py`** — `extract_fact` (singular, returns dict/None) **removed**; callers must use `extract_facts` (returns `list[dict]`).
- **`app/main.py`** — `from app.memory.fact_extractor import extract_fact` → `extract_facts`; `fact = extract_fact(prompt)` → `facts = extract_facts(prompt)`; now loops `for fact in facts: memory.add_fact(fact)` (previously added one fact).
- **`app/models/ollama_client.py`** — re-enabled `messages.extend(self.conversation)` (history flows to the LLM again) but the stale `print("Conversation extension is DISABLED")` line remains; added debug prints of `self.facts` type.
- **`app/memory/conversation.json`** — more seed dialogue; `facts` now holds 2 structured dicts (`chocolate`, `black tea`).

### Renamed / Moved
- Function rename `extract_fact` → `extract_facts` (signature/return-type change: `dict|None` → `list[dict]`). Downstream call sites updated in `main.py`.

### Note (Inferred)
- Debug `print()` statements (facts type introspection, "Conversation extension is DISABLED") remain in `ollama_client.py` — **Reason (Inferred):** left over from the v0.8.0 statelessness experiment, not yet cleaned up.

### Documentation
- **`docs/project_notes.md`** (new) — "JARVIS v0.9.0 Mission": design notes for multi-fact extraction (sentence splitter → per-sentence rule match → list of facts), including the planned two-loop structure and return-type change to `list`.
- **`docs/DEVLOG.md`** — the `## v0.8 -` header line amended to `## v0.8 - feat(v0.8): implement structured memory pipeline`.

### Dependencies
- No changes to `requirements.txt`.

### Summary
Extraction becomes multi-fact: a single user message is split into sentences and each is matched against the rules, producing a list of structured facts. The pipeline return type shifts from one dict to a list, and `main.py` now persists every extracted fact.

### Possible Next Version
With extraction producing many facts, the next step is giving facts *behaviours* (append/replace/ignore) and a behavior-driven memory engine — which the next commit (v0.9.0) documents.

---

## Version v0.9.0 - Behavior-driven memory engine
*Commit:* `4f71baf` — "feat(memory): implement behavior-driven memory engine and multi-fact extraction" (parent `2922129` / v0.8.1)

### Added
- **Behavior field on rules** — every entry in `app/memory/rules.py` gains `"behavior": "append"`.
- **`MemoryManager.apply_behavior()`** + **`MemoryManager.replace_fact()`** in `app/memory/manager.py`:
  ```
  MemoryManager
  └── add_fact(fact)
        self.apply_behavior(fact)        # dispatch on fact["behavior"]
        ├── "append"  -> self.facts.append(fact)
        ├── "replace" -> replace_fact()  # match by category+type, overwrite else append
        └── "ignore"  -> return
  ```
  - *What:* memory writes are now governed by a `behavior` declared in the rule, not hardcoded logic.
  - *Why (from Git / DEVLOG):* "behavior-driven memory engine" — MemoryManager no longer hardcodes replacement; rules decide.
  - *Problem solved:* foundation for replace/ignore semantics (e.g. updating a fact vs. duplicating it).

### Changed
- **`app/memory/fact_extractor.py`** — extracted `value` now `.rstrip(".!?")`; the produced fact dict now includes `"behavior": rule["behavior"]` (propagated from the matched rule).
- **`app/memory/manager.py`** — `add_fact(fact)` now calls `self.apply_behavior(fact)` (was a plain `append` since v0.7.2); debug `print("ADDING:"`, `"APPLY:"`) added.
- **`app/main.py`** — prints the extracted facts each turn (debug).
- **`app/memory/conversation.json`** — extended seed dialogue; `facts` grew (football, tea, name "sajan" ×2, band-maid, sabin rai, plus a `behavior: append` name entry).

### Defect (fact from Git)
- A **nested-list bug** risk is noted in DEVLOG: passing the entire fact *list* into `add_fact()` would store `[fact, [fact, fact]]`. Caught via `pprint` debugging. (The code as committed iterates correctly, but the lesson is recorded.)
- Duplicate facts (e.g. `"name": "sajan"` appears twice) are stored because there is no dedup yet.

### Documentation
- **`docs/DEVLOG.md`** — added `## v0.9 - Multi-Fact Memory Extraction` (`Version: v0.9.0`): goal, implementation, architecture diagram, problems (list-vs-dict, nested-list bug, conversation-history red-herring), lessons, limitations (regex splitter, no dedup, no compound-fact decomposition), and "Next Version (v0.10)".
- **`docs/changelog.md`** — added `# v0.9.0` section (Added / Changed / Fixed / Known Issues).

### Dependencies
- No changes to `requirements.txt`.

### Summary
Memory becomes behavior-driven: rules declare an `append`/`replace`/`ignore` behavior, and `MemoryManager` dispatches on it. Extraction also strips trailing punctuation and carries the behavior through. The multi-fact pipeline (v0.8.1) is now documented as the v0.9.0 release.

### Possible Next Version
The DEVLOG "Next Version (v0.10)" lists duplicate detection, better sentence parsing, compound-fact decomposition, and memory metadata — and the next commit (v0.9.1) widens rule coverage with multiple triggers per rule.

---

## Version v0.9.1 - Multi-trigger extraction
*Commit:* `6316917` — "feat(memory): implement multi-trigger extraction and behavior-based memory actions" (parent `4f71baf` / v0.9.0)

> *Version note:* Git carries **no version string at all** for this commit (`version.py` still `"0.8.0"`; DEVLOG/changelog untouched). The label **v0.9.1** is assigned by instruction (user), keeping the sequence monotonic after v0.9.0. Its code is what the next commit's `## v1.0` / `# v1.0.0` notes describe.

### Changed
- **`app/memory/rules.py`** — the single `"trigger"` key on every rule is **replaced by a `"triggers"` list** of natural-language variations:
  - `identity`: `"i am "` → `["i am ", "i'm "]`; `"my name is "` → `["my name is ", "my name's ", "call me ", "i go by "]`; etc.
  - `preferences`: `"i like "` now also matches `["i love ", "i enjoy ", "i prefer ", "i'm into ", "i'm a fan of"]`.
  - `skills`, `goals`, `plans`, `tasks`, `location`, `profession`: each expanded with synonymous phrasings (e.g. `"i can "` → `["i can ", "i know how to ", "i'm able to "]`).
  - *What changed:* one trigger string per rule became a list of trigger phrases.
  - *Why (from Git / DEVLOG v1.1):* "Recognize multiple natural language variation."
  - *Problem solved:* the extractor now catches many phrasings, not just one literal string.
- **`app/memory/fact_extractor.py`** — inner match loop changed from a single `rule["trigger"]` to `for trigger in rule["triggers"]:`; first matching trigger per sentence wins.
- **`app/memory/conversation.json`** — large "Alex" profile seed added (name, residence, profession, preferences, goals, plans, tasks, location, skills), exercising the expanded triggers; many facts stored with `behavior: append`.

### Defect (fact from Git)
- Pressure-testing exposed **architectural** (not coding) problems, later recorded in the v1.1 DEVLOG: current location vs. permanent residence, profession vs. identity, duplicate facts, and temporary vs. permanent facts. The extractor itself performed well; remaining issues are rule-design problems.
- **Duplicate facts persist** (e.g. `"name": "sajan"` and `"name": "alex"` each appear multiple times) — no deduplication or merge logic yet.

### Documentation
- None in this commit (DEVLOG/changelog unchanged; the v1.0.0 / v1.1 release notes are authored in the next commit).

### Dependencies
- No changes to `requirements.txt`.

### Summary
Rule coverage widens dramatically: each rule now matches a list of synonymous triggers, so the extractor recognizes many natural-language variations. This is the implementation behind the behavior-driven memory actions; the release notes land in v1.1.

### Possible Next Version
The next commit (v1.1) authors the v1.0.0 + v1.1 release notes and adds the post-v1.0 stable-architecture document, while also correcting the `version.py` value.

---

## Version v1.1 - Multi-trigger extraction & stable architecture (documents v1.0.0 too)
*Commit:* `db51ccc` — "feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over" (parent `6316917` / v0.9.1)

> *Version note:* Git labels this commit **v1.0.0 AND v1.1** — `docs/DEVLOG.md` adds `## v1.0` and `## v1.1`, `docs/changelog.md` adds `# v1.0.0` and `# v1.1`, and `app/config/version.py` is set to `"v.1.1"` (malformed). The implemented code change in this commit is the multi-trigger work already shipped in v0.9.1; the **v1.0.0** notes describe the behavior engine whose code landed in v0.9.1. Block header uses **v1.1** (the `version.py` value).

### Added
- **`docs/ARCHITECTURE.md`** — appended "## After v1.0 JARVIS ARCHITECTURE": a stable-architecture specification — core principles (single responsibility, stable data contracts, extend-not-rewrite), data flow `User → Orchestrator → LLM → Extractor → Memory Manager → Storage → Prompt Builder → LLM`, component contracts (Orchestrator, Rules, Extractor, Fact schema `category/type/value/behavior`, Memory Manager, Conversation, Prompt Builder), and a future-evolution path `Rules → Regex → Synonyms → Embeddings → Intent → LLM-based Extraction`.
  - *What:* the first written contract-level architecture since the early `ARCHITECTURE.md` (v0.4.0).
  - *Why (from Git):* "After v1.0 JARVIS ARCHITECTURE" — lock down interfaces as the system matures.
  - *Problem solved:* documents stable boundaries so implementations can evolve without breaking downstream components.

### Changed
- **`app/config/version.py`** — `VERSION = "0.8.0"` → `VERSION = "v.1.1"`.
  - *Defect (fact from Git):* the new value is malformed — `"v.1.1"` has no closing quote and an odd `v.` prefix (expected something like `"1.1.0"`). **Reason (Inferred):** a typo/truncation while bumping the version.

### Documentation
- **`docs/DEVLOG.md`** — added `## v1.0 - Rule Based Memory Behavior` (summary: behavior-driven memory, append/replace/ignore; problems: nested-list bug, old-format confusion, "behavior"/"behaviour" spelling mix-up, forgot to restart Python after editing imports; lessons; "v1.0 memory pipeline operational") and `## v1.1 - Recognize multiple natural language variation` (goal, `trigger → triggers` migration, behavior propagation, MemoryManager dispatcher, pressure-test discoveries, lesson: extraction stays simple, memory decides append/replace/ignore/merge).
- **`docs/changelog.md`** — added `# v1.0.0` (Added: multiple-fact extraction, sentence splitting, structured memory, behavior engine, append/replace/ignore; Changed: MemoryManager no longer hardcodes; Fixed: nested-list bug, behavior persistence) and `# v1.1` (Added: multiple triggers per rule, behavior field, dispatcher, pressure testing; Improved: rule flexibility; Fixed: trigger→triggers migration, rule iteration).

### Dependencies
- No changes to `requirements.txt`.

### Summary
This commit is primarily a **documentation + version-bump** commit: it authors the v1.0.0 and v1.1 release notes, adds the post-v1.0 stable-architecture spec, and bumps `version.py` (with a malformed value). The actual behavior-engine and multi-trigger code shipped in v0.9.1 / v0.9.1 respectively; here they are formally released and the architecture is pinned down.

### Possible Next Version (based on Git history)
The repository continues toward `v2.0.0` ("Complete architectural overhaul", tagged) — a major rewrite that likely realizes the architecture/evolution path documented here (embeddings, semantic memory, multi-backend, agents). Commits 21–26 in the repo move through the pre-v2.0.0 cleanup, `v2.0.0`, `v2.2.1`, `v2.4.0`, and `v2.4.1`.

---

## Version v1.2.0 - Debug cleanup & reasoner scaffold
*Commit:* `63addf6` — "before big change in memory management" (parent `db51ccc` / v1.1)

> *Version note:* Git carries **no release label** for this commit (message is "before big change in memory management"; `version.py` still `"v.1.1"`). The label **v1.2.0** is assigned by instruction (user), keeping the sequence monotonic after v1.1 and below the upcoming `v2.0.0` overhaul.

### Added
- **`app/memory/reasoner.py`** (new) — `decide_behavior(new_fact, existing_facts)`:
  ```
  app/memory/reasoner.py  decide_behavior(new_fact, existing_facts) -> str
  └── return new_fact["behavior"]   # placeholder: trusts the rule-declared behavior
  ```
  - *What:* a new, standalone reasoning module that decides how a fact should be stored.
  - *Why (from Git / upcoming overhaul):* commit message "before big change in memory management" — scaffolding laid just before the v2.0.0 memory rewrite.
  - *Problem solved (intent):* separates the "decide what to do with a fact" concern from `MemoryManager.apply_behavior` (which still holds the inline dispatcher).
  - *How:* pure function; `existing_facts` is accepted but currently unused, so it always returns the rule's `behavior`. **Not yet imported or wired into `manager.py`.**

### Changed
- **`app/config/version.py`** — fixed the syntax error introduced in v1.1: `VERSION = "v.1.1` (no closing quote) → `VERSION = "v.1.1"` (quote restored; the odd `v.` prefix remains, but it is now valid Python).
- **`app/memory/conversation.json`** — appended a new multi-turn dialogue (user building a JARVIS, a material-science question, modern AI architecture, memory/knowledge management, and API-privacy optimization via placeholders) plus one new structured `skills`/`ability` fact (about minimizing data sent to external servers using local-LLM-filled placeholders).
- **`app/main.py`** — removed debug `print("Extracted facts:")` / `print(facts)` from the extraction step.
- **`app/memory/manager.py`** — removed debug `print("ADDING:", fact)` and `print("APPLY:", fact)` from `add_fact()` / `apply_behavior()`.
- **`app/models/ollama_client.py`** — removed the `print("self.facts =", ...)` / `print("type(self.facts) =", ...)` introspection block and the `pprint(messages)` debug block (with its `from pprint import pprint`) from `build_messages()` / `ask()`.

### Removed
- Leftover debug instrumentation (`print` / `pprint`) across `main.py`, `manager.py`, and `ollama_client.py` that had accumulated since the v0.8.0 statelessness experiment.

### Note (Inferred)
- Commit `63addf6` again updates `__pycache__/*.pyc` (for `app/main.py`, `app/config/settings.py`, `app/config/__init__.py`). **Reason (Inferred):** these files were first tracked before `.gitignore` (v0.3.0) and Git keeps tracking already-tracked files.

### Documentation
- None (no DEVLOG / changelog / architecture changes in this commit).

### Dependencies
- No changes to `requirements.txt`.

### Summary
A pre-overhaul cleanup and scaffolding commit: the malformed `version.py` is repaired, accumulated debug prints are stripped from the memory/LLM path, conversation data grows with a JARVIS-design discussion, and a separate `reasoner.py` stub is introduced to hold future fact-decision logic (not yet wired in). This is the last commit before the tagged `v2.0.0` architectural overhaul.

### Possible Next Version (based on Git history)
The next commit, `8519f65`, is tagged **v2.0.0** ("Complete architectural overhaul") — the major rewrite that realizes the post-v1.0 architecture/evolution path. The changelog will resume at v2.0.0.

---

## Version v2.0.0 - Complete architectural overhaul
*Commit:* `8519f65` — "feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul" (parent `63addf6` / v1.2.0)
*Tag:* `v2.0.0` (Git)

### Added
- **`app/memory/schema.py`** — `Memory` / `MemoryResult` data classes: immutable `created_at`, mutable `updated_at`, with `touch()`, `mark_updated()`, `format_for_prompt()`, `to_dict()` / `from_dict()`.
- **`app/memory/store.py`** — `MemoryStore`: CRUD (`add`, `get_by_id`, `find_by_category_and_type`, `update_fields`, `remove`, `remove_by_category_and_type`, `clear`) plus **dirty-tracking** persistence (`is_dirty`, `save`, `save_if_dirty`, `force_save`, `_load`).
- **`app/memory/retrieval.py`** — `KeywordRetriever` (implements the `CandidateRetriever` Protocol): keyword-overlap candidate finding (`find_candidates`, index callbacks `on_memory_added` / `on_memory_removed` / `on_index_rebuilt`, `clear`).
- **`app/memory/ranking.py`** — `MemoryRanker` + `RankingWeights`: score-based relevance (`rank`, `_calculate_all_scores`, `_combine_scores`, `_score_relevance` / `_score_importance` / `_score_frequency` / `_score_recency` / `_score_confidence`), the `CandidateRetriever` Protocol, and stop-word handling.
- **`app/context/manager.py`** — `ContextWindowManager` + `ContextStats`: real token accounting (`count_tokens`, `count_tokens_text`), **pair-aware** trimming (`fit`, `_group_into_pairs`) so user/assistant pairs drop together, `get_stats`, `get_tokenizer_info`.
- **`app/conversation/manager.py`** — `ConversationManager` + `Message`: structured conversation store (`add_message`, `get_recent` / `get_recent_formatted` / `get_all`, `count`, `clear`, `set_summary` / `get_summary`, dirty-tracked `save` / `save_if_dirty`, `_load`); `Message.to_dict` / `from_dict` / `to_openai_format`.
- **`app/models/client.py`** — `ModelClient` (Protocol) + `ModelResponse`: unified generation interface (`generate`, `model_name`, `role`).
- **`app/models/llamacpp_client.py`** — `LlamaCppClient(ModelClient)`: local llama.cpp backend.
- **`app/models/router.py`** — `ModelRouter` + `TaskType(Enum)`: **score-based** task classification (`register`, `set_default`, `select`, `route`, `_classify_prompt`) replacing the old first-match logic.
- **`app/prompt/builder.py`** — `PromptBuilder`: assembles system + ranked memories + conversation (`build`, `build_with_stats`, `_format_memories`).
- **`app/utils/tokenizer.py`** — real token counting with fallback chain `tiktoken → transformers → word`: `get_token_counter`, `_try_tiktoken`, `_try_transformers`, `_word_counter`, `estimate_tokens`, `get_tokenizer_info`.
- **`app/config/settings.py`** — typed config objects: `ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, `PathsConfig` (path accessors `memories`, `conversations_dir`, `default_conversation`), `Settings` (`load`, `get_settings`, `reset_settings`), `_DefaultModel`.
- **`app/config/prompt.py`** — rewritten system prompt / constants.

### Changed
- **`app/memory/manager.py`** — `MemoryManager` decomposed from a monolith into an orchestrator over `MemoryStore` + `CandidateRetriever` + `MemoryRanker`: new `store` / `retrieve` / `update` / `replace` / `delete` / `delete_by_type` / `merge`, category/type/id getters, **event callbacks** (`on_store` / `on_update` / `on_delete`), `_handle_append` / `_handle_replace`, `facts`, dirty-aware `save` / `save_if_dirty`, `load() -> (conversation, facts)`.
- **`app/memory/fact_extractor.py`** — `extract_facts(message, source=SOURCE_USER)` with `_extract_value` and **boundary detection** (stops at conjunctions) to avoid garbage fact values.
- **`app/main.py`** — full loop rewrite: **extract/store facts BEFORE retrieval** (same-turn personalization), graceful OpenAI error handling (no 50-line stack traces), CLI helpers `_cleanup` / `_show_memories` / `_show_stats` / `_show_help` / `_format_time`, and fixed double-system-message formatting.
- **`app/config/version.py`** — `VERSION = "v.1.1"` → `"v.2.0.0"` (matches the Git tag).
- **Schema:** single mutable `timestamp` replaced by immutable `created_at` + mutable `updated_at` on memory records.
- **Context trimming:** now drops user/assistant **pairs** instead of individual messages (preserves conversational coherence).
- **ModelRouter:** first-match → score-based classification (removes keyword-order bias).
- **Tokenization:** integrated real counting (`tiktoken → transformers → word` fallback).
- **Offline mode:** enforced `local_files_only` to prevent HuggingFace network hangs at startup.

### Removed
- **`app/models/ollama_client.py`** — replaced by the `ModelClient` Protocol + `LlamaCppClient` + `ModelRouter` backend abstraction.
- **`app/memory/reasoner.py`** — the v1.2.0 decision stub; its logic is folded into `MemoryManager._handle_append` / `_handle_replace`.
- **`app/memory/conversation.json`** — old single-file conversation data removed (conversation now lives under `data/conversations/` at runtime).

### Renamed / Moved
- *Data-layout migration:* conversation storage moved from `app/memory/conversation.json` to **`data/conversations/`** (plural directory, created at runtime — not present in this diff); memory JSON adopted `created_at` / `updated_at` and is auto-migrated from v1 formats (a clean `data/` wipe is recommended).

### Dependencies
- `requirements.txt` is **unchanged** in this commit (absent from the file list). **Reason (Inferred):** the new tokenizer imports `tiktoken` and offline mode relies on `transformers` (already pinned) — if `tiktoken` was not already listed, the manifest now lags the code (latent gap). No formal dependency additions recorded here.

### Documentation
- **`docs/ARCHITECTURE.md`** (+182 lines) — extended with the v2.0.0 modular, pipeline-driven architecture: component boundaries, data flow (Extract → Store → Retrieve → Rank → Build → Generate), and the new config/schema contracts.

### Summary
JARVIS v2.0.0 is a ground-up re-architecture. The monolithic v1 `MemoryManager` is decomposed into `MemoryStore` (CRUD + dirty-tracking), `KeywordRetriever` / `CandidateRetriever` (candidate finding), and `MemoryRanker` (score-based relevance, frequency, recency, confidence). The model layer becomes backend-agnostic via `ModelClient` / `ModelRouter` (score-based task routing, now with a llama.cpp client). Token counting is real (`tiktoken → transformers → word`), context trimming is pair-aware, fact extraction gains boundary detection, and the main loop extracts/stores before retrieval for same-turn personalization. Strict offline mode and graceful API error handling improve startup and reliability. **Breaking:** new memory JSON schema (`created_at`/`updated_at`) and conversation path (`data/conversations/`); old formats auto-migrate but a clean `data/` wipe is recommended.

### Possible Next Version (based on Git history)
The repo continues through `5fccb37` (bug fixes + v2.0.0 docs), `df45be2` (Multi-Backend + Streaming + External Config), `b2c2211` (Semantic Memory with chromaDB, hybrid retriever, conversation_store, agent git-automation), and `891fe4b` (tagged `v2.2.1` / `v2.4.0` / `v2.4.1` — "Documentation agent wired, package structure fixed").

---

## Version v2.0.1 - v2.0.0 bug fixes & release docs
*Commit:* `5fccb37` — "Bug fixes and added archiecture, dev log and changelog for v2.0.0" (parent `8519f65` / v2.0.0)

> *Version note:* Git carries **no tag** for this commit (`version.py` unchanged at `"v.2.0.0"`). The label **v2.0.1** is assigned by instruction (user), the standard patch bump after v2.0.0.

### Added
- **`autocomplete` model config** in `app/config/settings.py` — `qwen2.5-1.5b-instruct-q4_k_m.gguf` (role `"autocomplete"`, `base_url="http://localhost:8082/v1"`, `max_tokens=150`); the `"general"` model gained `base_url="http://localhost:8080/v1"` ("Main brain").
- **`get_default_model()`** in `app/config/settings.py` — replaces the removed `_DefaultModel` class / `DEFAULT_MODEL` singleton as the lazy default-model accessor.
- **Release documentation for v2.0.0:** `docs/ARCHITECTURE.md` (long-term roadmap / forward vision), `docs/DEVLOG.md` (`## v2.0.0 -` section + inline fix notes), `docs/changelog.md` (`## v2.0.0 -` release entry).

### Changed
- **`app/config/settings.py`** — `ConversationConfig.save_on_every_message: False` → `True` (conversation now persisted on each message); `models` dict re-indented to nest correctly under `Settings`; removed `_DefaultModel` / `DEFAULT_MODEL`, added `get_default_model()`.
- **`app/main.py`** — error handling moved from `input()` to wrap `selected_model.generate(fitted_messages)`: on failure prints a friendly `[Error] Model unavailable` + "Is llama-server running on port 8080?" and calls `conversation.pop_last_message()`, then `continue` (no 50-line stack trace). The **ModelRouter is now wired into the loop**: `selected_model, task_type = router.route(prompt)` replaces the previous direct `model.generate(...)`. Minor whitespace cleanup.
- **`app/memory/manager.py`** — `retrieve()` and `update()` now call `self._store.force_save()` instead of `save_if_dirty()` / `save()`, so retrieval-touch and update writes are persisted immediately.
- **`app/models/llamacpp_client.py`** — imports `get_default_model` and uses it (`model or get_default_model()`) instead of the removed `settings.default_model` / `DEFAULT_MODEL` singleton.

### Removed
- **`_DefaultModel` class + `DEFAULT_MODEL`** from `app/config/settings.py` (replaced by `get_default_model()`).
- The `input()` `try/except (EOFError, KeyboardInterrupt)` quit-on-interrupt block in `app/main.py` (replaced by the generate-time error handling above).

### Documentation
- **`docs/ARCHITECTURE.md`** (+329) — large forward-looking expansion: "Final Rough Roadmap", "JARVIS Long-Term Architecture Roadmap", and vision sections for `v3.1`, `Knowledge`, and `v4`–`v7` (future architecture directions).
- **`docs/DEVLOG.md`** (+151) — added `## v2.0.0 -` developer log plus inline fix notes (e.g. `_handle_replace` / `retrieve()` corrections).
- **`docs/changelog.md`** (+114) — added the formal `## v2.0.0 -` release entry.

### Dependencies
- No changes to `requirements.txt`.

### Summary
A stabilization + documentation commit for the v2.0.0 release. It fixes several wiring/persistence bugs: conversations save on every message, memory retrieval/update force-persist their touches, the `ModelRouter` is finally used in the main loop (replacing the direct `model` call), and `LlamaCppClient` uses the new `get_default_model()` accessor. A new `autocomplete` (fast, small) model is configured alongside the general "Main brain". The bulk of the diff is the v2.0.0 release docs — architecture roadmap, devlog, and changelog.

### Possible Next Version (based on Git history)
The next commit, `df45be2`, is "Multi-Backend + Streaming + External Config" — extending the backend / streaming / configuration story beyond v2.0.0 / v2.0.1.

---

## Version v2.1.0 - Multi-Backend + Streaming + External Config
*Commit:* `df45be2` — "Multi-Backend + Streaming + External Config" (parent `5fccb37` / v2.0.1)

> *Version note:* Git carries **no tag** for this commit, but `app/config/version.py` was updated to `"v.2.1.0"` within the commit itself — used directly as the authoritative version.

### Added
- **`app/models/factory.py`** — `create_client(config: ModelConfig) -> ModelClient` backend factory: defaults to `LlamaCppClient`, optionally builds `OllamaClient` behind a graceful `ImportError` guard (`OLLAMA_AVAILABLE`) so `main.py` stays blind to backend specifics.
- **`app/models/ollama_client.py`** (re-added; removed in v2.0.0) — `OllamaClient(ModelClient)` using `ollama.Client(host=base_url)`; implements `stream`/`on_token`.
- **`app/utils/server_manager.py`** — `is_port_open(port)` + `ensure_server_running(port, command, name="LLM")` (auto-launch via `subprocess.Popen`, waits up to 30s for the port). Auto-start wiring present but **commented out** in `main.py`.
- **`config.yaml`** — external YAML config: `default_model`, per-role `models` (`general`→llamacpp `@8080`; `coder`/`reasoner`/`autocomplete`→ollama `@11434`), plus `memory`/`context` sections (`retrieval_limit`, `min_confidence`, `max_tokens`, `safety_margin`).
- **Streaming contract** in `app/models/client.py` — `ModelClient.generate(..., stream: bool = False, on_token: Callable[[str], None] = None, **kwargs)` added to the Protocol; `Callable` imported.
- **Streaming paths** in both clients — `LlamaCppClient` and `OllamaClient` iterate chunks and invoke `on_token(delta)`; the llama.cpp path carries a "BUG 2 FIX" note (streaming was previously dead code after an early `return`).
- **`.gitignore`** — `*.pyc`, duplicate `.venv/`/`venv/`, and the `data/` directory ignore added.

### Changed
- **`app/config/version.py`**: `"v.2.0.0"` → `"v.2.1.0"`.
- **`app/config/settings.py`**:
  - `ModelConfig.backend: str = "llamacpp"` field added (`"llamacpp"` or `"ollama"`).
  - `models` dict indentation fixed (was over-indented to 8 spaces → 4); each `ModelConfig` now passes `backend=`.
  - `Settings.load()` now reads `config.yaml` via `yaml.safe_load` and overrides `default_model`, `models`, `memory`, `context`, `conversation`, `retrieval`, `ranking`; falls back to defaults if the file is absent (previously a stub returning `cls()`). `import yaml` added.
- **`app/models/client.py`** — `ModelResponse` docstring trimmed; `generate` signature extended with `stream`/`on_token`; property stubs collapsed to single-line `...`.
- **`app/models/llamacpp_client.py`** — `generate` split into a standard (non-stream) and a streaming path; streaming returns `ModelResponse(content=full_content, model=self._model)`.
- **`app/main.py`**:
  - Header "v2.0" → "v2.1.0"; imports `sys`, `create_client` (replaces direct `LlamaCppClient`), `ensure_server_running`; prints `Starting Jarvis...`.
  - **Dynamic model loading:** loops `settings.models`, calls `create_client(cfg)`, registers `router.register(TaskType(role), client)`; `router.set_default` from `"general"` (or first). Auto-start block commented out.
  - **Loop bug fix:** `input()` moved back to the top of the loop (v2.0.1 had it after a `try/except` + `continue`, making user input dead); now handles `EOFError`/`KeyboardInterrupt` → goodbye + `_cleanup()` + `break`.
  - **Streaming generation:** `selected_model.generate(fitted_messages, stream=True, on_token=lambda t: print(t, end="", flush=True))`, wrapped in `try/except` with `conversation.pop_last_message()` + `continue` on failure. Assistant message added after streaming; the old non-streaming `print` removed.

### Removed
- (none — no files deleted; the v2.0.1 broken `try/except`+`continue` placement around `input()` was restructured rather than removed.)

### Renamed / Moved
- (none)

### Dependencies
- `yaml` (PyYAML) now imported at runtime in `app/config/settings.py`. `requirements.txt` change is not present in this commit — *Reason (Inferred):* PyYAML may already be pinned or the manifest update lagged. The `ollama` package is required only when an ollama-backend model is actually selected (the factory raises `ImportError` otherwise).

### Documentation
- **`docs/DEVLOG.md`** (+159) — new `## v2.1.0 -` section plus internal before/after notes (router wiring, `main.py` blindness to backend).
- **`docs/changelog.md`** (+242) — formal `## v2.1.0 - Multi-Backend + Streaming + External Config` entry.
- **`docs/project_notes.md`** (+299) — large design-notes addition ("For v2.0", roadmap, etc.).

### Summary
v2.1.0 makes JARVIS genuinely multi-backend, streaming, and externally configurable. A `create_client` factory plus the restored `OllamaClient` bring Ollama back alongside llama.cpp, selected by a new per-model `backend` field read from `config.yaml`. The `ModelClient` contract gains `stream`/`on_token`, implemented by both backends, and the main loop now streams tokens live to the terminal. `Settings.load()` finally consumes `config.yaml` (YAML) instead of being a no-op stub. A `server_manager` utility offers auto-launch / health-check of LLM servers (wired but commented out). It also fixes a v2.0.1 loop defect where `input()` sat after a `continue` (dead input) by restoring it to the top of the loop with proper `EOFError`/`KeyboardInterrupt` handling.

### Possible Next Version (based on Git history)
The next commit, `b2c2211`, is "Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted" — introducing semantic / vector memory (chromaDB) and agent-driven git automation.

---

## Version v2.2.0 - Semantic Memory (chromaDB + hybrid retriever + conversation store)
*Commit:* `b2c2211` — "Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted" (parent `df45be2` / v2.1.0)

> *Version note:* Git carries **no tag** for this commit, but `app/config/version.py` was updated to `"v.2.2.0"` within the commit itself — used directly as the authoritative version.

### Added
- **`app/memory/vector_retriever.py`** — `VectorRetriever` (chromadb `PersistentClient`, collection `jarvis-memories`, cosine HNSW, `OllamaEmbeddingFunction` with model `nomic-embed-text` @ `http://localhost:11434`). Implements the `CandidateRetriever` Protocol (`find_candidates`, `on_memory_added`/`on_memory_removed`/`on_index_rebuilt`, `clear`); embeds `f"{category} {memory_type}: {value}"` for richer semantic matching.
- **`app/memory/hybrid_retriever.py`** — `HybridRetriever` runs `KeywordRetriever` + `VectorRetriever` in parallel, dedupes by memory ID, and satisfies the `CandidateRetriever` Protocol (drop-in for either alone). Comment rationale: keyword catches exact matches, vector catches semantic matches — "neither alone is sufficient".
- **`app/memory/conversation_store.py`** — `ConversationVectorStore` (separate chroma collection `jarvis-conversations`): `index_history` (one-time bulk pair import), `add_exchange`, `search` (returns `{"user","assistant"}` list), `count`; `_extract_pairs` handles both `Message` dataclass and raw dicts; metadata capped at 1000 chars (ChromaDB limit).
- **`ConversationManager.pop_last_message()`** in `app/conversation/manager.py` — error-recovery helper that pops + saves the last message.
- **`past_exchanges` support** in `app/prompt/builder.py` — `build(..., past_exchanges=None)` + `_format_past_exchanges` append a "## Relevant Past Exchanges" section to the system prompt.
- **`config.yaml`** — `memory.retrieval_limit` 20 → 5; `context.safety_margin` 100 → 500.

### Changed
- **`app/config/version.py`**: `"v.2.1.0"` → `"v.2.2.0"`.
- **`app/main.py`**:
  - Imports `KeywordRetriever`, `HybridRetriever`, `VectorRetriever`, `ConversationVectorStore`, `LlamaCppClient`.
  - `MemoryManager` now constructed with `retriever=HybridRetriever(vector=VectorRetriever(...), keyword=KeywordRetriever(min_keyword_overlap=1))`.
  - `conv_store = ConversationVectorStore(...)`; one-time `conv_store.index_history(conversation.get_all())` if empty (log "Indexed N exchanges").
  - Pipeline: `past_exchanges = conv_store.search(prompt, limit=2)` after memory retrieval; passed into `prompt_builder.build(past_exchanges=...)`.
  - `conv_store.add_exchange(prompt, response.content)` after each assistant reply.
  - `if selected_model is None: selected_model = router.default_model` fallback added. (plus minor blank-line/whitespace churn)
- **`app/models/ollama_client.py`** — `generate` rewritten to use Ollama's OpenAI-compatible `chat.completions.create` (was `ollama.Client.chat` dict API); now returns `tokens_used`/`finish_reason` and mirrors the llamacpp streaming structure ("BUG 2 FIX").
- **`app/models/llamacpp_client.py`** — removed unused `get_settings` import + `settings = get_settings()`; dropped the now-settled "BUG 2 FIX" comment in the streaming path.

### Removed
- (none — no files deleted) The old `ollama.Client.chat` / dict-based streaming path was replaced by the OpenAI-compatible API.

### Renamed / Moved
- (none)

### Dependencies
- `chromadb` (+ `OllamaEmbeddingFunction`) is now imported at runtime in `app/memory/vector_retriever.py` and `app/memory/conversation_store.py`. `requirements.txt` change is not present in this commit — *Reason (Inferred):* chromadb may already be pinned or the manifest update lagged. Ollama embedding model `nomic-embed-text` is assumed running at `:11434`.

### Documentation
- **`docs/changelog.md`** (+50) — `## v.2.2.0 - — Semantic Memory` entry (note: double-dash typo in the heading).
- **`docs/DEVLOG.md`** (+245) — new `## Relevant Past Exchanges`, `## Known User Facts`, and `# 2.2.0 - — Semantic Memory` sections plus notes.

### Summary
v2.2.0 layers **semantic / vector memory** onto the v2.1.0 keyword + multi-backend foundation. A new `VectorRetriever` (chromaDB + Ollama embeddings) and `HybridRetriever` (keyword ∪ vector, deduped by ID) are wired into `MemoryManager`, giving JARVIS meaning-based recall ("what do I enjoy?" → "I like coding") alongside exact-match keyword recall. A separate `ConversationVectorStore` embeds full user/assistant exchanges for semantic history retrieval, surfaced in the prompt as "Relevant Past Exchanges". The main loop indexes existing history once and stores each new exchange; `MemoryManager.retrieve` still touches/force-saves. `OllamaClient` was upgraded to Ollama's OpenAI-compatible `chat.completions` API (matching llamacpp), and `config.yaml` tightens `retrieval_limit` to 5 and raises `safety_margin` to 500. Also adds `ConversationManager.pop_last_message()` for error recovery and a `selected_model is None` router fallback.

### Anomaly (flagged)
The commit message references *"Agent imtegration for git automation with auto make devlog and change reverted"*, but **no agent source module appears in this commit's diff** (16 files, none agent-related). *Reason (Inferred):* the agent / git-automation feature is either documented/planned here or was reverted (the message literally says "and change reverted"), so it is not reflected in code in this commit. To be confirmed against later commits (e.g., `891fe4b` "Documentation agent wired").

### Possible Next Version (based on Git history)
The next (and final) commit, `891fe4b`, is tagged **`v2.2.1` / `v2.4.0` / `v2.4.1`** — "fix: v2.2.1 — Documentation agent wired, package structure fixed". (Triple tag on a single commit — anomaly to verify when documenting.)

---

## Version v2.2.1 - Documentation agent wired, package structure fixed
*Commit:* `891fe4b` — "fix: v2.2.1 — Documentation agent wired, package structure fixed" (parent `b2c2211` / v2.2.0). **This is `HEAD` (final commit in the repo).**

> **Version note (anomaly — read carefully):** This single commit carries **three Git tags**: `v2.2.1`, `v2.4.0`, and `v2.4.1` (`git tag --points-at 891fe4b` confirms all three; they are the only tags besides `v2.0.0`). Meanwhile `app/config/version.py` was **not** modified by this commit and still reads `"v.2.2.0"` at HEAD, and the new agent source docstrings (`app/agents/doc_agent.py`) reference "JARVIS v2.4.0" and "v3.0". So there are **four conflicting version signals**: `v2.2.0` (declared `version.py`), `v2.2.1` (commit message + one tag), `v2.4.0` (tag + docstrings), `v2.4.1` (tag). The block is titled **v2.2.1** to match the commit message / lowest tag, but all three tags are recorded. Treat the version sequence as inconsistent in the repo itself.

### Added
- **`app/agents/doc_agent.py`** (228) — `DocumentationAgent` (a mini agentic loop where JARVIS documents its own evolution): `__init__(self, model: ModelClient)`, `run(self, task: str, verbose: bool = True) -> str`, and module-level `run_interactive(agent) -> None`. Reads git history/diffs + existing `docs/CHANGELOG.md`/`docs/DEVLOG.md`, generates matching entries, writes them (with confirmation). Uses a prompt-based `<tool_call>{...}</tool_call>` tag format (works on any local model; docstring notes the v3.0 upgrade path is "one method change in ModelClient").
- **`app/tools/base.py`** (131) — tool primitives: `ToolResult` (`__str__`/`__bool__`), `ToolDefinition` (`execute`, `to_openai_schema`), `ToolRegistry` (`register`, `register_many`, `get`, `all`, `to_openai_schemas`, `format_for_prompt`).
- **`app/tools/executor.py`** (146) — `ToolExecutor` (`__init__(registry, require_confirmation=True)`, `has_calls`, `parse`, `run`, `format_result`) + `ParsedCall`. Parses `<tool_call>...</tool_call>` via `_TOOL_CALL_RE` (tolerant of whitespace/newlines, `re.DOTALL | re.IGNORECASE`) — the "Regex fix … for large tool_call JSON blocks". Caps tool output at `MAX_OUTPUT_CHARS = 4096` to prevent context overflow; wraps all failures so the agent loop never sees raw exceptions.
- **`app/tools/file_tools.py`** (123) — `read_file`, `write_file` functions + `FILE_TOOLS` registry.
- **`app/tools/git_tools.py`** (156) — `_run_git`, `git_log`, `git_diff_stat`, `git_diff_full`, `git_status`, `git_show`, `git_tags`, `git_branch` functions + `GIT_TOOLS` registry.
- **`app/context/__init__.py`, `app/conversation/__init__.py`, `app/prompt/__init__.py`** — empty `__init__.py` files added (package-structure fix so `from app.context…` / `app.conversation…` / `app.prompt…` import cleanly).
- **`tests/stress_test.py`** (626) — new stress-test script.
- **`docs/CHANGELOG_recovered.md`** (+515) and **`docs/DEVLOG_recovered.md`** (+1259) — recovered/parallel doc copies.

### Changed
- **`app/main.py`**:
  - Imports `DocumentationAgent, run_interactive`.
  - Constructs `doc_agent = DocumentationAgent(model=router.select(TaskType.DOCS) if TaskType.DOCS in router.models else router.default_model)`.
  - New `docs` CLI command: `if prompt == "docs": print("DEBUG: intercepted"); try: run_interactive(doc_agent) except Exception: traceback.print_exc(); continue`. (A `print("DEBUG: intercepted")` debug line remains — *Reason (Inferred):* leftover; harmless.)
  - Pipeline step comments renumbered (5 → 5, then 6–10); no change to retrieval/prompt/generation logic beyond the agent wiring.
- **`app/models/router.py`** — `TaskType.DOCS = "docs"` added to the enum (the commit message's "TaskType.DOCS added to router"). ("ModelRouter dead code fixed — routing now active" per commit message; routing has been live since v2.0.1's loop integration.)
- **`config.yaml`** — new `docs` model (`qwen3-8b.gguf`, role `docs`, backend `llamacpp`, `base_url="http://localhost:8080/v1"`).
- **`docs/CHANGELOG.md`** (+25) — release entry added.
- **`docs/DEVLOG.md`** (net **−1270**) — heavily rewritten/reduced (parallel `docs/DEVLOG_recovered.md` added alongside).

### Removed
- **`__pycache__/*.pyc` removed from Git tracking** — `app/__pycache__/__init__.cpython-314.pyc`, `app/__pycache__/main.cpython-314.pyc`, `app/config/__pycache__/__init__.cpython-314.pyc`, `app/config/__pycache__/settings.cpython-314.pyc` all deleted in Git (binary size → 0). *Reason (Inferred):* clean-up of committed bytecode; `.gitignore` already ignored `__pycache__/`, so this detaches already-tracked artifacts.

### Renamed / Moved
- `docs/DEVLOG.md` content was substantially moved/reset into `docs/DEVLOG_recovered.md` (and `docs/CHANGELOG_recovered.md` added as a parallel copy) — *Reason (Inferred):* a "recovered" baseline was split out from the active devlog.

### Dependencies
- No new third-party dependencies. New code uses only the standard library (`json`, `re`, `subprocess` via `git_tools`, `datetime`). `requirements.txt` unchanged in this commit.

### Documentation
- **`docs/CHANGELOG.md`** (+25) — new release entry.
- **`docs/CHANGELOG_recovered.md`** (+515) — recovered changelog copy.
- **`docs/DEVLOG_recovered.md`** (+1259) — recovered devlog copy.
- **`docs/DEVLOG.md`** (−1270 net) — heavily rewritten.

### Summary
The final commit wires in the **DocumentationAgent** — a mini agentic loop in which JARVIS documents its own evolution — backed by a new **tool infrastructure**: `ToolRegistry`, `ToolExecutor` (prompt-based `<tool_call>` parsing with a whitespace/newline-tolerant regex and a 4096-char output cap), and `git_tools`/`file_tools` (read/write file + git log/diff/status/show/tags/branch). The agent is reachable via a new `docs` CLI command. Package structure is fixed by adding empty `__init__.py` to the `context`, `conversation`, and `prompt` packages, and a `docs` model + `TaskType.DOCS` are registered. `__pycache__` bytecode is removed from Git tracking, a new `tests/stress_test.py` is added, and recovered doc copies (`CHANGELOG_recovered.md`, `DEVLOG_recovered.md`) are introduced while `DEVLOG.md` is heavily rewritten.

### Version inconsistency (flagged)
As noted above, this commit is tagged **three** ways (`v2.2.1`, `v2.4.0`, `v2.4.1`) yet `version.py` stays at `"v.2.2.0"` and the agent docstrings say "v2.4.0". The repo's own version history is internally inconsistent from here forward; any consumer should not assume monotonic `version.py` == Git tag.

### Possible Next Version (based on Git history)
This is the **last commit in the repository** (`HEAD`). No further commits exist. Per the docstrings, the intended next milestones are **v2.4.2** (patch on the `v2.4.x` tag line) and **v3.0** (native function calling — the stated upgrade path that would replace the prompt-based `<tool_call>` parsing with model-returned structured JSON, leaving `ToolExecutor`/`ToolRegistry` unchanged). The changelog now covers **all 26 commits** (v0.0.0 → v2.2.1).