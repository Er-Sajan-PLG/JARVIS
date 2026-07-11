# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Scope: This document records the project's foundational development — the first ten
> commits, inspected oldest to newest (`1999e53` → `3cc9e4b`). It covers the project
> from initial scaffolding through the first conversational CLI with system-prompt
> identity and multi-turn history. Entries are listed in chronological order.

---

# Version v0.0.0 (2026-06-27)

## Added
- Initial project skeleton: placeholder `.gitignore`, `README.md`, `app/__init__.py`, and an empty `app/main.py`.
- `app/` package layout — `__init__.py` created for `agents`, `api`, `brain`, `config`, `memory`, `models`, `tools`, `utils`.
- `requirements.txt` with 117 fully pinned dependency versions.
- `.gitignore` tuned for Python projects.
- `docs/ARCHITECTURE.md` (modular, single-responsibility architecture philosophy) and `docs/ROADMAP.md`.

### Code — `.gitignore` (full)
```gitignore
# Python
__pycache__/
*.py[cod]
*.so

# Virtual Environment
.venv/

# Environment Variables
.env

# IDE
.vscode/
.idea/

# Logs
*.log

# Build artifacts
build/
dist/
*.egg-info/

# OS files
.DS_Store
Thumbs.db
```

### Dependencies — `requirements.txt` (117 pinned packages; categorized highlights)
```text
# LLM / ML runtime
ollama==0.6.2
torch==2.12.1
transformers==5.12.1
sentence-transformers==5.6.0
onnxruntime==1.27.0
chromadb==1.5.9

# Numerics / data
numpy==2.5.0
scipy==1.18.0
scikit-learn==1.9.0
PyYAML==6.0.3
orjson==3.11.9

# Web / API
fastapi==0.138.1
uvicorn==0.49.0
starlette==1.3.1
httpx==0.28.1
aiohttp==3.14.1
websockets==16.0

# Config / CLI
pydantic==2.13.4
pydantic-settings==2.14.2
typer==0.25.1
python-dotenv==1.2.2
click==8.4.2

# GPU / CUDA (local runtime)
cuda-toolkit==13.0.2
nvidia-cublas==13.1.1.3
nvidia-cuda-runtime==13.0.96
nvidia-cudnn-cu13==9.20.0.48
# ... plus ~90 additional pinned transitive packages
```
> The full pinned list is stored in `requirements.txt` at the repository root.

---

# Version v0.1.0 (2026-06-27)

## Added
- `OllamaClient` (`app/models/ollama_client.py`) — a single-turn client for a local Ollama instance.
- `app/config/settings.py` — `DEFAULT_MODEL`, `OLLAMA_HOST`, `APP_NAME`, `VERSION`.
- Single-turn CLI entry point (`app/main.py`).

### Code — `app/config/settings.py` (full)
```python
DEFAULT_MODEL = "deepseek-r1:32b"
OLLAMA_HOST = "http://localhost:11434"
APP_NAME = "Jarvis"
VERSION = "0.1.0"
```

### Code — `app/models/ollama_client.py` (full)
```python
from ollama import chat


class OllamaClient:
    def __init__(self, model: str):
        self.model = model

    def ask(self, prompt: str) -> str:
        response = chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        return response["message"]["content"]
```

### Code — `app/main.py` (relevant part)
```python
client = OllamaClient(model=DEFAULT_MODEL)

prompt = input("You: ")
answer = client.ask(prompt)
print(f"\nJarvis: {answer}")
```

---

# Version v0.2.0 (2026-06-27)

## Added
- Interactive CLI chat loop with a `quit` command to exit the session gracefully.

### Code — `app/main.py` loop (full change)
```python
while True:
    prompt = input("You: ")

    if prompt == 'quit':
        print("Good Bye")
        break

    answer = client.ask(prompt)
    print(f"\nJarvis: {answer}")
```

---

# Version v0.3.0 (2026-06-27)

## Added
- `app/config/prompt.py` defining the `SYSTEM_PROMPT` that establishes Jarvis's assistant identity.
- System message injected into Ollama requests, so the assistant identity is applied on every call.

## Fixed
- Corrected an incorrect import path (`app.config.prompts` → `app.config.prompt`) that prevented the system prompt module from loading.

### Code — `app/config/prompt.py` (full)
```python
SYSTEM_PROMPT = """
You are Jarvis.

You are an AI assistant focused on engineering, STEM, learning,
programming, productivity, and problem solving.

Be logical.
Be honest.
Explain your reasoning.
If you are uncertain, say so.
"""
```

### Code — `app/models/ollama_client.py` (relevant change: injected system message)
```python
response = chat(
    model=self.model,
    messages=[
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": prompt,
        }
    ],
)
```

### Code — Fix (import path)
```python
-from app.config.prompts import SYSTEM_PROMPT
+from app.config.prompt import SYSTEM_PROMPT
```

---

# Version v0.4.0 (2026-06-28)

## Added
- Multi-turn conversation history: `OllamaClient` keeps an in-memory `conversation` list seeded with the system prompt and appends user/assistant turns, so context persists across the session.

## Changed
- Default model switched from `deepseek-r1:32b` to `qwen3:8b` to speed up local development.

## Removed
- Accidentally committed `__pycache__` bytecode (`.pyc`) files removed from version control.

### Code — `app/models/ollama_client.py` (key parts: stateful client)
```python
from ollama import chat
from app.config.prompt import SYSTEM_PROMPT


class OllamaClient:
    def __init__(self, model: str):
        self.model = model
        self.conversation = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    def ask(self, prompt: str) -> str:
        self.conversation.append({"role": "user", "content": prompt})
        response = chat(model=self.model, messages=self.conversation)
        answer = response["message"]["content"]
        self.conversation.append({"role": "assistant", "content": answer})
        return answer
```

### Code — `app/config/settings.py` (model change; full file)
```python
DEFAULT_MODEL = "qwen3:8b"
OLLAMA_HOST = "http://localhost:11434"
APP_NAME = "Jarvis"
VERSION = "0.1.0"
```

---

# Version v0.5.0 (2026-06-28)

## Added
- Persistent conversation memory: a new `MemoryManager` (`app/memory/manager.py`) loads and saves the chat to `app/memory/conversation.json` so the dialogue survives process restarts.
- `app/memory/conversation.json` seed store holding an initial system message and a sample exchange.
- `OllamaClient` now receives an external `conversation` instead of building its own — the client no longer injects `SYSTEM_PROMPT` internally.
- `app/main.py` wires `MemoryManager` in: load on start, save after every turn.

## Changed
- `app/main.py` constructs `OllamaClient(model, conversation)` from the loaded file and saves `client.conversation` back after each answer.

### Code — `app/memory/manager.py` (full, initial version)
```python
import json


class MemoryManager:

    def __init__(self, path: str):
        self.path = path

    def load(self):
        with open(self.path, "r") as file:
            conversation = json.load(file)
        return conversation

    def save(self, conversation):
        with open(self.path, "w") as file:
            json.dump(conversation, file, indent=4)

    def clear(self):
        conversation = new_conversation()
        self.save(conversation)
```
> Note: `clear()` references `new_conversation()`, which is only defined in a later commit.

### Code — `app/models/ollama_client.py` (relevant change: external conversation)
```python
-from ollama import chat
-from app.config.prompt import SYSTEM_PROMPT
+from ollama import chat
+
 
 class OllamaClient:
-    def __init__(self, model: str):
+    def __init__(self, model: str, conversation : str):
         self.model = model
-        self.conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
+        self.conversation = conversation
```

### Code — `app/main.py` (relevant wiring)
```python
memory = MemoryManager(path="app/memory/conversation.json")
conversation = memory.load()
client = OllamaClient(model=DEFAULT_MODEL, conversation=conversation)
...
answer = client.ask(prompt)
memory.save(client.conversation)
```

---

# Version v0.6.0 (2026-06-28)

## Added
- Keyword-based fact extraction: new `app/memory/fact_extractor.py` with `extract_fact()` that pulls simple user facts from messages ("i like", "i am", "i prefer", "remember that").
- `MemoryManager` now stores `facts` separately from the conversation — `load()`/`save()` use a `{"conversation": [...], "facts": [...]}` structure, with backward-compatible handling of the old plain-list format.
- `MemoryManager.add_fact(fact)` appends to the persisted facts list.
- `app/main.py` extracts a fact from each user message and persists it alongside the conversation.

