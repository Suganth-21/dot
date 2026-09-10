"""Request-id middleware.

Every request gets a request id — the caller's own `X-Request-ID` header if
they sent one (so a client-side trace correlates end to end), otherwise a
generated UUID4. It's attached to `request.state`, echoed back in the
response header, and logged at start and finish. The exception handlers in
`app.core.errors` read it off `request.state` too, so every error response
and every log line for one request share the same id.
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("dot.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming else str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        logger.info(
            "request_started method=%s path=%s",
            request.method,
            request.url.path,
            extra={"request_id": request_id},
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request_finished status=%s duration_ms=%s",
            response.status_code,
            duration_ms,
            extra={"request_id": request_id},
        )
        return response
