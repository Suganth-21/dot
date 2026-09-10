"""Entity compliance scoring — ARCHITECTURE.md §8.9; BUILDPHASES.md Phase 8.
Real HTTP requests against a real database.
"""
import pytest


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_list_entities_requires_regulator(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.get("/api/entities", headers=retailer)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_entities_includes_all_three_types(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    resp = await client.get("/api/entities", headers=regulator)
    assert resp.status_code == 200
    body = resp.json()
    types = {e["type"] for e in body}
    assert types == {"PHARMACY", "DISTRIBUTOR", "MANUFACTURER"}
    ph1 = next(e for e in body if e["id"] == "ph_1")
    assert 20 <= ph1["score"] <= 100
    assert ph1["risk"] in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_entity_score_drops_after_reentry_alert(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    before = (await client.get("/api/entities/ph_1", headers=regulator)).json()

    retailer = await _headers(client, "RETAILER")
    await client.post(
        "/api/batches",
        json={"batchId": "BATCH-DOX-2026-B04", "drugName": "Doxorubicin 50mg", "drugKey": "DOX",
              "category": "oncology", "unitPrice": 4200, "manufacturerId": "mfr_1",
              "manufacturerName": "Cipla Ltd.", "mfgDate": "2026-01-01T00:00:00Z",
              "expiryDate": "2027-01-01T00:00:00Z", "quantity": 10},
        headers=retailer,
    )

    after = (await client.get("/api/entities/ph_1", headers=regulator)).json()
    assert after["alertsOn"] == before["alertsOn"] + 1
    assert after["score"] <= before["score"]
    assert len(after["alerts"]) == after["alertsOn"]


@pytest.mark.asyncio
async def test_get_entity_not_found(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    resp = await client.get("/api/entities/does_not_exist", headers=regulator)
    assert resp.status_code == 404
