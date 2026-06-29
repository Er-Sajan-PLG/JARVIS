# Jarvis Architecture

## Philosophy

Jarvis is designed as a modular AI system.

Each component has a single responsibility and communicates through clear interfaces.

The goal is to make every component replaceable without affecting the rest of the system.

---

# High-Level Architecture

User
│
▼
Input Layer
│
▼
Executive Brain
├── Memory
├── Router
├── Planner
├── Tools
└── Models
│
▼
Output Layer

---

# Components

## Main

Application entry point.

Responsible for:
- starting Jarvis
- initializing components
- running the application

---

## Brain

The central coordinator.

Responsible for:
- understanding requests
- deciding what to do
- communicating with memory, tools, and models

---

## Memory

Responsible for:
- conversation history
- long-term memory
- user preferences
- knowledge retrieval

---

## Router

Responsible for selecting the most appropriate model or service for a task.

Examples:
- Coding → Qwen
- Reasoning → DeepSeek
- Fast answers → API model

---

## Models

Responsible only for communicating with AI providers.

Examples:
- Ollama
- Springbase
- OpenAI API
- Anthropic
- Google Gemini

---

## Tools

Responsible for interacting with external systems.

Examples:
- Email
- Calculator
- Calendar
- File system
- Web search

---

## Output

Responsible for presenting responses.

Examples:
- Terminal
- Voice
- Mobile
- Web UI

---

# Design Principles

- Separation of concerns
- Modular architecture
- Replaceable components
- Scalability
- Reusability
- Local-first when practical
- Cloud-compatible

---

# Core Principles

1. Build for learning.
2. Build one feature at a time.
3. Prefer simple solutions.
4. Every module should have one responsibility.
5. Components should communicate through clear interfaces.
6. Optimize only when necessary.
7. Keep the architecture flexible for future growth.

---

## After v1.0 JARVIS ARCHITECTURE

# JARVIS Architecture

## Purpose

This document defines the stable architecture of JARVIS.

It describes the responsibilities of each component, the contracts between them, and the data flowing through the system.

Implementation details may change over time.

Architecture should remain stable whenever possible.

---

# Core Principles

* Each component should have one responsibility.
* Components communicate through well-defined data structures.
* Implementation can change without affecting other layers.
* Data contracts should remain stable.
* Prefer extending existing interfaces over rewriting them.

---

# Data Flow

User
↓
Orchestrator (main.py)
↓
LLM
↓
Extractor
↓
Memory Manager
↓
Persistent Storage
↓
Prompt Builder
↓
LLM

---

# Components

## Orchestrator

Responsible for coordinating the entire application.

Responsibilities:

* Receive user input.
* Call the LLM.
* Extract facts.
* Update memory.
* Save state.

The orchestrator should contain as little business logic as possible.

---

## Rules

Rules define how information is recognized.

Rules decide:

* what to detect
* how to classify it
* what memory behavior to apply

Rules should contain configuration, not logic.

Adding new rules should not require changes elsewhere.

---

## Extractor

Responsible for converting user messages into structured facts.

Input:

* User message

Output:

* List of Facts

The extractor should not know how memory works.

---

## Fact

A Fact is the fundamental unit of memory.

Current schema:

* category
* type
* value
* behavior

This schema should remain stable whenever possible.

---

## Memory Manager

Responsible for managing stored facts.

Responsibilities:

* append
* replace
* ignore
* load
* save

The memory manager should not know how facts were extracted.

It only manages facts.

---

## Conversation

Conversation stores dialogue history.

Conversation and Memory are separate systems.

Conversation stores messages.

Memory stores knowledge.

---

## Prompt Builder

Responsible for constructing prompts sent to the LLM.

Uses:

* system prompt
* memory
* conversation

Prompt construction should remain isolated from extraction and memory logic.

---

# Stable Contracts

These interfaces should rarely change.

Rules → Extractor

Extractor → List[Fact]

Memory Manager ← Fact

Prompt Builder ← Facts

LLM ← Prompt

---

# Future Evolution

Implementation may evolve from:

Rules

↓

Regex

↓

Synonyms

↓

Embeddings

↓

Intent Detection

↓

LLM-based Extraction

These improvements should not require major changes to downstream components.

---

# Philosophy

Protect interfaces.

Improve implementations.

Keep responsibilities clear.

Small components are easier to reason about, test, debug, and extend.
