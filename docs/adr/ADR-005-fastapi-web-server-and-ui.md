# ADR-005: FastAPI Web API Server & Modern Single-Page App

**Status**: HISTORICAL
**Type**: adr
**Last Updated**: 2026-07-18

- **Status**: Evolved into ADR-010
- **Date**: 2026-07-18
- **Version Tag**: `v2.5.0`
- **Commit**: `f9fa068`
- **Confidence**: `VERIFIED`

## Context
Command-line interface limited non-technical usability and rich visual status rendering.

## Decision
Build a FastAPI web server in `app/web_api_server.py` serving REST endpoints, WebSocket streams, and static HTML/CSS/JS frontend files from `frontend/`.

## Consequences
- **Positive**: Rich graphical web UI with live streaming tokens and interactive session management.
- **Negative**: Required securing endpoints against unauthorized local/remote access.
