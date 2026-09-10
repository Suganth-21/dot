"""FastAPI application entrypoint. No business logic here — this module
wires middleware, exception handlers, and routers together and nothing
else (CLAUDE.md rule 7).

`create_app()` is a factory rather than a bare module-level `app` so tests
can build isolated instances (see backend/tests/conftest.py).
"""
import asyncio
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.realtime import hub as realtime_hub
from app.simulation.gps_simulator import run_forever as run_gps_simulator


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Phase 7: the Redis-backed pub/sub hub (ARCHITECTURE.md §9) starts
    # before the Phase 5 GPS simulator, since the simulator publishes
    # position updates through it.
    await realtime_hub.start()
    # Phase 5: one background task advancing every active route's vehicle
    # position (ARCHITECTURE.md §9.4). httpx's ASGITransport (used by the
    # test suite) never invokes lifespan events, so neither this nor the
    # realtime hub ever starts under pytest — only under a real ASGI server
    # (uvicorn).
    task = asyncio.create_task(run_gps_simulator())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await realtime_hub.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=_lifespan)

    # Phase 3: tighter, explicit limits on the public routes
    # (ARCHITECTURE.md §6.6) via `@limiter.limit(...)` in
    # app.api.routes_public. Phase 9 additionally gives every *other* route
    # a generous baseline through the limiter's own `default_limits` (see
    # app/core/rate_limit.py) — "rate limiting on all authenticated
    # endpoints, not only public ones."
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Explicit allowlist only — never "*". CLAUDE.md rule 6 / ARCHITECTURE.md §9.1.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    # Added after CORS so it is the outermost layer: every response —
    # including CORS preflight responses — gets a request id and a log line.
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api")

    # Phase 9 real photo upload — serves what upload_service.save_photo
    # wrote to disk. Created on demand (mkdir at import time would run even
    # for processes that never upload anything, e.g. the test suite).
    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/uploads/files", StaticFiles(directory=str(uploads_dir)), name="uploads")

    return app


app = create_app()