### Code — `app/memory/fact_extractor.py` (full)
```python
def extract_fact(message: str):
    msg = message.lower()

    if "i like" in msg:
        return "user likes " + msg.split("i like")[1].strip()

    if "i am" in msg:
        return "user is " + msg.split("i am")[1].strip()

    if "i prefer" in msg:
        return "user prefers " + msg.split("i prefer")[1].strip()

    if "remember that" in msg:
        return msg.replace("remember that", "user").strip()

    return None
```

### Code — `app/memory/manager.py` (facts storage; key parts)
```python
def __init__(self, path: str):
    self.path = path
    self.facts = []

def load(self):
    try:
        with open(self.path, "r") as file:
            data = json.load(file)
        if isinstance(data, list):            # OLD FORMAT
            conversation, self.facts = data, []
        else:                                  # NEW FORMAT (dict)
            conversation = data.get("conversation", [])
            self.facts = data.get("facts", [])
    except FileNotFoundError:
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.facts = []
    return conversation, self.facts

def save(self, conversation, facts):
    data = {"conversation": conversation, "facts": facts}
    with open(self.path, "w") as file:
        json.dump(data, file, indent=4)

def add_fact(self, fact):
    self.facts.append(fact)
```

### Code — `app/main.py` (relevant wiring)
```python
conversation, facts = memory.load()
client = OllamaClient(model=DEFAULT_MODEL, conversation=conversation)
...
answer = client.ask(prompt)

fact = extract_fact(prompt)
if fact:
    memory.add_fact(fact)

memory.save(conversation=client.conversation, facts=memory.facts)
```

---

# Version v0.7.0 (2026-06-28)

## Added
- Context builder: `OllamaClient.build_messages()` assembles the system prompt, an optional facts system message, and the conversation into the final message list sent to the model.
- Long-term facts are now injected into every request via a synthetic system message that lists known facts.
- `OllamaClient.__init__` now accepts a `facts` list; `app/main.py` passes `facts=facts`.

## Changed
- `app/config/prompt.py` extended with the rule: "Do not repeat previous answers. If similar question appears, rephrase or extend."
- `OllamaClient.ask()` now sends `build_messages()` instead of the raw conversation.

### Code — `app/models/ollama_client.py` (key parts: `build_messages`)
```python
def __init__(self, model: str, conversation: list, facts: list):
    self.model = model
    self.SYSTEM_PROMPT = SYSTEM_PROMPT
    self.conversation = conversation
    self.facts = facts

def build_messages(self) -> list:
    messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
    if self.facts:
        facts_text = "Here are some known facts:\n"
        for fact in self.facts:
            facts_text += f"- {fact}\n"
        messages.append({"role": "system", "content": facts_text})
    messages.extend(self.conversation)
    return messages
```

### Code — `app/main.py` (pass facts to client)
```python
client = OllamaClient(
    model=DEFAULT_MODEL,
    conversation=conversation,
    facts=facts
)
```

### Code — `app/config/prompt.py` (added line)
```python
+Do not repeat previous answers. If similar question appears, rephrase or extend.
```

---

> Dependencies: commits 11–15 introduced **no new third-party dependencies** — they rely on the existing `ollama` SDK and the Python standard library (`json`).

---

# Version v0.8.0 (2026-06-29)

## Added
- Structured memory: facts are now stored as dicts with `category`, `type`, and `value` instead of plain strings.
- Rule-based extraction engine: new `app/memory/rules.py` with a `RULES` table covering identity, preferences, skills, goals, plans, tasks, location, and profession triggers.
- `app/config/version.py` introduced (`VERSION = "0.8.0"`); `app/main.py` banner now prints `JARVIS {VERSION}`.
- `app/memory/fact_extractor.py` rewritten to match against `RULES` and return a structured fact dict.

## Changed
- `OllamaClient.build_messages()` now renders facts as `- [category] type → value`; in this commit the conversation-history extension is commented out (debugging state), so only system prompt + facts are sent.

### Code — `app/config/version.py` (full)
```python
VERSION = "0.8.0"
```

### Code — `app/memory/fact_extractor.py` (rule-based extraction)
```python
from app.memory.rules import RULES

def extract_fact(message: str):
    msg = message.lower()
    for rule in RULES:
        if rule["trigger"] in msg:
            trigger = rule["trigger"]
            category = rule["category"]
            type_ = rule["type"]
            idx = msg.find(trigger)
            value = msg[idx + len(trigger):]
            return {"category": category, "type": type_, "value": value}
    return None
```

### Code — `app/memory/rules.py` (representative subset; 20+ rules total)
```python
RULES = [
    {"trigger": "i am ",        "category": "identity",    "type": "state"},
    {"trigger": "my name is ",  "category": "identity",    "type": "name"},
    {"trigger": "i like ",      "category": "preference",  "type": "like"},
    {"trigger": "i prefer ",    "category": "preference",  "type": "preference"},
    {"trigger": "i can ",       "category": "skills",      "type": "ability"},
    {"trigger": "i want to ",   "category": "goals",       "type": "desire"},
    {"trigger": "i am in ",     "category": "location",    "type": "current_position"},
    {"trigger": "i am a ",      "category": "profession",  "type": "job_title"},
    # ... plus plans, tasks, and more preference/skills/location rules
]
```

### Code — `app/models/ollama_client.py` (facts rendering; conversation extension disabled)
```python
if self.facts:
    facts_text = "Known user facts:\n"
    for fact in self.facts:
        facts_text += (
            f"- [{fact['category']}] "
            f"{fact['type']} → {fact['value']}\n"
        )
    messages.append({"role": "system", "content": facts_text})

# messages.extend(self.conversation)   # <-- disabled in this commit (debugging)
```

---

# Version v0.9.0 (2026-06-29)

## Added
- Multi-fact extraction pipeline: `extract_fact()` → `extract_facts()` now splits a message into sentences and returns a **list** of fact dicts (one per matching sentence).
- `app/main.py` loops over the returned facts and calls `memory.add_fact()` for each.
- Conversation-history extension re-enabled in `OllamaClient.build_messages()`.

### Code — `app/memory/fact_extractor.py` (key parts: sentence split + multi-fact)
```python
def _split_into_sentences(message: str) -> list[str]:
    sentences, current = [], []
    for char in message:
        current.append(char)
        if char in ".!?":
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []
    if current:
        leftover = "".join(current).strip()
        if leftover:
            sentences.append(leftover)
    return sentences

def extract_facts(message: str) -> list[dict]:
    facts = []
    for sentence in _split_into_sentences(message):
        lowered = sentence.lower()
        for rule in RULES:
            if rule["trigger"] in lowered:
                idx = lowered.find(rule["trigger"])
                value = lowered[idx + len(rule["trigger"]):].strip()
                facts.append({
                    "category": rule["category"],
                    "type":     rule["type"],
                    "value":    value,
                })
                break  # first matching rule wins per sentence
    return facts
```

### Code — `app/main.py` (relevant wiring)
```python
facts = extract_facts(prompt)
for fact in facts:
    memory.add_fact(fact)
```

### Code — `app/models/ollama_client.py` (conversation re-enabled)
```python
messages.extend(self.conversation)   # re-enabled
```

---

# Version v1.0.0 (2026-06-29)

## Added
- Behavior-driven memory engine: `MemoryManager` now applies `append`, `replace`, or `ignore` semantics based on each rule's `behavior` field.
- `MemoryManager.apply_behavior()` and `replace_fact()` (replaces an existing fact when `category`+`type` match, otherwise appends).
- Every rule in `app/memory/rules.py` gained a `behavior` field (default `append`).
- Extracted facts now carry a `behavior` field propagated from the matching rule; trailing punctuation is stripped from values.

## Changed
- `MemoryManager.add_fact()` now routes through `apply_behavior()` instead of a plain `append`.

### Code — `app/memory/fact_extractor.py` (behavior field added)
```python
value = lowered[idx + len(rule["trigger"]):].strip().rstrip(".!?")
facts.append({
    "category": rule["category"],
    "type":     rule["type"],
    "value":    value,
    "behavior": rule["behavior"],
})
```

### Code — `app/memory/manager.py` (behavior engine; key parts)
```python
def add_fact(self, fact: dict):
    self.apply_behavior(fact)

def apply_behavior(self, fact: dict):
    behavior = fact.get("behavior", "append")
    if behavior == "append":
        self.facts.append(fact)
    elif behavior == "replace":
        self.replace_fact(fact)
    elif behavior == "ignore":
        return

def replace_fact(self, new_fact: dict):
    for i, existing in enumerate(self.facts):
        if (existing["category"] == new_fact["category"]
                and existing["type"] == new_fact["type"]):
            self.facts[i] = new_fact
            return
    self.facts.append(new_fact)
```

