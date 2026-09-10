"""Deterministic Phase 2 seed: ~44 batches with full, genuinely verifiable
event histories. A faithful port of `pushBatch` in
`frontend/src/services/seed.js` — same ids, codes, quantities, statuses,
and event offsets — with two differences, both required to make seeded
data real rather than decorative:

1. Every event is authored through `event_service.append()` — the real
   SHA-256 canonical hash and a real Ed25519 signature, not a precomputed
   fake value. `GET /api/batches/{id}/verify-chain` must pass on every
   seeded batch, and the only way to guarantee that honestly is to build
   the chain through the same code a live request uses.
2. `seed.js` jitters each event's GPS with `Math.random()`. That is
   nondeterministic, which BUILDPHASES.md's seed spec forbids ("do not
   introduce nondeterministic demo data"). This module uses the acting
   entity's own seeded coordinates instead — deterministic, and arguably
   more truthful (the event happened where that pharmacy/distributor/
   manufacturer actually is).

The two hero batches (`BATCH-DOX-2026-A17`, `BATCH-DOX-2026-B04`) and the
absence of `BATCH-FAKE-9999-Z01` are load-bearing for later phases — do not
change their ids, statuses, or quantities without re-reading
BUILDPHASES.md's seed data spec.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.enums import BatchStatus, DrugCategory, EventType, HolderType
from app.models.sale import Sale
from app.repositories import batch_repo, sale_repo
from app.seed import seed_data
from app.services import event_service

# Fixed PRNG seed — BUILDPHASES.md "Seed data spec: determinism": the two
# values seed.js drew from Math.random() (a sold-quantity factor and a
# spread on expiry date) are reproduced here from a seeded Random so a
# reset produces the identical number every time, not a different one.
_RNG_SEED = 1337

_DRUG_KEYS = [d["key"] for d in seed_data.DRUGS]
_DRUG_BY_KEY = {d["key"]: d for d in seed_data.DRUGS}
_PHARMACY_BY_ID = {p["id"]: p for p in seed_data.PHARMACIES}

# First seeded agent for each distributor — seed.js indexes a flat agent
# array; Phase 1's smaller, explicitly-spread agent roster (7 total, see
# app/seed/seed_data.py) makes "that distributor's first agent" the natural
# equivalent for a seed script authoring historical PICKED_UP events.
_FIRST_AGENT_BY_DISTRIBUTOR = {}
for _agent in seed_data.AGENTS:
    _FIRST_AGENT_BY_DISTRIBUTOR.setdefault(_agent["distributor_id"], _agent)


class BatchConfig(TypedDict):
    id: str
    code: str
    drug_key: str
    pharmacy_id: str
    mfr_idx: int
    dist_idx: int
    initial_qty: int
    qty: int
    status: str
    mfg_days_ago: int
    expiry_in_days: int
    reg_days_ago: int
    flow_days_ago: int


_STATUS_PLAN = [
    {"status": "ACTIVE", "n": 14, "expiry": (120, 400)},
    {"status": "EXPIRING_SOON", "n": 8, "expiry": (10, 55)},
    {"status": "EXPIRED", "n": 5, "expiry": (-40, -2)},
    {"status": "IN_RETURN", "n": 6, "expiry": (-25, 10)},
    {"status": "DESTROYED", "n": 9, "expiry": (-90, -20)},
]


def build_batch_configs() -> list[BatchConfig]:
    """Same arithmetic as seed.js's `pushBatch` loop, `Math.random()` calls
    replaced with a fixed-seed `random.Random` — see module docstring."""
    rng = random.Random(_RNG_SEED)
    configs: list[BatchConfig] = [
        {  # BATCH-DOX-2026-A17 — the expiring-soon hero batch.
            "id": "BATCH-DOX-2026-A17", "code": "DOX-2026-A17", "drug_key": "DOX",
            "pharmacy_id": "ph_1", "mfr_idx": 0, "dist_idx": 0,
            "initial_qty": 50, "qty": 50, "status": "EXPIRING_SOON",
            "mfg_days_ago": 500, "expiry_in_days": 22, "reg_days_ago": 60, "flow_days_ago": 0,
        },
        {  # BATCH-DOX-2026-B04 — pre-destroyed, complete chain, re-entry fixture.
            "id": "BATCH-DOX-2026-B04", "code": "DOX-2026-B04", "drug_key": "DOX",
            "pharmacy_id": "ph_3", "mfr_idx": 0, "dist_idx": 0,
            "initial_qty": 40, "qty": 40, "status": "DESTROYED",
            "mfg_days_ago": 620, "expiry_in_days": -30, "reg_days_ago": 120, "flow_days_ago": 40,
        },
    ]

    counter = 5
    n_pharmacies = len(seed_data.PHARMACIES)
    n_manufacturers = len(seed_data.MANUFACTURERS)
    n_distributors = len(seed_data.DISTRIBUTORS)

    for plan in _STATUS_PLAN:
        for _ in range(plan["n"]):
            drug_key = _DRUG_KEYS[counter % len(_DRUG_KEYS)]
            code = f"{_DRUG_BY_KEY[drug_key]['key']}-2026-{chr(65 + (counter % 6))}{10 + (counter % 80)}"
            initial_qty = 40 + ((counter * 7) % 80)
            sold_factor = 0.4 if plan["status"] == "ACTIVE" else 0.55 if plan["status"] == "EXPIRING_SOON" else 0.3

            if plan["status"] in ("DESTROYED", "IN_RETURN"):
                qty = max(10, round(initial_qty * (1 - sold_factor)))
            else:
                qty = max(5, round(initial_qty * (1 - sold_factor * rng.random())))

            expiry_lo, expiry_hi = plan["expiry"]
            expiry_in_days = round(expiry_lo + rng.random() * (expiry_hi - expiry_lo))

            configs.append({
                "id": f"BATCH-{code}", "code": code, "drug_key": drug_key,
                "pharmacy_id": f"ph_{1 + (counter % n_pharmacies)}",
                "mfr_idx": counter % n_manufacturers, "dist_idx": counter % n_distributors,
                "initial_qty": initial_qty, "qty": qty, "status": plan["status"],
                "mfg_days_ago": 400 + (counter % 200), "expiry_in_days": expiry_in_days,
                "reg_days_ago": 90 + (counter % 120), "flow_days_ago": 10 + (counter % 30),
            })
            counter += 1

    return configs


async def _append_at(
    session: AsyncSession, *, batch: Batch, event_type: EventType, actor_id: str, actor_name: str,
    actor_role: str, days_ago: float, meta: dict, gps: tuple[float, float] | None, now: datetime,
) -> None:
    ts = now - timedelta(days=days_ago)
    await event_service.append(
        session, batch=batch, event_type=event_type, actor_id=actor_id, actor_name=actor_name,
        actor_role=actor_role, meta=meta, gps=gps, ts=ts,
    )


def _facility_gps(facility: dict) -> tuple[float, float]:
    return (facility["lat"], facility["lng"])


async def seed_one_batch(session: AsyncSession, cfg: BatchConfig, now: datetime) -> None:
    drug = _DRUG_BY_KEY[cfg["drug_key"]]
    pharmacy = _PHARMACY_BY_ID[cfg["pharmacy_id"]]
    manufacturer = seed_data.MANUFACTURERS[cfg["mfr_idx"] % len(seed_data.MANUFACTURERS)]
    distributor = seed_data.DISTRIBUTORS[cfg["dist_idx"] % len(seed_data.DISTRIBUTORS)]
    status = BatchStatus(cfg["status"])

    if status == BatchStatus.DESTROYED:
        facility = seed_data.FACILITIES[cfg["mfr_idx"] % len(seed_data.FACILITIES)]
        holder_type, holder_id, holder_name = HolderType.FACILITY, facility["id"], facility["name"]
    elif status == BatchStatus.IN_RETURN:
        holder_type, holder_id, holder_name = HolderType.DISTRIBUTOR, distributor["id"], distributor["name"]
    else:
        holder_type, holder_id, holder_name = HolderType.PHARMACY, pharmacy["id"], pharmacy["name"]

    destroyed = status == BatchStatus.DESTROYED
    destroyed_date = now - timedelta(days=cfg["flow_days_ago"] - 8) if destroyed else None
    cert_id = f"CERT-{cfg['code']}-2026" if destroyed else None

    batch = Batch(
        id=cfg["id"], code=cfg["code"], drug_key=cfg["drug_key"], drug_name=drug["name"],
        category=DrugCategory(drug["category"]), unit_price=drug["price"],
        manufacturer_id=manufacturer["id"], manufacturer_name=manufacturer["name"],
        pharmacy_id=pharmacy["id"],
        distributor_id=distributor["id"] if status in (BatchStatus.IN_RETURN, BatchStatus.DESTROYED) else None,
        mfg_date=now - timedelta(days=cfg["mfg_days_ago"]),
        expiry_date=now + timedelta(days=cfg["expiry_in_days"]),
        initial_quantity=cfg["initial_qty"], quantity=cfg["qty"], status=status,
        holder_type=holder_type, holder_id=holder_id, holder_name=holder_name,
        scheduled_facility_id=(seed_data.FACILITIES[cfg["mfr_idx"] % len(seed_data.FACILITIES)]["id"]
                                if destroyed else None),
        scheduled_facility_date=(now - timedelta(days=cfg["flow_days_ago"] - 6)).date() if destroyed else None,
        destroyed=destroyed, destroyed_date=destroyed_date, cert_id=cert_id,
        created_at=now, updated_at=now,
    )
    await batch_repo.create(session, batch)
    await session.flush()

    ph_gps = (pharmacy["lat"], pharmacy["lng"])
    dist_gps = (distributor["lat"], distributor["lng"])
    mfr_gps = (manufacturer["lat"], manufacturer["lng"])

    await _append_at(
        session, batch=batch, event_type=EventType.REGISTERED, actor_id=pharmacy["id"],
        actor_name=pharmacy["name"], actor_role="RETAILER", days_ago=cfg["reg_days_ago"],
        meta={"quantity": cfg["initial_qty"]}, gps=ph_gps, now=now,
    )

    sold = cfg["initial_qty"] - cfg["qty"]
    remaining = sold
    for s in range(10):
        if remaining <= 0:
            break
        units = max(1, round(remaining / (10 - s)))
        applied = min(units, remaining)
        remaining -= applied
        offset = cfg["reg_days_ago"] - round(((s + 1) / 11) * cfg["reg_days_ago"])
        await _append_at(
            session, batch=batch, event_type=EventType.SALE, actor_id=pharmacy["id"],
            actor_name=pharmacy["name"], actor_role="RETAILER", days_ago=offset,
            meta={"units": applied}, gps=ph_gps, now=now,
        )
        await sale_repo.create(session, Sale(
            id=f"sale_{cfg['id']}_{s}", batch_id=batch.id, pharmacy_id=pharmacy["id"],
            units=applied, ts=now - timedelta(days=offset),
        ))

    if status in (BatchStatus.IN_RETURN, BatchStatus.DESTROYED):
        agent = _FIRST_AGENT_BY_DISTRIBUTOR[distributor["id"]]
        flow = cfg["flow_days_ago"]
        await _append_at(session, batch=batch, event_type=EventType.RETURN_INITIATED, actor_id=pharmacy["id"],
                          actor_name=pharmacy["name"], actor_role="RETAILER", days_ago=flow,
                          meta={"quantity": cfg["qty"], "reason": "EXPIRED"}, gps=ph_gps, now=now)
        await _append_at(session, batch=batch, event_type=EventType.PICKUP_ASSIGNED, actor_id=distributor["id"],
                          actor_name=distributor["name"], actor_role="DISTRIBUTOR", days_ago=flow - 1,
                          meta={}, gps=dist_gps, now=now)
        await _append_at(session, batch=batch, event_type=EventType.PICKED_UP, actor_id=agent["id"],
                          actor_name=agent["name"], actor_role="PICKUP_AGENT", days_ago=flow - 2,
                          meta={"counted": cfg["qty"]}, gps=ph_gps, now=now)
        await _append_at(session, batch=batch, event_type=EventType.DISTRIBUTOR_CONFIRMED, actor_id=distributor["id"],
                          actor_name=distributor["name"], actor_role="DISTRIBUTOR", days_ago=flow - 3,
                          meta={"received": cfg["qty"]}, gps=dist_gps, now=now)
        await _append_at(session, batch=batch, event_type=EventType.FORWARDED, actor_id=distributor["id"],
                          actor_name=distributor["name"], actor_role="DISTRIBUTOR", days_ago=flow - 4,
                          meta={"to": manufacturer["name"]}, gps=dist_gps, now=now)

        if status == BatchStatus.DESTROYED:
            facility = seed_data.FACILITIES[cfg["mfr_idx"] % len(seed_data.FACILITIES)]
            await _append_at(session, batch=batch, event_type=EventType.FACILITY_SCHEDULED,
                              actor_id=manufacturer["id"], actor_name=manufacturer["name"],
                              actor_role="MANUFACTURER", days_ago=flow - 6,
                              meta={"facility": facility["name"]}, gps=mfr_gps, now=now)
            await _append_at(session, batch=batch, event_type=EventType.DESTROYED,
                              actor_id=manufacturer["id"], actor_name=manufacturer["name"],
                              actor_role="MANUFACTURER", days_ago=flow - 8,
                              meta={"facility": facility["name"], "certId": cert_id}, gps=_facility_gps(facility),
                              now=now)


async def seed_all_batches(session: AsyncSession, now: datetime) -> None:
    for cfg in build_batch_configs():
        await seed_one_batch(session, cfg, now)
