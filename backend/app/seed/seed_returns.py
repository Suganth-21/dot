"""Seeds a couple of realistic in-progress returns for ph_1 — the only
RETAILER demo login — so every role's dashboard shows real activity out of
the box instead of an all-zero baseline. `seed_batches.py` already gives
several *other* pharmacies a batch sitting at `IN_RETURN` with a full
historical event chain (return -> pickup -> confirm -> forward -> destroy),
but never a matching row in `returns`/`routes` — and ph_1 itself had no
in-progress example at all, since none of its own demo-login-relevant
account (dist_1/agent_1/mfr_1) ever appears in that chain. Added on
explicit request: a demo shouldn't look empty before anyone has clicked
anything.

Reuses the same building blocks a live request would (`pickup_service.
build_auto_route`, `event_service.append`, `alert_service.raise_alert`) —
none of them commit internally (same "caller owns the transaction"
discipline `app.seed.reset` already relies on for `seed_batches.py`) — so
the two returns/routes/events/alert this produces are indistinguishable
from ones a real demo walkthrough would have created.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.enums import (
    AlertSeverity,
    AlertType,
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
from app.services import alert_service, event_service, pickup_service


async def _seed_one(
    session: AsyncSession, *, now: datetime, batch: Batch, quantity_claimed: int, hours_ago: float,
    picked_quantity: int, quantity_received: int | None,
) -> None:
    pharmacy = await reference_repo.get_pharmacy(session, batch.pharmacy_id)
    distributor = await reference_repo.get_distributor(session, "dist_1")
    agent = await reference_repo.list_agents(session, "dist_1")
    vehicle = await reference_repo.list_vehicles(session, "dist_1")
    agent, vehicle = agent[0], vehicle[0]
    if pharmacy is None or distributor is None:
        return

    started = now - timedelta(hours=hours_ago)

    ret = Return(
        id=f"ret_seed_{batch.id.lower().replace('batch-', '').replace('-', '_')}",
        batch_id=batch.id, pharmacy_id=batch.pharmacy_id, distributor_id=distributor.id,
        drug_name=batch.drug_name, category=batch.category, quantity_claimed=quantity_claimed,
        picked_quantity=None, quantity_received=None, reason=ReturnReason.EXPIRED,
        status=ReturnStatus.REQUESTED, photo_hash=f"seed{batch.id}", distributor_photo_hash=None,
        distributor_notes=None, dispute_notes=None, resolution_notes=None, route_id=None,
        created_at=started, updated_at=started,
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

    # Real route-building code, not a hand-rolled copy — then fast-forwarded
    # to "already picked up, hours ago" for a believable in-progress demo.
    route = await pickup_service.build_auto_route(session, distributor=distributor, agent=agent, vehicle=vehicle, ret=ret)
    stop = (await route_repo.list_stops(session, route.id))[0]

    picked_at = started + timedelta(minutes=25)
    stop.status = StopStatus.DONE
    stop.counted = picked_quantity
    route.status = RouteStatus.completed
    route.running = False
    route.seg_index = max(0, len(route.path) - 2)
    route.seg_t = 1.0
    route.pos_lat, route.pos_lng = distributor.lat, distributor.lng

    ret.status = ReturnStatus.PICKED_UP
    ret.picked_quantity = picked_quantity
    ret.updated_at = picked_at

    await event_service.append(
        session, batch=batch, event_type=EventType.PICKED_UP,
        actor_id=agent.id, actor_name=agent.name, actor_role="PICKUP_AGENT",
        meta={"counted": picked_quantity}, gps=(pharmacy.lat, pharmacy.lng), ts=picked_at,
    )

    if quantity_received is None:
        return  # left at PICKED_UP — "awaiting distributor confirmation"

    received_at = picked_at + timedelta(minutes=90)
    ret.quantity_received = quantity_received
    ret.updated_at = received_at

    if quantity_received == quantity_claimed:
        ret.status = ReturnStatus.CONFIRMED
        batch.holder_type = HolderType.DISTRIBUTOR
        batch.holder_id = distributor.id
        batch.holder_name = distributor.name
        batch.updated_at = received_at
        await event_service.append(
            session, batch=batch, event_type=EventType.DISTRIBUTOR_CONFIRMED,
            actor_id=distributor.id, actor_name=distributor.name, actor_role="DISTRIBUTOR",
            meta={"received": quantity_received}, gps=(distributor.lat, distributor.lng), ts=received_at,
        )
        return

    ret.status = ReturnStatus.DISPUTED
    await alert_service.raise_alert(
        session, type_=AlertType.QUANTITY_MISMATCH, severity=AlertSeverity.high, batch=batch,
        entity_id=pharmacy.id, entity_name=pharmacy.name, district=pharmacy.city,
        manufacturer_id=batch.manufacturer_id,
        rule="Distributor received qty != pharmacy claimed qty",
        message=(
            f"QUANTITY MISMATCH: {ret.drug_name} ({ret.batch_id}) — "
            f"claimed {quantity_claimed}, received {quantity_received}"
        ),
    )


async def seed_example_returns(session: AsyncSession, now: datetime) -> None:
    """Two examples, both against ph_1/dist_1/agent_1 (the only demo-
    loginable entities) so they're visible from every role's account:
    one picked up and awaiting the distributor's confirmation, one already
    disputed (a live QUANTITY_MISMATCH alert). Deliberately leaves ph_1's
    hero batch (BATCH-DOX-2026-A17, asserted by test_seed_batches.py) and
    BATCH-CIS-2026-E20 untouched — genuinely free batches for a live "Start
    Return" walkthrough.

    `now` is the same fixed `DEMO_NOW` `seed_batches.seed_all_batches`
    already uses, not the real clock — `test_reset_is_deterministic_at_
    the_event_hash_level` resets twice and asserts the batch event chain
    (which these RETURN_INITIATED/PICKED_UP events join) is byte-identical
    both times; timestamping off the real clock would silently break that.
    """
    mer = await session.get(Batch, "BATCH-MER-2026-A40")
    cef = await session.get(Batch, "BATCH-CEF-2026-C30")
    if mer is not None:
        await _seed_one(session, now=now, batch=mer, quantity_claimed=40, hours_ago=6, picked_quantity=40, quantity_received=None)
    if cef is not None:
        await _seed_one(session, now=now, batch=cef, quantity_claimed=30, hours_ago=3, picked_quantity=30, quantity_received=25)
