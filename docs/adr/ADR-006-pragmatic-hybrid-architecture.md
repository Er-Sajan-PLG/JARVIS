# ADR-006: Pragmatic Hybrid Architecture


**Status**: ACTIVE
**Last Updated**: 2026-07-28
- **Status**: Approved
- **Date**: 2026-07-28
- **Version Tag**: `v3.0.0 Refactored`
- **Commit**: `c5a97b4`
- **Confidence**: `VERIFIED`

## Context
JARVIS required an architecture balancing low-latency direct request-reply execution loops with decoupled async telemetry, logging, and event notifications.

## Decision
Adopt a **Pragmatic Hybrid Architecture**:
1. **Direct Async Interface Calls (`await`)**: Used strictly for core cognitive orchestration loops (`IntentAnalyzer` ➔ `TaskPlanner` ➔ `ExecutionRunner` ➔ `ResponseSynthesizer`).
2. **InMemoryAsyncBus**: Reserved for passive telemetry, logging, metrics aggregation, streaming events, and scheduler notifications.

## Consequences
- **Positive**: Zero latency overhead in cognitive loops; clean decoupling of telemetry logging and event streams.
- **Negative**: Subsystem boundaries must strictly enforce where `await` vs `bus.publish()` is permitted.
