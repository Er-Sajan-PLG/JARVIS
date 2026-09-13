# I/O Protocol Adapters Subsystem (`app/adapters/`) - Version-by-Version History

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-13
**Source**: `app/adapters/` at HEAD

## Version-by-Version Evolutionary History

### Version v0.1.0 to v0.2.0 (`e13ee67` - `ded44b9`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27*
- **CLI Stdin/Stdout Adapter**: Terminal-based chat loop inside `app/main.py`.

### Version v2.5.0 (`f9fa068`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 | Tag Release Date: 2026-07-18*
- **FastAPI Web Server**: `app/web_api_server.py` introducing REST HTTP routes and HTML frontend.

### Version v3.0.0 Refactored (`ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **I/O Protocol Adapters Package (`app/adapters/`)**:
  - `http_router` (`app/adapters/http/router.py`): FastAPI APIRouter defining REST HTTP endpoints (`/api/v1/health`, `/api/v1/chat/completions`).
  - `ws_router` (`app/adapters/websocket/stream.py`): Real-time streaming APIRouter defining WebSocket (`/ws/chat`) and SSE (`/ws/stream`) endpoints.
  - `validate_api_key` (`app/adapters/http/router.py`): Security dependency validating Bearer token and `X-API-Key` headers against `JARVIS_API_KEY`.
- **Active Invariants at HEAD**:
  1. All external HTTP/WebSocket protocol handlers isolated in `app/adapters/`.
  2. Core domain entities and cognitive brain services DO NOT import from `adapters/`.
