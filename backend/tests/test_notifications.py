"""Notification read/mark endpoints — ARCHITECTURE.md §4.8, §8.11;
BUILDPHASES.md Phase 8. Real HTTP requests against a real database.
"""
import pytest


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_get_notifications_requires_authentication(client, seeded):
    resp = await client.get("/api/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_return_produces_a_readable_notification(client, seeded):
    retailer = await _headers(client, "RETAILER")
    await client.post(
        "/api/returns",
        json={"batchId": "BATCH-DOX-2026-A17", "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )

    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.get("/api/notifications", headers=distributor)
    assert resp.status_code == 200
    body = resp.json()
    assert any(n["title"] == "New return in inbox" for n in body)
    assert all(n["read"] is False for n in body if n["title"] == "New return in inbox")


@pytest.mark.asyncio
async def test_notifications_scoped_by_role_not_leaked_across_roles(client, seeded):
    retailer = await _headers(client, "RETAILER")
    await client.post(
        "/api/returns",
        json={"batchId": "BATCH-DOX-2026-A17", "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.get("/api/notifications", headers=manufacturer)
    assert resp.status_code == 200
    assert not any(n["title"] == "New return in inbox" for n in resp.json())


@pytest.mark.asyncio
async def test_mark_all_read(client, seeded):
    retailer = await _headers(client, "RETAILER")
    await client.post(
        "/api/returns",
        json={"batchId": "BATCH-DOX-2026-A17", "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    resp = await client.patch("/api/notifications/read-all", headers=retailer)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    after = (await client.get("/api/notifications", headers=retailer)).json()
    assert all(n["read"] is True for n in after)


@pytest.mark.asyncio
async def test_mark_read_single_notification(client, seeded):
    retailer = await _headers(client, "RETAILER")
    await client.post(
        "/api/returns",
        json={"batchId": "BATCH-DOX-2026-A17", "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    notifications = (await client.get("/api/notifications", headers=retailer)).json()
    target = notifications[0]

    resp = await client.patch(f"/api/notifications/{target['id']}/read", headers=retailer)
    assert resp.status_code == 200

    after = (await client.get("/api/notifications", headers=retailer)).json()
    updated = next(n for n in after if n["id"] == target["id"])
    assert updated["read"] is True


@pytest.mark.asyncio
async def test_mark_read_not_found(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.patch("/api/notifications/ntf_does_not_exist/read", headers=retailer)
    assert resp.status_code == 404
