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
from app.adapters.web.push_routes import push_router  # noqa: E402
from app.adapters.web.brief_routes import brief_router  # noqa: E402
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
app.include_router(push_router)
app.include_router(brief_router)
