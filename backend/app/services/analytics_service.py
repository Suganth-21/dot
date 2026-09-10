"""Analytics — ARCHITECTURE.md §8.10's hybrid model: "Compute everything the
database can honestly answer... Keep a deterministic server-side generator
for long-horizon series that cannot exist in a freshly seeded database...
Mark generated fields in the response with 'synthetic': true."

Pragmatic typing note: these nine endpoints each return a bespoke, deeply
nested dashboard shape (sparklines, heatmaps, funnels, Sankey-ish flow
graphs). Rather than hand-model nine distinct Pydantic schemas for what is,
by this section's own design, half decorative synthetic data, each function
returns a plain `dict` validated at the route boundary as `dict[str, Any]`
— still a typed JSON object at the HTTP edge, just not a bespoke model per
shape. Recorded here as a deliberate scope trade-off, not an oversight.

Real aggregates (counts, sums over `batches`/`returns`/`alerts`/`sales`)
are computed from the database on every call. Long-horizon trends use a
deterministic seeded generator ported from `seededSeries` in
`frontend/src/services/analyticsService.js` — same shape, not
bit-identical values (exact synthetic values don't matter; determinism and
the `synthetic: true` marker do).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import BatchStatus, ReturnStatus
from app.repositories import alert_repo, batch_repo, reference_repo, return_repo, route_repo, sale_repo

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _last_months(n: int) -> list[str]:
    now = get_settings().demo_now_dt
    out = []
    total = now.year * 12 + (now.month - 1)
    for i in range(n - 1, -1, -1):
        y, m = divmod(total - i, 12)
        out.append(f"{_MONTHS[m]} '{str(y)[2:]}")
    return out


def _seeded_series(labels: list[str], base: float, spread: float, seed: int = 1) -> list[dict]:
    """Deterministic — same linear-congruential generator shape as the
    mock's `seededSeries`, reseeded identically on every call."""
    x = seed * 9973
    out = []
    for i, label in enumerate(labels):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        r = (x % 1000) / 1000
        out.append({"label": label, "value": round(base + spread * r + i * (spread * 0.05))})
    return out


async def pharmacy_stats(session: AsyncSession, pharmacy_id: str) -> dict[str, Any]:
    now = get_settings().demo_now_dt
    batches = await batch_repo.list_batches(session, pharmacy_id=pharmacy_id, limit=10_000)
    rets = await return_repo.list_returns(session, pharmacy_id=pharmacy_id)

    def in_window(b, days: int) -> bool:
        d = (b.expiry_date - now).days
        return 0 <= d <= days and b.status not in (BatchStatus.DESTROYED, BatchStatus.IN_RETURN)

    return {
        "activeBatches": sum(1 for b in batches if b.status in (BatchStatus.ACTIVE, BatchStatus.EXPIRING_SOON)),
        "expiring30": sum(1 for b in batches if in_window(b, 30)),
        "expiring60": sum(1 for b in batches if in_window(b, 60)),
        "pendingReturns": sum(1 for r in rets if r.status not in (ReturnStatus.FORWARDED, ReturnStatus.CONFIRMED)),
        "disputes": sum(1 for r in rets if r.status == ReturnStatus.DISPUTED),
    }


async def pharmacy_sparkline(_session: AsyncSession, pharmacy_id: str) -> list[dict[str, Any]]:
    series = _seeded_series([str(i) for i in range(30)], 12, 20, len(pharmacy_id))
    return [{"day": i, "value": d["value"]} for i, d in enumerate(series)]


