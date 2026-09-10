"""Rate limiting. CLAUDE.md rule 4 / ARCHITECTURE.md §6.6: "Public endpoints
are rate-limited, never protected by making them harder to reach." Tighter
limits are configurable (`PUBLIC_VERIFY_RATE_LIMIT`,
`PUBLIC_REPORT_RATE_LIMIT` in `app.config`) and applied per-route in
`app.api.routes_public`.

Phase 9 (BUILDPHASES.md: "Rate limiting on all authenticated endpoints, not
only public ones") adds `default_limits` here — every route gets this
baseline unless it already carries a tighter per-route
`@limiter.limit(...)`. Deliberately generous (`DEFAULT_RATE_LIMIT`,
default 1000/minute): tight enough to stop a scripted flood, loose enough
that no normal session — or the ~190-test pytest suite, which shares one
fake client "IP" across its entire run — ever brushes it. A demo/production
deployment that wants it tighter sets `DEFAULT_RATE_LIMIT` in `.env`.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

limiter = Limiter(key_func=get_remote_address, default_limits=[get_settings().default_rate_limit])


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Same envelope as every other error response (ARCHITECTURE.md §10) —
    slowapi's own default handler doesn't know our shape."""
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Please wait a moment.",
                "details": None,
            },
            "requestId": request_id,
        },
    )
