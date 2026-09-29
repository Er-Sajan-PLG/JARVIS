"""JARVIS FastAPI Application Entrypoint & Server Mount."""

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Load .env before anything else
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.adapters import http_router, ws_router  # noqa: E402
from app.adapters.web.brief_routes import brief_router  # noqa: E402
from app.adapters.web.email_routes import email_router  # noqa: E402
from app.adapters.web.notify_routes import notify_router  # noqa: E402
from app.adapters.web.push_routes import push_public_router, push_router  # noqa: E402
from app.adapters.web.router import web_router  # noqa: E402
from app.adapters.web.voice_routes import voice_router  # noqa: E402
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

# The Telegram client puts the bot token in the request URL *path*
# (app/integrations/telegram/__init__.py), and httpx logs the full URL at INFO.
# With the root logger at INFO that wrote the live credential into the systemd
# journal on every poll -- 55,552 occurrences between 2026-09-17 and 2026-09-29.
# Quiet the transport loggers so a third-party URL can never re-introduce a
# secret into the journal. Rotating the leaked token is still required.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting JARVIS v3.0")
    bootstrap_system()
    # Telegram two-way bot: background poller, only when explicitly enabled
    # with a token. Polling (not webhooks) keeps the tailnet-only deployment.
    telegram_task = None
    try:
        from app.integrations.telegram import TelegramConfig, TelegramPoller

        tg_config = TelegramConfig.from_env()
        if tg_config.ready:
            poller = TelegramPoller(tg_config)
            telegram_task = asyncio.create_task(poller.run_forever())
            logger.info("Telegram poller task started")
        else:
            logger.info("Telegram poller disabled (no token or TELEGRAM_ENABLED!=true)")
    except Exception as exc:  # noqa: BLE001 - comms must not block boot
        logger.warning("Telegram poller failed to start: %s", exc)
    yield
    if telegram_task:
        telegram_task.cancel()
    logger.info("Shutting down JARVIS")


def _resolve_cors_origins() -> list[str]:
    """Allowed browser origins, including the phone-facing host.

    The console is served from the same origin it calls, so CORS matters mainly
    for the install prompt and the service worker. ``JARVIS_PUBLIC_ORIGIN`` lets
    a private tunnel (for example a Tailscale hostname) be allowlisted without
    editing code: set it to the exact URL the phone opens.
    """
    origins = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:8000,http://localhost:3000,"
            "http://127.0.0.1:8000,http://127.0.0.1:3000,"
            "capacitor://localhost,http://localhost,https://localhost",
        ).split(",")
        if origin.strip()
    ]

    public_origin = os.environ.get("JARVIS_PUBLIC_ORIGIN", "").strip().rstrip("/")
    if public_origin and public_origin not in origins:
        origins.append(public_origin)

    return origins


app = FastAPI(
    title="JARVIS Personal AI Platform",
    version=__version__,
    description="Single-tenant personal AI assistant platform with hybrid cognitive engine.",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(
    request: Request, call_next: Callable[[Request], Response]
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    # Migration Step 2.5: publish the ID to the contextvar so the event bus
    # and audit sink observe it without signature changes downstream.
    from app.telemetry.correlation import reset_correlation_id, set_correlation_id

    token = set_correlation_id(correlation_id)
    start_time = time.time()

    logger.info(
        f'{{"event": "request_start", "correlation_id": "{correlation_id}", '
        f'"method": "{request.method}", "path": "{request.url.path}"}}'
    )

    try:
        response = await call_next(request)
    finally:
        reset_correlation_id(token)

    process_time = time.time() - start_time
    logger.info(
        f'{{"event": "request_end", "correlation_id": "{correlation_id}", '
        f'"status_code": {response.status_code}, "duration_ms": {process_time * 1000:.2f}}}'
    )

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time"] = str(process_time)

    return response


# Mount frontend assets
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"

if ASSETS_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(ASSETS_DIR)), name="static")
elif FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Register routers
app.include_router(http_router)
app.include_router(ws_router)
app.include_router(web_router)
app.include_router(ocr_router)
app.include_router(email_router)
app.include_router(notify_router)
app.include_router(voice_router)
app.include_router(push_router)
app.include_router(push_public_router)
app.include_router(brief_router)


