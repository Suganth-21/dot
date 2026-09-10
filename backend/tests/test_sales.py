"""POST /api/batches/{id}/sale — ARCHITECTURE.md §8.2, §4.9."""
import pytest


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_sale_decrements_quantity_and_appends_sale_event(client, seeded):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}

    before = (await client.get("/api/batches/BATCH-DOX-2026-A17", headers=headers)).json()
    assert before["quantity"] == 50

    resp = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 5}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity"] == 45
    assert body["initialQuantity"] == 50  # never changes
    event_types = [e["type"] for e in body["events"]]
    assert event_types == ["REGISTERED", "SALE"]
    assert body["events"][-1]["meta"]["units"] == 5


@pytest.mark.asyncio
async def test_sale_chain_links_correctly_to_prior_event(client, seeded):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 1}, headers=headers)
    events = resp.json()["events"]
    assert events[1]["prevHash"] == events[0]["hash"]


@pytest.mark.asyncio
async def test_sale_cannot_exceed_available_stock(client, seeded):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 999}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"


@pytest.mark.asyncio
async def test_sale_quantity_never_goes_negative_even_at_the_exact_boundary(client, seeded):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}
    exact = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 50}, headers=headers)
    assert exact.status_code == 200
    assert exact.json()["quantity"] == 0

    over = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 1}, headers=headers)
    assert over.status_code == 409


@pytest.mark.asyncio
async def test_sale_rejects_zero_or_negative_units(client, seeded):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 0}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sale_requires_retailer_role(client, seeded):
    token = await _token(client, "DISTRIBUTOR")
    resp = await client.post(
        "/api/batches/BATCH-DOX-2026-A17/sale", json={"units": 1}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sale_rejects_batch_not_owned_by_caller(client, seeded):
    # A17 belongs to ph_1; the demo retailer IS ph_1, so use B04 (ph_3) instead.
    token = await _token(client, "RETAILER")
    resp = await client.post(
        "/api/batches/BATCH-DOX-2026-B04/sale", json={"units": 1}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_YOUR_BATCH"


@pytest.mark.asyncio
async def test_sale_on_unknown_batch_returns_404(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.post(
        "/api/batches/BATCH-DOES-NOT-EXIST/sale", json={"units": 1}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
