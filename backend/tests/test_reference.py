"""GET /api/reference/* — reads from PostgreSQL in the exact camelCase
shape frontend/src/services/referenceService.js already expects (CLAUDE.md
rule 3, ARCHITECTURE.md §8.8)."""
import pytest


async def _token(client) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": "RETAILER"})
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_distributors_read_from_postgres(client, seeded):
    token = await _token(client)
    resp = await client.get("/api/reference/distributors", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    dist_1 = next(d for d in body if d["id"] == "dist_1")
    assert dist_1["name"] == "Sunrise Pharma Distributors"
    assert dist_1["licenseNo"]  # camelCase alias, not license_no


@pytest.mark.asyncio
async def test_pharmacies_and_pharmacy_detail(client, seeded):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    list_resp = await client.get("/api/reference/pharmacies", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 10

    detail_resp = await client.get("/api/reference/pharmacies/ph_1", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "Apollo Pharmacy — T. Nagar"

    missing_resp = await client.get("/api/reference/pharmacies/ph_does_not_exist", headers=headers)
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_agents_and_vehicles_scope_by_distributor_id(client, seeded):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    all_agents = await client.get("/api/reference/agents", headers=headers)
    assert len(all_agents.json()) == 7

    dist1_agents = await client.get("/api/reference/agents?distributorId=dist_1", headers=headers)
    body = dist1_agents.json()
    assert len(body) == 3
    assert all(a["distributorId"] == "dist_1" for a in body)
    assert any(a["id"] == "agent_1" and a["name"] == "Ravi Kumar" for a in body)

    all_vehicles = await client.get("/api/reference/vehicles", headers=headers)
    assert len(all_vehicles.json()) == 5


@pytest.mark.asyncio
async def test_drugs_reference_data(client, seeded):
    token = await _token(client)
    resp = await client.get("/api/reference/drugs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    keys = {d["key"] for d in resp.json()}
    assert keys == {"DOX", "CIS", "CEF", "MER", "ATO", "AML", "PAR", "MET", "OME"}
