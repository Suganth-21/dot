"""Pickup/route business logic: route creation (nearest-neighbour ordering,
respecting `manualOrder`), dispatch, agent arrive, agent pickup. All rule
enforcement and role scoping live here (CLAUDE.md rule 7). See
ARCHITECTURE.md §4.6, §5.3, §8.4, §9.4.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.rbac import Role
from app.core.realtime import hub
from app.models.entity import Agent, Vehicle
from app.models.enums import (
    AgentStatus,
    EventType,
    NotificationKind,
    ReturnStatus,
    RouteStatus,
    StopStatus,
)
from app.models.route import Route, RouteStop
from app.models.user import User
from app.repositories import batch_repo, reference_repo, return_repo, route_repo
from app.schemas.reference import AgentOut, VehicleOut
from app.schemas.route import CreateRouteRequest, DispatchResponse, FleetOut, RouteOut
from app.services import event_service, notification_service


def _dist2(a: dict, b: dict) -> float:
    return (a["lat"] - b["lat"]) ** 2 + (a["lng"] - b["lng"]) ** 2


async def _publish_stop_transition(route: Route, stop_index: int, status: str, counted: int | None = None) -> None:
    """ARCHITECTURE.md §9.3's `route.stop` message shape."""
    data = {"routeId": route.id, "stopIndex": stop_index, "status": status}
    if counted is not None:
        data["counted"] = counted
    await hub.publish(f"route:{route.id}", "route.stop", data)


def _check_read_scope(current_user: User, route: Route, stops: list[RouteStop]) -> None:
    """ARCHITECTURE.md §6.5 "Routes — read" row."""
    role = current_user.role
    if role in (Role.REGULATOR, Role.MANUFACTURER):
        return  # "live positions" / "all" — national view, filtered client-side
    if role == Role.DISTRIBUTOR and route.distributor_id == current_user.entity_id:
        return
    if role == Role.PICKUP_AGENT and route.agent_id == current_user.entity_id:
        return
    if role == Role.RETAILER and any(s.pharmacy_id == current_user.entity_id for s in stops):
        return
    raise Forbidden("You do not have access to this route.", code="NOT_YOUR_ROUTE")


async def _to_route_out(session: AsyncSession, route: Route) -> RouteOut:
    stops = await route_repo.list_stops(session, route.id)
    return RouteOut.from_model(route, stops)


async def list_routes(
    session: AsyncSession, current_user: User, *, distributor_id: str | None = None, agent_id: str | None = None
) -> list[RouteOut]:
    role = current_user.role
    filters: dict[str, str] = {}
    if role == Role.DISTRIBUTOR:
        filters["distributor_id"] = current_user.entity_id
    elif role == Role.PICKUP_AGENT:
        filters["agent_id"] = current_user.entity_id
    elif role == Role.RETAILER:
        # "tracking on own return only" — narrowed after the fetch below,
        # since a pharmacy isn't a first-class route filter column.
        pass
    else:
        if distributor_id:
            filters["distributor_id"] = distributor_id
        if agent_id:
            filters["agent_id"] = agent_id

    rows = await route_repo.list_routes(session, **filters)

    if role == Role.RETAILER:
        kept = []
        for r in rows:
            stops = await route_repo.list_stops(session, r.id)
            if any(s.pharmacy_id == current_user.entity_id for s in stops):
                kept.append(r)
        rows = kept

    return [await _to_route_out(session, r) for r in rows]


async def get_route(session: AsyncSession, current_user: User, route_id: str) -> RouteOut:
    route = await route_repo.get_by_id(session, route_id)
    if route is None:
        raise NotFound("Route not found.", code="ROUTE_NOT_FOUND")
    stops = await route_repo.list_stops(session, route.id)
    _check_read_scope(current_user, route, stops)
    return RouteOut.from_model(route, stops)


async def list_fleet(session: AsyncSession, distributor_id: str | None) -> FleetOut:
    vehicles = await reference_repo.list_vehicles(session, distributor_id)
    agents = await reference_repo.list_agents(session, distributor_id)
    return FleetOut(
        vehicles=[VehicleOut.model_validate(v) for v in vehicles],
        agents=[AgentOut.model_validate(a) for a in agents],
    )


