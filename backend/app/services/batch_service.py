"""Batch business logic: list/get/search, registration, sale, chain
verification. All rule enforcement and role scoping live here — routers
validate HTTP input and serialize what these functions return (CLAUDE.md
rule 7). See ARCHITECTURE.md §5.1 (status), §8.2 (contract).

Phase 2 scope only: no re-entry detection, no quantity-cap check, no
fraud alerts — those are Phase 3 (`app.services.fraud_service`). A
duplicate batch id is simply rejected here regardless of the existing
batch's status; Phase 3 replaces that one branch (the `DESTROYED` case)
with the alert-and-refuse behavior, it does not change anything else in
this file.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.rbac import Role
from app.models.batch import Batch
from app.models.enums import BatchStatus, EventType, HolderType
from app.models.event import Event
from app.models.sale import Sale
from app.models.user import User
from app.repositories import batch_repo, event_repo, reference_repo, sale_repo
from app.schemas.batch import (
    BatchOut,
    ChainVerificationError,
    ChainVerificationOut,
    EventOut,
    HolderOut,
    RegisterBatchRequest,
    RegisterBatchResponse,
    ScheduledFacilityOut,
    SearchResultOut,
)
from app.services import event_service

_STICKY_STATUSES = {BatchStatus.IN_RETURN, BatchStatus.DESTROYED}


def _derive_status(expiry_date: datetime, stored_status: BatchStatus, now: datetime) -> BatchStatus:
    """ARCHITECTURE.md §5.1: `IN_RETURN` and `DESTROYED` are terminal/sticky
    and never recomputed from expiry. The other three are derived on every
    read against the pinned demo clock (`DEMO_NOW`) rather than real
    wall-clock time — ARCHITECTURE.md §4.10 pins the whole system to it so
    "days to expiry" stays consistent with what the frontend computes."""
    if stored_status in _STICKY_STATUSES:
        return stored_status
    days = (expiry_date - now).days
    if days < 0:
        return BatchStatus.EXPIRED
    if days <= 60:
        return BatchStatus.EXPIRING_SOON
    return BatchStatus.ACTIVE


async def _scheduled_facility_name(session: AsyncSession, batch: Batch) -> str | None:
    if not batch.scheduled_facility_id:
        return None
    facility = await reference_repo.get_facility(session, batch.scheduled_facility_id)
    return facility.name if facility else None


def _serialize_batch(batch: Batch, events: list[Event], facility_name: str | None) -> BatchOut:
    now = get_settings().demo_now_dt
    status = _derive_status(batch.expiry_date, batch.status, now)

    holder = None
    if batch.holder_type and batch.holder_id:
        holder = HolderOut(type=batch.holder_type, id=batch.holder_id, name=batch.holder_name or "")

    scheduled_facility = None
    if batch.scheduled_facility_id:
        scheduled_facility = ScheduledFacilityOut(
            id=batch.scheduled_facility_id, name=facility_name or "", date=batch.scheduled_facility_date
        )

    return BatchOut(
        id=batch.id,
        code=batch.code,
        drug_name=batch.drug_name,
        drug_key=batch.drug_key,
        category=batch.category,
        unit_price=float(batch.unit_price),
        manufacturer_id=batch.manufacturer_id,
        manufacturer_name=batch.manufacturer_name,
        pharmacy_id=batch.pharmacy_id,
        distributor_id=batch.distributor_id,
        mfg_date=batch.mfg_date,
        expiry_date=batch.expiry_date,
        initial_quantity=batch.initial_quantity,
        quantity=batch.quantity,
        status=status,
        holder=holder,
        scheduled_facility=scheduled_facility,
        destroyed=batch.destroyed,
        destroyed_date=batch.destroyed_date,
        cert_id=batch.cert_id,
        events=[EventOut.from_model(e) for e in events],
    )


async def _to_batch_out(session: AsyncSession, batch: Batch) -> BatchOut:
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
    return [await _to_batch_out(session, b) for b in rows]


async def get_batch(session: AsyncSession, current_user: User, identifier: str) -> BatchOut:
    batch = await batch_repo.get_by_id_or_code(session, identifier)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    _check_read_scope(current_user, batch)
    return await _to_batch_out(session, batch)


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
        raise Conflict("A batch with this id already exists.", code="BATCH_ALREADY_EXISTS")

    now = datetime.now(timezone.utc)
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
    await session.commit()
    return RegisterBatchResponse(reentry=False, batch=_serialize_batch(batch, [event], None))


async def record_sale(session: AsyncSession, actor: User, batch_id: str, units: int) -> BatchOut:
    batch = await batch_repo.get_for_update(session, batch_id)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    if batch.pharmacy_id != actor.entity_id:
        raise Forbidden("This batch does not belong to your pharmacy.", code="NOT_YOUR_BATCH")
    if batch.quantity < units:
        raise Conflict("Not enough stock to record this sale.", code="INSUFFICIENT_STOCK",
                        details={"available": batch.quantity, "requested": units})

    batch.quantity -= units
    batch.updated_at = datetime.now(timezone.utc)

    pharmacy = await reference_repo.get_pharmacy(session, batch.pharmacy_id)

    sale = Sale(
        id=f"sale_{uuid.uuid4().hex[:16]}",
        batch_id=batch.id,
        pharmacy_id=batch.pharmacy_id,
        units=units,
        ts=datetime.now(timezone.utc),
    )
    await sale_repo.create(session, sale)

    await event_service.append(
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
    return await _to_batch_out(session, batch)


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
