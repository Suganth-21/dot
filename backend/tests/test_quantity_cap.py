"""Quantity-cap check — ARCHITECTURE.md §7.4. Exercised directly against
`fraud_service.check_quantity_cap`, the same way `tests/test_tampering.py`
exercises `event_service.verify_chain` directly: a real, independently
correct implementation of the rule, testable at the service layer without
going through an HTTP endpoint.

This is deliberate, not a shortcut — see the docstring on
`fraud_service.check_quantity_cap` and `batch_service.register_batch`'s
Phase-3 comments: `batches.id` is a primary key, and the registration
endpoint's duplicate-id gate (unchanged from Phase 2 except for the
DESTROYED branch) already refuses any second registration attempt before
this rule could ever be reached, through the API, with a genuinely
*additional* incoming quantity. These tests prove the rule itself — the
arithmetic and the alert it raises — independent of that wiring question.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.alert import Alert
from app.models.batch import Batch
from app.models.enums import BatchStatus, DrugCategory
from app.services import fraud_service

MFR_ID = "mfr_1"  # seeded — see app/seed/seed_data.py


def _batch(id_: str, *, initial_quantity: int, quantity: int, category: DrugCategory,
           status: BatchStatus = BatchStatus.ACTIVE) -> Batch:
    now = datetime.now(timezone.utc)
    return Batch(
        id=id_, code=id_.removeprefix("BATCH-"), drug_key="DOX", drug_name="Doxorubicin 50mg",
        category=category, unit_price=4200, manufacturer_id=MFR_ID, manufacturer_name="Cipla Ltd.",
        pharmacy_id="ph_1", distributor_id=None,
        mfg_date=now - timedelta(days=100), expiry_date=now + timedelta(days=200),
        initial_quantity=initial_quantity, quantity=quantity, status=status,
        holder_type=None, holder_id=None, holder_name=None, destroyed=False,
        created_at=now, updated_at=now,
    )


@pytest.mark.asyncio
async def test_incoming_quantity_within_cap_raises_no_alert(seeded, db_session):
    batch = _batch("BATCH-QCAP-0001", initial_quantity=50, quantity=50, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=0, entity_id="ph_2")
    assert alert is None


@pytest.mark.asyncio
async def test_incoming_quantity_exactly_at_cap_raises_no_alert(seeded, db_session):
    # circulating (50) + incoming (0) == initial_quantity (50) — the
    # boundary, per ARCHITECTURE.md §7.4: "if total <= known.initial_quantity: return None".
    batch = _batch("BATCH-QCAP-0002", initial_quantity=50, quantity=50, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=0, entity_id="ph_2")
    assert alert is None


@pytest.mark.asyncio
async def test_incoming_quantity_over_cap_raises_alert_with_correct_excess(seeded, db_session):
    """ARCHITECTURE.md §7.4's own worked example: initial_quantity 50,
    50 already circulating, 30 more incoming -> excess 30."""
    batch = _batch("BATCH-QCAP-0003", initial_quantity=50, quantity=50, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=30, entity_id="ph_2")
    assert alert is not None
    assert alert.type.value == "QUANTITY_CAP"
    assert "30 unaccounted" in alert.message
    assert alert.entity_id == "ph_2"
    assert alert.manufacturer_id == MFR_ID


@pytest.mark.asyncio
async def test_oncology_breach_is_critical_severity(seeded, db_session):
    batch = _batch("BATCH-QCAP-0004", initial_quantity=50, quantity=50, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=10, entity_id="ph_2")
    assert alert.severity.value == "critical"


@pytest.mark.asyncio
async def test_non_oncology_breach_is_high_severity(seeded, db_session):
    batch = _batch("BATCH-QCAP-0005", initial_quantity=50, quantity=50, category=DrugCategory.antibiotics)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=10, entity_id="ph_2")
    assert alert.severity.value == "high"


@pytest.mark.asyncio
async def test_sold_units_still_count_toward_circulating(seeded, db_session):
    """ARCHITECTURE.md §7.4 "How to test": "Sold units still count toward
    circulation" — `sum_registered_units` sums `initial_quantity` (the
    ceiling this batch was ever registered for), not the live `quantity`
    remaining after sales, so a partially-sold batch still contributes its
    full original amount to `circulating`."""
    batch = _batch("BATCH-QCAP-0006", initial_quantity=50, quantity=30, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=10, entity_id="ph_2")
    assert alert is not None
    assert "10 unaccounted" in alert.message


@pytest.mark.asyncio
async def test_destroyed_batch_contributes_nothing_to_circulating(seeded, db_session):
    """ARCHITECTURE.md §7.4: "excluding units destroyed through a completed
    return." """
    batch = _batch(
        "BATCH-QCAP-0007", initial_quantity=50, quantity=50,
        category=DrugCategory.oncology, status=BatchStatus.DESTROYED,
    )
    db_session.add(batch)
    await db_session.flush()

    from app.repositories import batch_repo
    circulating = await batch_repo.sum_registered_units(db_session, batch.id)
    assert circulating == 0


@pytest.mark.asyncio
async def test_unknown_batch_is_not_this_rules_problem(seeded, db_session):
    """ARCHITECTURE.md §7.4: `if known is None: return None` — a brand new
    batch id has no baseline to breach."""
    alert = await fraud_service.check_quantity_cap(db_session, batch=None, incoming_quantity=1000, entity_id="ph_2")
    assert alert is None


@pytest.mark.asyncio
async def test_alert_persists_and_is_readable_after_commit(seeded, db_session):
    batch = _batch("BATCH-QCAP-0008", initial_quantity=50, quantity=50, category=DrugCategory.oncology)
    db_session.add(batch)
    await db_session.flush()

    alert = await fraud_service.check_quantity_cap(db_session, batch=batch, incoming_quantity=15, entity_id="ph_2")
    await db_session.commit()

    result = await db_session.execute(select(Alert).where(Alert.id == alert.id))
    row = result.scalar_one()
    assert row.type.value == "QUANTITY_CAP"
    assert row.status.value == "OPEN"
