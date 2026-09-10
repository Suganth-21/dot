"""Analytics — ARCHITECTURE.md §8.10; BUILDPHASES.md Phase 8. Smoke tests:
every endpoint returns 200 with the expected top-level keys, real aggregate
counts are consistent with a real action, and "own scope" is enforced.
Real HTTP requests against a real database.
"""
import pytest


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_pharmacy_stats_own_scope(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.get("/api/analytics/pharmacy/ph_1/stats", headers=retailer)
    assert resp.status_code == 200
    body = resp.json()
    assert "activeBatches" in body
    assert body["activeBatches"] >= 1  # the seeded 44-batch fixture always has some


@pytest.mark.asyncio
async def test_pharmacy_stats_reflects_a_real_return(client, seeded):
    retailer = await _headers(client, "RETAILER")
    before = (await client.get("/api/analytics/pharmacy/ph_1/stats", headers=retailer)).json()
    await client.post(
        "/api/returns",
        json={"batchId": "BATCH-DOX-2026-A17", "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    after = (await client.get("/api/analytics/pharmacy/ph_1/stats", headers=retailer)).json()
    assert after["pendingReturns"] == before["pendingReturns"] + 1


@pytest.mark.asyncio
async def test_pharmacy_stats_other_pharmacy_forbidden(client, seeded):
    retailer = await _headers(client, "RETAILER")  # ph_1
    resp = await client.get("/api/analytics/pharmacy/ph_2/stats", headers=retailer)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_YOUR_ENTITY"


@pytest.mark.asyncio
async def test_regulator_can_view_any_pharmacys_stats(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    resp = await client.get("/api/analytics/pharmacy/ph_2/stats", headers=regulator)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pharmacy_sparkline(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.get("/api/analytics/pharmacy/ph_1/sparkline", headers=retailer)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 30
    assert all("day" in d and "value" in d for d in body)


@pytest.mark.asyncio
async def test_pharmacy_analytics_marks_synthetic(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.get("/api/analytics/pharmacy/ph_1", headers=retailer)
    assert resp.status_code == 200
    body = resp.json()
    assert body["synthetic"] is True
    assert "monthlySales" in body and "kpis" in body


@pytest.mark.asyncio
async def test_distributor_stats_and_analytics(client, seeded):
    distributor = await _headers(client, "DISTRIBUTOR")
    stats = await client.get("/api/analytics/distributor/dist_1/stats", headers=distributor)
    assert stats.status_code == 200
    assert "pendingPickups" in stats.json()

    analytics = await client.get("/api/analytics/distributor/dist_1", headers=distributor)
    assert analytics.status_code == 200
    assert "weekly" in analytics.json()


@pytest.mark.asyncio
async def test_manufacturer_stats_and_analytics(client, seeded):
    manufacturer = await _headers(client, "MANUFACTURER")
    stats = await client.get("/api/analytics/manufacturer/mfr_1/stats", headers=manufacturer)
    assert stats.status_code == 200
    assert "destroyedThisMonth" in stats.json()

    analytics = await client.get("/api/analytics/manufacturer/mfr_1", headers=manufacturer)
    assert analytics.status_code == 200
    assert "destroyed" in analytics.json()


@pytest.mark.asyncio
async def test_regulator_stats_and_analytics(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    stats = await client.get("/api/analytics/regulator/stats", headers=regulator)
    assert stats.status_code == 200
    assert "activeAlerts" in stats.json()

    analytics = await client.get("/api/analytics/regulator", headers=regulator)
    assert analytics.status_code == 200
    body = analytics.json()
    assert "national" in body and "network" in body


@pytest.mark.asyncio
async def test_regulator_analytics_requires_regulator_role(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.get("/api/analytics/regulator", headers=retailer)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analytics_requires_authentication(client, seeded):
    resp = await client.get("/api/analytics/pharmacy/ph_1/stats")
    assert resp.status_code == 401
