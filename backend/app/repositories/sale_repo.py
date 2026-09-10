"""Database access for `sales`. ARCHITECTURE.md §4.9."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale import Sale


async def create(session: AsyncSession, sale: Sale) -> Sale:
    session.add(sale)
    return sale


async def list_for_pharmacy(session: AsyncSession, pharmacy_id: str) -> list[Sale]:
    result = await session.execute(
        select(Sale).where(Sale.pharmacy_id == pharmacy_id).order_by(Sale.ts.desc())
    )
    return list(result.scalars().all())


async def delete_all(session: AsyncSession) -> None:
    """Phase-2-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(Sale.__table__.delete())
