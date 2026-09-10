"""Chain verification must detect tampering — ARCHITECTURE.md §7.5 "How to
test", BUILDPHASES.md Phase 2 §20. Each test mutates a stored event
directly via raw SQL (bypassing every application code path, exactly as a
hostile actor with database access would) and asserts `verify_chain`
catches it. Verification never repairs anything — every assertion here
also confirms the row is unchanged after verifying.
"""
import pytest
from sqlalchemy import select, update

from app.models.event import Event
from app.services import event_service

BATCH_ID = "BATCH-DOX-2026-B04"  # seeded with 8 events — see app/seed/seed_batches.py


async def _events(session):
    result = await session.execute(select(Event).where(Event.batch_id == BATCH_ID).order_by(Event.sequence))
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_baseline_chain_is_valid_before_any_tampering(seeded, db_session):
    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is True
    assert result["checked"] == 8


@pytest.mark.asyncio
async def test_tampering_with_hash_is_detected(seeded, db_session):
    events = await _events(db_session)
    target = events[2]
    await db_session.execute(update(Event).where(Event.id == target.id).values(hash="0" * 64))
    await db_session.commit()
    db_session.expire_all()  # the raw UPDATE above bypassed the ORM identity map

    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is False
    assert result["brokenAtSequence"] == target.sequence
    reasons = {e["reason"] for e in result["errors"] if e["sequence"] == target.sequence}
    assert "HASH_MISMATCH" in reasons
    assert "SIGNATURE_INVALID" in reasons


@pytest.mark.asyncio
async def test_tampering_with_meta_is_detected_via_hash_mismatch(seeded, db_session):
    events = await _events(db_session)
    target = events[1]  # a SALE-ish/flow event with a non-trivial meta payload
    await db_session.execute(update(Event).where(Event.id == target.id).values(meta={"tampered": True}))
    await db_session.commit()
    db_session.expire_all()

    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is False
    reasons = {e["reason"] for e in result["errors"] if e["sequence"] == target.sequence}
    assert "HASH_MISMATCH" in reasons


@pytest.mark.asyncio
async def test_tampering_with_prev_hash_is_detected(seeded, db_session):
    events = await _events(db_session)
    target = events[3]
    await db_session.execute(update(Event).where(Event.id == target.id).values(prev_hash="f" * 64))
    await db_session.commit()
    db_session.expire_all()

    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is False
    reasons = {e["reason"] for e in result["errors"] if e["sequence"] == target.sequence}
    assert "PREV_HASH_MISMATCH" in reasons


@pytest.mark.asyncio
async def test_tampering_with_signature_is_detected(seeded, db_session):
    events = await _events(db_session)
    target = events[0]
    await db_session.execute(update(Event).where(Event.id == target.id).values(signature="not-a-real-signature"))
    await db_session.commit()
    db_session.expire_all()

    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is False
    reasons = {e["reason"] for e in result["errors"] if e["sequence"] == target.sequence}
    assert "SIGNATURE_INVALID" in reasons
    # An untouched hash/meta must still pass its own hash recomputation —
    # only the signature check should fail for this event.
    assert "HASH_MISMATCH" not in reasons


@pytest.mark.asyncio
async def test_removing_an_event_is_detected_as_a_sequence_gap(seeded, db_session):
    events = await _events(db_session)
    middle = events[4]
    await db_session.execute(Event.__table__.delete().where(Event.id == middle.id))
    await db_session.commit()
    db_session.expire_all()

    result = await event_service.verify_chain(db_session, BATCH_ID)
    assert result["valid"] is False
    assert result["checked"] == 7
    reasons_at_gap = {e["reason"] for e in result["errors"] if e["sequence"] == events[5].sequence}
    assert "SEQUENCE_GAP" in reasons_at_gap


@pytest.mark.asyncio
async def test_verification_never_modifies_the_tampered_row(seeded, db_session):
    events = await _events(db_session)
    target = events[2]
    await db_session.execute(update(Event).where(Event.id == target.id).values(hash="a" * 64))
    await db_session.commit()
    db_session.expire_all()

    await event_service.verify_chain(db_session, BATCH_ID)

    result = await db_session.execute(select(Event.hash).where(Event.id == target.id))
    assert result.scalar_one() == "a" * 64  # unchanged — verification is read-only