# ── PWA surface ──────────────────────────────────────────────────────────────
#
# A phone reaches JARVIS over the network (LAN or a private tunnel), so the
# installable-app surface has to live at the origin root rather than behind a
# prefix: a manifest and a service worker are only honoured at the scope they
# are served from. These routes are what make the console installable and, in
# turn, what makes Web Push reachable on a phone -- a browser will not grant
# notification permission without an active service worker registration.

SERVICE_WORKER_SCOPE = "/"


@app.get("/", include_in_schema=False)
async def serve_spa() -> FileResponse:
    """Serve the console shell so a phone can load and install the app."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(str(index_path), media_type="text/html")


@app.get("/manifest.json", include_in_schema=False)
async def serve_manifest() -> FileResponse:
    manifest_path = ASSETS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    return FileResponse(str(manifest_path), media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
async def serve_service_worker() -> FileResponse:
    """Serve the worker at root scope.

    ``Service-Worker-Allowed: /`` is required because the worker ships from
    ``/static`` as an asset; without it the browser caps the registration scope
    at the script's own directory and the worker cannot control navigations.
    """
    sw_path = ASSETS_DIR / "service-worker.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="service-worker.js not found")
    return FileResponse(
        str(sw_path),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": SERVICE_WORKER_SCOPE},
    )


@app.get("/offline.html", include_in_schema=False)
async def serve_offline() -> FileResponse:
    """Offline fallback. Precached by the service worker, so it must exist."""
    offline_path = FRONTEND_DIR / "offline.html"
    if not offline_path.exists():
        raise HTTPException(status_code=404, detail="offline.html not found")
    return FileResponse(str(offline_path), media_type="text/html")


def _register_asset_route(app: FastAPI, filename: str, media_type: str) -> None:
    """Expose an asset from ``frontend/assets`` at the origin root.

    The manifest and the service worker both reference icons at root paths
    (``/icon-192.png``), and the Web Push API takes the same URLs. A dedicated
    route per file keeps those URLs stable and independent of the ``/static``
    mount. ``HEAD`` is registered alongside ``GET`` because some clients and
    link-preview fetchers probe an image before requesting it.
    """

    async def _serve() -> FileResponse:
        asset_path = ASSETS_DIR / filename
        if not asset_path.exists():
            raise HTTPException(status_code=404, detail=f"{filename} not found")
        return FileResponse(str(asset_path), media_type=media_type)

    _serve.__name__ = f"serve_{filename.replace('.', '_')}"
    app.get(f"/{filename}", include_in_schema=False)(_serve)
    app.head(f"/{filename}", include_in_schema=False)(_serve)


for _asset_name, _asset_type in (
    ("icon-192.png", "image/png"),
    ("icon-512.png", "image/png"),
    ("badge.png", "image/png"),
):
    _register_asset_route(app, _asset_name, _asset_type)


def main() -> None:
    """Run the server for network access.

    Binds ``0.0.0.0`` by default so a phone on the LAN or a private tunnel can
    reach it; ``127.0.0.1`` would be invisible to every other device. Override
    with ``JARVIS_HOST``/``JARVIS_PORT``.

    Warning: binding a non-loopback interface exposes JARVIS to anything that can
    route to this host. Set ``JARVIS_API_KEY`` before doing so -- with the key
    unset, ``app.adapters.security`` deliberately allows every request.
    """
    import uvicorn

    host = os.environ.get("JARVIS_HOST", "0.0.0.0")
    port = int(os.environ.get("JARVIS_PORT", "8000"))

    if host not in {"127.0.0.1", "localhost"} and not os.environ.get("JARVIS_API_KEY", "").strip():
        logger.warning(
            "JARVIS is binding %s with JARVIS_API_KEY unset: authentication is "
            "DISABLED and every device that can reach this host has full control.",
            host,
        )

    uvicorn.run(app, host=host, port=port, log_level=os.environ.get("JARVIS_LOG_LEVEL", "info"))


if __name__ == "__main__":
    main()
