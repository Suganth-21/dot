"""Return business logic: create, receive, resolve, forward, Kanban status
transitions, and the dispute gate. All rule enforcement and role scoping
live here — routers validate HTTP input and serialize what these functions
return (CLAUDE.md rule 7). See ARCHITECTURE.md §4.5, §5.2, §7.1, §8.3.

`assert_not_disputed` is the single reusable dispute-gate guard
(ARCHITECTURE.md §7.1: "One implementation, three call sites — never a
copy-pasted check"). It is used here by `forward_returns` and
`set_return_status`, and is written to be imported unchanged by a later
phase's `manufacturer_service.assert_cert_eligible` (§7.2) — it takes a
`Return | None` and raises, nothing about it is return-service-specific.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.rbac import Role
from app.core.realtime import hub
from app.models.batch import Batch
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    BatchStatus,
    EventType,
    HolderType,
    NotificationKind,
    ReturnStatus,
)
from app.models.return_ import Return
from app.models.user import User
from app.repositories import batch_repo, event_repo, reference_repo, return_repo, route_repo
from app.schemas.alert import AlertOut
from app.schemas.batch import BatchOut, EventOut
from app.schemas.reference import DistributorOut, PharmacyOut
from app.schemas.return_ import (
    CreateReturnRequest,
    DistributorReceiveRequest,
    DistributorReceiveResponse,
    ForwardReturnsResponse,
    ResolveDisputeResponse,
    ReturnDetailOut,
    ReturnOut,
)
from app.services import (
    alert_service,
    batch_service,
    event_service,
    fraud_service,
    notification_service,
    pickup_service,
)

# ARCHITECTURE.md §5.2: legacy aliases accepted on input, never stored or emitted.
_STATUS_ALIASES = {"ASSIGNED": ReturnStatus.SCHEDULED, "EN_ROUTE": ReturnStatus.SCHEDULED}

# Phase 4 adaptation: §7.1's pseudocode gates `receive` on
# (SCHEDULED, ARRIVED, PICKED_UP) — statuses only reachable once Phase 5's
# pickup pipeline exists to advance a return past REQUESTED. Since Phase 4
# explicitly does not implement pickups/routes, a return created here would
# otherwise be permanently unreceivable. REQUESTED is included so the
# demo path (create -> distributor receives) works without Phase 5 —
# see BUILDPHASES.md's Phase 4 implementation notes for the full reasoning.
_RECEIVABLE_STATUSES = (ReturnStatus.REQUESTED, ReturnStatus.SCHEDULED, ReturnStatus.ARRIVED, ReturnStatus.PICKED_UP)

# The Kanban board's four columns (frontend/src/pages/distributor.jsx `COLS`)
# — the only transitions `set_return_status` (the manual drag endpoint)
# permits. Forward-only; a client-supplied status outside this adjacency,
# in either direction, is rejected. DISPUTED is never a key here — moving
# out of it is handled by `assert_not_disputed` before this map is consulted.
_KANBAN_TRANSITIONS: dict[ReturnStatus, set[ReturnStatus]] = {
    ReturnStatus.REQUESTED: {ReturnStatus.SCHEDULED},
    ReturnStatus.SCHEDULED: {ReturnStatus.PICKED_UP},
    ReturnStatus.PICKED_UP: {ReturnStatus.CONFIRMED},
    ReturnStatus.CONFIRMED: set(),
}


async def _publish_alert(alert_dict: dict, manufacturer_id: str | None) -> None:
    """ARCHITECTURE.md §9.2/§9.3, called after commit. `hub.publish` is a
    no-op when Redis isn't configured, so every call site can call this
    unconditionally."""
    await hub.publish("alerts:regulator", "alert.created", alert_dict)
    if manufacturer_id:
        await hub.publish(f"alerts:manufacturer:{manufacturer_id}", "alert.created", alert_dict)


async def _publish_batch_updated(batch: Batch, event_out: dict | None = None) -> None:
    await hub.publish(
        f"batch:{batch.id}", "batch.updated", {"batchId": batch.id, "status": batch.status.value, "event": event_out},
    )


async def _publish_returns_updated(distributor_id: str) -> None:
    await hub.publish(f"returns:{distributor_id}", "returns.updated", {"distributorId": distributor_id})


def assert_not_disputed(ret: Return | None) -> None:
    """ARCHITECTURE.md §7.1: the shared dispute-gate guard. `forward`,
    `schedule_facility` (Phase 6), and `upload_certificate` (Phase 6) all
    call this — one implementation, every call site. Raises the exact
    message the frontend's blocked-banner renders directly."""
    if ret is not None and ret.status == ReturnStatus.DISPUTED:
        raise Conflict(
            "Quantity dispute unresolved. Chain halted.",
            code="CHAIN_HALTED_DISPUTE",
            details={"returnId": ret.id},
        )


