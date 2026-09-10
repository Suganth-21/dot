"""The database itself refuses a forked or duplicated chain — ARCHITECTURE.md
§4.4 "Constraints — these are the teeth", BUILDPHASES.md Phase 2 §21.
These exercise the real PostgreSQL schema (a raw INSERT through the ORM),
not the Python service's own error handling — the service is not what is
under test here, the `UNIQUE` constraints are.
"""
import uuid
from datetime import UTC

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import EventType
from app.models.event import Event

BATCH_ID = "BATCH-DOX-2026-A17"  # seeded with exactly 1 event (sequence 0)


def _make_event(**overrides) -> Event:
    defaults = dict(
        id=f"evt_test_{uuid.uuid4().hex[:8]}",
        batch_id=BATCH_ID,
        sequence=99,
        type=EventType.SALE,
        actor_id="ph_1",
        actor_name="Apollo Pharmacy — T. Nagar",
        actor_role="RETAILER",
        ts=None,
        gps_lat=None,
        gps_lng=None,
        photo_hash=None,
        meta={},
        prev_hash="1" * 64,
        hash="2" * 64,
        signature="fake-signature",
        signer_key_id="ph_1",
    )
    defaults.update(overrides)
    from datetime import datetime

    if defaults["ts"] is None:
        defaults["ts"] = datetime.now(UTC)
    return Event(**defaults)


@pytest.mark.asyncio
async def test_duplicate_batch_id_and_sequence_is_rejected(seeded, db_session):
    # A17 already has an event at sequence 0.
    dup = _make_event(sequence=0, prev_hash="3" * 64, hash="4" * 64)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_hash_is_rejected(seeded, db_session):
    from sqlalchemy import select

    existing_hash = (await db_session.execute(
        select(Event.hash).where(Event.batch_id == BATCH_ID).limit(1)
    )).scalar_one()

    dup = _make_event(sequence=1, prev_hash="5" * 64, hash=existing_hash)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_batch_id_and_prev_hash_is_rejected(seeded, db_session):
    from sqlalchemy import select

    existing_prev_hash = (await db_session.execute(
        select(Event.prev_hash).where(Event.batch_id == BATCH_ID).limit(1)
    )).scalar_one()

    # A second event claiming to follow the same prior event — a fork.
    dup = _make_event(sequence=1, prev_hash=existing_prev_hash, hash="6" * 64)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_a_correctly_chained_second_event_is_accepted(seeded, db_session):
    """Negative-test control: proves the three rejections above are really
    about the constraint being violated, not about inserting a second event
    at all."""
    from sqlalchemy import select

    existing_hash = (await db_session.execute(
        select(Event.hash).where(Event.batch_id == BATCH_ID).limit(1)
    )).scalar_one()

    ok_event = _make_event(sequence=1, prev_hash=existing_hash, hash="7" * 64)
    db_session.add(ok_event)
    await db_session.commit()  # must not raise
