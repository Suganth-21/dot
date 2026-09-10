"""The return flow and the dispute gate — ARCHITECTURE.md §4.5, §5.2, §7.1,
§8.3; BUILDPHASES.md Phase 4. Real HTTP requests against a real database,
seeded via the real reset path.
"""
import asyncio
from datetime import UTC

import pytest
from sqlalchemy import select

from app.models.alert import Alert
from app.models.batch import Batch
from app.models.event import Event
from app.models.notification import Notification
from app.models.return_ import Return

A17 = "BATCH-DOX-2026-A17"  # ph_1, dist_1, EXPIRING_SOON, 50 units — see app/seed/seed_batches.py
B04 = "BATCH-DOX-2026-B04"  # ph_3, DESTROYED


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


async def _headers(client, role: str) -> dict:
    return {"Authorization": f"Bearer {await _token(client, role)}"}


async def _create_return(client, headers, *, batch_id=A17, quantity=50, distributor_id="dist_1", reason="EXPIRED"):
    resp = await client.post(
        "/api/returns",
        json={"batchId": batch_id, "quantity": quantity, "distributorId": distributor_id, "reason": reason,
              "photoHash": "0xstrip" + batch_id},
        headers=headers,
    )
    return resp


# ---------------------------------------------------------------------------
# CREATE RETURN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retailer_can_create_valid_return(client, seeded):
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["batchId"] == A17
    assert body["pharmacyId"] == "ph_1"
    assert body["distributorId"] == "dist_1"
    assert body["quantityClaimed"] == 50
    assert body["quantityReceived"] is None
    assert body["pickedQuantity"] is None
    assert body["status"] == "REQUESTED"
    assert body["reason"] == "EXPIRED"


@pytest.mark.asyncio
async def test_unauthorized_retailer_cannot_create_return_for_another_pharmacys_batch(client, seeded):
    # The only seeded RETAILER demo account is ph_1; B04 belongs to ph_3.
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers, batch_id=B04, quantity=10)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_YOUR_BATCH"


@pytest.mark.asyncio
async def test_invalid_quantity_exceeding_held_is_rejected(client, seeded):
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers, quantity=9999)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "QUANTITY_EXCEEDS_HELD"


@pytest.mark.asyncio
async def test_zero_quantity_is_rejected(client, seeded):
    headers = await _headers(client, "RETAILER")
    resp = await client.post(
        "/api/returns",
        json={"batchId": A17, "quantity": 0, "distributorId": "dist_1", "reason": "EXPIRED"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_return_generates_return_initiated_event(client, seeded, db_session):
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers)
    assert resp.status_code == 200

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "RETURN_INITIATED"
    assert events[-1].meta["quantity"] == 50
    assert events[-1].meta["reason"] == "EXPIRED"


@pytest.mark.asyncio
async def test_create_return_sets_batch_in_return_status(client, seeded, db_session):
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers)
    assert resp.status_code == 200

    db_session.expire_all()
    batch = await db_session.get(Batch, A17)
    assert batch.status.value == "IN_RETURN"


@pytest.mark.asyncio
async def test_create_return_notifies_distributor_and_retailer(client, seeded, db_session):
    headers = await _headers(client, "RETAILER")
    resp = await _create_return(client, headers)
    assert resp.status_code == 200

    result = await db_session.execute(select(Notification))
    roles = {n.role.value for n in result.scalars().all()}
    assert "DISTRIBUTOR" in roles
    assert "RETAILER" in roles


@pytest.mark.asyncio
async def test_create_return_on_already_in_return_batch_is_rejected(client, seeded):
    headers = await _headers(client, "RETAILER")
    first = await _create_return(client, headers, quantity=10)
    assert first.status_code == 200

    second = await _create_return(client, headers, quantity=5)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "BATCH_NOT_RETURNABLE"


