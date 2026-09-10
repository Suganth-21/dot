"""Re-entry detection — ARCHITECTURE.md §7.3, wired into registration
(`POST /api/batches`) and sale (`POST /api/batches/{id}/sale`) per
BUILDPHASES.md Phase 3. Real HTTP requests against a real database, seeded
via the real reset path — see ARCHITECTURE.md's "How to test" list under §7.3.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.errors import Conflict
from app.core.rbac import Role
from app.models.alert import Alert
from app.models.batch import Batch
from app.models.event import Event
from app.models.user import User
from app.services import batch_service

DESTROYED_BATCH = "BATCH-DOX-2026-B04"  # ph_3, pre-destroyed — see app/seed/seed_batches.py

_REGISTER_PAYLOAD = {
    "batchId": DESTROYED_BATCH, "drugName": "Doxorubicin 50mg", "drugKey": "DOX",
    "category": "oncology", "unitPrice": 4200, "manufacturerId": "mfr_1",
    "manufacturerName": "Cipla Ltd.", "mfgDate": "2026-01-01T00:00:00Z",
    "expiryDate": "2027-01-01T00:00:00Z", "quantity": 10,
}


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


def _fake_actor(entity_id: str) -> User:
    """An unpersisted `User` for a service-level call — `record_sale` only
    ever reads `actor.entity_id` / `.name` / `.role`, never queries this row
    back out of the database, so it never needs to be committed. Used here
    because the one seeded RETAILER demo account is `ph_1`, and
    `BATCH-DOX-2026-B04` belongs to `ph_3` — the pharmacy that originally
    registered it, which is exactly who a sale-side re-entry attempt would
    plausibly come from."""
    return User(
        id="usr_test_ph3", email="test-ph3@dot.in", password_hash="x", name="Test PH3 Login",
        role=Role.RETAILER, entity_id=entity_id, is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_registering_destroyed_batch_is_refused_with_409(client, seeded):
    token = await _token(client, "RETAILER")
    resp = await client.post(
        "/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "BATCH_DESTROYED_REENTRY"
    alert = body["error"]["details"]["alert"]
    assert alert["type"] == "REENTRY"
    assert alert["severity"] == "critical"
    assert alert["batchId"] == DESTROYED_BATCH
    assert alert["status"] == "OPEN"


@pytest.mark.asyncio
async def test_registering_destroyed_batch_appends_reentry_blocked_event(client, seeded, db_session):
    token = await _token(client, "RETAILER")
    await client.post("/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"})

    result = await db_session.execute(
        select(Event).where(Event.batch_id == DESTROYED_BATCH).order_by(Event.sequence)
    )
    events = list(result.scalars().all())
    assert events[-1].type.value == "REENTRY_BLOCKED"
    assert events[-1].meta["source"] == "registration"


@pytest.mark.asyncio
async def test_registering_destroyed_batch_creates_exactly_one_alert(client, seeded, db_session):
    token = await _token(client, "RETAILER")
    await client.post("/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"})

    result = await db_session.execute(
        select(Alert).where(Alert.type == "REENTRY", Alert.batch_id == DESTROYED_BATCH)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].severity.value == "critical"
    assert rows[0].manufacturer_id == "mfr_1"


@pytest.mark.asyncio
async def test_reentry_does_not_change_batch_quantity_or_status(client, seeded, db_session):
    before = await db_session.get(Batch, DESTROYED_BATCH)
    before_qty, before_status = before.quantity, before.status

    token = await _token(client, "RETAILER")
    await client.post("/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"})

    db_session.expire_all()
    after = await db_session.get(Batch, DESTROYED_BATCH)
    assert after.quantity == before_qty
    assert after.status == before_status


@pytest.mark.asyncio
async def test_repeated_registration_attempts_each_raise_their_own_alert(client, seeded, db_session):
    token = await _token(client, "RETAILER")
    await client.post("/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    await client.post("/api/batches", json=_REGISTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"})

    result = await db_session.execute(
        select(Alert).where(Alert.type == "REENTRY", Alert.batch_id == DESTROYED_BATCH)
    )
    assert len(result.scalars().all()) == 2


@pytest.mark.asyncio
async def test_registering_active_batch_id_stays_a_flat_conflict(client, seeded):
    """ARCHITECTURE.md §7.5.1's documented deviation: Phase 3 only changes
    the DESTROYED branch — a duplicate id for a non-destroyed batch is
    still a flat 409, not a re-entry alert."""
    token = await _token(client, "RETAILER")
    resp = await client.post(
        "/api/batches",
        json={**_REGISTER_PAYLOAD, "batchId": "BATCH-DOX-2026-A17"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BATCH_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_selling_a_destroyed_batch_is_refused_and_raises_reentry_alert(seeded, db_session):
    """Service-level: `record_sale` requires `batch.pharmacy_id ==
    actor.entity_id`, and B04's registering pharmacy is `ph_3` — not the
    one seeded RETAILER demo account (`ph_1`) — so this is exercised
    directly against the service rather than through a demo-login token."""
    actor = _fake_actor("ph_3")
    with pytest.raises(Conflict) as exc_info:
        await batch_service.record_sale(db_session, actor, DESTROYED_BATCH, 5)
    assert exc_info.value.code == "BATCH_DESTROYED_REENTRY"

    db_session.expire_all()
    batch = await db_session.get(Batch, DESTROYED_BATCH)
    assert batch.quantity == 40  # unchanged — BUILDPHASES.md seed spec: B04 is 40 units

    result = await db_session.execute(
        select(Event).where(Event.batch_id == DESTROYED_BATCH).order_by(Event.sequence)
    )
    events = list(result.scalars().all())
    assert events[-1].type.value == "REENTRY_BLOCKED"
    assert events[-1].meta["source"] == "sale"

    result = await db_session.execute(
        select(Alert).where(Alert.type == "REENTRY", Alert.batch_id == DESTROYED_BATCH)
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_selling_someone_elses_batch_is_still_forbidden_before_any_reentry_check(seeded, db_session):
    """Ownership is checked before re-entry — a non-owner shouldn't be able
    to trigger an alert (or learn a batch is destroyed) on a batch that
    isn't theirs by crafting a sale request."""
    actor = _fake_actor("ph_1")  # not B04's registering pharmacy
    with pytest.raises(Exception) as exc_info:
        await batch_service.record_sale(db_session, actor, DESTROYED_BATCH, 5)
    assert exc_info.value.code == "NOT_YOUR_BATCH"

    result = await db_session.execute(
        select(Alert).where(Alert.type == "REENTRY", Alert.batch_id == DESTROYED_BATCH)
    )
    assert result.scalars().all() == []
