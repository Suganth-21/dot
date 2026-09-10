"""Seeded batch/event data — BUILDPHASES.md Phase 2 §23-25. Exercises the
real reset path, not fixtures — a batch whose chain doesn't actually verify
would be seed-data theater, not a foundation for later phases.
"""
import pytest
from sqlalchemy import func, select

from app.models.batch import Batch
from app.models.event import Event
from app.seed.reset import reset_demo_data
from app.services import event_service


@pytest.mark.asyncio
async def test_expected_batch_count(seeded, db_session):
    count = (await db_session.execute(select(func.count()).select_from(Batch))).scalar_one()
    assert count == 44


@pytest.mark.asyncio
async def test_hero_batch_a17(seeded, db_session):
    batch = await db_session.get(Batch, "BATCH-DOX-2026-A17")
    assert batch is not None
    assert batch.drug_name == "Doxorubicin 50mg"
    assert batch.pharmacy_id == "ph_1"
    assert batch.initial_quantity == 50
    assert batch.quantity == 50
    assert batch.status.value == "EXPIRING_SOON"


@pytest.mark.asyncio
async def test_hero_batch_b04_is_destroyed_with_complete_chain(seeded, db_session):
    batch = await db_session.get(Batch, "BATCH-DOX-2026-B04")
    assert batch is not None
    assert batch.pharmacy_id == "ph_3"
    assert batch.quantity == 40
    assert batch.destroyed is True
    assert batch.cert_id == "CERT-DOX-2026-B04-2026"

    result = await event_service.verify_chain(db_session, batch.id)
    assert result["valid"] is True
    assert result["checked"] == 8


@pytest.mark.asyncio
async def test_fake_batch_does_not_exist(seeded, db_session):
    batch = await db_session.get(Batch, "BATCH-FAKE-9999-Z01")
    assert batch is None


@pytest.mark.asyncio
async def test_every_seeded_batch_chain_verifies(seeded, db_session):
    batch_ids = (await db_session.execute(select(Batch.id))).scalars().all()
    assert len(batch_ids) == 44

    for batch_id in batch_ids:
        result = await event_service.verify_chain(db_session, batch_id)
        assert result["valid"] is True, f"{batch_id}: {result}"
        assert result["checked"] > 0


@pytest.mark.asyncio
async def test_reset_is_deterministic_at_the_event_hash_level(seeded, db_session):
    """Stronger than logical equivalence: every event's canonical hash is
    computed from fields that are themselves fully deterministic (pinned
    DEMO_NOW, fixed-seed PRNG, entities' own fixed coordinates — see
    app/seed/seed_batches.py), so two resets must reproduce byte-identical
    hashes, even though the Ed25519 keypair (and therefore the signature)
    is freshly generated, and legitimately differs, on every reset."""

    async def snapshot():
        result = await db_session.execute(
            select(Event.batch_id, Event.sequence, Event.hash, Event.prev_hash).order_by(
                Event.batch_id, Event.sequence
            )
        )
        return result.all()

    before = await snapshot()
    await reset_demo_data(db_session)
    db_session.expire_all()
    after = await snapshot()

    assert len(before) == len(after)
    assert before == after