@pytest.mark.asyncio
async def test_create_return_on_destroyed_batch_fires_reentry_not_a_normal_return(client, seeded):
    """ARCHITECTURE.md §7.6 rule-interaction table: "Create return | rules
    ... re-entry" — reuses fraud_service rather than a second implementation."""
    # ph_1 has no destroyed batch of its own in the seed; exercise this at
    # the service layer directly against B04 (ph_3) the same way
    # test_reentry.py does for record_sale.
    from datetime import datetime

    from app.core.errors import Conflict
    from app.core.rbac import Role
    from app.models.user import User
    from app.schemas.return_ import CreateReturnRequest
    from app.services import return_service

    actor = User(
        id="usr_test_ph3", email="test-ph3-return@dot.in", password_hash="x", name="Test PH3",
        role=Role.RETAILER, entity_id="ph_3", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    payload = CreateReturnRequest(batch_id=B04, quantity=5, distributor_id="dist_1", reason="EXPIRED")

    from app.db import async_session_factory

    async with async_session_factory() as session:
        with pytest.raises(Conflict) as exc_info:
            await return_service.create_return(session, actor, payload)
    assert exc_info.value.code == "BATCH_DESTROYED_REENTRY"


@pytest.mark.asyncio
async def test_wrong_role_cannot_create_return(client, seeded):
    headers = await _headers(client, "DISTRIBUTOR")
    resp = await _create_return(client, headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_return_requires_authentication(client, seeded):
    resp = await client.post(
        "/api/returns", json={"batchId": A17, "quantity": 10, "distributorId": "dist_1", "reason": "EXPIRED"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# RECEIVE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distributor_can_receive_matching_quantity_confirms(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.patch(
        f"/api/returns/{created['id']}/receive",
        json={"quantityReceived": 50, "photoHash": "0xdist", "notes": "matches"},
        headers=distributor,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"dispute": False, "alert": None}

    get_resp = await client.get(f"/api/returns/{created['id']}", headers=distributor)
    body = get_resp.json()
    assert body["status"] == "CONFIRMED"
    assert body["quantityClaimed"] == 50  # untouched — independent attestation
    assert body["quantityReceived"] == 50


@pytest.mark.asyncio
async def test_quantity_claimed_preserved_and_quantity_received_independent(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor,
    )
    get_resp = await client.get(f"/api/returns/{created['id']}", headers=distributor)
    body = get_resp.json()
    # Neither quantity was copied into the other at any point.
    assert body["quantityClaimed"] == 50
    assert body["quantityReceived"] == 45
    assert body["pickedQuantity"] is None


@pytest.mark.asyncio
async def test_mismatch_creates_disputed_status_and_alert(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dispute"] is True
    assert body["alert"]["type"] == "QUANTITY_MISMATCH"
    assert body["alert"]["severity"] == "high"

    get_resp = await client.get(f"/api/returns/{created['id']}", headers=distributor)
    assert get_resp.json()["status"] == "DISPUTED"

    result = await db_session.execute(
        select(Alert).where(Alert.type == "QUANTITY_MISMATCH", Alert.batch_id == A17)
    )
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_receive_confirm_generates_distributor_confirmed_event(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor)

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "DISTRIBUTOR_CONFIRMED"
    assert events[-1].meta["received"] == 50


@pytest.mark.asyncio
async def test_receive_dispute_does_not_generate_a_batch_event(client, seeded, db_session):
    """Matches the mock and ARCHITECTURE.md §7.1 exactly: a dispute raises
    an alert but does not touch the batch's event chain — the batch stays
    pharmacy-held until the dispute clears."""
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "RETURN_INITIATED"  # unchanged since creation

    db_session.expire_all()
    batch = await db_session.get(Batch, A17)
    assert batch.holder_type.value == "PHARMACY"


@pytest.mark.asyncio
async def test_wrong_distributor_cannot_receive(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    # Only one DISTRIBUTOR demo account (dist_1) exists; simulate dist_2
    # directly at the service layer.
    from datetime import datetime

    from app.core.errors import Forbidden
    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.schemas.return_ import DistributorReceiveRequest
    from app.services import return_service

    actor = User(
        id="usr_test_dist2", email="test-dist2@dot.in", password_hash="x", name="Test Dist2",
        role=Role.DISTRIBUTOR, entity_id="dist_2", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    async with async_session_factory() as session:
        with pytest.raises(Forbidden) as exc_info:
            await return_service.distributor_receive(
                session, actor, created["id"], DistributorReceiveRequest(quantity_received=50),
            )
    assert exc_info.value.code == "NOT_YOUR_RETURN"


@pytest.mark.asyncio
async def test_receive_on_already_forwarded_return_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor)
    await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)

    resp = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RETURN_NOT_RECEIVABLE"


@pytest.mark.asyncio
async def test_repeat_receive_after_confirmed_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    first = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor,
    )
    assert first.status_code == 200

    second = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "RETURN_NOT_RECEIVABLE"


# ---------------------------------------------------------------------------
# DISPUTE GATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disputed_return_blocks_forward_direct_bypass_returns_409(client, seeded):
    """The required direct-bypass proof (item 10): create a dispute, then
    call forward directly with a valid distributor token — no UI involved."""
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    resp = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "CHAIN_HALTED_DISPUTE"
    assert body["error"]["message"] == "Quantity dispute unresolved. Chain halted."


@pytest.mark.asyncio
async def test_blank_resolution_notes_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    resp = await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": ""}, headers=distributor,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "RESOLUTION_NOTES_REQUIRED"


@pytest.mark.asyncio
async def test_whitespace_only_resolution_notes_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    resp = await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": "   "}, headers=distributor,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "RESOLUTION_NOTES_REQUIRED"


@pytest.mark.asyncio
async def test_valid_resolution_clears_dispute_and_unlocks_forwarding(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    resolve_resp = await client.patch(
        f"/api/returns/{created['id']}/resolve",
        json={"resolutionNotes": "Recounted with pharmacy — 45 confirmed correct."},
        headers=distributor,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json() == {"ok": True}

    get_resp = await client.get(f"/api/returns/{created['id']}", headers=distributor)
    body = get_resp.json()
    assert body["status"] == "CONFIRMED"
    assert body["resolutionNotes"] == "Recounted with pharmacy — 45 confirmed correct."

    # Forwarding is now unlocked — proves the gate actually reopened.
    fwd_resp = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert fwd_resp.status_code == 200
    assert created["id"] in fwd_resp.json()["forwarded"]


@pytest.mark.asyncio
async def test_dispute_resolved_event_generated(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)
    await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": "confirmed by phone"}, headers=distributor,
    )

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "DISPUTE_RESOLVED"
    assert events[-1].meta["notes"] == "confirmed by phone"


@pytest.mark.asyncio
async def test_resolution_closes_the_quantity_mismatch_alert(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)
    await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": "confirmed by phone"}, headers=distributor,
    )

    result = await db_session.execute(select(Alert).where(Alert.type == "QUANTITY_MISMATCH", Alert.batch_id == A17))
    alert = result.scalar_one()
    assert alert.status.value == "CLOSED"
    assert alert.audit_trail[-1]["action"] == "RESOLVED_AT_DISTRIBUTOR"
    assert alert.audit_trail[-1]["notes"] == "confirmed by phone"


@pytest.mark.asyncio
async def test_resolve_non_disputed_return_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    resp = await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": "not disputed yet"}, headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RETURN_NOT_DISPUTED"


# ---------------------------------------------------------------------------
# FORWARD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmed_return_can_forward(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor)

    resp = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["forwarded"] == [created["id"]]
    assert body["skipped"] == []

    get_resp = await client.get(f"/api/returns/{created['id']}", headers=distributor)
    assert get_resp.json()["status"] == "FORWARDED"


@pytest.mark.asyncio
async def test_forward_appends_forwarded_event(client, seeded, db_session):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=distributor)
    await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)

    result = await db_session.execute(select(Event).where(Event.batch_id == A17).order_by(Event.sequence))
    events = list(result.scalars().all())
    assert events[-1].type.value == "FORWARDED"


@pytest.mark.asyncio
async def test_forwarding_requested_return_directly_is_illegal(client, seeded):
    """A never-received return has no business being forwarded — never
    trust a client-supplied status (item 11)."""
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    resp = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RETURN_NOT_CONFIRMED"


@pytest.mark.asyncio
async def test_forward_unowned_return_is_silently_skipped_not_leaked(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    # dist_2 has no demo login; simulate a second distributor directly.
    from datetime import datetime

    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.services import return_service

    actor = User(
        id="usr_test_dist2b", email="test-dist2b@dot.in", password_hash="x", name="Test Dist2",
        role=Role.DISTRIBUTOR, entity_id="dist_2", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    async with async_session_factory() as session:
        result = await return_service.forward_returns(session, actor, [created["id"]])
    assert result.forwarded == []
    assert result.skipped == [created["id"]]


@pytest.mark.asyncio
async def test_forward_nonexistent_return_id_is_skipped_not_500(client, seeded):
    distributor = await _headers(client, "DISTRIBUTOR")
    resp = await client.post(
        "/api/returns/forward", json={"returnIds": ["ret_does_not_exist"]}, headers=distributor,
    )
    assert resp.status_code == 200
    assert resp.json()["skipped"] == ["ret_does_not_exist"]


@pytest.mark.asyncio
async def test_forward_requires_distributor_role(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()

    resp = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=retailer)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# KANBAN STATUS TRANSITIONS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kanban_forward_only_chain_succeeds(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    for status in ("SCHEDULED", "PICKED_UP", "CONFIRMED"):
        resp = await client.patch(
            f"/api/returns/{created['id']}/status", json={"status": status}, headers=distributor,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == status


@pytest.mark.asyncio
async def test_kanban_skipping_a_stage_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    resp = await client.patch(
        f"/api/returns/{created['id']}/status", json={"status": "CONFIRMED"}, headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_kanban_backwards_transition_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/status", json={"status": "SCHEDULED"}, headers=distributor)

    resp = await client.patch(
        f"/api/returns/{created['id']}/status", json={"status": "REQUESTED"}, headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_kanban_move_out_of_disputed_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)

    resp = await client.patch(
        f"/api/returns/{created['id']}/status", json={"status": "CONFIRMED"}, headers=distributor,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CHAIN_HALTED_DISPUTE"


@pytest.mark.asyncio
async def test_kanban_manipulating_status_via_arbitrary_string_is_rejected(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    resp = await client.patch(
        f"/api/returns/{created['id']}/status", json={"status": "TOTALLY_MADE_UP"}, headers=distributor,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_STATUS"


# ---------------------------------------------------------------------------
# AUTHORIZATION
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manufacturer_cannot_receive_a_return(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    manufacturer = await _headers(client, "MANUFACTURER")

    resp = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 50}, headers=manufacturer,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pickup_agent_sees_no_returns_yet(client, seeded):
    """PICKUP_AGENT *is* in the `returns:read` permission matrix (unlike
    `alerts:read`), so the role guard lets it through — but the service
    layer returns an empty list, matching `batch_service.list_batches`'s
    identical Phase-5-not-implemented-yet behavior."""
    headers = await _headers(client, "PICKUP_AGENT")
    resp = await client.get("/api/returns", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_returns_list_requires_authentication(client, seeded):
    resp = await client.get("/api/returns")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_retailer_cannot_read_another_pharmacys_return(client, seeded):
    # Simulate a ph_3-owned return, then confirm ph_1's RETAILER token can't read it.
    from datetime import datetime

    from app.core.rbac import Role
    from app.db import async_session_factory
    from app.models.user import User
    from app.schemas.return_ import CreateReturnRequest
    from app.services import return_service

    actor = User(
        id="usr_test_ph3c", email="test-ph3c@dot.in", password_hash="x", name="Test PH3",
        role=Role.RETAILER, entity_id="ph_3", is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )
    # ph_3 needs its own ACTIVE/EXPIRING/EXPIRED batch to return — register one.
    async with async_session_factory() as session:
        from app.schemas.batch import RegisterBatchRequest
        from app.services import batch_service

        await batch_service.register_batch(
            session, actor,
            RegisterBatchRequest(
                batch_id="BATCH-TEST-2026-RET1", drug_name="Cefixime 200mg", drug_key="CEF",
                category="antibiotics", unit_price=320, manufacturer_id="mfr_2",
                manufacturer_name="Sun Pharmaceutical Industries",
                mfg_date="2026-01-01T00:00:00Z", expiry_date="2027-01-01T00:00:00Z", quantity=10,
            ),
        )
    async with async_session_factory() as session:
        created = await return_service.create_return(
            session, actor, CreateReturnRequest(batch_id="BATCH-TEST-2026-RET1", quantity=5,
                                                  distributor_id="dist_1", reason="EXPIRED"),
        )

    retailer = await _headers(client, "RETAILER")  # ph_1
    resp = await client.get(f"/api/returns/{created.id}", headers=retailer)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_YOUR_RETURN"


# ---------------------------------------------------------------------------
# CONCURRENCY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_receive_calls_produce_exactly_one_outcome(client, seeded, db_session):
    """Two concurrent `receive` calls with different quantities against the
    same return — the row lock in `return_repo.get_for_update` must
    serialize them so exactly one wins and the loser sees the
    already-updated (no-longer-receivable) row, not a corrupted read."""
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")

    async def receive(qty):
        return await client.patch(
            f"/api/returns/{created['id']}/receive", json={"quantityReceived": qty}, headers=distributor,
        )

    r1, r2 = await asyncio.gather(receive(50), receive(45))
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409]  # exactly one succeeded

    winner = r1 if r1.status_code == 200 else r2
    winning_qty = 50 if winner.json()["dispute"] is False else 45

    db_session.expire_all()
    ret = await db_session.get(Return, created["id"])
    assert ret.quantity_received == winning_qty
    assert ret.status.value in ("CONFIRMED", "DISPUTED")

    # No duplicate/contradictory DISTRIBUTOR_CONFIRMED events — at most one.
    result = await db_session.execute(
        select(Event).where(Event.batch_id == A17, Event.type == "DISTRIBUTOR_CONFIRMED")
    )
    confirmed_events = result.scalars().all()
    assert len(confirmed_events) <= 1

    verify_resp = await client.get(
        f"/api/batches/{A17}/verify-chain", headers=await _headers(client, "REGULATOR"),
    )
    assert verify_resp.json()["valid"] is True


# ---------------------------------------------------------------------------
# EVENT INTEGRITY / FULL CHAIN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_return_flow_chain_still_verifies(client, seeded):
    retailer = await _headers(client, "RETAILER")
    created = (await _create_return(client, retailer, quantity=50)).json()
    distributor = await _headers(client, "DISTRIBUTOR")
    await client.patch(f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor)
    await client.patch(
        f"/api/returns/{created['id']}/resolve", json={"resolutionNotes": "verified count"}, headers=distributor,
    )
    fwd = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert fwd.status_code == 200

    regulator = await _headers(client, "REGULATOR")
    verify_resp = await client.get(f"/api/batches/{A17}/verify-chain", headers=regulator)
    body = verify_resp.json()
    assert body["valid"] is True
    assert body["checked"] == 4  # REGISTERED, RETURN_INITIATED, DISPUTE_RESOLVED, FORWARDED

    batch_resp = await client.get(f"/api/batches/{A17}", headers=regulator)
    event_types = [e["type"] for e in batch_resp.json()["events"]]
    assert event_types == ["REGISTERED", "RETURN_INITIATED", "DISPUTE_RESOLVED", "FORWARDED"]


# ---------------------------------------------------------------------------
# DEMO PATH — steps 1, 2, 3, 6 (BUILDPHASES.md Phase 4 "Demoable")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_path_create_inbox_dispute_gate(client, seeded):
    # 1-2: Pharmacy already has stock (seeded A17); Start Return.
    retailer = await _headers(client, "RETAILER")
    created_resp = await _create_return(client, retailer, quantity=50, reason="EXPIRED")
    assert created_resp.status_code == 200
    created = created_resp.json()
    assert created["status"] == "REQUESTED"

    # 3: Return appears in the distributor's inbox.
    distributor = await _headers(client, "DISTRIBUTOR")
    inbox_resp = await client.get("/api/returns?distributorId=dist_1&status=REQUESTED", headers=distributor)
    assert any(r["id"] == created["id"] for r in inbox_resp.json())

    # 6: Distributor records a mismatching quantity -> dispute gate fires.
    recv_resp = await client.patch(
        f"/api/returns/{created['id']}/receive", json={"quantityReceived": 45}, headers=distributor,
    )
    assert recv_resp.json()["dispute"] is True

    blocked = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert blocked.status_code == 409

    # Resolution notes reopen the path.
    resolved = await client.patch(
        f"/api/returns/{created['id']}/resolve",
        json={"resolutionNotes": "Pharmacy confirmed 45 was correct after recount."},
        headers=distributor,
    )
    assert resolved.status_code == 200

    forwarded = await client.post("/api/returns/forward", json={"returnIds": [created["id"]]}, headers=distributor)
    assert forwarded.status_code == 200
    assert created["id"] in forwarded.json()["forwarded"]
