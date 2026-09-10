"""Batch business logic: list/get/search, registration, sale, chain
verification. All rule enforcement and role scoping live here — routers
validate HTTP input and serialize what these functions return (CLAUDE.md
rule 7). See ARCHITECTURE.md §5.1 (status), §8.2 (contract).

Phase 3 wires `app.services.fraud_service`'s re-entry detection (§7.3) into
registration and sale — see the "Phase 3 implementation notes" in
ARCHITECTURE.md for how the duplicate-id gate and re-entry now interact.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.rbac import Role
from app.core.realtime import hub
from app.models.batch import Batch
from app.models.enums import BatchStatus, EventType, HolderType
from app.models.event import Event
from app.models.sale import Sale
from app.models.user import User
from app.repositories import batch_repo, event_repo, reference_repo, sale_repo
from app.schemas.alert import AlertOut
from app.schemas.batch import (
    BatchOut,
    ChainVerificationError,
    ChainVerificationOut,
    EventOut,
    RegisterBatchRequest,
    RegisterBatchResponse,
    SearchResultOut,
)
from app.services import batch_status, event_service, fraud_service

_derive_status = batch_status.derive_status  # local alias — this module's existing call sites


async def _publish_alert(alert_dict: dict, manufacturer_id: str | None) -> None:
    """ARCHITECTURE.md §9.2/§9.3 — always called after commit. `hub.publish`
    is a no-op when Redis isn't configured (e.g. under pytest), so every
    call site can call this unconditionally."""
    await hub.publish("alerts:regulator", "alert.created", alert_dict)
    if manufacturer_id:
        await hub.publish(f"alerts:manufacturer:{manufacturer_id}", "alert.created", alert_dict)


async def _publish_batch_updated(batch: Batch, event_out: dict | None = None) -> None:
    await hub.publish(
        f"batch:{batch.id}", "batch.updated", {"batchId": batch.id, "status": batch.status.value, "event": event_out},
    )


async def _scheduled_facility_name(session: AsyncSession, batch: Batch) -> str | None:
    if not batch.scheduled_facility_id:
        return None
    facility = await reference_repo.get_facility(session, batch.scheduled_facility_id)
    return facility.name if facility else None


def _serialize_batch(batch: Batch, events: list[Event], facility_name: str | None) -> BatchOut:
    now = get_settings().demo_now_dt
    status = _derive_status(batch.expiry_date, batch.status, now)
    return BatchOut.from_model(batch, status=status, events=events, facility_name=facility_name)


async def to_batch_out(session: AsyncSession, batch: Batch) -> BatchOut:
    events = await event_repo.list_for_batch(session, batch.id)
    facility_name = await _scheduled_facility_name(session, batch)
    return _serialize_batch(batch, events, facility_name)


def _check_read_scope(current_user: User, batch: Batch) -> None:
    """ARCHITECTURE.md §6.5 "Batches — read" row. Two layers as always: the
    router's role guard lets any of these five roles in at all; this is the
    second layer — does *this* batch belong to *this* caller's scope."""
    role = current_user.role
    if role == Role.REGULATOR:
        return
    if role == Role.RETAILER and batch.pharmacy_id == current_user.entity_id:
        return
    if role == Role.DISTRIBUTOR and batch.distributor_id == current_user.entity_id:
        return
    if role == Role.MANUFACTURER and batch.manufacturer_id == current_user.entity_id:
        return
    # PICKUP_AGENT's documented scope is "own route stops" — routes don't
    # exist until Phase 5, so an agent has no legitimate batch access yet.
    raise Forbidden("You do not have access to this batch.", code="NOT_YOUR_BATCH")


async def list_batches(
    session: AsyncSession,
    current_user: User,
    *,
    status: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
    pharmacy_id: str | None = None,
    manufacturer_id: str | None = None,
) -> list[BatchOut]:
    role = current_user.role
    filters: dict[str, str] = {}

    if role == Role.RETAILER:
        filters["pharmacy_id"] = current_user.entity_id
    elif role == Role.DISTRIBUTOR:
        filters["distributor_id"] = current_user.entity_id
    elif role == Role.MANUFACTURER:
        filters["manufacturer_id"] = current_user.entity_id
    elif role == Role.PICKUP_AGENT:
        return []  # see _check_read_scope's note — no route data until Phase 5
    else:
        # REGULATOR sees everything, and may narrow with the same query
        # params a caller would otherwise be scoped by.
        if pharmacy_id:
            filters["pharmacy_id"] = pharmacy_id
        if manufacturer_id:
            filters["manufacturer_id"] = manufacturer_id

    rows = await batch_repo.list_batches(
        session, status=status, query=query, limit=limit, offset=offset, **filters
    )
    return [await to_batch_out(session, b) for b in rows]


