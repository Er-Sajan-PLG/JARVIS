"""JARVIS FastAPI Application Entrypoint & Server Mount."""

import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env before anything else
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.adapters import http_router, ws_router  # noqa: E402
from app.adapters.web.router import web_router  # noqa: E402
from app.adapters.web.email_routes import email_router  # noqa: E402
from app.api.ocr.routes import ocr_router  # noqa: E402
from app.bootstrap import bootstrap_system  # noqa: E402
from app.config.version import VERSION as __version__  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format=(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "message": "%(message)s"}'
    ),
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting JARVIS v3.0")
    bootstrap_system()
    yield
    logger.info("Shutting down JARVIS")


app = FastAPI(
    title="JARVIS Personal AI Platform",
    version=__version__,
    description="Single-tenant personal AI assistant platform with hybrid cognitive engine.",
    lifespan=lifespan,
)

# CORS
allowed_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(
    request: Request, call_next: Callable[[Request], Response]
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    start_time = time.time()

    logger.info(
        f'{{"event": "request_start", "correlation_id": "{correlation_id}", '
        f'"method": "{request.method}", "path": "{request.url.path}"}}'
    )

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f'{{"event": "request_end", "correlation_id": "{correlation_id}", '
        f'"status_code": {response.status_code}, "duration_ms": {process_time * 1000:.2f}}}'
    )

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time"] = str(process_time)

    return response


# Register routers
app.include_router(http_router)
app.include_router(ws_router)
app.include_router(web_router)
app.include_router(ocr_router)
app.include_router(email_router)

# Mount frontend assets. The HTML references /static/<file>, and the JS/CSS
# live under frontend/assets/, so serve that directory directly.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if (FRONTEND_DIR / "assets").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="static")
elif FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend():
    from fastapi.responses import FileResponse

    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "JARVIS API — frontend not built"}


@app.get("/health")
async def health_check() -> dict[str, object]:
    return {"status": "healthy", "system": "JARVIS v3.0"}


@app.get("/ready")
async def readiness_check() -> Response:
    import json as _json

    try:
        container = bootstrap_system()
        checks = {
            "model_router": container.model_router is not None,
            "memory_service": container.memory_service is not None,
            "session_manager": container.session_manager is not None,
            "safety_policy": container.safety_policy is not None,
        }
        all_ready = all(checks.values())
        status_code = 200 if all_ready else 503
        return Response(
            content=_json.dumps({"ready": all_ready, "checks": checks}),
            status_code=status_code,
            media_type="application/json",
        )
    except Exception as e:
        return Response(
            content=_json.dumps({"ready": False, "error": str(e)}),
            status_code=503,
            media_type="application/json",
        )


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    container = bootstrap_system()
    metrics = container.metrics if hasattr(container, "metrics") else None
    if metrics:
        metrics_text = (
            metrics.export_prometheus()
            if hasattr(metrics, "export_prometheus")
            else "# No metrics available"
        )
        return Response(content=metrics_text, media_type="text/plain")
    return Response(content="# Metrics not available", media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
