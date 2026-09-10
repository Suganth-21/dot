"""Pickups, routes, and the agent app — ARCHITECTURE.md §4.6, §5.3, §8.4;
BUILDPHASES.md Phase 5. Real HTTP requests against a real database.
"""
from datetime import UTC

import pytest
from sqlalchemy import select

from app.models.event import Event

A17 = "BATCH-DOX-2026-A17"  # ph_1, dist_1


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


async def _create_and_schedule_return(client):
    retailer = await _headers(client, "RETAILER")
    ret_resp = await client.post(
        "/api/returns",
        json={"batchId": A17, "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    assert ret_resp.status_code == 200, ret_resp.text
    ret_id = ret_resp.json()["id"]

    distributor = await _headers(client, "DISTRIBUTOR")
    route_resp = await client.post(
        "/api/routes",
        json={"distributorId": "dist_1", "returnIds": [ret_id], "agentId": "agent_1", "vehicleId": "veh_1",
              "manualOrder": True},
        headers=distributor,
    )
    assert route_resp.status_code == 200, route_resp.text
    return ret_id, route_resp.json(), distributor


@pytest.mark.asyncio
async def test_create_route_sets_return_scheduled(client, seeded):
    ret_id, route, distributor = await _create_and_schedule_return(client)
    assert route["status"] == "planned"
    assert route["stops"][0]["returnId"] == ret_id

    ret_resp = await client.get(f"/api/returns/{ret_id}", headers=distributor)
    assert ret_resp.json()["status"] == "SCHEDULED"
    assert ret_resp.json()["routeId"] == route["id"]


@pytest.mark.asyncio
async def test_create_route_requires_requested_returns(client, seeded):
    ret_id, _route, distributor = await _create_and_schedule_return(client)
    # Already SCHEDULED — a second route creation attempt must reject it.
    resp = await client.post(
        "/api/routes",
        json={"distributorId": "dist_1", "returnIds": [ret_id], "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RETURN_NOT_SCHEDULABLE"


@pytest.mark.asyncio
async def test_dispatch_flips_running_status_agent_vehicle(client, seeded):
    _ret_id, route, distributor = await _create_and_schedule_return(client)
    resp = await client.post(f"/api/routes/{route['id']}/dispatch", headers=distributor)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    get_resp = await client.get(f"/api/routes/{route['id']}", headers=distributor)
    body = get_resp.json()
    assert body["running"] is True
    assert body["status"] == "active"
    assert body["stops"][0]["status"] == "CURRENT"


@pytest.mark.asyncio
async def test_agent_arrive_and_pickup_append_events_and_update_return(client, seeded, db_session):
    ret_id, route, distributor = await _create_and_schedule_return(client)
    await client.post(f"/api/routes/{route['id']}/dispatch", headers=distributor)

    agent = await _headers(client, "PICKUP_AGENT")
    arrive_resp = await client.post(f"/api/routes/{route['id']}/stops/0/arrive", headers=agent)
    assert arrive_resp.status_code == 200
    assert arrive_resp.json()["stops"][0]["status"] == "ARRIVED"

    pickup_resp = await client.post(
        f"/api/routes/{route['id']}/stops/0/pickup", json={"counted": 45}, headers=agent,
    )
    assert pickup_resp.status_code == 200
    body = pickup_resp.json()
    assert body["stops"][0]["status"] == "DONE"
    assert body["stops"][0]["counted"] == 45
    # Only stop — route completes (ARCHITECTURE.md §5.3: stop-driven, not position-driven).
    assert body["status"] == "completed"
    assert body["running"] is False

    ret_resp = await client.get(f"/api/returns/{ret_id}", headers=distributor)
    ret_body = ret_resp.json()
    assert ret_body["status"] == "PICKED_UP"
    assert ret_body["pickedQuantity"] == 45
    assert ret_body["quantityClaimed"] == 50  # independent attestation, untouched

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    event_types = [e.type.value for e in result.scalars().all()]
    assert event_types[-2:] == ["AGENT_ARRIVED", "PICKED_UP"]


@pytest.mark.asyncio
async def test_pickup_then_dispute_gate_still_works(client, seeded):
    """The documented step-5-into-step-6 demo flow: the retailer claimed
    50 (`_create_and_schedule_return`'s quantity), the agent physically
    counts 45 at the stop, and the dispute gate compares the distributor's
    received count against the *claimed* 50 — not against what the agent
    counted — so entering 45 at receive still (correctly) trips the gate.
    This is the three-quantity independence itself: `pickedQuantity` (45)
    never substitutes for `quantityClaimed` (50) in the dispute check."""
    ret_id, route, distributor = await _create_and_schedule_return(client)
    await client.post(f"/api/routes/{route['id']}/dispatch", headers=distributor)
    agent = await _headers(client, "PICKUP_AGENT")
    await client.post(f"/api/routes/{route['id']}/stops/0/arrive", headers=agent)
    await client.post(f"/api/routes/{route['id']}/stops/0/pickup", json={"counted": 45}, headers=agent)

    recv_resp = await client.patch(
        f"/api/returns/{ret_id}/receive", json={"quantityReceived": 45}, headers=distributor,
    )
    assert recv_resp.json()["dispute"] is True  # claimed 50 != received 45, even though agent also counted 45

    get_resp = await client.get(f"/api/returns/{ret_id}", headers=distributor)
    body = get_resp.json()
    assert body["status"] == "DISPUTED"
    assert body["quantityClaimed"] == 50
    assert body["pickedQuantity"] == 45
    assert body["quantityReceived"] == 45


@pytest.mark.asyncio
async def test_agent_cannot_act_on_another_agents_route(client, seeded):
    _ret_id, route, _distributor = await _create_and_schedule_return(client)
    # Only one PICKUP_AGENT demo account (agent_1, on dist_1) exists, and
    # the route was assigned to agent_1 — simulate agent_2 directly.
    from datetime import datetime

    from app.core.errors import Forbidden
    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.services import pickup_service

    actor = User(
        id="usr_test_agent2", email="test-agent2@dot.in", password_hash="x", name="Test Agent 2",
        role=Role.PICKUP_AGENT, entity_id="agent_2", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    async with async_session_factory() as session:
        with pytest.raises(Forbidden) as exc_info:
            await pickup_service.agent_arrive(session, actor, route["id"], 0)
    assert exc_info.value.code == "NOT_YOUR_ROUTE"


@pytest.mark.asyncio
async def test_dispatch_requires_distributor_or_agent_role(client, seeded):
    _ret_id, route, _distributor = await _create_and_schedule_return(client)
    retailer = await _headers(client, "RETAILER")
    resp = await client.post(f"/api/routes/{route['id']}/dispatch", headers=retailer)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_route_requires_distributor_role(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.post(
        "/api/routes",
        json={"distributorId": "dist_1", "returnIds": [], "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=retailer,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_fleet_scoped_by_distributor(client, seeded):
    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.get("/api/fleet?distributorId=dist_1", headers=distributor)
    assert resp.status_code == 200
    body = resp.json()
    assert all(a["distributorId"] == "dist_1" for a in body["agents"])
    assert all(v["distributorId"] == "dist_1" for v in body["vehicles"])