### Code — `app/memory/rules.py` (rule with behavior)
```python
{"trigger": "i am ", "category": "identity", "type": "state", "behavior": "append"}
```

---

# Version v1.1.0 (2026-06-29)

## Added
- Multi-trigger rules: each rule now uses a `triggers` **list** of phrasings (e.g. `"i am "`, `"i'm "`) instead of a single `trigger`; duplicate preference rules (`i prefer`, `i enjoy`) were merged into one rule's trigger list.
- `app/memory/reasoner.py` (new) — `decide_behavior()` stub that returns a fact's `behavior` (placeholder for future reasoning logic).
- `app/config/version.py` bumped to `v1.1`.

## Changed
- `app/memory/fact_extractor.py` now iterates `rule["triggers"]` to detect a match.
- Removed debug `print()` calls from `app/main.py`, `app/memory/manager.py`, and `app/models/ollama_client.py`; the version string's closing quote was fixed (`"v.1.1"`).
- Documentation expanded: `docs/ARCHITECTURE.md` (+213 lines) and dev/notes docs.

### Code — `app/memory/rules.py` (multi-trigger example)
```python
{
    "triggers": ["i am ", "i'm "],
    "category": "identity",
    "type": "state",
    "behavior": "append",
},
{
    "triggers": ["i like ", "i love ", "i enjoy ", "i prefer ",
                 "i'm into ", "i'm a fan of "],
    "category": "preference",
    "type": "like",
    "behavior": "append",
},
```

### Code — `app/memory/fact_extractor.py` (triggers loop)
```python
for rule in RULES:
    for trigger in rule["triggers"]:
        if trigger in lowered:
            idx = lowered.find(trigger)
            value = lowered[idx + len(trigger):].strip().rstrip(".!?")
            facts.append({
                "category": rule["category"],
                "type":     rule["type"],
                "value":    value,
                "behavior": rule["behavior"],
            })
            break
```

### Code — `app/memory/reasoner.py` (full)
```python
def decide_behavior(new_fact, existing_facts):
    """
    Decide how a new fact should be stored.
    Returns: "append" / "replace" / "ignore"
    """
    return new_fact["behavior"]
```

### Code — `app/config/version.py` (version bump)
```python
-VERSION = "0.8.0"
+VERSION = "v.1.1"   # (closing quote fixed in a later cleanup commit)
```

---

> Dependencies: commits 16–21 introduced **no new third-party dependencies** — they build on the existing `ollama` SDK and Python standard library (`json`, `pprint`).

---

# Version v2.0.0 (2026-07-03)

> Commit `8519f65` — `feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul`.
> A major paradigm shift from the monolithic v1 design to a modular, pipeline-driven
> architecture. This is a large commit (~2,400 insertions across 23 files); snippets
> show the most important new components. (Raw version string in code: `"v.2.0.0"`.)

## Added
- **Modular memory subsystem** decomposed from the monolithic `MemoryManager` into focused components:
  - `app/memory/schema.py` — `Memory`/`MemoryResult` dataclasses with rich metadata (category, type, value, behavior, `created_at`/`updated_at`/`last_used`, confidence, importance, access_count).
  - `app/memory/store.py` — `MemoryStore` (low-level CRUD + dirty-tracked JSON persistence; handles v1→v2 migration).
  - `app/memory/retrieval.py` — `KeywordRetriever` (`CandidateRetriever` protocol) for keyword-based candidate finding.
  - `app/memory/ranking.py` — `MemoryRanker` with weighted scoring (relevance/importance/frequency/recency/confidence).
- **Model layer**: `app/models/client.py` (`ModelClient` protocol + `ModelResponse`), `app/models/llamacpp_client.py` (OpenAI-compatible client), `app/models/router.py` (`ModelRouter` with score-based `TaskType` classification).
- **Prompt/context**: `app/prompt/builder.py` (`PromptBuilder`) assembles one system message (system prompt + retrieved facts) + conversation; `app/context/manager.py` (`ContextWindowManager`) trims in user/assistant PAIRS.
- **Conversation manager** `app/conversation/manager.py`; **token counting** `app/utils/tokenizer.py` (tiktoken → transformers → word fallback).
- **Central config** `app/config/settings.py` rewritten around typed dataclasses (`ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, `PathsConfig`).
- Conversation storage moved to plural `data/conversations/`; memories persisted at `data/memories.json`.

## Changed
- **Pipeline reordered**: facts are now Extracted + Stored BEFORE retrieval, so a just-stored fact is available for personalization in the same turn.
- `OllamaClient` (`app/models/ollama_client.py`) removed; generation flows through `ModelClient`/`ModelRouter` + `PromptBuilder`.
- Token counting uses a real tokenizer; `ModelRouter` uses score-based classification (no first-match order bias).
- `fact_extractor.py` gained boundary detection (stops at conjunctions) to avoid garbage fact values.
- Strict offline mode (`local_files_only`) enforced for HuggingFace loads; graceful OpenAI API error handling added to the main loop; double system-message formatting fixed.

## Breaking
- Memory JSON schema changed: single `timestamp` replaced by immutable `created_at` + mutable `updated_at` (auto-migrated, clean `data/` wipe recommended).
- Conversation path changed to plural `data/conversations/`.
- `MemoryManager` public API changed substantially (`store()`, `retrieve()`, …); v1 callers are incompatible.

### Code — `app/config/version.py` (full)
```python
VERSION = "v.2.0.0"
```

### Code — `app/memory/schema.py` (`Memory` dataclass, key parts)
```python
@dataclass
class Memory:
    category: str
    memory_type: str
    value: str
    behavior: str = "append"

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.time)   # immutable
    updated_at: float = field(default_factory=time.time)   # mutable
    last_used: float = field(default_factory=time.time)

    confidence: float = 1.0
    importance: float = 0.5
    access_count: int = 0

    def format_for_prompt(self) -> str:
        return f"- [{self.category}] {self.memory_type}: {self.value}"
    # from_dict() migrates v1 single "timestamp" -> created_at/updated_at
```

### Code — `app/memory/store.py` (dirty-tracked persistence, key parts)
```python
class MemoryStore:
    def add(self, memory: Memory) -> Memory:
        self._memories.append(memory)
        self._dirty = True
        return memory

    def save(self) -> None:
        if not self._dirty:
            return
        data = {"version": "2.0", "memories": [m.to_dict() for m in self._memories]}
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        self._dirty = False
```

### Code — `app/memory/retrieval.py` (keyword candidate finding, key part)
```python
class KeywordRetriever:
    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        query_keywords = self._extract_keywords(query)
        candidates = []
        for memory in self._memories:
            if query_keywords & self._get_memory_keywords(memory):
                candidates.append(memory)
                if len(candidates) >= limit:
                    break
        return candidates
```

### Code — `app/memory/ranking.py` (weighted ranking, key parts)
```python
@dataclass
class RankingWeights:
    relevance: float = 0.35
    importance: float = 0.25
    frequency: float = 0.15
    recency: float = 0.15
    confidence: float = 0.10

class MemoryRanker:
    def rank(self, candidates, query, limit=20, min_score=0.0) -> list[MemoryResult]:
        # scores each candidate on relevance/importance/frequency/recency/confidence
        # returns MemoryResult list sorted by score (highest first)
        ...
```

### Code — `app/models/router.py` (score-based routing, key parts)
```python
class ModelRouter:
    KEYWORDS = {
        TaskType.CODE: ["code", "function", "class", "bug", "debug", ...],
        TaskType.STEM: ["math", "calculate", "equation", "physics", ...],
        TaskType.REASONING: ["think", "analyze", "reason", "logic", ...],
    }

    def _classify_prompt(self, prompt: str) -> TaskType:
        scores = {t: sum(1 for kw in kws if kw in prompt.lower())
                  for t, kws in self.KEYWORDS.items()}
        # score-based: max score wins (no order bias);
        # tie-break prefers CODE > STEM > REASONING > GENERAL
        ...
```

### Code — `app/utils/tokenizer.py` (counter selection, key part)
```python
@lru_cache(maxsize=1)
def get_token_counter(model_name: str = "default") -> Callable[[str], int]:
    counter = _try_tiktoken(model_name)      # 1. tiktoken (most accurate)
    if counter: return counter
    counter = _try_transformers(model_name)  # 2. transformers (Llama)
    if counter: return counter
    return _word_counter                      # 3. word fallback
