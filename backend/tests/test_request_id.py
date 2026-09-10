"""Every response carries a traceable X-Request-ID header, generated when
absent and honoured when the caller supplies one (BUILDPHASES.md Phase 0 §7)."""
import uuid


async def test_request_id_generated_when_absent(client):
    resp = await client.get("/api/health")
    request_id = resp.headers.get("x-request-id")
    assert request_id
    uuid.UUID(request_id)  # raises ValueError if not a valid UUID


async def test_request_id_honoured_when_supplied(client):
    supplied = "test-trace-abc-123"
    resp = await client.get("/api/health", headers={"X-Request-ID": supplied})
    assert resp.headers.get("x-request-id") == supplied
