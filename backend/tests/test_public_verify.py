"""GET /api/public/verify/{batchId}, POST /api/public/report —
ARCHITECTURE.md §3, §6.6, §7.3, §8.7. CLAUDE.md rule 4: these routes must
never require authentication, forever. Real HTTP requests against a real
database, seeded via the real reset path.
"""
import re

import pytest

from app.core.rate_limit import limiter

GENUINE_BATCH = "BATCH-DOX-2026-A17"  # EXPIRING_SOON — see app/seed/seed_batches.py
DESTROYED_BATCH = "BATCH-DOX-2026-B04"
FAKE_BATCH = "BATCH-FAKE-9999-Z01"  # deliberately absent from the seed


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter's in-memory storage is a module-level singleton shared
    across every test's `app` instance (conftest's `app` fixture builds a
    fresh FastAPI app per test, but `app.core.rate_limit.limiter` itself is
    imported once) — reset it before each test so one test's calls never
    eat into another's budget."""
    limiter.reset()
    yield


@pytest.mark.asyncio
async def test_verify_genuine_batch_by_id_no_auth_header(client, seeded):
    resp = await client.get(f"/api/public/verify/{GENUINE_BATCH}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "GENUINE"
    assert body["batch"]["id"] == GENUINE_BATCH
    assert body["batch"]["drugName"] == "Doxorubicin 50mg"
    assert body["batch"]["status"] == "EXPIRING_SOON"
    # Public responses exclude quantities, holder chain, event meta, GPS —
    # ARCHITECTURE.md §3.
    assert "quantity" not in body["batch"]
    assert "holder" not in body["batch"]


@pytest.mark.asyncio
async def test_verify_genuine_batch_by_bare_code(client, seeded):
    resp = await client.get("/api/public/verify/DOX-2026-A17")
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "GENUINE"


@pytest.mark.asyncio
async def test_verify_destroyed_batch_returns_red_verdict(client, seeded):
    resp = await client.get(f"/api/public/verify/{DESTROYED_BATCH}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "DESTROYED"
    assert body["batch"]["certId"] == "CERT-DOX-2026-B04-2026"
    assert body["batch"]["destroyedDate"] is not None
    assert len(body["history"]) == 5
    assert body["history"][-1]["type"] == "DESTROYED"


@pytest.mark.asyncio
async def test_verify_destroyed_batch_does_not_raise_a_reentry_alert(client, seeded, db_session):
    """ARCHITECTURE.md §7.3: "Public verification of a destroyed batch
    returns the red verdict but does NOT raise a REENTRY alert."""
    from sqlalchemy import select

    from app.models.alert import Alert

    await client.get(f"/api/public/verify/{DESTROYED_BATCH}")

    result = await db_session.execute(select(Alert).where(Alert.type == "REENTRY"))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_verify_unknown_batch_via_batch_prefix_fallback_is_not_found(client, seeded):
    resp = await client.get("/api/public/verify/FAKE-9999-Z01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "NOT_FOUND"
    assert body["batchId"] == "FAKE-9999-Z01"


@pytest.mark.asyncio
async def test_verify_deliberately_absent_batch_is_not_found(client, seeded):
    resp = await client.get(f"/api/public/verify/{FAKE_BATCH}")
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_report_suspicious_without_batch_id(client, seeded):
    resp = await client.post(
        "/api/public/report",
        json={"batchId": None, "location": {"lat": 13.08, "lng": 80.27, "district": "Chennai"},
              "notes": "smells off", "pharmacyName": "Some Pharmacy"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["batchId"] is None
    assert body["notes"] == "smells off"
    assert body["location"]["district"] == "Chennai"


@pytest.mark.asyncio
async def test_report_suspicious_on_destroyed_batch_raises_critical_patient_report_alert(client, seeded, db_session):
    from sqlalchemy import select

    from app.models.alert import Alert

    resp = await client.post(
        "/api/public/report",
        json={"batchId": DESTROYED_BATCH, "location": {"district": "Chennai"}, "notes": "found on shelf"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(Alert).where(Alert.type == "PATIENT_REPORT", Alert.batch_id == DESTROYED_BATCH)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].severity.value == "critical"
    assert rows[0].entity_id == "public"


@pytest.mark.asyncio
async def test_report_suspicious_on_genuine_batch_raises_high_severity_alert(client, seeded, db_session):
    from sqlalchemy import select

    from app.models.alert import Alert

    resp = await client.post(
        "/api/public/report",
        json={"batchId": GENUINE_BATCH, "location": {"district": "Chennai"}, "notes": "looks off"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(Alert).where(Alert.type == "PATIENT_REPORT", Alert.batch_id == GENUINE_BATCH)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].severity.value == "high"


@pytest.mark.asyncio
async def test_verify_rate_limit_returns_429_with_standard_envelope(client, seeded, monkeypatch):
    from app.config import get_settings

    # Mutating the cached Settings singleton's attribute directly (rather
    # than env var + cache_clear) so monkeypatch's own teardown reverts it
    # cleanly regardless of lru_cache timing.
    monkeypatch.setattr(get_settings(), "public_verify_rate_limit", "2/minute")

    for _ in range(2):
        resp = await client.get(f"/api/public/verify/{GENUINE_BATCH}")
        assert resp.status_code == 200
    resp = await client.get(f"/api/public/verify/{GENUINE_BATCH}")
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_report_rate_limit_returns_429(client, seeded, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "public_report_rate_limit", "1/minute")

    resp = await client.post("/api/public/report", json={"notes": "first"})
    assert resp.status_code == 200
    resp = await client.post("/api/public/report", json={"notes": "second"})
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_no_public_route_ever_requires_authentication(app, client):
    """ARCHITECTURE.md §6.6: "A test asserts every /api/public/* route
    returns non-401 with no credentials, and it fails the build if a new
    route is added without one." Iterates the app's actual route table
    rather than a hardcoded list, so a future route added to
    routes_public.py is covered automatically — and a route that somehow
    picked up an auth dependency fails this immediately with a 401."""
    checked_any = False
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/public"):
            continue
        methods = getattr(route, "methods", None) or set()
        built_path = re.sub(r"\{(\w+)\}", "x", path)

        for method in methods:
            if method == "GET":
                resp = await client.get(built_path)
            elif method == "POST":
                resp = await client.post(built_path, json={})
            else:
                continue
            checked_any = True
            assert resp.status_code != 401, f"{method} {built_path} required authentication"

    assert checked_any, "no /api/public/* routes were found to check"