```

### Code — `app/prompt/builder.py` (single system message + conversation)
```python
class PromptBuilder:
    def build(self, memories=None, conversation=None, user_prompt="") -> list[dict]:
        system_parts = [self.system_prompt]
        if memories:
            system_parts.append(self._format_memories(memories))
        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        if conversation:
            messages.extend(conversation)
        if user_prompt and (not conversation or conversation[-1].get("content") != user_prompt):
            messages.append({"role": "user", "content": user_prompt})
        return messages
```

### Code — `app/context/manager.py` (pair-preserving trim, key concept)
```python
class ContextWindowManager:
    # Trims conversation in user/assistant PAIRS (not individual messages)
    # to preserve conversational coherence; never breaks an exchange.
    def fit(self, messages, max_tokens=None) -> list[dict]: ...
```

### Code — `app/config/settings.py` (typed config, key parts)
```python
@dataclass
class MemoryConfig:
    max_memories: int = 1000
    retrieval_limit: int = 20
    min_relevance_score: float = 0.1
    candidate_overshoot_factor: int = 3

@dataclass
class RankingConfig:
    weight_relevance: float = 0.35
    weight_importance: float = 0.25
    weight_frequency: float = 0.15
    weight_recency: float = 0.15
    weight_confidence: float = 0.10

@dataclass
class PathsConfig:
    data_dir: Path = field(default_factory=lambda: Path("data"))
    @property
    def memories(self) -> Path: return self.data_dir / "memories.json"
    @property
    def conversations_dir(self) -> Path: return self.data_dir / "conversations"
```

### Code — `app/main.py` (new pipeline: extract/store BEFORE retrieve)
```python
# Per turn:
#   1. Build context   2. Extract facts   3. Store facts (BEFORE retrieve)
#   4. Retrieve relevant memories (includes just-stored facts)   5. Generate
facts = extract_facts(prompt)
for fact in facts:
    stored = memory.store(fact)

relevant_memories = memory.retrieve(prompt, limit=settings.memory.retrieval_limit)
messages = prompt_builder.build(memories=relevant_memories, conversation=conversation, user_prompt=prompt)
response = model.generate(messages)
```

### Dependencies
- New runtime imports introduced by this commit: **`openai`** (used by `LlamaCppClient` via the OpenAI-compatible API) and **`tiktoken`** (optional, for accurate token counting).
- `transformers` / `sentence-transformers` (already pinned) back the tokenizer fallback.
- Note: `requirements.txt` was **not** updated in this commit to pin the new `openai`/`tiktoken` dependencies.

---

# Version v2.0.1 (2026-07-04)

> Scope: First post-v2.0.0 patch. Bug fixes for the new modular runtime plus the initial round of project documentation (`ARCHITECTURE.md`, `DEVLOG.md`, and a separate `docs/changelog.md`). Note: `app/config/version.py` still reported `VERSION = "v.2.0.0"` at this commit — the version constant was bumped in a later commit.

## Changed
- `ConversationConfig.save_on_every_message` flipped `False` → `True` so the conversation is persisted after every exchange.
- `MemoryManager` persistence calls switched from lazy/`dirty`-based saves to explicit `force_save()`.
- `LlamaCppClient` now resolves its default model name through the new `get_default_model()` accessor instead of reading `settings.default_model` directly.
- `app/main.py` chat loop restructured: generation moved into a `try/except` with model-unavailable handling, and the `ModelRouter` was wired in to pick the backend per prompt.

## Fixed
- Model-unavailable crashes no longer abort the session: the loop catches `Exception`, prints a hint, and pops the just-added user message.
- `LlamaCppClient` default-model resolution decoupled from the `Settings` singleton via `get_default_model()`.

## Added
- A second model entry, `autocomplete`, with its own `base_url`/`max_tokens`, registered in `Settings.models`.
- `get_default_model()` helper in `app/config/settings.py`.
- Project docs: `docs/ARCHITECTURE.md` (new, ~329 lines), expanded `docs/DEVLOG.md`, and `docs/changelog.md` (lower-level log).

## Removed
- The `_DefaultModel` class and the `DEFAULT_MODEL` instance in `app/config/settings.py` (replaced by `get_default_model()`).

### Code — `app/config/settings.py` (save-on-every-message + new autocomplete model + `get_default_model`)
```python
@dataclass
class ConversationConfig:
    """Conversation management configuration"""
    max_recent_messages: int = 20
    enable_summarization: bool = False
    save_on_every_message: bool = True   # was: False

# models dict gained base_url + a dedicated autocomplete backend
models: dict = field(default_factory=lambda: {
    "general": ModelConfig(
        name="llama-3.2-3b-instruct-q4_k_m.gguf",
        role="general",
        base_url="http://localhost:8080/v1"  # Main brain
    ),
    "autocomplete": ModelConfig(
        name="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        role="autocomplete",
        base_url="http://localhost:8082/v1", # Fast brain
        max_tokens=150
    ),
})

# removed:
# class _DefaultModel:
#     @property
#     def value(self) -> str:
#         return get_settings().default_model
# DEFAULT_MODEL = _DefaultModel()

# added:
def get_default_model() -> str:
    return get_settings().default_model
```

### Code — `app/main.py` (model-unavailable handling + router wiring)
```python
while True:
    # Fix in main.py:
    try:
        response = selected_model.generate(fitted_messages)
    except Exception as e:
        print(f"\n[Error] Model unavailable: {e}")
        print("Is llama-server running on port 8080?\n")
        conversation.pop_last_message()  # remove the user message we just added
    continue

    # ... later, in the pipeline:
    # 7. Generate response
    selected_model, task_type = router.route(prompt)
    response = selected_model.generate(fitted_messages)
```

### Code — `app/memory/manager.py` (force save)
```python
# retrieve path
if results:
    for result in results:
        result.memory.touch()
    self._store.force_save()   # was: self._store.save_if_dirty()

# update path
if self._on_update:
    self._on_update(memory)
self._store.force_save()       # was: self._store.save()
```

### Code — `app/models/llamacpp_client.py` (use `get_default_model`)
```python
from app.config.settings import get_settings, get_default_model
# ...
self._model = model or get_default_model()   # was: model or settings.default_model
```

### Code — `docs/ARCHITECTURE.md` (new, ~329 lines)
```markdown
# Jarvis Architecture

## Philosophy
Jarvis is designed as a modular AI system.
Each component has a single responsibility and communicates through clear interfaces.
The goal is to make every component replaceable without affecting the rest of the system.

# High-Level Architecture
User -> Input Layer -> Executive Brain
  (Memory, Router, Planner, Tools, Models) -> Output Layer
```

### Dependencies
- No new third-party packages were introduced in this commit; `openai` and `tiktoken` were already added in v2.0.0.
- `requirements.txt` remains unchanged here.

---

# Version v2.1.0 (2026-07-05)

> Scope: Multi-backend model support (llama.cpp **and** Ollama), token streaming in the CLI, external YAML configuration via `config.yaml`, a `ModelClient` factory so `main.py` stays backend-agnostic, and a server manager utility. Version constant bumped `v.2.0.0` → `v.2.1.0`.

## Added
- `app/models/ollama_client.py`: `OllamaClient` — a second `ModelClient` backend speaking to Ollama's native API (with streaming).
- `app/models/factory.py`: `create_client(config)` builds the right client from `config.backend` (`"llamacpp"` default, `"ollama"` otherwise); Ollama import is guarded so JARVIS still runs if `ollama` isn't installed.
- `app/utils/server_manager.py`: `is_port_open()` + `ensure_server_running()` to lazily start an LLM server and wait for its port.
- `config.yaml`: external configuration file (models, memory, context) loaded by `Settings.load()`.
- `ModelResponse.finish_reason` field; `ModelClient.generate()` now supports `stream` / `on_token`.
- Streaming output in the chat loop (`print` per token).

## Changed
- `ModelConfig` gained a `backend: str = "llamacpp"` field.
- `Settings.load()` now actually parses `config.yaml` (YAML) and overrides defaults per section, instead of always returning `cls()`.
- `main.py` now builds clients from `settings.models` and registers them on the `ModelRouter` (dynamic, config-driven routing).
- `.gitignore`: now ignores `*.pyc`, `.venv/`/`venv/`, and the `data/` directory.

## Fixed
- The v2.0.1 chat-loop regression (`input()` had been removed) — `input("You: ")` is back at the top of the loop with `EOFError`/`KeyboardInterrupt` handling.
- `LlamaCppClient` streaming path was previously dead code after an early `return`; it is now a real branch.

## Removed
- (none)

### Code — `app/config/settings.py` (backend field + YAML loading)
```python
import yaml  # NEW

