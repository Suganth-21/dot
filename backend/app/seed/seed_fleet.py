"""Seeds five simultaneously in-progress pickup routes — one per seeded
vehicle (`app.seed.seed_data.VEHICLES`), one distinct agent each, spread
across all three distributors — so the fleet map (`/regulator/fleet-map`,
the national dashboard widget, `/distributor/fleet`, `/manufacturer/
fleet-map`) shows several live-moving trucks immediately after a reset
instead of the near-empty map a fresh demo would otherwise start with.
Purely additive: it does not touch `ph_1`/`dist_1`/`agent_1`'s existing
`seed_returns.py` returns, the two hero batches, or any pharmacy those
already used, so it can never collide with the guided demo walkthrough in
BUILDPHASES.md.

Reuses the same route-construction code a live dispatch would
(`pickup_service.build_auto_route`) and mirrors `pickup_service.
dispatch_route`'s own field mutations by hand (route running/status, first
stop CURRENT, agent/vehicle status) rather than calling `dispatch_route`
itself — that function requires an authenticated `User` actor and re-reads
the route `FOR UPDATE`, neither of which makes sense inside a single seed
transaction that already holds every row it needs uncommitted.

Left mid-route (stop CURRENT, not DONE) rather than already picked up: the
gps_simulator tick loop (ARCHITECTURE.md §9.4) only ever completes a route
once every real stop is DONE, so a truck seeded here drives from its
distributor toward its pharmacy stop and then simply waits there — visibly
alive on the map for as long as anyone's watching, never auto-completing
or freeing its vehicle/agent back to idle (nothing in this demo marks a
stop DONE except a real agent app action, which these synthetic routes
never get).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.entity import Agent, Vehicle
from app.models.enums import (
    AgentStatus,
    BatchStatus,
    EventType,
    HolderType,
    ReturnReason,
    ReturnStatus,
    RouteStatus,
    StopStatus,
)
from app.models.return_ import Return
from app.repositories import reference_repo, route_repo
from app.services import event_service, pickup_service

# (vehicleId, agentId, distributorId, batchId, quantityClaimed, minutesAgo)
# — five free EXPIRING_SOON batches (app/seed/seed_batches.py), none of
# them ph_1/ph_3 (hero batches) or the two seed_returns.py already used
# (BATCH-MER-2026-A40, BATCH-CEF-2026-C30), one per seeded vehicle/agent
# pair so no truck or driver is double-booked within this seed. Chennai x3
# + Coimbatore + Madurai — a spread wide enough to actually read as a
# *national* fleet on the regulator's map, not a cluster in one city.
_FLEET_PLAN: list[tuple[str, str, str, str, int, float]] = [
    ("veh_1", "agent_1", "dist_1", "BATCH-MER-2026-D31", 80, 18),
    ("veh_2", "agent_2", "dist_1", "BATCH-PAR-2026-A34", 33, 12),
    ("veh_3", "agent_4", "dist_2", "BATCH-ATO-2026-E32", 101, 22),
    ("veh_4", "agent_5", "dist_2", "BATCH-MET-2026-B35", 43, 9),
    ("veh_5", "agent_6", "dist_3", "BATCH-OME-2026-C36", 41, 15),
]


async def _seed_one_truck(
    session: AsyncSession, *, now: datetime, vehicle_id: str, agent_id: str, distributor_id: str,
    batch_id: str, quantity_claimed: int, minutes_ago: float,
) -> None:
    batch = await session.get(Batch, batch_id)
    if batch is None:
        return
    pharmacy = await reference_repo.get_pharmacy(session, batch.pharmacy_id)
    distributor = await reference_repo.get_distributor(session, distributor_id)
    agent = await session.get(Agent, agent_id)
    vehicle = await session.get(Vehicle, vehicle_id)
    if pharmacy is None or distributor is None or agent is None or vehicle is None:
        return

    started = now - timedelta(minutes=minutes_ago)

    ret = Return(
        id=f"ret_fleet_{vehicle_id}", batch_id=batch.id, pharmacy_id=batch.pharmacy_id,
        distributor_id=distributor.id, drug_name=batch.drug_name, category=batch.category,
        quantity_claimed=quantity_claimed, picked_quantity=None, quantity_received=None,
        reason=ReturnReason.EXPIRED, status=ReturnStatus.REQUESTED, photo_hash=f"seedfleet{batch.id}",
        distributor_photo_hash=None, distributor_notes=None, dispute_notes=None, resolution_notes=None,
        route_id=None, created_at=started, updated_at=started,
    )
    session.add(ret)

    batch.status = BatchStatus.IN_RETURN
    batch.holder_type = HolderType.PHARMACY
    batch.holder_id = batch.pharmacy_id
    batch.updated_at = started

    await event_service.append(
        session, batch=batch, event_type=EventType.RETURN_INITIATED,
        actor_id=pharmacy.id, actor_name=pharmacy.name, actor_role="RETAILER",
        meta={"quantity": quantity_claimed, "reason": "EXPIRED", "photoHash": ret.photo_hash},
        gps=(pharmacy.lat, pharmacy.lng), ts=started,
    )

    # Real route-building code, not a hand-rolled copy — see module
    # docstring. Builds the route `planned`/not-running with a single
    # distributor -> pharmacy stop.
    route = await pickup_service.build_auto_route(session, distributor=distributor, agent=agent, vehicle=vehicle, ret=ret)

    # Hand-applied equivalent of pickup_service.dispatch_route's mutations
    # (see module docstring for why that function itself isn't called).
    stops = await route_repo.list_stops(session, route.id)
    if stops and stops[0].status == StopStatus.PENDING:
        stops[0].status = StopStatus.CURRENT
    route.status = RouteStatus.active
    route.running = True
    agent.status = AgentStatus.active
    vehicle.status = AgentStatus.active


async def seed_demo_fleet(session: AsyncSession, now: datetime) -> None:
    """Five dispatched, currently-driving routes — see module docstring."""
    for vehicle_id, agent_id, distributor_id, batch_id, quantity_claimed, minutes_ago in _FLEET_PLAN:
        await _seed_one_truck(
            session, now=now, vehicle_id=vehicle_id, agent_id=agent_id, distributor_id=distributor_id,
            batch_id=batch_id, quantity_claimed=quantity_claimed, minutes_ago=minutes_ago,
        )
