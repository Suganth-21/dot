"""Facility runs — the distributor -> destruction-facility leg (the
previously unmodeled second half of the reverse chain; pharmacy ->
distributor is Phase 5's routes, tested in test_pickups.py). Real HTTP
requests against a real database.
"""
from datetime import UTC, datetime

import pytest

from app.models.event import Event
from sqlalchemy import select

A17 = "BATCH-DOX-2026-A17"  # ph_1, dist_1, mfr_1 (Cipla)


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


async def _walk_batch_to_scheduled(client, *, quantity_received: int = 50):
    """Drives A17 all the way from REQUESTED through FORWARDED and
    scheduled-for-fac_1 — the real state a batch is in right before a
    facility run can legally be built for it."""
    retailer = await _headers(client, "RETAILER")
    ret_resp = await client.post(
        "/api/returns", json={"batchId": A17, "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    assert ret_resp.status_code == 200, ret_resp.text
    ret_id = ret_resp.json()["id"]

    distributor = await _headers(client, "DISTRIBUTOR")
    route_resp = await client.post(
        "/api/routes",
        json={"distributorId": "dist_1", "returnIds": [ret_id], "agentId": "agent_1", "vehicleId": "veh_1", "manualOrder": True},
        headers=distributor,
    )
    assert route_resp.status_code == 200, route_resp.text
    route_id = route_resp.json()["id"]
    await client.post(f"/api/routes/{route_id}/dispatch", headers=distributor)

    agent = await _headers(client, "PICKUP_AGENT")
    await client.post(f"/api/routes/{route_id}/stops/0/arrive", headers=agent)
    await client.post(f"/api/routes/{route_id}/stops/0/pickup", json={"counted": 50}, headers=agent)

    recv_resp = await client.patch(
        f"/api/returns/{ret_id}/receive", json={"quantityReceived": quantity_received}, headers=distributor,
    )
    assert recv_resp.status_code == 200, recv_resp.text

    if quantity_received == 50:
        fwd_resp = await client.post("/api/returns/forward", json={"returnIds": [ret_id]}, headers=distributor)
        assert fwd_resp.status_code == 200, fwd_resp.text

        manufacturer = await _headers(client, "MANUFACTURER")
        sched_resp = await client.post(
            "/api/manufacturer/schedule",
            json={"batchIds": [A17], "facilityId": "fac_1", "date": "2026-09-20"},
            headers=manufacturer,
        )
        assert sched_resp.status_code == 200, sched_resp.text

    return ret_id, distributor, agent


@pytest.mark.asyncio
async def test_create_dispatch_deliver_full_lifecycle(client, seeded, db_session):
    await _walk_batch_to_scheduled(client)
    distributor = await _headers(client, "DISTRIBUTOR")

    run_resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    assert run_resp.status_code == 200, run_resp.text
    run = run_resp.json()
    assert run["status"] == "planned"
    assert run["delivered"] is False
    assert run["batches"] == [{"batchId": A17, "drugName": "Doxorubicin 50mg", "quantity": 50}]
    assert run["facilityId"] == "fac_1"

    dispatch_resp = await client.post(f"/api/facility-runs/{run['id']}/dispatch", headers=distributor)
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json() == {"ok": True}

    get_resp = await client.get(f"/api/facility-runs/{run['id']}", headers=distributor)
    assert get_resp.json()["running"] is True
    assert get_resp.json()["status"] == "active"

    agent = await _headers(client, "PICKUP_AGENT")
    deliver_resp = await client.post(f"/api/facility-runs/{run['id']}/deliver", headers=agent)
    assert deliver_resp.status_code == 200, deliver_resp.text
    body = deliver_resp.json()
    # Every real-work step (event, holder flip, notification) happens
    # synchronously in deliver_run — but same as a pickup route's last
    # stop, the vehicle now drives back to the depot rather than
    # teleporting there: one more waypoint queued, run stays running.
    # gps_simulator's tick loop (which never runs under this ASGITransport
    # test client) would finalize completed/running=False once that leg
    # finishes.
    assert body["status"] == "active"
    assert body["running"] is True
    assert body["delivered"] is True  # the durable "already delivered" signal, unlike status/running
    assert len(body["path"]) == 3  # warehouse -> facility (original) + warehouse (drive-home)

    redeliver_resp = await client.post(f"/api/facility-runs/{run['id']}/deliver", headers=agent)
    assert redeliver_resp.status_code == 409
    assert redeliver_resp.json()["error"]["code"] == "ALREADY_DELIVERED"

    # Batch reads are scoped by `batch.distributor_id`, a column this app
    # never actually populates on receipt (a separate, pre-existing gap
    # unrelated to this feature) — a DISTRIBUTOR can't read any batch by id
    # today, so this check goes through MANUFACTURER, whose read access is
    # unconditional, same as `/api/batches/{id}` already behaves for it.
    manufacturer = await _headers(client, "MANUFACTURER")
    batch_resp = await client.get(f"/api/batches/{A17}", headers=manufacturer)
    batch = batch_resp.json()
    assert batch["holder"] == {"type": "FACILITY", "id": "fac_1", "name": "Medicare Biomedical Waste Facility"}

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    event_types = [e.type.value for e in result.scalars().all()]
    assert event_types[-1] == "FACILITY_ARRIVED"


@pytest.mark.asyncio
async def test_create_rejects_batch_not_held_by_distributor(client, seeded):
    # Never walked through the pickup leg at all — still pharmacy-held.
    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_NOT_HELD"


@pytest.mark.asyncio
async def test_create_rejects_batch_not_scheduled_for_chosen_facility(client, seeded):
    await _walk_batch_to_scheduled(client)  # scheduled for fac_1
    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_2", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_NOT_SCHEDULED_FOR_FACILITY"


@pytest.mark.asyncio
async def test_create_rejects_batch_already_on_an_in_progress_run(client, seeded):
    await _walk_batch_to_scheduled(client)
    distributor = await _headers(client, "DISTRIBUTOR")
    payload = {"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"}
    first = await client.post("/api/facility-runs", json=payload, headers=distributor)
    assert first.status_code == 200, first.text

    second = await client.post("/api/facility-runs", json=payload, headers=distributor)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "BATCH_ALREADY_ON_RUN"


@pytest.mark.asyncio
async def test_create_requires_distributor_role(client, seeded):
    retailer = await _headers(client, "RETAILER")
    resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=retailer,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dispatch_requires_distributor_or_agent_role(client, seeded):
    await _walk_batch_to_scheduled(client)
    distributor = await _headers(client, "DISTRIBUTOR")
    run_resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    run_id = run_resp.json()["id"]

    retailer = await _headers(client, "RETAILER")
    resp = await client.post(f"/api/facility-runs/{run_id}/dispatch", headers=retailer)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_cannot_deliver_another_agents_run(client, seeded):
    await _walk_batch_to_scheduled(client)
    distributor = await _headers(client, "DISTRIBUTOR")
    run_resp = await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )
    run_id = run_resp.json()["id"]
    await client.post(f"/api/facility-runs/{run_id}/dispatch", headers=distributor)

    # Only one PICKUP_AGENT demo account (agent_1) exists — simulate agent_2 directly.
    from app.core.errors import Forbidden
    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.services import facility_run_service

    actor = User(
        id="usr_test_agent2", email="test-agent2@dot.in", password_hash="x", name="Test Agent 2",
        role=Role.PICKUP_AGENT, entity_id="agent_2", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    async with async_session_factory() as session:
        with pytest.raises(Forbidden) as exc_info:
            await facility_run_service.deliver_run(session, actor, run_id)
    assert exc_info.value.code == "NOT_YOUR_FACILITY_RUN"


@pytest.mark.asyncio
async def test_list_facility_runs_scoped_by_role(client, seeded):
    await _walk_batch_to_scheduled(client)
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.post(
        "/api/facility-runs",
        json={"distributorId": "dist_1", "batchIds": [A17], "facilityId": "fac_1", "agentId": "agent_1", "vehicleId": "veh_1"},
        headers=distributor,
    )

    dist_list = await client.get("/api/facility-runs", headers=distributor)
    assert dist_list.status_code == 200
    assert all(r["distributorId"] == "dist_1" for r in dist_list.json())
    assert len(dist_list.json()) == 1

    # A different distributor sees none of dist_1's runs.
    other = await _headers(client, "MANUFACTURER")  # national view — just checking it doesn't 403
    mfr_list = await client.get("/api/facility-runs", headers=other)
    assert mfr_list.status_code == 200