async def _check_read_scope(session: AsyncSession, current_user: User, ret: Return, batch: Batch | None) -> None:
    """ARCHITECTURE.md §6.5 "Returns — read" row.

    PICKUP_AGENT's documented scope is "own route stops": this used to
    unconditionally reject the role with a comment claiming routes didn't
    exist yet — stale (the pickup pipeline has been live for a while) and,
    as of the agent Stop page now fetching the expected batch/drug/quantity
    straight off the return (`pages/agent.jsx`'s `Stop()`), a real bug:
    every agent request for their own assigned return's details was a
    guaranteed 403, silently breaking the on-scan verification and quantity
    pre-fill it depends on.
    """
    role = current_user.role
    if role == Role.REGULATOR:
        return
    if role == Role.RETAILER and ret.pharmacy_id == current_user.entity_id:
        return
    if role == Role.DISTRIBUTOR and ret.distributor_id == current_user.entity_id:
        return
    if (
        role == Role.MANUFACTURER
        and batch is not None
        and batch.manufacturer_id == current_user.entity_id
        and ret.status == ReturnStatus.FORWARDED
    ):
        return
    if role == Role.PICKUP_AGENT and ret.route_id is not None:
        route = await route_repo.get_by_id(session, ret.route_id)
        if route is not None and route.agent_id == current_user.entity_id:
            return
    raise Forbidden("You do not have access to this return.", code="NOT_YOUR_RETURN")


async def list_returns(
    session: AsyncSession,
    current_user: User,
    *,
    pharmacy_id: str | None = None,
    distributor_id: str | None = None,
    status: str | None = None,
) -> list[ReturnOut]:
    role = current_user.role
    filters: dict[str, str] = {}
    if status:
        filters["status"] = status

    if role == Role.RETAILER:
        filters["pharmacy_id"] = current_user.entity_id
    elif role == Role.DISTRIBUTOR:
        filters["distributor_id"] = current_user.entity_id
    elif role == Role.PICKUP_AGENT:
        return []  # no route data until Phase 5
    elif role == Role.MANUFACTURER:
        filters["manufacturer_id"] = current_user.entity_id
        filters["status"] = ReturnStatus.FORWARDED.value  # "forwarded, own batches" — not caller-widenable
    else:
        if pharmacy_id:
            filters["pharmacy_id"] = pharmacy_id
        if distributor_id:
            filters["distributor_id"] = distributor_id

    rows = await return_repo.list_returns(session, **filters)
    return [ReturnOut.from_model(r) for r in rows]


async def get_return(session: AsyncSession, current_user: User, return_id: str) -> ReturnDetailOut:
    ret = await return_repo.get_by_id(session, return_id)
    if ret is None:
        raise NotFound("Return not found.", code="RETURN_NOT_FOUND")

    batch = await batch_repo.get_by_id(session, ret.batch_id)
    await _check_read_scope(session, current_user, ret, batch)

    batch_out: BatchOut | None = await batch_service.to_batch_out(session, batch) if batch is not None else None
    pharmacy = await reference_repo.get_pharmacy(session, ret.pharmacy_id)
    distributor = await reference_repo.get_distributor(session, ret.distributor_id)

    base = ReturnOut.from_model(ret)
    return ReturnDetailOut(
        **base.model_dump(),
        batch=batch_out,
        pharmacy=PharmacyOut.model_validate(pharmacy) if pharmacy else None,
        distributor=DistributorOut.model_validate(distributor) if distributor else None,
    )


