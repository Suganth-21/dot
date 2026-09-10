"""GET/POST /api/batches — ARCHITECTURE.md §8.2. Real HTTP requests against
a real database, seeded via the real reset path."""
import pytest

RETAILER_EMAIL = "retailer@dot.in"
DEMO_PASSWORD = "Demo@Test123"


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_list_batches_scopes_to_own_pharmacy_for_retailer(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get("/api/batches", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(b["pharmacyId"] == "ph_1" for b in body)


@pytest.mark.asyncio
async def test_list_batches_regulator_sees_all(client, seeded):
    token = await _token(client, "REGULATOR")
    resp = await client.get("/api/batches", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 44


@pytest.mark.asyncio
async def test_list_batches_manufacturer_scopes_to_own_manufactured(client, seeded):
    token = await _token(client, "MANUFACTURER")
    resp = await client.get("/api/batches", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(b["manufacturerId"] == "mfr_1" for b in body)


@pytest.mark.asyncio
async def test_list_batches_pickup_agent_sees_none_yet(client, seeded):
    token = await _token(client, "PICKUP_AGENT")
    resp = await client.get("/api/batches", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_batches_requires_authentication(client, seeded):
    resp = await client.get("/api/batches")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_hero_batch_a17_by_id(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get("/api/batches/BATCH-DOX-2026-A17", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["drugName"] == "Doxorubicin 50mg"
    assert body["status"] == "EXPIRING_SOON"
    assert body["quantity"] == 50
    assert body["initialQuantity"] == 50
    assert body["holder"] == {"type": "PHARMACY", "id": "ph_1", "name": "Apollo Pharmacy — T. Nagar"}
    assert len(body["events"]) == 1
    assert body["events"][0]["type"] == "REGISTERED"
    assert body["events"][0]["prevHash"] == "0" * 64


@pytest.mark.asyncio
async def test_get_hero_batch_b04_by_code(client, seeded):
    token = await _token(client, "REGULATOR")
    resp = await client.get("/api/batches/DOX-2026-B04", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "BATCH-DOX-2026-B04"
    assert body["status"] == "DESTROYED"
    assert body["destroyed"] is True
    assert body["certId"] == "CERT-DOX-2026-B04-2026"
    event_types = [e["type"] for e in body["events"]]
    assert event_types == [
        "REGISTERED", "RETURN_INITIATED", "PICKUP_ASSIGNED", "PICKED_UP",
        "DISTRIBUTOR_CONFIRMED", "FORWARDED", "FACILITY_SCHEDULED", "DESTROYED",
    ]


@pytest.mark.asyncio
async def test_fake_batch_does_not_exist(client, seeded):
    token = await _token(client, "REGULATOR")
    resp = await client.get("/api/batches/BATCH-FAKE-9999-Z01", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retailer_cannot_read_another_pharmacys_batch(client, seeded):
    token = await _token(client, "RETAILER")  # ph_1
    # BATCH-DOX-2026-B04 belongs to ph_3.
    resp = await client.get("/api/batches/BATCH-DOX-2026-B04", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_batch_creates_batch_and_registered_event(client, seeded):
    token = await _token(client, "RETAILER")
    payload = {
        "batchId": "BATCH-TEST-2026-Z01", "drugName": "Cefixime 200mg", "drugKey": "CEF",
        "category": "antibiotics", "unitPrice": 320, "manufacturerId": "mfr_2",
        "manufacturerName": "Sun Pharmaceutical Industries", "mfgDate": "2026-01-01T00:00:00Z",
        "expiryDate": "2027-01-01T00:00:00Z", "quantity": 25,
    }
    resp = await client.post("/api/batches", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reentry"] is False
    batch = body["batch"]
    assert batch["id"] == "BATCH-TEST-2026-Z01"
    assert batch["pharmacyId"] == "ph_1"
    assert batch["quantity"] == 25
    assert batch["initialQuantity"] == 25
    assert batch["status"] == "ACTIVE"
    assert len(batch["events"]) == 1
    assert batch["events"][0]["type"] == "REGISTERED"
    assert batch["events"][0]["meta"]["quantity"] == 25


@pytest.mark.asyncio
async def test_register_batch_rejects_duplicate_id(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.post(
        "/api/batches",
        json={
            "batchId": "BATCH-DOX-2026-A17", "drugName": "Doxorubicin 50mg", "drugKey": "DOX",
            "category": "oncology", "unitPrice": 4200, "manufacturerId": "mfr_1",
            "manufacturerName": "Cipla Ltd.", "mfgDate": "2026-01-01T00:00:00Z",
            "expiryDate": "2027-01-01T00:00:00Z", "quantity": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_register_batch_requires_retailer_role(client, seeded):
    token = await _token(client, "DISTRIBUTOR")
    resp = await client.post(
        "/api/batches",
        json={
            "batchId": "BATCH-TEST-2026-Z02", "drugName": "Cefixime 200mg", "drugKey": "CEF",
            "category": "antibiotics", "unitPrice": 320, "manufacturerId": "mfr_2",
            "manufacturerName": "Sun Pharmaceutical Industries", "mfgDate": "2026-01-01T00:00:00Z",
            "expiryDate": "2027-01-01T00:00:00Z", "quantity": 25,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_registered_batch_chain_verifies(client, seeded):
    retailer_token = await _token(client, "RETAILER")
    await client.post(
        "/api/batches",
        json={
            "batchId": "BATCH-TEST-2026-Z03", "drugName": "Cefixime 200mg", "drugKey": "CEF",
            "category": "antibiotics", "unitPrice": 320, "manufacturerId": "mfr_2",
            "manufacturerName": "Sun Pharmaceutical Industries", "mfgDate": "2026-01-01T00:00:00Z",
            "expiryDate": "2027-01-01T00:00:00Z", "quantity": 25,
        },
        headers={"Authorization": f"Bearer {retailer_token}"},
    )
    regulator_token = await _token(client, "REGULATOR")
    resp = await client.get(
        "/api/batches/BATCH-TEST-2026-Z03/verify-chain", headers={"Authorization": f"Bearer {regulator_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["checked"] == 1
    assert body["brokenAtSequence"] is None
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_verify_chain_requires_regulator_role(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get(
        "/api/batches/BATCH-DOX-2026-A17/verify-chain", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_all_seeded_batch_chains_verify(client, seeded):
    token = await _token(client, "REGULATOR")
    list_resp = await client.get("/api/batches", headers={"Authorization": f"Bearer {token}"})
    batch_ids = [b["id"] for b in list_resp.json()]
    assert len(batch_ids) == 44

    for batch_id in batch_ids:
        resp = await client.get(f"/api/batches/{batch_id}/verify-chain", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True, f"{batch_id}: {body}"


@pytest.mark.asyncio
async def test_search_finds_batch_by_drug_name(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get("/api/search?q=doxorubicin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["id"] == "BATCH-DOX-2026-A17" for r in results)


@pytest.mark.asyncio
async def test_search_finds_pharmacy_by_name(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get("/api/search?q=apollo", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["type"] == "pharmacy" and r["id"] == "ph_1" for r in results)


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.get("/api/search?q=", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []
