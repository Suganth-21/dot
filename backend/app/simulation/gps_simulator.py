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

**Never mutates stop status.** ARCHITECTURE.md §5.3: "the simulator moves
the vehicle and never marks a stop `DONE` by itself" — only
`pickup_service.agent_pickup` does that. This task only ever touches
position, ETA, `seg_index`/`seg_t`, and (never once it's already active)
`running`/`status` — a route earned `completed` and `running=False` from
`agent_pickup` finishing the last stop, not from position math here.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.realtime import hub
from app.db import async_session_factory
from app.repositories import reference_repo, route_repo

logger = logging.getLogger("dot.gps_simulator")

TICK_SECONDS = 1.0
_SEG_STEP = 0.02  # matches db.js's `r.segT += 0.02` — ~10 ticks per leg


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


async def _tick() -> None:
    async with async_session_factory() as session:
        routes = await route_repo.list_active(session)
        if not routes:
            return

        positions: list[dict] = []  # published after commit
        for route in routes:
            path = route.path or []
            if len(path) < 2:
                continue

            route.seg_t += _SEG_STEP
            if route.seg_t >= 1.0:
                route.seg_t = 0.0
                route.seg_index += 1
                if route.seg_index >= len(path) - 1:
                    # Reached the end of the physical path. Position holds
                    # at the final point; `running`/`status` stay whatever
                    # agent_pickup last set them to — arrival here does not
                    # imply the last stop was actually completed.
                    route.seg_index = len(path) - 2
                    route.seg_t = 1.0

            a, b = path[route.seg_index], path[min(route.seg_index + 1, len(path) - 1)]
            route.pos_lat = _lerp(a["lat"], b["lat"], route.seg_t)
            route.pos_lng = _lerp(a["lng"], b["lng"], route.seg_t)
            remaining_legs = max(0.0, (len(path) - 1) - (route.seg_index + route.seg_t))
            route.eta_min = max(1, round(remaining_legs * 12))

            vehicle = await reference_repo.get_vehicle(session, route.vehicle_id)
            if vehicle is not None:
                vehicle.lat = route.pos_lat
                vehicle.lng = route.pos_lng

            positions.append({
                "routeId": route.id, "distributorId": route.distributor_id,
                "pos": {"lat": route.pos_lat, "lng": route.pos_lng}, "etaMin": route.eta_min,
                "vehicleReg": route.vehicle_reg, "agentName": route.agent_name,
            })

        await session.commit()

        # ARCHITECTURE.md §9.4: "Publish once per channel, not once per
        # subscriber." One route.position message per active route, fanned
        # out to its own route: channel plus its distributor's fleet and
        # the national fleet:all.
        for data in positions:
            await hub.publish(f"route:{data['routeId']}", "route.position", data)
            await hub.publish(f"fleet:{data['distributorId']}", "route.position", data)
            await hub.publish("fleet:all", "route.position", data)


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
