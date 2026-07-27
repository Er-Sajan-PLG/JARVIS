"""JARVIS FastAPI Application Entrypoint & Server Mount.

Wires HTTP REST adapters, WebSockets / SSE streaming adapters, CORS middleware,
frontend static asset mounts, and ApplicationContainer bootstrap initialization.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.adapters import http_router, ws_router
from app.bootstrap import bootstrap_system

app = FastAPI(
    title="JARVIS Personal AI Platform",
    version="3.0.0",
    description="Single-tenant personal AI assistant platform with hybrid cognitive execution engine.",
)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Register Adapter Routers
app.include_router(http_router)
app.include_router(ws_router)

# 3. Mount Frontend Static Files if directory exists
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    """Bootstrap application container on startup."""
    bootstrap_system()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
