"""Structured error envelope (ARCHITECTURE.md §10). Every DomainError and
every unhandled exception must come back through the same JSON shape, and a
traceback must never reach the client (CLAUDE.md rule 7).

Exercises the real global exception handlers by attaching a temporary
raising route to a scratch app instance built from the same create_app()
factory used in production — nothing here touches the real route table.
"""
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.errors import Conflict
from app.main import create_app


def _client_with_temp_route(router: APIRouter) -> AsyncClient:
    app = create_app()
    app.include_router(router)
    # Starlette's ServerErrorMiddleware sends our custom 500 response AND
    # re-raises the original exception afterward — real ASGI servers
    # (uvicorn) just log that re-raise and the client never sees it.
    # raise_app_exceptions=False makes httpx behave the same way, so this
    # test observes what an actual client receives.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_domain_error_returns_structured_envelope():
    router = APIRouter()

    @router.get("/__test/domain-error")
    async def _raise_domain_error():
        raise Conflict("Simulated domain rule violation.", details={"field": "quantity"})

    async with _client_with_temp_route(router) as client:
        resp = await client.get("/__test/domain-error")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["message"] == "Simulated domain rule violation."
    assert body["error"]["details"] == {"field": "quantity"}
    assert "requestId" in body


async def test_framework_404_returns_same_envelope_shape(client):
    """A route that simply doesn't exist must return the same envelope as a
    raised DomainError — not Starlette's bare {"detail": "..."} default."""
    resp = await client.get("/api/this-route-does-not-exist")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "requestId" in body


async def test_unhandled_exception_returns_structured_envelope_not_traceback():
    router = APIRouter()

    @router.get("/__test/boom")
    async def _raise_unexpected():
        raise RuntimeError("something genuinely unexpected")

    async with _client_with_temp_route(router) as client:
        resp = await client.get("/__test/boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in resp.text
    assert "something genuinely unexpected" not in resp.text
