## v0.1

Created JARVIS
-Learned about architecture, system design, future proof(upgradability, localized debug)
-created virtual environment, 
-created core files and folders
-written core code for main.py for running JARVIS, importing model, created client.py in model for ollama
-edited settings.py
-git setup and commited and pushed


## v0.2

Built CLI loop for Jarvis.

Key learning:
- while loops are better for open-ended interaction
- client should be created once, not inside loop
- input/output flow must be sequential (input → process → output)

Mistakes:
- initially tried mixing assignment inside while condition
- confused loop condition with loop body logic


## v0.3

Added:
- System prompt support.
- Jarvis identity layer.

Design decisions:
- Moved prompts into app/config/prompts.py.
- Kept settings.py for application configuration only.

Learned:
- System prompts influence model behavior.
- The model only follows the system prompt if it's included in the messages list.

Next:
- Session memory.



## v0.4 – Conversation Memory

Date: 2026-06-27

### Features
- Added conversation history to `OllamaClient`.
- Stored the system prompt during initialization.
- Appended each user message before sending a request to the LLM.
- Appended each assistant response after receiving it.
- Jarvis can now maintain context across multiple conversation turns.

### What I Learned
- Objects can own state (`self.conversation`).
- `__init__()` is used to initialize object attributes.
- Execution order matters: append → chat → append → return.
- The `messages` parameter belongs to the `chat()` function; `self.conversation` belongs to the object.
- `return` ends a function immediately, so any code after it won't execute.

### Notes
- Configured Git to ignore Python cache (`__pycache__`) files.


## v0.5 - Persistent Memory Core

🧠 Overview

In this version, Jarvis gained persistent conversational memory. The system now stores chat history on disk and reloads it on startup, allowing continuity across sessions and system restarts.

This moves Jarvis from a stateless LLM wrapper into a stateful conversational system.

⚙️ Major Features Added
💾 Persistent Memory System
Introduced MemoryManager
Stores conversation history in a JSON file
Loads previous conversation on startup
Saves updated conversation after every interaction
🔁 Conversation Continuity
Chat history is preserved across program restarts
Model receives full conversation context every request
Enables context-aware responses over time
🧩 Separation of Concerns (Architecture Refactor)

System now cleanly split into:

main.py → Orchestrates workflow
OllamaClient → Handles LLM interaction
MemoryManager → Handles persistence (load/save/clear)
🏗️ Architecture (v0.5)
User
 ↓
main.py
 ↓
MemoryManager → loads conversation.json
 ↓
OllamaClient → sends full conversation to model
 ↓
AI response
 ↓
MemoryManager → saves updated conversation.json
🧪 Behavior Changes
Before v0.5
Every run = fresh conversation
No memory between sessions
After v0.5
Jarvis remembers past messages
Identity and context persist
Conversations continue seamlessly after reboot
📂 Data Storage
Format: JSON
Structure: list of role-based messages
Location: app/memory/conversation.json

Example:

[
  {"role": "system", "content": "SYSTEM_PROMPT"},
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi!"}
]
🧠 Key Engineering Concepts Learned
State persistence in applications
Dependency injection (conversation passed into client)
Separation of concerns (memory vs model vs orchestration)
File-based storage using JSON
Lifecycle design: load → run → save loop
⚠️ Known Limitations
Memory grows indefinitely (no pruning yet)
No structured long-term memory (everything stored equally)
No recovery handling for corrupted JSON
No semantic memory (pure raw chat history only)
🚀 What v0.6 should focus on (suggested)
Memory trimming / summarization
Error handling for corrupted memory file
“Forget last N messages”
Structured memory (facts vs chat history)
Optional SQLite upgrade
Session tagging
🏁 Summary

v0.5 transforms Jarvis into a persistent conversational agent.

It now has:

continuity, identity, and memory across sessions.