# JARVIS Documentation Index

This folder contains repository documentation. Use Git tags as the canonical
source for release versions and dates — tags are authoritative.

Quick index

- CHANGELOG.md — User-facing release summaries (short, what changed and why it matters).
- DEVLOG.md — Engineering-focused release notes (why decisions were made, architecture rationale).
- PROJECT_HISTORY.md — Long-form history and architecture evolution (reconciled with git history).
- API.md — Public API and CLI surface.
- ARCHITECTURE.md, ARCHITECTURE_CONTINUE_AGENT.md — High-level architecture and diagrams.
- DATABASE.md, MEMORY.md — Persistence and memory subsystem descriptions.
- AGENTS.md — Agent design and the DocumentationAgent specifics.
- TOOLS.md, CONFIG.md, LLM.md, KNOWLEDGE.md — Subsystem reference docs.

Notes for contributors

- Always treat Git tags as the single source of truth for releases.
- When updating docs about releases, derive dates and commit references from git (`git tag`, `git show`, `git log`).
- Do not create or write empty placeholder docs without asking the repository owner.

If you want me to reconcile a specific doc with git history, tell me which one and I will pull the relevant commits and diffs.