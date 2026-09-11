"""Facility-run business logic: eligibility, create, dispatch, deliver.
The distributor -> destruction-facility leg — the drop-off counterpart to
`app.services.pickup_service`'s pharmacy -> distributor pickup leg. All
rule enforcement and role scoping live here (CLAUDE.md rule 7).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.rbac import Role
from app.core.realtime import hub
from app.models.entity import Agent, Vehicle
from app.models.enums import AgentStatus, EventType, HolderType, NotificationKind, RouteStatus
from app.models.facility_run import FacilityRun
from app.models.user import User
from app.repositories import batch_repo, facility_run_repo, reference_repo
from app.schemas.batch import EventOut
from app.schemas.facility_run import (
    CreateFacilityRunRequest,
    DispatchResponse,
    FacilityRunBatchOut,
    FacilityRunOut,
)
from app.services import event_service, notification_service


def _check_read_scope(current_user: User, run: FacilityRun) -> None:
    """Same shape as pickup_service's route read-scope: national view for
    REGULATOR/MANUFACTURER (filtered client-side), own-fleet for
    DISTRIBUTOR/PICKUP_AGENT."""
    role = current_user.role
    if role in (Role.REGULATOR, Role.MANUFACTURER):
        return
    if role == Role.DISTRIBUTOR and run.distributor_id == current_user.entity_id:
        return
    if role == Role.PICKUP_AGENT and run.agent_id == current_user.entity_id:
        return
    raise Forbidden("You do not have access to this facility run.", code="NOT_YOUR_FACILITY_RUN")


async def _to_run_out(session: AsyncSession, run: FacilityRun) -> FacilityRunOut:
    batch_outs = []
    for batch_id in run.batch_ids:
        batch = await batch_repo.get_by_id(session, batch_id)
        if batch is not None:
            batch_outs.append(FacilityRunBatchOut(batch_id=batch.id, drug_name=batch.drug_name, quantity=batch.quantity))
    return FacilityRunOut.from_model(run, batch_outs)


async def list_runs(
    session: AsyncSession, current_user: User, *, distributor_id: str | None = None, agent_id: str | None = None
) -> list[FacilityRunOut]:
    role = current_user.role
    filters: dict[str, str] = {}
    if role == Role.DISTRIBUTOR:
        filters["distributor_id"] = current_user.entity_id
    elif role == Role.PICKUP_AGENT:
        filters["agent_id"] = current_user.entity_id
    else:
        # REGULATOR/MANUFACTURER — national view, filtered client-side
        # (same precedent as pickup_service.list_routes).
        if distributor_id:
            filters["distributor_id"] = distributor_id
        if agent_id:
            filters["agent_id"] = agent_id

    rows = await facility_run_repo.list_runs(session, **filters)
    return [await _to_run_out(session, r) for r in rows]


async def get_run(session: AsyncSession, current_user: User, run_id: str) -> FacilityRunOut:
    run = await facility_run_repo.get_by_id(session, run_id)
    if run is None:
        raise NotFound("Facility run not found.", code="FACILITY_RUN_NOT_FOUND")
    _check_read_scope(current_user, run)
    return await _to_run_out(session, run)


async def create_run(session: AsyncSession, actor: User, payload: CreateFacilityRunRequest) -> FacilityRunOut:
    if actor.entity_id != payload.distributor_id:
        raise Forbidden("You can only create facility runs for your own distributorship.", code="NOT_YOUR_DISTRIBUTOR")

    distributor = await reference_repo.get_distributor(session, payload.distributor_id)
    if distributor is None:
        raise NotFound("Distributor not found.", code="DISTRIBUTOR_NOT_FOUND")
    facility = await reference_repo.get_facility(session, payload.facility_id)
    if facility is None:
        raise NotFound("Facility not found.", code="FACILITY_NOT_FOUND")
    agent = await session.get(Agent, payload.agent_id)
    if agent is None or agent.distributor_id != payload.distributor_id:
        raise NotFound("Agent not found for this distributor.", code="AGENT_NOT_FOUND")
    vehicle = await session.get(Vehicle, payload.vehicle_id)
    if vehicle is None or vehicle.distributor_id != payload.distributor_id:
        raise NotFound("Vehicle not found for this distributor.", code="VEHICLE_NOT_FOUND")

    if not payload.batch_ids:
        raise ValidationFailed("At least one batch is required to build a facility run.", code="NO_BATCHES_SELECTED")

    # A batch already riding an in-progress run can't be loaded onto a
    # second one — `batch_ids` is a JSONB manifest, not a normal FK column,
    # so this can't be enforced with a unique constraint; checked here
    # instead, same spirit as the pickup leg's REQUESTED-only guard.
    existing_runs = await facility_run_repo.list_runs(session)
    busy_batch_ids = {bid for r in existing_runs if r.status != RouteStatus.completed for bid in r.batch_ids}

    batches = []
    for batch_id in payload.batch_ids:
        batch = await batch_repo.get_for_update(session, batch_id)
        if batch is None:
            raise NotFound(f"Batch {batch_id} not found.", code="BATCH_NOT_FOUND")
        if batch.id in busy_batch_ids:
            raise Conflict(
                f"Batch {batch.id} is already on an in-progress facility run.", code="BATCH_ALREADY_ON_RUN",
                details={"batchId": batch.id},
            )
        # Only a batch this distributor physically holds, and only once its
        # manufacturer has actually scheduled *this* facility for it
        # (manufacturer_service.schedule_facility) — a run can't be built
        # ahead of that decision or for a batch someone else still holds.
        if batch.holder_type != HolderType.DISTRIBUTOR or batch.holder_id != payload.distributor_id:
            raise Conflict(
                f"Batch {batch.id} is not currently held by your distributorship.", code="BATCH_NOT_HELD",
                details={"batchId": batch.id},
            )
        if batch.scheduled_facility_id != payload.facility_id:
            raise Conflict(
                f"Batch {batch.id} is not scheduled for this facility.", code="BATCH_NOT_SCHEDULED_FOR_FACILITY",
                details={"batchId": batch.id, "scheduledFacilityId": batch.scheduled_facility_id},
            )
        batches.append(batch)

    now = datetime.now(UTC)
    path = [{"lat": distributor.lat, "lng": distributor.lng}, {"lat": facility.lat, "lng": facility.lng}]
    run = FacilityRun(
        id=f"frun_{uuid.uuid4().hex[:16]}",
        distributor_id=payload.distributor_id, agent_id=agent.id, agent_name=agent.name,
        vehicle_id=vehicle.id, vehicle_reg=vehicle.reg_no,
        facility_id=facility.id, facility_name=facility.name,
        batch_ids=[b.id for b in batches],
        status=RouteStatus.planned, running=False, path=path,
        seg_index=0, seg_t=0.0, pos_lat=distributor.lat, pos_lng=distributor.lng,
        eta_min=12, created_at=now,
    )
    await facility_run_repo.create(session, run)
    await session.flush()

    await notification_service.notify(
        session, Role.PICKUP_AGENT, "New facility run assigned",
        f"{len(batches)} batch(es) to {facility.name}", NotificationKind.info, "/agent/today",
    )
    await notification_service.notify(
        session, Role.MANUFACTURER, "Facility run scheduled",
        f"A vehicle is being prepared to deliver {len(batches)} batch(es) to {facility.name}",
        NotificationKind.info, "/manufacturer/fleet-map",
    )

    await session.commit()
    return await _to_run_out(session, run)


async def dispatch_run(session: AsyncSession, actor: User, run_id: str) -> DispatchResponse:
    run = await facility_run_repo.get_for_update(session, run_id)
    if run is None:
        raise NotFound("Facility run not found.", code="FACILITY_RUN_NOT_FOUND")
    if actor.role == Role.DISTRIBUTOR and run.distributor_id != actor.entity_id:
        raise Forbidden("This facility run does not belong to your distributorship.", code="NOT_YOUR_FACILITY_RUN")
    if actor.role == Role.PICKUP_AGENT and run.agent_id != actor.entity_id:
        raise Forbidden("This facility run is not assigned to you.", code="NOT_YOUR_FACILITY_RUN")

    run.running = True
    run.status = RouteStatus.active

    agent = await session.get(Agent, run.agent_id)
    vehicle = await session.get(Vehicle, run.vehicle_id)
    if agent is not None:
        agent.status = AgentStatus.active
    if vehicle is not None:
        vehicle.status = AgentStatus.active

    await notification_service.notify(
        session, Role.MANUFACTURER, "Facility run en route",
        f"{run.vehicle_reg or 'A vehicle'} is on its way to {run.facility_name}",
        NotificationKind.info, "/manufacturer/fleet-map",
    )

    await session.commit()
    # Same reason pickup_service._publish_stop_transition fans out to
    # fleet:* now, not just a per-run channel: a distributor/manufacturer
    # session already open when this run is created+dispatched by someone
    # else needs to see it without a manual reload.
    await hub.publish(f"fleet:{run.distributor_id}", "facilityrun.updated", {"runId": run.id})
    await hub.publish("fleet:all", "facilityrun.updated", {"runId": run.id})
    return DispatchResponse(ok=True)


async def deliver_run(session: AsyncSession, actor: User, run_id: str) -> FacilityRunOut:
    run = await facility_run_repo.get_for_update(session, run_id)
    if run is None:
        raise NotFound("Facility run not found.", code="FACILITY_RUN_NOT_FOUND")
    if run.agent_id != actor.entity_id:
        raise Forbidden("This facility run is not assigned to you.", code="NOT_YOUR_FACILITY_RUN")
    if run.delivered:
        raise Conflict("This facility run has already been delivered.", code="ALREADY_DELIVERED")

    run.delivered = True
    facility = await reference_repo.get_facility(session, run.facility_id)
    # Same drive-home treatment as pickup_service.agent_pickup's last stop:
    # the vehicle doesn't teleport back to the depot instantly — one more
    # waypoint is appended and the run stays running so it visibly drives
    # back; gps_simulator's tick loop finalizes `completed`/`running=False`
    # once that leg actually finishes (see its module docstring).
    distributor = await reference_repo.get_distributor(session, run.distributor_id)
    if distributor is not None:
        run.path = [*run.path, {"lat": distributor.lat, "lng": distributor.lng}]
        run.seg_index = len(run.path) - 2
        run.seg_t = 0.0
    else:
        run.status = RouteStatus.completed
        run.running = False

    updated_batches = []
    for batch_id in run.batch_ids:
        batch = await batch_repo.get_for_update(session, batch_id)
        if batch is None:
            continue
        event = await event_service.append(
            session, batch=batch, event_type=EventType.FACILITY_ARRIVED,
            actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
            meta={"facility": run.facility_name}, gps=(facility.lat, facility.lng) if facility else None,
        )
        if facility is not None:
            batch.holder_type = HolderType.FACILITY
            batch.holder_id = facility.id
            batch.holder_name = facility.name
            batch.updated_at = datetime.now(UTC)
        updated_batches.append((batch, event))
        await notification_service.notify(
            session, Role.MANUFACTURER, "Batch arrived at facility",
            f"{batch.drug_name} ({batch.id}) arrived at {run.facility_name} — ready for the destruction certificate",
            NotificationKind.success, f"/manufacturer/certificates/upload/{batch.id}",
        )

    await session.commit()
    for batch, event in updated_batches:
        event_out = EventOut.from_model(event).model_dump(mode="json", by_alias=True)
        await hub.publish(f"batch:{batch.id}", "batch.updated", {"batchId": batch.id, "status": batch.status.value, "event": event_out})
    await hub.publish(f"fleet:{run.distributor_id}", "facilityrun.updated", {"runId": run.id})
    await hub.publish("fleet:all", "facilityrun.updated", {"runId": run.id})
    return await _to_run_out(session, run)