async def create_return(session: AsyncSession, actor: User, payload: CreateReturnRequest) -> ReturnOut:
    batch = await batch_repo.get_for_update(session, payload.batch_id)
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    if batch.pharmacy_id != actor.entity_id:
        raise Forbidden("This batch does not belong to your pharmacy.", code="NOT_YOUR_BATCH")

    if batch.status == BatchStatus.DESTROYED:
        # ARCHITECTURE.md's rule-interaction table (§7.6): "Create return |
        # rules that must pass: ... re-entry." Reuses fraud_service exactly
        # as batch_service does — never a second re-entry implementation.
        pharmacy = await reference_repo.get_pharmacy(session, actor.entity_id)
        alert = await fraud_service.check_reentry(session, batch=batch, actor=actor, pharmacy=pharmacy, source="return")
        await session.commit()
        alert_dict = AlertOut.from_model(alert).model_dump(mode="json", by_alias=True)
        await _publish_alert(alert_dict, batch.manufacturer_id)
        raise Conflict(
            f"Destroyed batch {batch.id} cannot be returned. A critical re-entry alert has been raised.",
            code="BATCH_DESTROYED_REENTRY",
            details={"alert": alert_dict},
        )

    if batch.status not in (BatchStatus.ACTIVE, BatchStatus.EXPIRING_SOON, BatchStatus.EXPIRED):
        raise Conflict(
            f"Batch {batch.id} is not in a returnable state.", code="BATCH_NOT_RETURNABLE",
            details={"status": batch.status.value},
        )
    if payload.quantity > batch.quantity:
        raise ValidationFailed(
            "Return quantity cannot exceed the quantity currently held.",
            code="QUANTITY_EXCEEDS_HELD",
            details={"held": batch.quantity, "requested": payload.quantity},
        )

    pharmacy = await reference_repo.get_pharmacy(session, actor.entity_id)
    if pharmacy is None:
        raise NotFound("Pharmacy not found.", code="PHARMACY_NOT_FOUND")

    # Finalized flow: no distributor picker — the nearest available pickup
    # agent (and their distributor) is assigned by location the instant
    # the return is created, same as pickup_service._build_route's own
    # nearest-neighbour stop ordering. Resolved *before* the Return row is
    # built since `distributor_id` is a required column on it.
    assignment = await pickup_service.pick_nearest_agent(session, pharmacy)
    if assignment is None:
        raise Conflict("No pickup agent is currently available.", code="NO_AGENT_AVAILABLE")
    agent, vehicle, distributor = assignment

    now = datetime.now(UTC)
    ret = Return(
        id=f"ret_{uuid.uuid4().hex[:16]}",
        batch_id=batch.id,
        pharmacy_id=batch.pharmacy_id,
        distributor_id=distributor.id,
        drug_name=batch.drug_name,
        category=batch.category,
        quantity_claimed=payload.quantity,
        picked_quantity=None,
        quantity_received=None,
        reason=payload.reason,
        status=ReturnStatus.REQUESTED,
        photo_hash=payload.photo_hash,
        distributor_photo_hash=None,
        distributor_notes=None,
        dispute_notes=None,
        resolution_notes=None,
        route_id=None,
        created_at=now,
        updated_at=now,
    )
    await return_repo.create(session, ret)

    batch.status = BatchStatus.IN_RETURN
    batch.holder_type = HolderType.PHARMACY
    batch.holder_id = batch.pharmacy_id
    # holder_name is already the pharmacy's own name from registration —
    # holder doesn't actually move until the distributor confirms receipt.
    batch.updated_at = now

    event = await event_service.append(
        session,
        batch=batch,
        event_type=EventType.RETURN_INITIATED,
        actor_id=actor.entity_id,
        actor_name=actor.name,
        actor_role=actor.role.value,
        meta={"quantity": payload.quantity, "reason": payload.reason.value, "photoHash": payload.photo_hash},
        gps=(pharmacy.lat, pharmacy.lng),
    )

    # Auto-creates the (not-yet-dispatched) pickup route for the agent just
    # chosen above — the agent still taps "Start Route" themselves, a real,
    # visible action; nothing here dispatches it.
    await pickup_service.build_auto_route(session, distributor=distributor, agent=agent, vehicle=vehicle, ret=ret)

    await notification_service.notify(
        session, Role.DISTRIBUTOR, "Pickup auto-assigned to your fleet",
        f"{batch.drug_name} from {pharmacy.name} — {agent.name} assigned",
        NotificationKind.info, "/distributor/pickups",
    )
    await notification_service.notify(
        session, Role.RETAILER, "Return created",
        f"{agent.name} assigned — tracking live",
        NotificationKind.success, f"/pharmacy/returns/{ret.id}/track",
    )

    await session.commit()
    await _publish_batch_updated(batch, EventOut.from_model(event).model_dump(mode="json", by_alias=True))
    await _publish_returns_updated(ret.distributor_id)
    return ReturnOut.from_model(ret)


