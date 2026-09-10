"""Structured domain errors and the global exception handler.

CLAUDE.md rule 2: every domain rule is enforced server-side, and a caller
must be able to tell *why* something failed. Services raise a `DomainError`
subclass; routers never construct an `HTTPException` themselves and never
swallow an exception. See ARCHITECTURE.md §10 for the envelope shape and
the code/status table.

Phase 0 defines only the generic hierarchy — no business-specific codes yet.
Later phases raise these (or a feature-specific subclass) from services.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("dot.errors")

# Framework-raised HTTPExceptions (404 route-not-found, 405 method-not-
# allowed, etc.) don't carry a DomainError code — map the common ones so
# they still fit the same envelope as everything else in this API.
_HTTP_STATUS_CODE = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    422: "VALIDATION_ERROR",
}


class DomainError(Exception):
    """Base for every structured application error.

    Raised by services, never by routers or repositories. `code` is the
    machine-readable identifier the frontend branches on; `message` is the
    human-readable string the UI is allowed to render directly (see the
    409 convention in ARCHITECTURE.md §10 and BUILDPHASES.md's error
    conventions section).
    """

    code: str = "DOMAIN_ERROR"
    status_code: int = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None, code: str | None = None):
        self.message = message
        self.details = details or {}
        if code is not None:
            self.code = code
        super().__init__(message)


class ValidationFailed(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422


class Unauthorized(DomainError):
    code = "UNAUTHORIZED"
    status_code = 401


class Forbidden(DomainError):
    code = "FORBIDDEN"
    status_code = 403


class NotFound(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class Conflict(DomainError):
    """The generic 409. Domain-rule violations (dispute gate, certificate
    binding, re-entry, etc.) subclass this or pass an explicit `code` — see
    ARCHITECTURE.md §7."""

    code = "CONFLICT"
    status_code = 409


class RateLimited(DomainError):
    code = "RATE_LIMITED"
    status_code = 429


class InternalError(DomainError):
    code = "INTERNAL_ERROR"
    status_code = 500


def _envelope(code: str, message: str, details: dict[str, Any] | None, request_id: str | None) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details or None},
        "requestId": request_id,
    }


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "domain_error code=%s status=%s path=%s",
        exc.code,
        exc.status_code,
        request.url.path,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.details, request_id),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Catches framework-raised HTTPExceptions (route not found, method not
    allowed, ...) so literally every error response — ours or the
    framework's — comes back in the same envelope (ARCHITECTURE.md §10)."""
    request_id = getattr(request.state, "request_id", None)
    code = _HTTP_STATUS_CODE.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(code, str(exc.detail), None, request_id),
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # Full traceback goes to the server log, keyed by request id. The client
    # never sees it — CLAUDE.md forbids leaking stack traces or internals.
    logger.exception("unhandled_exception path=%s", request.url.path, extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content=_envelope("INTERNAL_ERROR", "An unexpected error occurred.", None, request_id),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
