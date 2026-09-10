"""GET /api/health must perform a real database round-trip and honestly
report failure — not blindly return ok (BUILDPHASES.md Phase 0 §8)."""
from unittest.mock import patch


async def test_health_ok_when_db_reachable(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["service"]
    assert body["version"]


async def test_health_reports_db_failure_when_db_unreachable(client):
    """Simulates a DB outage by making the session factory raise, exactly as
    it would if PostgreSQL were down. Proves the endpoint detects the
    failure and reports it (503, db: "error") rather than faking success."""
    with patch("app.api.routes_health.async_session_factory") as mock_factory:
        mock_factory.side_effect = ConnectionRefusedError("simulated DB outage")
        resp = await client.get("/api/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["db"] == "error"
