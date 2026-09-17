# ADR-009: Multi-Provider Failover & Circuit Breaker

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-07-28
**Reviewed**: 2026-09-14

- **Status**: Approved
- **Date**: 2026-07-28
- **Version Tag**: `v3.0.0 Refactored`
- **Commit**: `bb7e20b`
- **Confidence**: `VERIFIED`

## Context
Commercial LLM providers frequently encounter rate limits (429 HTTP status) and temporary outages (503 HTTP status). Single-provider configurations lead to high failure rates during API rate limiting.

## Decision
Build a **Multi-Provider Failover Pool & Circuit Breaker**:
1. All LLM providers implement `BaseLLMProvider` ABC (`app/models/interface.py`).
2. `ResourceManager` maintains `ProviderHealthMonitor` tracking consecutive failures and 429/503 status codes.
3. Circuit states transition from `CLOSED` (healthy) ➔ `OPEN` (failing) ➔ `HALF_OPEN` (probing recovery).
4. `ModelRouter` automatically routes requests away from `OPEN` providers to healthy fallback providers in the pool.

## Consequences
- **Positive**: High system availability and resilience against 429/503 provider outages.
- **Negative**: Requires maintaining standard `BaseLLMProvider` implementations for multiple cloud/local backends.