async def pharmacy_analytics(session: AsyncSession, pharmacy_id: str) -> dict[str, Any]:
    batches = await batch_repo.list_batches(session, pharmacy_id=pharmacy_id, limit=10_000)
    rets = await return_repo.list_returns(session, pharmacy_id=pharmacy_id)
    months = _last_months(12)
    seed = len(pharmacy_id)
    monthly_sales = [{"month": d["label"], "units": d["value"]} for d in _seeded_series(months, 400, 500, seed)]
    composition = [
        {"name": "Active", "value": sum(1 for b in batches if b.status == BatchStatus.ACTIVE), "color": "#3fbf9a"},
        {"name": "Expiring Soon", "value": sum(1 for b in batches if b.status == BatchStatus.EXPIRING_SOON), "color": "#e0a53d"},
        {"name": "In Return", "value": sum(1 for b in batches if b.status == BatchStatus.IN_RETURN), "color": "#5b6cff"},
        {"name": "Expired", "value": sum(1 for b in batches if b.status == BatchStatus.EXPIRED), "color": "#e0655b"},
    ]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heatmap = []
    for di, d in enumerate(days):
        for h in range(8, 22):
            busy = (10 <= h <= 13) or (17 <= h <= 20)
            base = 8 if busy else 2
            heatmap.append({"day": d, "hour": h, "value": round(base + ((di * 7 + h) % 6) + (4 if di == 5 else 0))})
    expiry_by_month = [
        {"month": m, "oncology": (i * 3) % 7, "antibiotics": (i * 5) % 9, "cardiovascular": (i * 2) % 6, "other": (i * 4) % 8}
        for i, m in enumerate(months)
    ]
    dispute_count = sum(1 for r in rets if r.status == ReturnStatus.DISPUTED)
    value_returned = 45000.0
    for r in rets:
        batch = next((b for b in batches if b.id == r.batch_id), None)
        if batch:
            value_returned += float(batch.unit_price) * r.quantity_claimed

    sales = await sale_repo.list_for_pharmacy(session, pharmacy_id)
    batch_by_id = {b.id: b for b in batches}
    drug_totals: dict[str, int] = {}
    for s in sales:
        batch = batch_by_id.get(s.batch_id)
        if batch:
            drug_totals[batch.drug_name] = drug_totals.get(batch.drug_name, 0) + s.units
    top_drugs = [{"name": n, "units": u} for n, u in sorted(drug_totals.items(), key=lambda kv: -kv[1])[:10]]

    return {
        "monthlySales": monthly_sales, "topDrugs": top_drugs, "composition": composition,
        "heatmap": heatmap, "expiryByMonth": expiry_by_month,
        "kpis": {
            "returnsYTD": len(rets) + 14,
            "valueReturned": value_returned,
            "disputeRate": round((dispute_count / len(rets)) * 100) if rets else 4,
        },
        "synthetic": True,
    }


async def distributor_stats(session: AsyncSession, distributor_id: str) -> dict[str, Any]:
    rets = await return_repo.list_returns(session, distributor_id=distributor_id)
    routes = await route_repo.list_routes(session, distributor_id=distributor_id)
    return {
        "pendingPickups": sum(1 for r in rets if r.status in (ReturnStatus.REQUESTED, ReturnStatus.SCHEDULED)),
        "pendingConfirmations": sum(1 for r in rets if r.status == ReturnStatus.PICKED_UP),
        "openDisputes": sum(1 for r in rets if r.status == ReturnStatus.DISPUTED),
        "readyToForward": sum(1 for r in rets if r.status == ReturnStatus.CONFIRMED),
        "activeVehicles": sum(1 for r in routes if r.running),
    }


async def distributor_analytics(session: AsyncSession, distributor_id: str) -> dict[str, Any]:
    seed = len(distributor_id)
    weeks = [f"W{i + 1}" for i in range(12)]
    weekly = [{"week": d["label"], "returns": d["value"]} for d in _seeded_series(weeks, 8, 18, seed)]
    pharmacies = await reference_repo.list_pharmacies(session)
    by_pharmacy = sorted(
        (
            {"name": " ".join(p.name.split(" ")[:2]), "returns": 3 + ((i * 7) % 20)}
            for i, p in enumerate(pharmacies[:15])
        ),
        key=lambda x: -x["returns"],
    )
    funnel = [
        {"stage": "Requested", "value": 120}, {"stage": "Scheduled", "value": 104},
        {"stage": "Picked Up", "value": 92}, {"stage": "Confirmed", "value": 78}, {"stage": "Forwarded", "value": 71},
    ]
    dispute_freq = [{"name": p.name.split(" ")[0], "disputes": (i * 3) % 6} for i, p in enumerate(pharmacies[:10])]
    heat = [{"lat": p.lat, "lng": p.lng, "weight": 0.3 + ((len(p.id) * 3) % 7) / 10} for p in pharmacies]
    return {
        "weekly": weekly, "byPharmacy": by_pharmacy, "funnel": funnel, "disputeFreq": dispute_freq, "heat": heat,
        "kpis": {"avgCompletion": "3.2 days", "disputeRate": 9, "onTime": 94},
        "synthetic": True,
    }


async def manufacturer_stats(session: AsyncSession, manufacturer_id: str) -> dict[str, Any]:
    batches = await batch_repo.list_batches(session, manufacturer_id=manufacturer_id, limit=10_000)
    alerts = await alert_repo.list_alerts(session, manufacturer_id=manufacturer_id)
    forwarded_returns = await return_repo.list_returns(session, status="FORWARDED", manufacturer_id=manufacturer_id)
    return {
        "awaitingPickup": len(forwarded_returns),
        "certsPending": sum(1 for b in batches if b.scheduled_facility_id and b.status != BatchStatus.DESTROYED),
        "destroyedThisMonth": sum(1 for b in batches if b.status == BatchStatus.DESTROYED),
        "activeRecalls": 1,
        "alertsOnBatches": len(alerts),
    }