async def get_batch(session: AsyncSession, current_user: User, identifier: str) -> BatchOut:
    batch = await batch_repo.get_by_id_or_code(session, identifier)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    _check_read_scope(current_user, batch)
    return await to_batch_out(session, batch)


async def search(session: AsyncSession, term: str) -> list[SearchResultOut]:
    term = term.strip()
    if not term:
        return []

    results: list[SearchResultOut] = []
    for batch in await batch_repo.search(session, term, limit=12):
        results.append(
            SearchResultOut(type="batch", id=batch.id, title=batch.drug_name, subtitle=batch.id,
                             status=batch.status.value)
        )
    if len(results) < 12:
        remaining = 12 - len(results)
        for pharmacy in await reference_repo.search_pharmacies(session, term, limit=remaining):
            results.append(SearchResultOut(type="pharmacy", id=pharmacy.id, title=pharmacy.name,
                                            subtitle=pharmacy.city, status=None))
    return results[:12]


async def register_batch(session: AsyncSession, actor: User, payload: RegisterBatchRequest) -> RegisterBatchResponse:
    pharmacy = await reference_repo.get_pharmacy(session, actor.entity_id)
    if pharmacy is None:
        raise NotFound("No pharmacy is associated with this account.", code="PHARMACY_NOT_FOUND")

    existing = await batch_repo.get_by_id_or_code(session, payload.batch_id)
    if existing is not None:
        if existing.status == BatchStatus.DESTROYED:
            # ARCHITECTURE.md §7.3 / §7.5.1's documented deviation: this is
            # the one branch Phase 3 changes — everything else about
            # registration (including the flat conflict just below for a
            # non-destroyed duplicate) is unchanged from Phase 2. Lock the
            # row first: event_service.append requires the caller already
            # hold it.
            locked = await batch_repo.get_for_update(session, existing.id)
            alert = await fraud_service.check_reentry(
                session, batch=locked, actor=actor, pharmacy=pharmacy, source="registration",
            )
            # The alert and the REENTRY_BLOCKED event must survive even
            # though the registration itself is refused — commit before
            # raising, since no batch write happens on this path for the
            # session teardown to roll back.
            await session.commit()
            alert_dict = AlertOut.from_model(alert).model_dump(mode="json", by_alias=True)
            await _publish_alert(alert_dict, locked.manufacturer_id)
            raise Conflict(
                f"Destroyed batch {locked.id} was scanned for registration. "
                f"A critical re-entry alert has been raised.",
                code="BATCH_DESTROYED_REENTRY",
                details={"alert": alert_dict},
            )
        raise Conflict("A batch with this id already exists.", code="BATCH_ALREADY_EXISTS")

    now = datetime.now(UTC)
    status = _derive_status(payload.expiry_date, BatchStatus.ACTIVE, get_settings().demo_now_dt)

    batch = Batch(
        id=payload.batch_id,
        code=payload.batch_id.removeprefix("BATCH-"),
        drug_key=payload.drug_key,
        drug_name=payload.drug_name,
        category=payload.category,
        unit_price=payload.unit_price,
        manufacturer_id=payload.manufacturer_id,
        manufacturer_name=payload.manufacturer_name,
        pharmacy_id=actor.entity_id,
        distributor_id=None,
        mfg_date=payload.mfg_date,
        expiry_date=payload.expiry_date,
        initial_quantity=payload.quantity,
        quantity=payload.quantity,
        status=status,
        holder_type=HolderType.PHARMACY,
        holder_id=actor.entity_id,
        holder_name=pharmacy.name,
        destroyed=False,
        created_at=now,
        updated_at=now,
    )
    await batch_repo.create(session, batch)
    try:
        # Flushing here (rather than waiting for the final commit) turns a
        # PK collision from a concurrent duplicate registration into an
        # IntegrityError we can catch and answer with 409, instead of an
        # unhandled 500 surfacing from the commit at the very end.
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("A batch with this id already exists.", code="BATCH_ALREADY_EXISTS") from exc

    event = await event_service.append(
        session,
        batch=batch,
        event_type=EventType.REGISTERED,
        actor_id=actor.entity_id,
        actor_name=actor.name,
        actor_role=actor.role.value,
        meta={"quantity": payload.quantity},
        gps=(pharmacy.lat, pharmacy.lng),
    )

    # ARCHITECTURE.md §7.4. `known` here is the row just created above, so
    # `circulating` (via `batch_repo.sum_registered_units`) always equals
    # `batch.initial_quantity` exactly — this can structurally never breach
    # under the current one-row-per-batch-id schema, because the duplicate-
    # id gate a few lines up already refuses any second registration
    # attempt before this point could ever be reached with a genuinely
    # *additional* incoming quantity. Wired in anyway, per §7.4, so the rule
    # is live and correct the moment a future phase gives it a real second
    # registration path (nightly sweep, or a top-up flow) — see
    # BUILDPHASES.md's Phase 3 implementation notes for the full reasoning,
    # and tests/test_quantity_cap.py for direct, schema-independent coverage
    # of the rule itself.
    quantity_cap_alert = await fraud_service.check_quantity_cap(
        session, batch=batch, incoming_quantity=0, entity_id=actor.entity_id,
    )

    await session.commit()
    event_out = EventOut.from_model(event).model_dump(mode="json", by_alias=True)
    await _publish_batch_updated(batch, event_out)
    if quantity_cap_alert is not None:
        await _publish_alert(
            AlertOut.from_model(quantity_cap_alert).model_dump(mode="json", by_alias=True), batch.manufacturer_id,
        )
    return RegisterBatchResponse(
        reentry=False,
        batch=_serialize_batch(batch, [event], None),
        quantity_cap_breach=quantity_cap_alert is not None,
        alert=AlertOut.from_model(quantity_cap_alert) if quantity_cap_alert else None,
    )


