"""Entity compliance scoring — ARCHITECTURE.md §8.9, ported from
`entityService.js`'s `scoreEntity` formula exactly: `100 - alertsOn*12 -
disputeRate*0.4`, clamped 20-100; risk bands LOW >= 80, MEDIUM >= 55, else
HIGH. REGULATOR-only (CLAUDE.md rule 7 — role guard lives in the route).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.enums import ReturnStatus
from app.repositories import alert_repo, batch_repo, reference_repo, return_repo
from app.schemas.alert import AlertOut
from app.schemas.entity import EntityDetailOut, EntityOut


def _score(alerts_on: int, dispute_rate: int) -> tuple[int, str]:
    score = 100 - alerts_on * 12 - dispute_rate * 0.4
    score = max(20, min(100, round(score)))
    risk = "LOW" if score >= 80 else "MEDIUM" if score >= 55 else "HIGH"
    return int(score), risk


async def _pharmacy_return_stats(session: AsyncSession, pharmacy_id: str) -> tuple[int, int]:
    rets = await return_repo.list_returns(session, pharmacy_id=pharmacy_id)
    disputes = sum(1 for r in rets if r.status == ReturnStatus.DISPUTED or (r.resolution_notes and r.resolution_notes.strip()))
    return_rate = len(rets)
    dispute_rate = round((disputes / return_rate) * 100) if return_rate else 0
    return return_rate, dispute_rate


async def _batch_count(session: AsyncSession, entity_id: str) -> int:
    ids: set[str] = set()
    for batches in (
        await batch_repo.list_batches(session, pharmacy_id=entity_id, limit=10_000),
        await batch_repo.list_batches(session, manufacturer_id=entity_id, limit=10_000),
        await batch_repo.list_batches(session, distributor_id=entity_id, limit=10_000),
    ):
        ids.update(b.id for b in batches)
    return len(ids)


async def _to_entity_out(session: AsyncSession, entity, entity_type: str) -> EntityOut:
    alerts = await alert_repo.list_alerts(session, entity_id=entity.id)
    alerts_on = len(alerts)
    if entity_type == "PHARMACY":
        return_rate, dispute_rate = await _pharmacy_return_stats(session, entity.id)
    else:
        return_rate, dispute_rate = 0, 0
    score, risk = _score(alerts_on, dispute_rate)
    return EntityOut(
        id=entity.id, name=entity.name, city=entity.city, lat=entity.lat, lng=entity.lng,
        address=getattr(entity, "address", None), license_no=entity.license_no, type=entity_type,
        score=score, risk=risk, alerts_on=alerts_on, return_rate=return_rate, dispute_rate=dispute_rate,
    )


async def list_entities(session: AsyncSession) -> list[EntityOut]:
    out: list[EntityOut] = []
    for p in await reference_repo.list_pharmacies(session):
        out.append(await _to_entity_out(session, p, "PHARMACY"))
    for d in await reference_repo.list_distributors(session):
        out.append(await _to_entity_out(session, d, "DISTRIBUTOR"))
    for m in await reference_repo.list_manufacturers(session):
        out.append(await _to_entity_out(session, m, "MANUFACTURER"))
    return out


async def get_entity(session: AsyncSession, entity_id: str) -> EntityDetailOut:
    entity = await reference_repo.get_pharmacy(session, entity_id)
    entity_type = "PHARMACY"
    if entity is None:
        entity = await reference_repo.get_distributor(session, entity_id)
        entity_type = "DISTRIBUTOR"
    if entity is None:
        entity = await reference_repo.get_manufacturer(session, entity_id)
        entity_type = "MANUFACTURER"
    if entity is None:
        raise NotFound("Entity not found.", code="ENTITY_NOT_FOUND")

    base = await _to_entity_out(session, entity, entity_type)
    alerts = await alert_repo.list_alerts(session, entity_id=entity_id)
    batch_count = await _batch_count(session, entity_id)
    return EntityDetailOut(
        **base.model_dump(), alerts=[AlertOut.from_model(a) for a in alerts], batch_count=batch_count,
    )
