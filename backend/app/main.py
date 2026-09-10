"""FastAPI application entrypoint. No business logic here — this module
wires middleware, exception handlers, and routers together and nothing
else (CLAUDE.md rule 7).

`create_app()` is a factory rather than a bare module-level `app` so tests
can build isolated instances (see backend/tests/conftest.py).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.middleware import RequestIDMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version=settings.app_version)

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

    return app


app = create_app()