async def distributor_receive(
    session: AsyncSession, actor: User, return_id: str, payload: DistributorReceiveRequest
) -> DistributorReceiveResponse:
    ret = await return_repo.get_for_update(session, return_id)
    if ret is None:
        raise NotFound("Return not found.", code="RETURN_NOT_FOUND")
    if ret.distributor_id != actor.entity_id:
        raise Forbidden("This return does not belong to your distributorship.", code="NOT_YOUR_RETURN")
    if ret.status not in _RECEIVABLE_STATUSES:
        raise Conflict(
            f"Return {ret.id} is not in a receivable state.", code="RETURN_NOT_RECEIVABLE",
            details={"status": ret.status.value},
        )
    # ARCHITECTURE.md §7.1: a sanity ceiling, not the dispute check itself —
    # the dispute check is "does it equal claimed", not "is it in range".
    if not (0 <= payload.quantity_received <= ret.quantity_claimed * 2):
        raise ValidationFailed(
            "Received quantity is out of a plausible range for this return.", code="QUANTITY_OUT_OF_RANGE",
            details={"quantityClaimed": ret.quantity_claimed, "quantityReceived": payload.quantity_received},
        )

    ret.quantity_received = payload.quantity_received
    ret.distributor_photo_hash = payload.photo_hash
    ret.distributor_notes = payload.notes
    ret.updated_at = datetime.now(UTC)

    batch = await batch_repo.get_for_update(session, ret.batch_id)
    distributor = await reference_repo.get_distributor(session, ret.distributor_id)

    if payload.quantity_received == ret.quantity_claimed:
        ret.status = ReturnStatus.CONFIRMED
        confirm_event = None
        if batch is not None and distributor is not None:
            batch.holder_type = HolderType.DISTRIBUTOR
            batch.holder_id = distributor.id
            batch.holder_name = distributor.name
            batch.updated_at = ret.updated_at
            confirm_event = await event_service.append(
                session, batch=batch, event_type=EventType.DISTRIBUTOR_CONFIRMED,
                actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                meta={"received": payload.quantity_received}, gps=(distributor.lat, distributor.lng),
            )
        await session.commit()
        if batch is not None:
            event_out = EventOut.from_model(confirm_event).model_dump(mode="json", by_alias=True) if confirm_event else None
            await _publish_batch_updated(batch, event_out)
        return DistributorReceiveResponse(dispute=False)

    ret.status = ReturnStatus.DISPUTED
    pharmacy = await reference_repo.get_pharmacy(session, ret.pharmacy_id)
    alert = await alert_service.raise_alert(
        session,
        type_=AlertType.QUANTITY_MISMATCH,
        severity=AlertSeverity.high,
        batch=batch,
        entity_id=ret.pharmacy_id,
        entity_name=pharmacy.name if pharmacy else None,
        district=pharmacy.city if pharmacy else None,
        manufacturer_id=batch.manufacturer_id if batch else None,
        rule="Distributor received qty ≠ pharmacy claimed qty",
        message=(
            f"QUANTITY MISMATCH: {ret.drug_name} ({ret.batch_id}) — "
            f"claimed {ret.quantity_claimed}, received {payload.quantity_received}"
        ),
    )
    await notification_service.notify(
        session, Role.REGULATOR, "Quantity mismatch alert", alert.message,
        NotificationKind.warning, f"/regulator/alerts/{alert.id}",
    )
    await notification_service.notify(
        session, Role.RETAILER, "Dispute on your return", f"Quantity mismatch on {ret.drug_name}",
        NotificationKind.warning, "/pharmacy/alerts",
    )
    await session.commit()
    alert_dict = AlertOut.from_model(alert).model_dump(mode="json", by_alias=True)
    await _publish_alert(alert_dict, batch.manufacturer_id if batch else None)
    return DistributorReceiveResponse(dispute=True, alert=alert_dict)