async def create_route(session: AsyncSession, actor: User, payload: CreateRouteRequest) -> RouteOut:
    if actor.entity_id != payload.distributor_id:
        raise Forbidden("You can only create routes for your own distributorship.", code="NOT_YOUR_DISTRIBUTOR")

    distributor = await reference_repo.get_distributor(session, payload.distributor_id)
    if distributor is None:
        raise NotFound("Distributor not found.", code="DISTRIBUTOR_NOT_FOUND")
    agent = await session.get(Agent, payload.agent_id)
    if agent is None or agent.distributor_id != payload.distributor_id:
        raise NotFound("Agent not found for this distributor.", code="AGENT_NOT_FOUND")
    vehicle = await session.get(Vehicle, payload.vehicle_id)
    if vehicle is None or vehicle.distributor_id != payload.distributor_id:
        raise NotFound("Vehicle not found for this distributor.", code="VEHICLE_NOT_FOUND")

    returns: list = []
    for return_id in payload.return_ids:
        ret = await return_repo.get_for_update(session, return_id)
        if ret is None or ret.distributor_id != payload.distributor_id:
            raise NotFound(f"Return {return_id} not found for this distributor.", code="RETURN_NOT_FOUND")
        if ret.status != ReturnStatus.REQUESTED:
            raise Conflict(
                f"Return {ret.id} is not in a schedulable state.", code="RETURN_NOT_SCHEDULABLE",
                details={"status": ret.status.value},
            )
        returns.append(ret)
    if not returns:
        raise ValidationFailed("At least one return is required to create a route.", code="NO_RETURNS_SELECTED")

    stop_specs = []
    for ret in returns:
        pharmacy = await reference_repo.get_pharmacy(session, ret.pharmacy_id)
        if pharmacy is None:
            continue
        stop_specs.append({
            "pharmacy_id": pharmacy.id, "pharmacy_name": pharmacy.name, "address": pharmacy.address,
            "lat": pharmacy.lat, "lng": pharmacy.lng, "return_id": ret.id,
        })

    if payload.manual_order:
        ordered = stop_specs
    else:
        # Greedy nearest-neighbour from the distributor's warehouse — matches
        # pickupService.js's `createRoute` exactly.
        ordered = []
        cur = {"lat": distributor.lat, "lng": distributor.lng}
        pool = list(stop_specs)
        while pool:
            pool.sort(key=lambda s: _dist2(cur, s))
            nxt = pool.pop(0)
            ordered.append(nxt)
            cur = nxt

    now = datetime.now(UTC)
    path = [{"lat": distributor.lat, "lng": distributor.lng}] + [{"lat": s["lat"], "lng": s["lng"]} for s in ordered]
    route = Route(
        id=f"route_{uuid.uuid4().hex[:16]}",
        distributor_id=payload.distributor_id, agent_id=agent.id, agent_name=agent.name,
        vehicle_id=vehicle.id, vehicle_reg=vehicle.reg_no,
        status=RouteStatus.planned, running=False, path=path,
        seg_index=0, seg_t=0.0, pos_lat=distributor.lat, pos_lng=distributor.lng,
        eta_min=len(ordered) * 12, created_at=now,
    )
    await route_repo.create(session, route)
    await session.flush()

    for i, spec in enumerate(ordered):
        stop = RouteStop(
            id=f"stop_{uuid.uuid4().hex[:16]}", route_id=route.id, return_id=spec["return_id"],
            pharmacy_id=spec["pharmacy_id"], pharmacy_name=spec["pharmacy_name"], address=spec["address"],
            lat=spec["lat"], lng=spec["lng"], stop_order=i + 1, status=StopStatus.PENDING,
            expected_batches=1, counted=None,
        )
        await route_repo.create_stop(session, stop)

    for ret in returns:
        ret.status = ReturnStatus.SCHEDULED
        ret.route_id = route.id
        ret.updated_at = now

    await notification_service.notify(
        session, Role.PICKUP_AGENT, "New route assigned", f"{len(ordered)} stops assigned",
        NotificationKind.info, "/agent/today",
    )

    await session.commit()
    return await _to_route_out(session, route)


