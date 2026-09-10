"""Fraud detection rules: re-entry detection (§7.3) and the quantity-cap
check (§7.4). CLAUDE.md rule 2's non-negotiables.

Both functions are pure rule-evaluation-plus-alert-raising helpers — the
caller (`batch_service`) owns the transaction, already holds whatever row
lock `event_service.append` requires, and decides what to do with the
result (refuse the write, or let it through flagged). Neither function here
commits.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.entity import Pharmacy
from app.models.enums import AlertSeverity, AlertType, BatchStatus, EventType
from app.models.user import User
from app.repositories import batch_repo
from app.services import alert_service, event_service


async def check_reentry(
    session: AsyncSession, *, batch: Batch, actor: User, pharmacy: Pharmacy | None, source: str
):
    """ARCHITECTURE.md §7.3. Returns `None` when `batch` isn't `DESTROYED`
    ("a different rule's problem"); the caller in that case does not refuse
    anything. Caller must already hold `batch`'s row lock
    (`batch_repo.get_for_update`) — `event_service.append` requires it.

    Always fires for *any* pharmacy attempting to re-register or re-sell a
    destroyed batch — there is no "existing owner" to check against, which
    is the whole point: the batch already left legitimate circulation.
    """
    if batch is None or batch.status != BatchStatus.DESTROYED:
        return None

    entity_id = pharmacy.id if pharmacy else actor.entity_id
    entity_name = pharmacy.name if pharmacy else "Unknown pharmacy"
    district = pharmacy.city if pharmacy else "Unknown"

    alert = await alert_service.raise_alert(
        session,
        type_=AlertType.REENTRY,
        severity=AlertSeverity.critical,
        batch=batch,
        entity_id=entity_id,
        entity_name=entity_name,
        district=district,
        manufacturer_id=batch.manufacturer_id,
        rule="Batch marked DESTROYED re-registered at a pharmacy",
        message=(
            f"RE-ENTRY: Destroyed batch {batch.id} ({batch.drug_name}) was "
            f"scanned for registration at {entity_name}"
        ),
    )
    await event_service.append(
        session,
        batch=batch,
        event_type=EventType.REENTRY_BLOCKED,
        actor_id=actor.entity_id,
        actor_name=actor.name,
        actor_role=actor.role.value,
        meta={"attemptedAt": entity_name, "source": source},
    )
    return alert


async def check_quantity_cap(
    session: AsyncSession, *, batch: Batch, incoming_quantity: int, entity_id: str | None
):
    """ARCHITECTURE.md §7.4. `batch` is the already-known row (the caller's
    `known` in the architecture's pseudocode) — if there is no known batch
    at all, this is "a different rule's problem" and the caller should not
    invoke this function.

    A note on why this can never actually breach under the current schema,
    recorded here rather than only in BUILDPHASES.md so whoever next touches
    this function sees it before "fixing" the wiring: `batches.id` is a
    primary key, and Phase 2's registration gate (`batch_service.register_batch`)
    already refuses any second registration attempt under an existing,
    non-destroyed id with a flat 409 before this function could ever be
    reached with a genuinely *additional* incoming quantity. `check_reentry`
    above covers the destroyed-id case, and refuses that write entirely too.
    So today, whenever `batch_service` calls this, `incoming_quantity` is 0
    and `circulating` already equals `batch.initial_quantity` exactly —
    never breaching, by construction. The function itself is still correct
    and independently testable (see tests/test_quantity_cap.py, which calls
    it directly against two different quantities the way the architecture's
    own worked example does) — it is ready the moment a future phase gives
    registration a real "top up an existing batch id" path, or wires a
    nightly sweep (BUILDPHASES.md Phase 3 cut list #6).
    """
    if batch is None:
        return None
    circulating = await batch_repo.sum_registered_units(session, batch.id)
    total = circulating + incoming_quantity
    if total <= batch.initial_quantity:
        return None

    excess = total - batch.initial_quantity
    severity = AlertSeverity.critical if batch.category.value == "oncology" else AlertSeverity.high
    return await alert_service.raise_alert(
        session,
        type_=AlertType.QUANTITY_CAP,
        severity=severity,
        batch=batch,
        entity_id=entity_id,
        entity_name=None,
        district=None,
        manufacturer_id=batch.manufacturer_id,
        rule="Units in circulation exceed units ever manufactured",
        message=(
            f"QUANTITY CAP BREACH: {batch.drug_name} ({batch.id}) — "
            f"{total} units in circulation vs {batch.initial_quantity} manufactured "
            f"({excess} unaccounted)"
        ),
    )