async def resolve_dispute(
    session: AsyncSession, actor: User, return_id: str, resolution_notes: str
) -> ResolveDisputeResponse:
    if not resolution_notes or not resolution_notes.strip():
        raise ValidationFailed("Resolution notes are required to clear a dispute.", code="RESOLUTION_NOTES_REQUIRED")

    ret = await return_repo.get_for_update(session, return_id)
    if ret is None:
        raise NotFound("Return not found.", code="RETURN_NOT_FOUND")
    if ret.distributor_id != actor.entity_id:
        raise Forbidden("This return does not belong to your distributorship.", code="NOT_YOUR_RETURN")
    if ret.status != ReturnStatus.DISPUTED:
        raise Conflict(
            f"Return {ret.id} is not disputed.", code="RETURN_NOT_DISPUTED",
            details={"status": ret.status.value},
        )

    ret.resolution_notes = resolution_notes
    ret.status = ReturnStatus.CONFIRMED
    ret.updated_at = datetime.now(UTC)

    batch = await batch_repo.get_for_update(session, ret.batch_id)
    distributor = await reference_repo.get_distributor(session, ret.distributor_id)
    resolved_event = None
    if batch is not None and distributor is not None:
        batch.holder_type = HolderType.DISTRIBUTOR
        batch.holder_id = distributor.id
        batch.holder_name = distributor.name
        batch.updated_at = ret.updated_at
        resolved_event = await event_service.append(
            session, batch=batch, event_type=EventType.DISPUTE_RESOLVED,
            actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
            meta={"received": ret.quantity_received, "notes": resolution_notes},
            gps=(distributor.lat, distributor.lng),
        )

    open_alert = await alert_service.find_latest_open(session, ret.batch_id, AlertType.QUANTITY_MISMATCH)
    if open_alert is not None:
        alert_service.transition(
            open_alert, AlertStatus.CLOSED, actor.name,
            action="RESOLVED_AT_DISTRIBUTOR", notes=resolution_notes,
        )

    await notification_service.notify(
        session, Role.RETAILER, "Dispute resolved",
        f"{ret.drug_name} dispute resolved — forwarding unlocked",
        NotificationKind.success, f"/pharmacy/returns/{ret.id}/track",
    )

    await session.commit()
    if batch is not None:
        event_out = EventOut.from_model(resolved_event).model_dump(mode="json", by_alias=True) if resolved_event else None
        await _publish_batch_updated(batch, event_out)
    return ResolveDisputeResponse(ok=True)


async def forward_returns(session: AsyncSession, actor: User, return_ids: list[str]) -> ForwardReturnsResponse:
    forwarded: list[str] = []
    skipped: list[str] = []
    updated_batches: list[tuple] = []  # (batch, event) pairs, published after commit

    for return_id in return_ids:
        ret = await return_repo.get_for_update(session, return_id)
        if ret is None or ret.distributor_id != actor.entity_id:
            # Not found or not this distributor's — treated the same way
            # (don't leak existence of another distributor's return),
            # skipped rather than aborting the whole batch: a data/identity
            # issue, not a state-machine violation.
            skipped.append(return_id)
            continue

        # State-machine violations abort the whole call rather than being
        # silently skipped — ARCHITECTURE.md §7.1's dispute gate must
        # reject a direct attempt outright, and the same "never trust a
        # client-supplied status" principle applies to any other illegal
        # forward attempt bundled into the same request.
        assert_not_disputed(ret)
        if ret.status != ReturnStatus.CONFIRMED:
            raise Conflict(
                f"Return {ret.id} is not confirmed and cannot be forwarded.", code="RETURN_NOT_CONFIRMED",
                details={"status": ret.status.value},
            )

        ret.status = ReturnStatus.FORWARDED
        ret.updated_at = datetime.now(UTC)

        batch = await batch_repo.get_for_update(session, ret.batch_id)
        if batch is not None:
            fwd_event = await event_service.append(
                session, batch=batch, event_type=EventType.FORWARDED,
                actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                meta={"to": batch.manufacturer_name},
                gps=None,
            )
            await notification_service.notify(
                session, Role.MANUFACTURER, "Return forwarded",
                f"{batch.drug_name} ({batch.id}) awaiting facility pickup",
                NotificationKind.info, "/manufacturer/inbox",
            )
            updated_batches.append((batch, fwd_event))
        forwarded.append(ret.id)

    await session.commit()
    for updated_batch, fwd_event in updated_batches:
        await _publish_batch_updated(
            updated_batch, EventOut.from_model(fwd_event).model_dump(mode="json", by_alias=True),
        )
    return ForwardReturnsResponse(ok=True, forwarded=forwarded, skipped=skipped)


