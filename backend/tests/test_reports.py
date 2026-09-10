"""Reports — ARCHITECTURE.md §4.9, §8.6; BUILDPHASES.md Phase 8. Real HTTP
requests against a real database.
"""
import pytest


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_generate_report_requires_regulator(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.post("/api/reports", json={}, headers=retailer)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_report_with_defaults(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    resp = await client.post("/api/reports", json={}, headers=regulator)
    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "Tamil Nadu"
    assert body["category"] == "all"
    assert "CDSCO Compliance Report" in body["title"]
    assert body["size"].endswith("MB")


@pytest.mark.asyncio
async def test_generate_report_with_explicit_fields(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    resp = await client.post(
        "/api/reports", json={"title": "Q3 Oncology Review", "region": "Chennai", "category": "oncology"},
        headers=regulator,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Q3 Oncology Review"
    assert body["region"] == "Chennai"
    assert body["category"] == "oncology"


@pytest.mark.asyncio
async def test_list_reports_returns_generated_reports_newest_first(client, seeded):
    regulator = await _headers(client, "REGULATOR")
    await client.post("/api/reports", json={"title": "First"}, headers=regulator)
    await client.post("/api/reports", json={"title": "Second"}, headers=regulator)

    resp = await client.get("/api/reports", headers=regulator)
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert titles.index("Second") < titles.index("First")
