# ADR-003: Multi-Model Task Router & Classification


**Status**: HISTORICAL
**Last Updated**: 2026-07-03
- **Status**: Evolved into ADR-009
- **Date**: 2026-07-03
- **Version Tag**: `v2.0.0`
- **Commit**: `8519f65`
- **Confidence**: `VERIFIED`

## Context
Different user queries (coding, reasoning, documentation, general chat) perform optimally on different specialized LLMs.

## Decision
Build `ModelRouter` to classify prompt intent into `TaskType` categories (`CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`) and route to specialized models.

## Consequences
- **Positive**: Improved answer quality by sending code prompts to coding models and reasoning prompts to reasoning models.
- **Negative**: Hardcoded model choices failed when specific models hit rate limits.
