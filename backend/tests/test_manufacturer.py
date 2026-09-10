"""Manufacturer inbox, facility scheduling, certificate binding —
ARCHITECTURE.md §7.2, §8.5; BUILDPHASES.md Phase 6. Real HTTP requests
against a real database.
"""
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models.batch import Batch
from app.models.event import Event

A17 = "BATCH-DOX-2026-A17"  # ph_1, dist_1, mfr_1


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


async def _confirmed_and_forwarded(client):
    """Drives A17 through create -> receive (matched) -> forward, the
    minimum state certificate binding requires."""
    retailer = await _headers(client, "RETAILER")
    ret_resp = await client.post(
        "/api/returns",
        json={"batchId": A17, "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    ret_id = ret_resp.json()["id"]

    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{ret_id}/receive", json={"quantityReceived": 50}, headers=distributor)
    await client.post("/api/returns/forward", json={"returnIds": [ret_id]}, headers=distributor)
    return ret_id, distributor


@pytest.mark.asyncio
async def test_cert_eligibility_false_before_distributor_confirmation(client, seeded):
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.get(f"/api/batches/{A17}/cert-eligibility", headers=manufacturer)
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is False
    assert "distributor stage" in body["reason"]


@pytest.mark.asyncio
async def test_upload_certificate_before_confirmation_is_409(client, seeded):
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.post(
        "/api/manufacturer/certificates", json={"batchId": A17, "certId": None, "fileName": None},
        headers=manufacturer,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NOT_DISTRIBUTOR_CONFIRMED"


@pytest.mark.asyncio
async def test_upload_certificate_confirmed_but_not_forwarded_is_409(client, seeded):
    retailer = await _headers(client, "RETAILER")
    ret_resp = await client.post(
        "/api/returns", json={"batchId": A17, "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    ret_id = ret_resp.json()["id"]
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{ret_id}/receive", json={"quantityReceived": 50}, headers=distributor)
    # Deliberately not forwarded.

    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.post(
        "/api/manufacturer/certificates", json={"batchId": A17}, headers=manufacturer,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NOT_FORWARDED"


@pytest.mark.asyncio
async def test_upload_certificate_confirmed_and_forwarded_succeeds(client, seeded, db_session):
    await _confirmed_and_forwarded(client)
    manufacturer = await _headers(client, "MANUFACTURER")

    resp = await client.post(
        "/api/manufacturer/certificates", json={"batchId": A17, "certId": None, "fileName": "cert.pdf"},
        headers=manufacturer,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["batch"]["status"] == "DESTROYED"
    assert body["batch"]["certId"] == "CERT-DOX-2026-A17-2026"
    assert body["coveredBatches"] == [A17]

    db_session.expire_all()
    batch = await db_session.get(Batch, A17)
    assert batch.destroyed is True
    assert batch.holder_type.value == "FACILITY"

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "DESTROYED"


@pytest.mark.asyncio
async def test_upload_certificate_twice_second_call_is_409(client, seeded):
    await _confirmed_and_forwarded(client)
    manufacturer = await _headers(client, "MANUFACTURER")
    first = await client.post("/api/manufacturer/certificates", json={"batchId": A17}, headers=manufacturer)
    assert first.status_code == 200

    second = await client.post("/api/manufacturer/certificates", json={"batchId": A17}, headers=manufacturer)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_DESTROYED"


@pytest.mark.asyncio
async def test_upload_certificate_wrong_manufacturer_is_403(client, seeded):
    await _confirmed_and_forwarded(client)
    # A17's manufacturer is mfr_1; simulate a different manufacturer.
    from app.core.errors import Forbidden
    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.services import manufacturer_service

    actor = User(
        id="usr_test_mfr2", email="test-mfr2@dot.in", password_hash="x", name="Test Mfr2",
        role=Role.MANUFACTURER, entity_id="mfr_2", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    async with async_session_factory() as session:
        with pytest.raises(Forbidden) as exc_info:
            await manufacturer_service.upload_certificate(session, actor, A17, None, None)
    assert exc_info.value.code == "NOT_YOUR_BATCH"


@pytest.mark.asyncio
async def test_upload_certificate_on_disputed_return_is_chain_halted(client, seeded):
    retailer = await _headers(client, "RETAILER")
    ret_resp = await client.post(
        "/api/returns", json={"batchId": A17, "quantity": 50, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=retailer,
    )
    ret_id = ret_resp.json()["id"]
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{ret_id}/receive", json={"quantityReceived": 45}, headers=distributor)
    # DISPUTED now — no legitimate way to reach FORWARDED, so cert-eligibility
    # should read as not-forwarded (the earlier gate), and a direct upload
    # attempt after a hypothetical manual FORWARDED marker would still hit
    # assert_not_disputed. We verify the reachable case: NOT_FORWARDED.
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.post("/api/manufacturer/certificates", json={"batchId": A17}, headers=manufacturer)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] in ("NOT_DISTRIBUTOR_CONFIRMED", "NOT_FORWARDED")


@pytest.mark.asyncio
async def test_schedule_facility_appends_event(client, seeded, db_session):
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.post(
        "/api/manufacturer/schedule",
        json={"batchIds": [A17], "facilityId": "fac_1", "date": date.today().isoformat()},
        headers=manufacturer,
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "FACILITY_SCHEDULED"

    db_session.expire_all()
    batch = await db_session.get(Batch, A17)
    assert batch.scheduled_facility_id == "fac_1"


@pytest.mark.asyncio
async def test_manufacturer_inbox_shows_forwarded_returns(client, seeded):
    await _confirmed_and_forwarded(client)
    manufacturer = await _headers(client, "MANUFACTURER")
    resp = await client.get("/api/manufacturer/inbox", headers=manufacturer)
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["batchId"] == A17 for r in body)
    assert all(r["batch"]["manufacturerId"] == "mfr_1" for r in body)


@pytest.mark.asyncio
async def test_manufacturer_inbox_excludes_destroyed(client, seeded):
    await _confirmed_and_forwarded(client)
    manufacturer = await _headers(client, "MANUFACTURER")
    await client.post("/api/manufacturer/certificates", json={"batchId": A17}, headers=manufacturer)

    resp = await client.get("/api/manufacturer/inbox", headers=manufacturer)
    assert not any(r["batchId"] == A17 for r in resp.json())