async def set_return_status(session: AsyncSession, actor: User, return_id: str, raw_status: str) -> ReturnOut:
    """Kanban drag (`PATCH /api/returns/{id}/status`) — ARCHITECTURE.md
    §5.2 / §8.3. A client-supplied status is never trusted as-is: it is
    normalised (alias resolution), then checked against
    `_KANBAN_TRANSITIONS`, after the shared dispute gate has already run.
    """
    alias_resolved = _STATUS_ALIASES.get(raw_status, None)
    try:
        target = alias_resolved or ReturnStatus(raw_status)
    except ValueError as exc:
        raise ValidationFailed(f"'{raw_status}' is not a valid return status.", code="INVALID_STATUS") from exc

    ret = await return_repo.get_for_update(session, return_id)
    if ret is None:
        raise NotFound("Return not found.", code="RETURN_NOT_FOUND")
    if ret.distributor_id != actor.entity_id:
        raise Forbidden("This return does not belong to your distributorship.", code="NOT_YOUR_RETURN")

    assert_not_disputed(ret)  # never a move *out of* DISPUTED via this endpoint either

    if ret.status == target:
        return ReturnOut.from_model(ret)

    legal_targets = _KANBAN_TRANSITIONS.get(ret.status, set())
    if target not in legal_targets:
        raise Conflict(
            f"Cannot move return {ret.id} from {ret.status.value} to {target.value}.",
            code="INVALID_STATUS_TRANSITION",
            details={"from": ret.status.value, "to": target.value},
        )

    ret.status = target
    ret.updated_at = datetime.now(UTC)
    batch = await batch_repo.get_for_update(session, ret.batch_id)
    distributor = await reference_repo.get_distributor(session, ret.distributor_id)

    if target == ReturnStatus.PICKED_UP:
        # No real pickup agent exists until Phase 5 — this manual override
        # records the distributor's own count, defaulting to the claimed
        # quantity, matching the mock's `pickedQuantity ?? quantityClaimed`.
        if ret.picked_quantity is None:
            ret.picked_quantity = ret.quantity_claimed
        if batch is not None:
            existing_types = {e.type for e in await event_repo.list_for_batch(session, batch.id)}
            if EventType.PICKED_UP not in existing_types:
                await event_service.append(
                    session, batch=batch, event_type=EventType.PICKED_UP,
                    actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                    meta={"counted": ret.picked_quantity},
                    gps=(distributor.lat, distributor.lng) if distributor else None,
                )
    elif target == ReturnStatus.CONFIRMED:
        if ret.quantity_received is None:
            ret.quantity_received = ret.quantity_claimed
        if batch is not None and distributor is not None:
            batch.holder_type = HolderType.DISTRIBUTOR
            batch.holder_id = distributor.id
            batch.holder_name = distributor.name
            batch.updated_at = ret.updated_at
            existing_types = {e.type for e in await event_repo.list_for_batch(session, batch.id)}
            if EventType.DISTRIBUTOR_CONFIRMED not in existing_types:
                await event_service.append(
                    session, batch=batch, event_type=EventType.DISTRIBUTOR_CONFIRMED,
                    actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                    meta={"received": ret.quantity_received},
                    gps=(distributor.lat, distributor.lng),
                )

    await session.commit()
    return ReturnOut.from_model(ret)
