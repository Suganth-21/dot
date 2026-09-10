"""Database access for `reports`. No business decisions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


async def create(session: AsyncSession, report: Report) -> Report:
    session.add(report)
    return report


async def list_reports(session: AsyncSession) -> list[Report]:
    result = await session.execute(select(Report).order_by(Report.created_at.desc()))
    return list(result.scalars().all())


async def delete_all(session: AsyncSession) -> None:
    """Phase-8-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(Report.__table__.delete())