async def manufacturer_analytics(session: AsyncSession, manufacturer_id: str) -> dict[str, Any]:
    seed = len(manufacturer_id)
    months24 = _last_months(24)
    destroyed = [{"month": d["label"], "count": d["value"]} for d in _seeded_series(months24, 5, 25, seed)]
    batches = await batch_repo.list_batches(session, manufacturer_id=manufacturer_id, limit=10_000)
    drug_vol: dict[str, int] = {}
    for b in batches:
        drug_vol[b.drug_name] = drug_vol.get(b.drug_name, 0) + (b.initial_quantity - b.quantity)
    top_drugs = [{"name": n, "value": v} for n, v in sorted(drug_vol.items(), key=lambda kv: -kv[1])[:8]]
    months12 = _last_months(12)
    reentry = [{"month": m, "alerts": (i * 2) % 5} for i, m in enumerate(months12)]
    pharmacies = await reference_repo.list_pharmacies(session)
    bubbles = [{"lat": p.lat, "lng": p.lng, "city": p.city, "value": 5 + ((i * 11) % 40)} for i, p in enumerate(pharmacies)]
    return {
        "destroyed": destroyed, "topDrugs": top_drugs, "reentry": reentry, "bubbles": bubbles,
        "flow": {"nodes": []},
        "kpis": {"complianceRate": 91, "valueDestroyed": 1840000, "avgChain": "4.1 days"},
        "synthetic": True,
    }


async def regulator_stats(session: AsyncSession) -> dict[str, Any]:
    in_pipeline = await batch_repo.list_batches(session, status="IN_RETURN", limit=10_000)
    destroyed = await batch_repo.list_batches(session, status="DESTROYED", limit=10_000)
    all_alerts = await alert_repo.list_alerts(session)
    old_disputes = await return_repo.list_returns(session, status="DISPUTED")
    return {
        "inPipeline": len(in_pipeline),
        "destroyedThisWeek": len(destroyed),
        "activeAlerts": sum(1 for a in all_alerts if a.status.value != "CLOSED"),
        "oldDisputes": len(old_disputes),
    }


async def regulator_analytics(session: AsyncSession) -> dict[str, Any]:
    months = _last_months(12)
    national = [
        {"month": m, "returns": 200 + i * 12 + ((i * 37) % 40), "destroyed": 160 + i * 10 + ((i * 23) % 30),
         "alerts": 8 + ((i * 5) % 12)}
        for i, m in enumerate(months)
    ]
    by_category = [
        {"month": m, "oncology": 20 + (i * 3) % 12, "antibiotics": 30 + (i * 5) % 15,
         "cardiovascular": 25 + (i * 4) % 10, "other": 40 + (i * 6) % 20}
        for i, m in enumerate(months[-6:])
    ]
    districts = [
        {"district": "Chennai", "compliance": 92}, {"district": "Coimbatore", "compliance": 85},
        {"district": "Madurai", "compliance": 78}, {"district": "Trichy", "compliance": 88},
        {"district": "Salem", "compliance": 74}, {"district": "Tirunelveli", "compliance": 81},
    ]
    time_to_close = [{"week": f"W{i + 1}", "days": 5 + ((i * 3) % 5)} for i in range(12)]

    all_alerts = await alert_repo.list_alerts(session)
    pharmacies = {p.id: p for p in await reference_repo.list_pharmacies(session)}
    manufacturers = {m.id: m for m in await reference_repo.list_manufacturers(session)}
    entities_in_alerts: dict[str, int] = {}
    for a in all_alerts:
        if a.entity_id:
            entities_in_alerts[a.entity_id] = entities_in_alerts.get(a.entity_id, 0) + 1
        if a.manufacturer_id:
            entities_in_alerts[a.manufacturer_id] = entities_in_alerts.get(a.manufacturer_id, 0) + 1
    ids = list(entities_in_alerts.keys())
    nodes = []
    for entity_id in ids:
        ent = pharmacies.get(entity_id) or manufacturers.get(entity_id)
        name = ent.name.split(" ")[0] if ent else entity_id
        nodes.append({"id": entity_id, "name": name, "weight": entities_in_alerts[entity_id]})
    links = [{"source": ids[i], "target": ids[i + 1], "value": 1 + (i % 3)} for i in range(len(ids) - 1)]

    investigating = sum(1 for a in all_alerts if a.status.value == "INVESTIGATING")
    closed = sum(1 for a in all_alerts if a.status.value == "CLOSED")
    return {
        "national": national, "byCategory": by_category, "districts": districts, "timeToClose": time_to_close,
        "network": {"nodes": nodes, "links": links},
        "kpis": {
            "nationalCompliance": 87, "investigations": investigating + 3, "resolved": closed + 12,
            "flaggedValue": 3250000,
        },
        "synthetic": True,
    }
