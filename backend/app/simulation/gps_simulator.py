"""Server-side replacement for the client `setInterval` loop in
`frontend/src/services/db.js`'s `startSimulation()`. ARCHITECTURE.md §9.4,
§5.3, BUILDPHASES.md Phase 5.

One asyncio task, started from `app.main`'s lifespan, ticking every ~1s.
Each tick re-reads every `running=True` route from the database, advances
its position along `path`, and persists — a DB round trip per tick rather
than an in-memory cache, deliberately: an in-memory cache would need to
stay consistent with concurrent HTTP writes (an agent completing a stop
mid-tick), and at this demo's scale a round trip per tick is not a
bottleneck worth the complexity. ARCHITECTURE.md's "persist every ~5th
tick" write-amplification optimization is not implemented — recorded as a
simplification, not silently dropped.

**Never marks a stop DONE.** ARCHITECTURE.md §5.3: "the simulator moves the
vehicle and never marks a stop `DONE` by itself" — only
`pickup_service.agent_pickup`/`agent_arrive` do that, and this remains
strictly true here.

**One narrow, deliberate exception on route/run *completion*.** Finishing
the last real stop no longer instantly teleports the truck home — the
completing action (`agent_pickup`'s last stop, `facility_run_service.
deliver_run`) instead appends the warehouse as one final path waypoint and
leaves the route/run `running`, so the vehicle visibly drives back rather
than freezing at the pickup/drop-off point forever. Something still has to
flip `running=False`/`status=completed` once that drive-home leg actually
finishes, and no further human action exists to call an endpoint for it —
so this tick loop does it, gated on every real stop already being DONE
(checked below), never on position alone. This is why the module docstring
above says "never marks a *stop* DONE" rather than "never changes route
status" — the distinction is deliberate.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.realtime import hub
from app.db import async_session_factory
from app.models.entity import Agent
from app.models.enums import AgentStatus, RouteStatus, StopStatus
from app.repositories import facility_run_repo, reference_repo, route_repo

logger = logging.getLogger("dot.gps_simulator")

TICK_SECONDS = 1.0
# 5 ticks per leg — fast enough for a demo to see the vehicle glide across
# the map and reach its destination without dragging; was 0.02 (50
# ticks/leg), then 0.1 (10 ticks/leg).
_SEG_STEP = 0.2


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _advance(vehicle_like) -> None:
    """Shared position/ETA math for anything shaped like a Route or a
    FacilityRun (`path`, `seg_index`, `seg_t`, `pos_lat`, `pos_lng`,
    `eta_min`) — a facility run is physically the same "vehicle on a
    straight leg between two points" simulation as a pickup route, just
    with a two-point path (distributor -> facility) instead of a multi-stop
    one. Mutates in place; caller decides whether the path is even long
    enough to advance."""
    path = vehicle_like.path or []
    if len(path) < 2:
        return

    vehicle_like.seg_t += _SEG_STEP
    if vehicle_like.seg_t >= 1.0:
        vehicle_like.seg_t = 0.0
        vehicle_like.seg_index += 1
        if vehicle_like.seg_index >= len(path) - 1:
            # Reached the end of the physical path. Position holds at the
            # final point; `running`/`status` stay whatever the completing
            # action (agent_pickup / deliver_run) last set them to —
            # arrival here does not itself imply that action happened.
            vehicle_like.seg_index = len(path) - 2
            vehicle_like.seg_t = 1.0

    a, b = path[vehicle_like.seg_index], path[min(vehicle_like.seg_index + 1, len(path) - 1)]
    vehicle_like.pos_lat = _lerp(a["lat"], b["lat"], vehicle_like.seg_t)
    vehicle_like.pos_lng = _lerp(a["lng"], b["lng"], vehicle_like.seg_t)
    remaining_legs = max(0.0, (len(path) - 1) - (vehicle_like.seg_index + vehicle_like.seg_t))
    vehicle_like.eta_min = max(1, round(remaining_legs * 12))


def _reached_path_end(vehicle_like) -> bool:
    """True once the vehicle has physically reached the very end of its
    (possibly drive-home-extended) path. Position-only — callers must also
    confirm every real stop is DONE before treating this as "safe to
    complete", so a route mid-transit toward a stop it hasn't reached yet
    is never mistaken for finished."""
    path = vehicle_like.path or []
    return len(path) >= 2 and vehicle_like.seg_index >= len(path) - 2 and vehicle_like.seg_t >= 1.0


async def _tick_routes(session) -> list[dict]:
    routes = await route_repo.list_active(session)
    positions: list[dict] = []
    for route in routes:
        if not route.path or len(route.path) < 2:
            continue
        _advance(route)

        just_completed = False
        if route.status != RouteStatus.completed and _reached_path_end(route):
            stops = await route_repo.list_stops(session, route.id)
            if stops and all(s.status == StopStatus.DONE for s in stops):
                route.status = RouteStatus.completed
                route.running = False
                just_completed = True

        vehicle = await reference_repo.get_vehicle(session, route.vehicle_id)
        if vehicle is not None:
            vehicle.lat = route.pos_lat
            vehicle.lng = route.pos_lng
            if just_completed:
                # Free the agent/vehicle back up the instant they're
                # actually home — without this, `pickup_service.
                # pick_nearest_agent`'s idle-preference permanently skips
                # anyone who's ever completed a single job (their status
                # was set to `active` on dispatch and nothing else ever
                # reset it), silently routing every later return to a
                # different agent forever.
                vehicle.status = AgentStatus.idle
        if just_completed:
            agent = await session.get(Agent, route.agent_id)
            if agent is not None:
                agent.status = AgentStatus.idle

        positions.append({
            "routeId": route.id, "distributorId": route.distributor_id,
            "pos": {"lat": route.pos_lat, "lng": route.pos_lng}, "etaMin": route.eta_min,
            "vehicleReg": route.vehicle_reg, "agentName": route.agent_name,
        })
    return positions


async def _tick_facility_runs(session) -> list[dict]:
    runs = await facility_run_repo.list_active(session)
    positions: list[dict] = []
    for run in runs:
        if not run.path or len(run.path) < 2:
            continue
        _advance(run)

        # A facility run has no further stops after delivery — unlike a
        # route, reaching path-end alone is enough to finalize it (deliver_run
        # already did every real-work step synchronously; this only finishes
        # the drive-home visual + the running/completed bookkeeping).
        just_completed = False
        if run.status != RouteStatus.completed and _reached_path_end(run):
            run.status = RouteStatus.completed
            run.running = False
            just_completed = True

        vehicle = await reference_repo.get_vehicle(session, run.vehicle_id)
        if vehicle is not None:
            vehicle.lat = run.pos_lat
            vehicle.lng = run.pos_lng
            if just_completed:
                vehicle.status = AgentStatus.idle  # same reasoning as _tick_routes
        if just_completed:
            agent = await session.get(Agent, run.agent_id)
            if agent is not None:
                agent.status = AgentStatus.idle

        positions.append({
            "runId": run.id, "distributorId": run.distributor_id,
            "pos": {"lat": run.pos_lat, "lng": run.pos_lng}, "etaMin": run.eta_min,
            "vehicleReg": run.vehicle_reg, "agentName": run.agent_name,
        })
    return positions


async def _tick() -> None:
    async with async_session_factory() as session:
        route_positions = await _tick_routes(session)
        run_positions = await _tick_facility_runs(session)
        if not route_positions and not run_positions:
            return

        await session.commit()

        # ARCHITECTURE.md §9.4: "Publish once per channel, not once per
        # subscriber." One position message per active route/run, fanned
        # out to its own channel plus its distributor's fleet and the
        # national fleet:all — facility runs reuse the same fleet:*
        # channels as routes, so DISTRIBUTOR/MANUFACTURER/REGULATOR need no
        # extra subscription wiring to receive them.
        for data in route_positions:
            await hub.publish(f"route:{data['routeId']}", "route.position", data)
            await hub.publish(f"fleet:{data['distributorId']}", "route.position", data)
            await hub.publish("fleet:all", "route.position", data)
        for data in run_positions:
            await hub.publish(f"facilityrun:{data['runId']}", "facilityrun.position", data)
            await hub.publish(f"fleet:{data['distributorId']}", "facilityrun.position", data)
            await hub.publish("fleet:all", "facilityrun.position", data)


async def run_forever() -> None:
    """The lifespan-managed background task. Cancelled cleanly on shutdown."""
    logger.info("gps_simulator started")
    try:
        while True:
            try:
                await _tick()
            except Exception:
                logger.exception("gps_simulator tick failed")
            await asyncio.sleep(TICK_SECONDS)
    except asyncio.CancelledError:
        logger.info("gps_simulator stopped")
        raise
