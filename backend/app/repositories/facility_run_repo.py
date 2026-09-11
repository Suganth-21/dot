"""Database access for `facility_runs`. No business decisions — eligibility,
dispatch, and delivery live in `app.services.facility_run_service`
(ARCHITECTURE.md §2)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility_run import FacilityRun


async def get_by_id(session: AsyncSession, run_id: str) -> FacilityRun | None:
    return await session.get(FacilityRun, run_id)


async def get_for_update(session: AsyncSession, run_id: str) -> FacilityRun | None:
    result = await session.execute(select(FacilityRun).where(FacilityRun.id == run_id).with_for_update())
    return result.scalar_one_or_none()


async def create(session: AsyncSession, run: FacilityRun) -> FacilityRun:
    session.add(run)
    return run


async def list_runs(
    session: AsyncSession, *, distributor_id: str | None = None, agent_id: str | None = None
) -> list[FacilityRun]:
    stmt = select(FacilityRun)
    if distributor_id:
        stmt = stmt.where(FacilityRun.distributor_id == distributor_id)
    if agent_id:
        stmt = stmt.where(FacilityRun.agent_id == agent_id)
    stmt = stmt.order_by(FacilityRun.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_active(session: AsyncSession) -> list[FacilityRun]:
    """Every currently-running run — the GPS simulator's tick target."""
    result = await session.execute(select(FacilityRun).where(FacilityRun.running.is_(True)))
    return list(result.scalars().all())


async def delete_all(session: AsyncSession) -> None:
    """Phase-9-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(FacilityRun.__table__.delete())
