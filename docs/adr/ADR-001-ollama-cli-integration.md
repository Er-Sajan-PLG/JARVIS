# ADR-001: Direct Ollama Integration & Interactive CLI Loop

**Status**: HISTORICAL
**Last Updated**: 2026-06-27

- **Status**: Superseded by ADR-006
- **Date**: 2026-06-27
- **Version Tag**: `v0.1.0` / `v0.2.0`
- **Commit**: `e13ee67`, `ded44b9`
- **Confidence**: `VERIFIED`

## Context
Initial version of JARVIS needed a lightweight mechanism to communicate with local LLMs without external API costs or complex cloud dependencies.

## Decision
Connect directly to local Ollama server API (`http://localhost:11434/api/generate`) using python HTTP requests and implement an interactive CLI loop reading stdin.

## Consequences
- **Positive**: Zero API costs, instant local execution.
- **Negative**: Monolithic coupling between CLI loop and model HTTP client.