async def record_sale(session: AsyncSession, actor: User, batch_id: str, units: int) -> BatchOut:
    batch = await batch_repo.get_for_update(session, batch_id)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    if batch.pharmacy_id != actor.entity_id:
        raise Forbidden("This batch does not belong to your pharmacy.", code="NOT_YOUR_BATCH")

    if batch.status == BatchStatus.DESTROYED:
        # ARCHITECTURE.md §7.3: a DESTROYED batch re-entering circulation
        # via a sale attempt is the same rule as registration — refuse and
        # alert, don't silently allow. `batch` is already locked above.
        pharmacy = await reference_repo.get_pharmacy(session, actor.entity_id)
        alert = await fraud_service.check_reentry(
            session, batch=batch, actor=actor, pharmacy=pharmacy, source="sale",
        )
        await session.commit()
        alert_dict = AlertOut.from_model(alert).model_dump(mode="json", by_alias=True)
        await _publish_alert(alert_dict, batch.manufacturer_id)
        raise Conflict(
            f"Destroyed batch {batch.id} cannot be sold. A critical re-entry alert has been raised.",
            code="BATCH_DESTROYED_REENTRY",
            details={"alert": alert_dict},
        )

    if batch.quantity < units:
        raise Conflict("Not enough stock to record this sale.", code="INSUFFICIENT_STOCK",
                        details={"available": batch.quantity, "requested": units})

    batch.quantity -= units
    batch.updated_at = datetime.now(UTC)

    pharmacy = await reference_repo.get_pharmacy(session, batch.pharmacy_id)

    sale = Sale(
        id=f"sale_{uuid.uuid4().hex[:16]}",
        batch_id=batch.id,
        pharmacy_id=batch.pharmacy_id,
        units=units,
        ts=datetime.now(UTC),
    )
    await sale_repo.create(session, sale)

    event = await event_service.append(
        session,
        batch=batch,
        event_type=EventType.SALE,
        actor_id=actor.entity_id,
        actor_name=actor.name,
        actor_role=actor.role.value,
        meta={"units": units},
        gps=(pharmacy.lat, pharmacy.lng) if pharmacy else None,
    )
    await session.commit()
    await _publish_batch_updated(batch, EventOut.from_model(event).model_dump(mode="json", by_alias=True))
    return await to_batch_out(session, batch)


async def verify_chain(session: AsyncSession, identifier: str) -> ChainVerificationOut:
    batch = await batch_repo.get_by_id_or_code(session, identifier)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    result = await event_service.verify_chain(session, batch.id)
    return ChainVerificationOut(
        valid=result["valid"],
        broken_at_sequence=result["brokenAtSequence"],
        checked=result["checked"],
        errors=[ChainVerificationError(**e) for e in result["errors"]],
    )
