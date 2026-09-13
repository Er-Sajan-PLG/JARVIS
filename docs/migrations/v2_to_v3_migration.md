# Migration Guide: v2.x to v3.0.0 Architecture

**Status**: ACTIVE
**Last Updated**: 2026-09-13

## Breaking Changes Summary
1. **Domain Purity**: Direct instantiation of database schemas or framework models in business logic is deprecated. Use `app/domain/` dataclasses (`ContentSource`, `MemoryRecord`, `ExecutionPlan`).
2. **LLM Provider API**: LLM clients now implement `BaseLLMProvider` (`app/models/interface.py`). Request routing is handled via `ModelRouter.select_healthy_provider()`.
3. **Memory Access**: Memory operations now go through `MemoryService` (`app/memory/service.py`), which returns pure `MemoryRecord` objects.
4. **API Authentication**: All API endpoints require single-tenant `JARVIS_API_KEY` authentication via Bearer token (`Authorization: Bearer <key>`) or `X-API-Key` header.

## Migration Steps
- Update client HTTP calls to include `Authorization: Bearer $JARVIS_API_KEY`.
- Update code importing `app.prompt.builder.PromptBuilder` to use `app.prompt.loader.PromptLoader` and `app.context.builder.ContextBuilder`.