@dataclass
class ModelConfig:
    name: str
    role: str
    backend: str = "llamacpp"   # NEW: "llamacpp" or "ollama"
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "not-needed"
    max_tokens: int = 4096

@classmethod
def load(cls, path: Optional[str] = None) -> "Settings":
    """Load settings from YAML file, or return hardcoded defaults"""
    if path is None:
        path = "config.yaml"
    yaml_path = Path(path)
    if not yaml_path.exists():
        return cls()  # No config file found, use defaults
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f) or {}
    settings = cls()
    if "default_model" in data:
        settings.default_model = data["default_model"]
    if "models" in data:
        settings.models = {k: ModelConfig(**m) for k, m in data["models"].items()}
    if "memory" in data:
        settings.memory = MemoryConfig(**data["memory"])
    # ... same override for context, conversation, retrieval, ranking
    return settings
```

### Code — `app/models/client.py` (streaming-capable Protocol + `finish_reason`)
```python
@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None   # NEW

class ModelClient(Protocol):
    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate a response. If stream=True, calls on_token for each chunk."""
        ...
    @property
    def model_name(self) -> str: ...
    @property
    def role(self) -> str: ...
```

### Code — `app/models/factory.py` (NEW — backend-agnostic client creation)
```python
def create_client(config: ModelConfig) -> ModelClient:
    """Instantiate the correct client based on backend type."""
    if config.backend == "ollama":
        if not OLLAMA_AVAILABLE:
            raise ImportError("The 'ollama' python package is required ... pip install ollama")
        return OllamaClient(model=config.name, base_url=config.base_url, role=config.role)
    # Default to llamacpp (OpenAI compatible)
    return LlamaCppClient(model=config.name, base_url=config.base_url,
                          api_key=config.api_key, role=config.role)
```

### Code — `app/models/ollama_client.py` (NEW — Ollama backend)
```python
class OllamaClient(ModelClient):
    def __init__(self, model: str, base_url: str = "http://localhost:11434", role: str = "general"):
        self._model = model
        self._role = role
        self._client = ollama.Client(host=base_url)

    def generate(self, messages, stream=False, on_token=None, **kwargs) -> ModelResponse:
        if not stream:
            response = self._client.chat(model=self._model, messages=messages)
            return ModelResponse(content=response["message"]["content"], model=self._model)
        full_content = ""
        for chunk in self._client.chat(model=self._model, messages=messages, stream=True):
            delta = chunk.get("message", {}).get("content", "")
            full_content += delta
            if on_token:
                on_token(delta)
        return ModelResponse(content=full_content, model=self._model)
```

### Code — `app/models/llamacpp_client.py` (real streaming branch)
```python
def generate(self, messages, stream=False, on_token=None, **kwargs) -> ModelResponse:
    if not stream:
        # --- STANDARD PATH ---
        response = self._client.chat.completions.create(model=self._model, messages=messages, **kwargs)
        choice = response.choices[0]
        return ModelResponse(content=choice.message.content, model=self._model,
                             tokens_used=response.usage.total_tokens if response.usage else None,
                             finish_reason=choice.finish_reason)
    else:
        # --- STREAMING PATH ---
        full_content = ""
        stream_response = self._client.chat.completions.create(
            model=self._model, messages=messages, stream=True, **kwargs)
        for chunk in stream_response:
            delta = chunk.choices[0].delta.content or ""
            full_content += delta
            if on_token:
                on_token(delta)
        return ModelResponse(content=full_content, model=self._model)
```

### Code — `app/main.py` (dynamic routing + streaming output + loop fix)
```python
from app.models.factory import create_client
from app.utils.server_manager import ensure_server_running

router = ModelRouter()
for key, model_cfg in settings.models.items():
    try:
        client = create_client(model_cfg)
        router.register(TaskType(model_cfg.role), client)
        print(f"✅ Loaded {model_cfg.role}: {model_cfg.name} ({model_cfg.backend})")
    except Exception as e:
        print(f"❌ Failed to load {key}: {e}")

# inside the loop:
try:
    prompt = input("You: ").strip()
except (EOFError, KeyboardInterrupt):
    print("\n\nGoodbye!"); _cleanup(memory, conversation); break
if not prompt:
    continue
# ...
selected_model, task_type = router.route(prompt)
try:
    print(f"\nJarvis: ", end="", flush=True)
    response = selected_model.generate(
        fitted_messages,
        stream=True,
        on_token=lambda t: print(t, end="", flush=True))
    print()
except Exception as e:
    print(f"\n[Error] Model unavailable: {e}")
    print("Is the required server running?\n")
    conversation.pop_last_message()
    continue
```

### Code — `app/utils/server_manager.py` (NEW)
```python
def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', port)) == 0

def ensure_server_running(port: int, command: list[str], name: str = "LLM"):
    if is_port_open(port):
        print(f"✅ {name} already running on port {port}"); return
    print(f"⏳ {name} not found on port {port}. Starting in background...")
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(30):
        time.sleep(1)
        if is_port_open(port):
            print(f"✅ {name} started successfully on port {port}"); return
        print(f"   Waiting for {name} to boot... ({i+1}s)")
    print(f"❌ Failed to start {name} after 30 seconds."); sys.exit(1)
```

### Code — `config.yaml` (NEW — external configuration)
```yaml
default_model: "qwen3-8b.gguf"

models:
  general:
    name: "qwen3-8b.gguf"
    role: "general"
    backend: "llamacpp"
    base_url: "http://localhost:8080/v1"
  coder:
    name: "qwen3:8b"
    role: "code"
    backend: "ollama"
    base_url: "http://localhost:11434"
  reasoner:
    name: "deepseek-r1:32b"
    role: "reasoning"
    backend: "ollama"
    base_url: "http://localhost:11434"
  autocomplete:
    name: "qwen2.5-coder:1.5b"
    role: "autocomplete"
    backend: "ollama"
    base_url: "http://localhost:11434"

memory:
  retrieval_limit: 20
  min_confidence: 0.0

context:
  max_tokens: 4096
  safety_margin: 100
```

### Dependencies
- New runtime dependency: **`PyYAML`** (`import yaml`) for loading `config.yaml`.
- **`ollama`** is now a supported backend (`OllamaClient`); its import is lazy/guarded inside `factory.py`, so JARVIS still runs without it unless an Ollama-backed model is selected (already pinned at `ollama==0.6.2`).
- `openai` / `tiktoken` usage unchanged from v2.0.0.

---

# Version v2.2.0 (2026-07-05)

> Scope: Semantic memory. Adds ChromaDB-backed vector retrieval (`VectorRetriever`), a `HybridRetriever` that fuses keyword + vector candidates, and a conversation exchange store (`ConversationVectorStore`) so past exchanges are recallable by meaning. `OllamaClient` now speaks the OpenAI-compatible API. Version constant bumped `v.2.1.0` → `v.2.2.0`.

## Added
- `app/memory/vector_retriever.py`: `VectorRetriever` — persists facts in a ChromaDB collection (`jarvis-memories`) using Ollama embeddings (`nomic-embed-text`), with `find_candidates`/`on_memory_added`/`on_memory_removed`/`on_index_rebuilt`/`clear`.
- `app/memory/hybrid_retriever.py`: `HybridRetriever` — runs `KeywordRetriever` + `VectorRetriever` in parallel, dedups by `memory.id`, and satisfies the `CandidateRetriever` Protocol.
- `app/memory/conversation_store.py`: `ConversationVectorStore` — embeds user/assistant pairs into a separate ChromaDB collection (`jarvis-conversations`) for semantic history search (`index_history`, `add_exchange`, `search`).
- `ConversationManager.pop_last_message()` for error recovery.
- `PromptBuilder.build(..., past_exchanges=...)` and `_format_past_exchanges()` inject retrieved past exchanges into the system prompt.
- `main.py` wires `MemoryManager(retriever=HybridRetriever(...))` and indexes/stores conversation exchanges in `ConversationVectorStore`.

## Changed
- `MemoryManager` now takes a `retriever` (hybrid) instead of a bare keyword retriever.
- `OllamaClient.generate()` rewritten to use the OpenAI-compatible `self._client.chat.completions.create(...)` for both standard and streaming paths (was the native dict-based `self._client.chat(...)`), now returning `tokens_used`/`finish_reason`.
- `LlamaCppClient` dropped its unused `get_settings()` import/call (uses `get_default_model()` directly).
- `config.yaml`: `memory.retrieval_limit` 20 → 5; `context.safety_margin` 100 → 500.

## Fixed
- `main.py` falls back to `router.default_model` when `router.route()` returns `None` (prevents `NoneType.generate` crash).
- Conversation history is now indexed once when the vector store is empty, so prior chats become searchable.

## Removed
- (none)

### Code — `app/memory/vector_retriever.py` (NEW — ChromaDB fact retrieval)
```python
class VectorRetriever:
    def __init__(self, persist_dir="data/chroma",
                 ollama_url="http://localhost:11434",
                 embed_model="nomic-embed-text"):
        embedding_fn = OllamaEmbeddingFunction(url=ollama_url, model_name=embed_model)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="jarvis-memories",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(query_texts=[query], n_results=min(limit, count))
        memories = []
        for metadata in results["metadatas"][0]:
            try:
                memories.append(Memory.from_dict(metadata))
            except Exception:
                pass
        return memories
    # on_memory_added -> upsert(id, document=f"{category} {type}: {value}", metadata=...)
```

### Code — `app/memory/hybrid_retriever.py` (NEW — keyword + vector fusion)
```python
class HybridRetriever:
    """Combines keyword and vector retrieval (drop-in CandidateRetriever)."""
    def __init__(self, keyword: KeywordRetriever, vector: VectorRetriever):
        self._keyword = keyword
        self._vector = vector

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        kw_results = self._keyword.find_candidates(query, limit)
        vec_results = self._vector.find_candidates(query, limit)
        seen: set[str] = set()
        combined: list[Memory] = []
        for memory in kw_results + vec_results:
            if memory.id not in seen:
                seen.add(memory.id)
                combined.append(memory)
        return combined[:limit]
```

### Code — `app/memory/conversation_store.py` (NEW — semantic history)
```python
class ConversationVectorStore:
    def __init__(self, persist_dir="data/chroma",
                 ollama_url="http://localhost:11434",
                 embed_model="nomic-embed-text"):
        self._embedding_fn = OllamaEmbeddingFunction(url=ollama_url, model_name=embed_model)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="jarvis-conversations", embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"})

    def add_exchange(self, user_msg, assistant_msg, timestamp=None) -> None:
        ts = timestamp or time.time()
        pair_id = hashlib.md5(f"{ts}{user_msg[:20]}".encode()).hexdigest()[:8]
        self._upsert(pair_id, user_msg, assistant_msg, ts)

    def search(self, query: str, limit: int = 2) -> list[dict]:
        # returns [{"user": ..., "assistant": ...}, ...]
        ...
```

### Code — `app/main.py` (wire hybrid retriever + conversation vector store)
```python
from app.memory.retrieval import KeywordRetriever
from app.memory.hybrid_retriever import HybridRetriever
from app.memory.vector_retriever import VectorRetriever
from app.memory.conversation_store import ConversationVectorStore

memory = MemoryManager(
    retriever=HybridRetriever(
        vector=VectorRetriever(persist_dir="data/chroma", ollama_url="http://localhost:11434"),
        keyword=KeywordRetriever(min_keyword_overlap=1),
    )
)
conversation = ConversationManager()
prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)
conv_store = ConversationVectorStore(persist_dir="data/chroma")
if conv_store.count() == 0:
    indexed = conv_store.index_history(conversation.get_all())
    if indexed > 0:
        print(f"  [ConversationStore] Indexed {indexed} exchanges indexed")

# in the loop:
past_exchanges = conv_store.search(prompt, limit=2)
messages = prompt_builder.build(
    memories=relevant_memories,
    conversation=conversation.get_recent_formatted(),
    past_exchanges=past_exchanges,
)
selected_model, task_type = router.route(prompt)
if selected_model is None:
    selected_model = router.default_model
# ... after response:
conversation.add_message("assistant", response.content)
conv_store.add_exchange(prompt, response.content)
```

### Code — `app/conversation/manager.py` (error recovery)
```python
def pop_last_message(self) -> 'Message | None':
    """Remove the last message (used for error recovery if a model fails)."""
    if self._messages:
        popped = self._messages.pop()
        self.save()
        return popped
    return None
```

### Code — `app/prompt/builder.py` (past exchanges in system prompt)
```python
def build(self, memories=None, conversation=None, user_prompt="", past_exchanges=None) -> list[dict]:
    system_parts = [self.system_prompt]
    if past_exchanges:
        past_text = self._format_past_exchanges(past_exchanges)
        if past_text:
            system_parts.append(past_text)
    # ...

def _format_past_exchanges(self, exchanges) -> str:
    lines = ["## Relevant Past Exchanges", "Earlier conversation that may be relevant:", ""]
    for exchange in exchanges:
        lines.append(f"- User: {exchange.get('user', '').strip()}")
        lines.append(f"  Assistant: {exchange.get('assistant', '').strip()}")
    return "\n".join(lines)
```

### Code — `app/models/ollama_client.py` (OpenAI-compatible API)
```python
# standard path
response = self._client.chat.completions.create(model=self._model, messages=messages, **kwargs)
choice = response.choices[0]
return ModelResponse(content=choice.message.content, model=self._model,
                     tokens_used=response.usage.total_tokens if response.usage else None,
                     finish_reason=choice.finish_reason)
# streaming path: iterate stream_response, delta = chunk.choices[0].delta.content
```

### Code — `config.yaml` (tuned limits)
```yaml
memory:
  retrieval_limit: 5          # was 20
  min_confidence: 0.0
context:
  max_tokens: 4096
  safety_margin: 500          # was 100
```

### Dependencies
- New runtime dependency: **`chromadb`** (ChromaDB vector store, persisted under `data/chroma` — already gitignored since v2.1.0).
- Embeddings are produced by **Ollama's `nomic-embed-text`** model via `chromadb.utils.embedding_functions.OllamaEmbeddingFunction` — requires an Ollama server on `:11434`.
- `ollama` is now actively exercised (embeddings + OpenAI-compatible chat) rather than only lazily imported.

---

# Version v2.2.1 (2026-07-06)

> Scope: Introduces the **Documentation Agent** and the supporting **tool infrastructure** (`ToolRegistry`/`ToolExecutor` + git/file tools), wired into the CLI via a new `docs` command. `TaskType.DOCS` added to the router; package `__init__.py` files added; `__pycache__` dropped from tracking. Note: the commit message labels this `v2.2.1`, but `app/config/version.py` still reported `VERSION = "v.2.2.0"` at this commit (version constant lags the message).

## Added
- `app/agents/doc_agent.py`: `DocumentationAgent` — a prompt-based mini-agentic loop that reads git history + existing docs and writes CHANGELOG/DEVLOG entries; `run_interactive()` menu driven from the `docs` command.
- `app/tools/base.py`: `ToolResult`, `ToolDefinition` (with `to_openai_schema()`), and `ToolRegistry` (holds tools; `format_for_prompt()` for prompt-based calling, `to_openai_schemas()` for future native calling).
- `app/tools/executor.py`: `ToolExecutor` — parses `<tool_call>{...}</tool_call>` tags, executes via the registry, enforces confirmation for risky tools, caps output (`MAX_OUTPUT_CHARS = 4096`), and wraps every failure.
- `app/tools/git_tools.py`: read-only `GIT_TOOLS` (`git_log`, `git_diff_stat`, `git_diff_full`, `git_show`, `git_tags`, `git_branch`/`git_status`).
- `app/tools/file_tools.py`: `FILE_TOOLS` (`read_file`, `write_file`) guarded by `ALLOWED_READ`/`ALLOWED_WRITE` allowlists (blast radius defined here).
- `app/models/router.py`: `TaskType.DOCS = "docs"`.
- `config.yaml`: new `docs` model entry (llamacpp, `qwen3-8b.gguf`).
- Empty `__init__.py` added to `app/context`, `app/conversation`, `app/prompt` packages.
- `tests/stress_test.py` (new test harness) and recovered/backup docs (`docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`); `docs/DEVLOG.md` refactored/trimmed.

## Changed
- `main.py`: instantiates `DocumentationAgent(model=router.select(TaskType.DOCS) if TaskType.DOCS in router.models else router.default_model)`; new `if prompt == "docs": run_interactive(doc_agent)` branch; pipeline step comments renumbered (1–10).
- `OllamaEmbeddingFunction`/ChromaDB flow unchanged; embedding model still `nomic-embed-text`.

## Fixed
- Package import errors resolved by adding the missing `__init__.py` files.
- `ToolExecutor` regex hardened to tolerate whitespace/newlines inside `<tool_call>` blocks (large JSON no longer breaks parsing).
- `__pycache__` artifacts removed from git tracking.

## Removed
- (none in source logic)

### Code — `app/agents/doc_agent.py` (NEW — prompt-based agentic loop)
```python
class DocumentationAgent:
    def __init__(self, model: ModelClient):
        self._model = model
        self._registry = ToolRegistry()
        self._registry.register_many(GIT_TOOLS)
        self._registry.register_many(FILE_TOOLS)
        self._executor = ToolExecutor(registry=self._registry, require_confirmation=True)

    def run(self, task: str, verbose: bool = True) -> str:
        for iteration in range(1, MAX_ITERATIONS + 1):
            response = self._model.generate(messages)
            text = response.content
            if not self._executor.has_calls(text):
                return text                       # done
            calls = self._executor.parse(text)
            messages.append({"role": "assistant", "content": text})
            result_blocks = []
            for call in calls:
                result = self._executor.run(call)
                result_blocks.append(self._executor.format_result(call, result))
            messages.append({"role": "user", "content": "\n\n".join(result_blocks)})
        return "[Documentation agent reached iteration limit without completing]"
```
The agent emits tool calls as `<tool_call>{"name": "tool_name", "args": {...}}</tool_call>` and the system prompt instructs it to read existing CHANGELOG/DEVLOG first to match format, then `write_file` the complete updated file with the new entry prepended.

### Code — `app/tools/base.py` (NEW — tool primitives)
```python
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
    def __bool__(self) -> bool: return self.success

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable
    risk_level: str = "low"          # none | low | medium | high
    requires_confirmation: bool = False
    def execute(self, **kwargs) -> ToolResult:
        try:
            return ToolResult(success=True, output=str(self.handler(**kwargs)))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    def to_openai_schema(self) -> dict: ...   # ready for v3.0 native calling

class ToolRegistry:
    def register(self, tool): self._tools[tool.name] = tool
    def format_for_prompt(self) -> str: ...    # injected into system prompt
```

### Code — `app/tools/executor.py` (NEW — parse + execute)
```python
_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
MAX_OUTPUT_CHARS = 4096

class ToolExecutor:
    def has_calls(self, text: str) -> bool: return bool(_TOOL_CALL_RE.search(text))
    def parse(self, text: str) -> list[ParsedCall]: ...   # skips malformed JSON
    def run(self, call: ParsedCall) -> ToolResult:
        tool = self._registry.get(call.name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: '{call.name}'")
        if self._require_confirmation and tool.requires_confirmation:
            if input("  Execute? (y/N): ").strip().lower() != "y":
                return ToolResult(success=False, error="User declined")
        result = tool.execute(**call.args)
        if result.success and len(result.output) > MAX_OUTPUT_CHARS:
            result.output = result.output[:MAX_OUTPUT_CHARS] + f"\n\n... (trimmed)"
        return result
    def format_result(self, call, result) -> str:
        # returns <tool_result name="..." status="...">...</tool_result>
```

### Code — `app/tools/git_tools.py` (NEW — read-only git eyes)
```python
def git_log(n: int = 15) -> str:
    return _run_git("log", "--oneline", f"-{n}", "--format=%h %ad %s", "--date=short")
def git_diff_full(from_ref="HEAD~1", to_ref="HEAD") -> str:
    diff = _run_git("diff", from_ref, to_ref)
    return diff[:DIFF_MAX_CHARS] + "...(truncated)" if len(diff) > DIFF_MAX_CHARS else (diff or "(no changes)")
# GIT_TOOLS = [git_log, git_diff_stat, git_diff_full, git_show, git_tags, ...]  risk_level="none"
```

### Code — `app/tools/file_tools.py` (NEW — allowlist-guarded writes)
```python
ALLOWED_READ = {"docs/CHANGELOG.md", "docs/DEVLOG.md", "README.md", "config.yaml", ...}
ALLOWED_WRITE = {"docs/CHANGELOG.md", "docs/DEVLOG.md", "CHANGELOG.md", "DEVLOG.md"}

def write_file(path: str, content: str) -> str:
    if path not in ALLOWED_WRITE:
        raise PermissionError(f"'{path}' is not in the allowed write list.")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"
# FILE_TOOLS: read_file (risk="low"), write_file (risk="medium", requires_confirmation=True)
```

### Code — `app/main.py` (wire the docs command)
```python
from app.agents.doc_agent import DocumentationAgent, run_interactive

doc_agent = DocumentationAgent(
    model=router.select(TaskType.DOCS) if TaskType.DOCS in router.models else router.default_model
)

# in the loop:
if prompt == "docs":
    try:
        run_interactive(doc_agent)
    except Exception as e:
        import traceback; traceback.print_exc()
    continue
```

### Code — `app/models/router.py` & `config.yaml`
```python
class TaskType(Enum):
    # ...
    DOCS = "docs"   # New task type for documentation-related tasks
```
```yaml
  docs:
    name: "qwen3-8b.gguf"
    role: "docs"
    backend: "llamacpp"
    base_url: "http://localhost:8080/v1"
```

### Dependencies
- No new third-party packages in this commit (builds on `openai`, `ollama`, `chromadb`, `pyyaml` already present).
- Note: the `doc_agent.py`/`tools/*` docstrings reference a future **v2.4.0 / v3.0** agentic runtime (native function calling, permission system) — forward-looking design notes, not yet implemented.

# Document Addition with each one explaining each its importance.

## docs/ROADMAP.md
- What: Project Roadmap document outlining JARVIS's purpose, vision, development stage, milestones, work-in-progress, planned work, dependencies, limitations, risks, future vision, and AI verification status.
- When: 2026/07/11 · v2.4.0 working tree
- Why: To provide a consolidated, evidence-backed overview of the JARVIS project's past, present, and future development, directly addressing documented architectural principles and development goals. It acts as a single source of truth for the project's direction.
- Says/does: Details the project's evolution from v2 to robust model switching and API integration, listing completed features like core architecture overhaul, Ollama/LLM integration, structured memory, semantic memory, multi-backend support, and the documentation agent. It also outlines current work on ModelSwitcher, doc_agent, environment variables, and new backend support, along with future plans for memory, agent runtime, and multi-agent systems. A key feature is the "AI Verification Status" that explicitly tracks verification of statements against source code, git history, diffs, and documentation.

## docs/MEMORY.md
- What: Source-verified reference doc for the memory subsystem — architecture, lifecycle, storage, retrieval, ranking, fact extraction, vector search, conversation memory, future improvements.
- When: 2026/07/11 · v2.4.0 working tree
- Why: Created to consolidate how the memory system works (FactExtractor → MemoryManager → Store/Retriever/Ranker, plus ChromaDB-backed vector  + conversation stores) into one place, traced and verified against the actual app/memory/ source.
- Says/does: Explains each memory component, how memories are created/retrieved/ranked/updated/stored, the storage formats (JSON + ChromaDB), and the retrieval pipeline.

## docs/CONFIG.md
- What: Configuration reference document for JARVIS (single file, ~7 sections).
- When: 2026/07/11 · v2.4.0 working tree
- Why: Added to document the centralized config system in app/config/settings.py
so the architecture, config sources, defaults, validation, runtime overrides, and
lifecycle are captured in one place instead of being inferred from source.
- Says/does: Explains the Settings dataclass architecture, the config.yaml source,
environment-variable capability, all dataclass default values, the lack of explicit
validation, singleton-based runtime behavior, and the load/override lifecycle.

## docs/STARTUP_FLOW.md
- What: Startup-flow reference doc — traces app boot from main.py through every
subsystem init to the start of the request-processing loop.
- When: 2026/07/11 · v2.4.0 working tree (uncommitted)
- Why: Added to make the boot order explicit and source-verified (entry point,
init order, config loading, objects created, dependency graph, event loop,
shutdown) instead of having it rediscovered by reading code each time.
- Says/does: Documents the entry point, startup sequence, initialization order,
objects created, configuration loading, dependency graph, event loop, and
shutdown sequence — all traced line-by-line against source.

## docs/ARCHITECTURE
- What: Architecture reference document for JARVIS (10 sections: Purpose, High-level architecture, Mermaid layer diagram, Startup flow, Dependency injection, Component responsibilities, Runtime lifecycle, Design rationale, Future improvements, Uncertainties/Unimplemented).
- When: 2026/07/11 · v2.4.0 working tree
- Why: Added to give future developers a verified, source-traced map of the system — folder purposes, startup execution path, inter-component dependencies, and the main conversational loop — closing the gap where no single architecture doc existed.
- Says/does: Documents how JARVIS is structured and initialized, shows the runtime flow from app/main.py through memory/model/prompt/context subsystems, explains constructor-based dependency injection, and lists what each module is responsible for; ends by flagging empty/unimplemented areas.

## docs/DATABASE.md 
- What: Persistence / database-architecture document (storage engines, data models, lifecycle, indexing, vector DB, JSON storage, future improvements + AI Verification Status).
- When: 2026/07/11 · v2.4.0 working tree 
- Why: Added to consolidate how JARVIS actually persists data and back every claim with source verification; closes the doc gap where no single file explained the dual JSON + ChromaDB design, indexing split, and runtime-unverifiable items.
- Says/does: Documents the two storage engines (JSON files + ChromaDB), the Memory/Message models, the CRUD + persistence flow, keyword/vector/hybrid indexing, the ChromaDB collections, the JSON file formats, and flags unwired config + stale-embedding behavior, with a source-checked appendix.

## docs/PROJECT_HISTORY.md
- What: Project-history / architecture-evolution document (19 sections + Verification Notes).
- When: 2026/07/11 · v2.4.0 working tree 
- Why: Added to consolidate lineage knowledge and back the narrative with source
  verification; closes doc gaps (missing §7–§10 notes and missing §11–§19 deep-dives).
- Says/does: Documents how JARVIS evolved and what its current architecture, standards,
  debt, and future direction are, with a source-checked appendix.

# Version v2.4.0 (2026-07-11) After Documents overhaul.

> Scope: Diagnoses and fixes the runtime crash `ValueError: No model for task type: TaskType.GENERAL` that occurred on the first user prompt. Root cause was `Settings.load()` silently ignoring the `profiles:` section of `config.yaml`, so the active `local` profile pointed at non-existent model keys and built an empty router. Also hardens router selection, removes dead fallback code, and documents several latent configuration issues. Version constant normalized from `"v.2.4.0"` → `"v2.4.0"` to match the `vX.Y.Z` convention used throughout this file.

## Added
- `app/config/settings.py`: `Settings.load()` now reads the `profiles:` block from `config.yaml` (previously ignored entirely), so the active profile's role→model-key mapping actually resolves to loaded clients.
- `app/models/router.py`: `select()`/`route()` now fall back to the first registered model instead of raising when a task type is unregistered and no default is set — graceful degradation instead of a hard crash.
- `ModelSwitcher`: guarantees a default model (the profile's `general` mapping) is always set, so `route()` never returns `None`.

## Changed
- `app/main.py`: removed the dead `if selected_model is None: selected_model = switcher.router.default_model` branch (it was unreachable because `route()` raised before returning); `doc_agent` construction now resolves to a valid client instead of potentially `None`.

## Fixed
- Root-cause crash `ValueError: No model for task type: TaskType.GENERAL`. The hardcoded default `profiles["local"]` mapped roles to keys `general`/`code`/`reasoning`/`docs`, but `config.yaml` defines models under keys like `local_general`/`local_code`/etc. Because `profiles` was never loaded, the switcher registered nothing and set no default, leaving the router empty. Loading `profiles` wires `local_general` (llamacpp, no API key) in as the `GENERAL`/`default` model.
- `VERSION` constant normalized from `"v.2.4.0"` to `"v2.4.0"`.

## Known Issues
- `cerebras_general` has a malformed `api_key: "env:"` (empty variable name) → always warns `Environment variable '' is not set`; also a copy-paste leftover (`name: gemini-2.0-flash`) with no `cerebras` profile referencing it. Orphaned and broken.
- Local llamacpp server auto-start (`ensure_server_running`) is still commented out in `main.py`. `local_general`/`local_docs` (`qwen3-8b.gguf` @ `http://localhost:8080/v1`) need a manually started server; `local_code`/`local_reasoning` need Ollama on `:11434`.
- `google_*` and `cerebras_general` are declared `backend: "llamacpp"` but only function via the commented-out 🟡 ISOLATED GOOGLE BLOCK in `llamacpp_client.py`; otherwise they hit `base_url: http://localhost` and fail.
- `config.yaml` defines `grok`/`openrouter`/`google` profiles that were previously ignored; they now resolve, but still require valid API keys (currently commented in `.env`).

### Code — `app/config/settings.py` (load `profiles` from YAML)
```python
# Inside Settings.load(), alongside the other overrides (models/memory/context/...):
if "profiles" in data:
    settings.profiles = data["profiles"]   # use the profiles: block from config.yaml
```

### Code — `app/models/router.py` (graceful fallback in select)
```python
def select(self, task_type: TaskType) -> ModelClient:
    if task_type in self.models:
        return self.models[task_type]
    if self.default_model:
        return self.default_model
    if self.models:                       # last-resort fallback, never crash
        return next(iter(self.models.values()))
    raise ValueError(f"No model for task type: {task_type}")
```




> Scope: Adds an interactive model picker to the chat CLI. Typing `model` now opens a Local/API menu; Local lists local profiles, API lists cloud providers and then the specific models within each provider (e.g. pick OpenRouter → qwen3-30b vs llama-3.3-70b). `ModelSwitcher.switch_to_model()` builds a router mapping every role to one chosen cloud/local model, so users can swap exact models mid-session without editing `config.yaml`.

## Added
- `app/models/switcher.py`: `ModelSwitcher.switch_to_model(model_key)` — routes all task types (general/code/reasoning/docs/stem/autocomplete) to a single chosen client and sets it active; returns `False` if the model didn't load.
- `app/main.py`: helpers `_categorize_profiles(settings)` (local vs api, by the general model's `base_url`), `_categorize_cloud_models(settings)` (groups cloud model keys by provider, inferred from `base_url` host), and `_interactive_model_select(switcher, settings)` (Local → profile list; API → provider → specific model, with a `✓ loaded` / `✗ key missing` status per model).
- `app/main.py`: the `model` command (no args) now opens the interactive picker; `model list` and `model <name>` shortcuts are unchanged.
- `config.yaml`: supports multiple model entries per cloud provider (e.g. `openrouter_llama`, `openrouter_qwen`, `grok_mini`) so there is a real choice within a provider.

## Changed
- `model` (no arg) previously printed `switcher.status()`; it now launches the interactive Local/API → provider → model selector.
- After selecting a specific cloud model, `doc_agent` is rebuilt against that model (via the `model:<key>` return convention).

## Fixed
- Prevents the crash from switching to a provider whose models failed to load: `_interactive_model_select` refuses models with no client (`✗ key missing`) and `switch_to_model` returns `False`, so an unconfigured API model can't become the active (empty) router.

## Known Issues
- Google models in `config.yaml` use `base_url: "http://localhost"` (the Python-block path), so `_categorize_cloud_models` excludes them unless their host is set to the real Google endpoint or hardcoded into `host_map`.
- The interactive picker bypasses the `profiles:` block for single-model selection; `profiles` remain the mechanism for role-differentiated routing (different model per task type).

### Code — `app/models/switcher.py` (NEW method)
```python
def switch_to_model(self, model_key: str) -> bool:
    client = self._clients.get(model_key)
    if not client:
        return False
    router = ModelRouter()
    for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
        try:
            router.register(TaskType(role), client)
        except ValueError:
            pass
    router.set_default(client)
    key = f"model:{model_key}"
    self._routers[key] = router
    self._active_profile = key
    return True
```

### Code — `app/main.py` (NEW helpers, abridged)
```python
def _categorize_cloud_models(settings) -> dict:
    from urllib.parse import urlparse
    host_map = {"api.x.ai": "grok", "openrouter.ai": "openrouter",
                "generativelanguage.googleapis.com": "google"}
    groups = {}
    for key, cfg in settings.models.items():
        if "localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url:
            continue
        host = urlparse(cfg.base_url).netloc
        provider = host_map.get(host, host)
        groups.setdefault(provider, []).append(key)
    return groups
# _interactive_model_select(): Local -> profile list; API -> provider -> model,
# with per-model load status; returns profile name or 'model:<key>'.
```
```