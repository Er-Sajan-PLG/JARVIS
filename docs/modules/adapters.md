# I/O Protocol Adapters Subsystem (`app/adapters/`) - Version-by-Version History

## Version-by-Version Evolutionary History

### Version v0.1.0 to v0.2.0 (`e13ee67` - `ded44b9`)
- **CLI Stdin/Stdout Adapter**: Terminal-based chat loop inside `app/main.py`.

### Version v2.5.0 (`f9fa068`)
- **FastAPI Web Server**: `app/web_api_server.py` introducing REST HTTP routes and HTML frontend.

### Version v3.0.0 Refactored (`ec0dc4e`) - Current HEAD
- **I/O Protocol Adapters Package (`app/adapters/`)**:
  - `http_router` (`http/router.py`): FastAPI APIRouter defining REST HTTP endpoints (`/api/v1/health`, `/api/v1/chat/completions`).
  - `ws_router` (`websocket/stream.py`): Real-time streaming APIRouter defining WebSocket (`/ws/chat`) and SSE (`/ws/stream`) endpoints.
  - `validate_api_key` (`http/router.py`): Security dependency validating Bearer token and `X-API-Key` headers against `JARVIS_API_KEY`.
- **Active Invariants at HEAD**:
  1. All external HTTP/WebSocket protocol handlers isolated in `app/adapters/`.
  2. Core domain entities and cognitive brain services DO NOT import from `adapters/`.
