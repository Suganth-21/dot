"""Database access for `alerts`. No business decisions — the category to
severity to recency ordering and the raise/transition rules that decide an
alert's fields live in `app.services.alert_service` /
`app.services.fraud_service` (ARCHITECTURE.md §2, §4.7).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


async def create(session: AsyncSession, alert: Alert) -> Alert:
    session.add(alert)
    return alert


async def get(session: AsyncSession, alert_id: str) -> Alert | None:
    return await session.get(Alert, alert_id)


async def list_alerts(
    session: AsyncSession,
    *,
    type_: str | None = None,
    status: str | None = None,
    district: str | None = None,
    drug_category: str | None = None,
    manufacturer_id: str | None = None,
    entity_id: str | None = None,
    batch_id: str | None = None,
) -> list[Alert]:
    """Unordered — `app.services.alert_service.list_alerts` applies the
    category -> severity -> recency ordering that ARCHITECTURE.md §4.7
    declares a domain rule, not a query convenience."""
    stmt = select(Alert)
    if type_:
        stmt = stmt.where(Alert.type == type_)
    if status:
        stmt = stmt.where(Alert.status == status)
    if district:
        stmt = stmt.where(Alert.district == district)
    if drug_category:
        stmt = stmt.where(Alert.drug_category == drug_category)
    if manufacturer_id:
        stmt = stmt.where(Alert.manufacturer_id == manufacturer_id)
    if entity_id:
        stmt = stmt.where(Alert.entity_id == entity_id)
    if batch_id:
        stmt = stmt.where(Alert.batch_id == batch_id)
    stmt = stmt.order_by(Alert.ts.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_all(session: AsyncSession) -> None:
    """Phase-3-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(Alert.__table__.delete())
