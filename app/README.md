# app

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Core Application Package. | — |
| `bootstrap.py` | Composition Root for Dependency Injection & Service Wiring. | `ApplicationContainer`, `bootstrap_system()` |
| `main.py` | JARVIS FastAPI Application Entrypoint & Server Mount. | `_register_asset_route()`, `_resolve_cors_origins()`, `lifespan()`, `logging_middleware()`, `main()`, `serve_manifest()`, `serve_offline()`, `serve_service_worker()` |
| `provider_registry.py` | Comprehensive provider registry for JARVIS. | `AIProvider`, `ProviderCapability`, `ProviderRegistry`, `ProviderStatus`, `get_provider_registry()` |

<!-- generated:module_readmes end -->