async def dispatch_route(session: AsyncSession, actor: User, route_id: str) -> DispatchResponse:
    route = await route_repo.get_for_update(session, route_id)
    if route is None:
        raise NotFound("Route not found.", code="ROUTE_NOT_FOUND")
    if actor.role == Role.DISTRIBUTOR and route.distributor_id != actor.entity_id:
        raise Forbidden("This route does not belong to your distributorship.", code="NOT_YOUR_ROUTE")
    if actor.role == Role.PICKUP_AGENT and route.agent_id != actor.entity_id:
        raise Forbidden("This route is not assigned to you.", code="NOT_YOUR_ROUTE")

    route.running = True
    route.status = RouteStatus.active

    stops = await route_repo.list_stops(session, route.id)
    if stops and stops[0].status == StopStatus.PENDING:
        stops[0].status = StopStatus.CURRENT

    agent = await session.get(Agent, route.agent_id)
    vehicle = await session.get(Vehicle, route.vehicle_id)
    if agent is not None:
        agent.status = AgentStatus.active
    if vehicle is not None:
        vehicle.status = AgentStatus.active

    await notification_service.notify(
        session, Role.RETAILER, "Pickup en route", f"{route.vehicle_reg or 'A vehicle'} is on the way",
        NotificationKind.info, "/pharmacy/returns",
    )

    await session.commit()
    if stops:
        await _publish_stop_transition(route, 0, stops[0].status.value)
    return DispatchResponse(ok=True)


async def agent_arrive(session: AsyncSession, actor: User, route_id: str, stop_index: int) -> RouteOut:
    route = await route_repo.get_for_update(session, route_id)
    if route is None:
        raise NotFound("Route not found.", code="ROUTE_NOT_FOUND")
    if route.agent_id != actor.entity_id:
        raise Forbidden("This route is not assigned to you.", code="NOT_YOUR_ROUTE")

    stop = await route_repo.get_stop_by_order(session, route_id, stop_index + 1)
    if stop is None:
        raise NotFound("Stop not found.", code="STOP_NOT_FOUND")

    stop.status = StopStatus.ARRIVED

    if stop.return_id:
        ret = await return_repo.get_for_update(session, stop.return_id)
        if ret is not None:
            ret.status = ReturnStatus.ARRIVED
            ret.updated_at = datetime.now(UTC)
            batch = await batch_repo.get_for_update(session, ret.batch_id)
            if batch is not None:
                await event_service.append(
                    session, batch=batch, event_type=EventType.AGENT_ARRIVED,
                    actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                    meta={}, gps=(stop.lat, stop.lng),
                )

    await session.commit()
    await _publish_stop_transition(route, stop_index, StopStatus.ARRIVED.value)
    return await _to_route_out(session, route)


async def agent_pickup(session: AsyncSession, actor: User, route_id: str, stop_index: int, counted: int) -> RouteOut:
    route = await route_repo.get_for_update(session, route_id)
    if route is None:
        raise NotFound("Route not found.", code="ROUTE_NOT_FOUND")
    if route.agent_id != actor.entity_id:
        raise Forbidden("This route is not assigned to you.", code="NOT_YOUR_ROUTE")

    stop = await route_repo.get_stop_by_order(session, route_id, stop_index + 1)
    if stop is None:
        raise NotFound("Stop not found.", code="STOP_NOT_FOUND")

    stop.status = StopStatus.DONE
    stop.counted = counted

    next_stop = await route_repo.get_stop_by_order(session, route_id, stop_index + 2)
    if next_stop is not None and next_stop.status == StopStatus.PENDING:
        next_stop.status = StopStatus.CURRENT
    elif next_stop is None:
        # ARCHITECTURE.md §5.3: "completed (last stop DONE)" — stop-driven,
        # never position-driven (the simulator itself never marks this).
        route.status = RouteStatus.completed
        route.running = False

    if stop.return_id:
        ret = await return_repo.get_for_update(session, stop.return_id)
        if ret is not None:
            ret.status = ReturnStatus.PICKED_UP
            ret.picked_quantity = counted
            ret.updated_at = datetime.now(UTC)
            batch = await batch_repo.get_for_update(session, ret.batch_id)
            if batch is not None:
                await event_service.append(
                    session, batch=batch, event_type=EventType.PICKED_UP,
                    actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
                    meta={"counted": counted}, gps=(stop.lat, stop.lng),
                )
                await notification_service.notify(
                    session, Role.DISTRIBUTOR, "Pickup completed",
                    f"{ret.drug_name} picked up ({counted} units) — confirm receipt",
                    NotificationKind.info, f"/distributor/returns/{ret.id}",
                )

    await session.commit()
    await _publish_stop_transition(route, stop_index, StopStatus.DONE.value, counted)
    if next_stop is not None and next_stop.status == StopStatus.CURRENT:
        await _publish_stop_transition(route, stop_index + 1, StopStatus.CURRENT.value)
    return await _to_route_out(session, route)
