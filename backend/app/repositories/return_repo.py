"""Database access for `returns`. No business decisions — ownership, the
dispute gate, and every state transition rule live in
`app.services.return_service` (ARCHITECTURE.md §2).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.return_ import Return


async def get_by_id(session: AsyncSession, return_id: str) -> Return | None:
    return await session.get(Return, return_id)


async def get_for_update(session: AsyncSession, return_id: str) -> Return | None:
    """`SELECT ... FOR UPDATE` — the row lock every read-modify-write on a
    return must take before inspecting or mutating it (ARCHITECTURE.md §3,
    §7.1). This is what makes two concurrent `distributor_receive` calls on
    the same return resolve to exactly one outcome: the second caller's
    `FOR UPDATE` blocks until the first transaction commits, then reads the
    already-updated row and correctly finds it no longer receivable."""
    result = await session.execute(select(Return).where(Return.id == return_id).with_for_update())
    return result.scalar_one_or_none()


async def create(session: AsyncSession, ret: Return) -> Return:
    session.add(ret)
    return ret


async def list_returns(
    session: AsyncSession,
    *,
    pharmacy_id: str | None = None,
    distributor_id: str | None = None,
    manufacturer_id: str | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
) -> list[Return]:
    stmt = select(Return)
    if pharmacy_id:
        stmt = stmt.where(Return.pharmacy_id == pharmacy_id)
    if distributor_id:
        stmt = stmt.where(Return.distributor_id == distributor_id)
    if status:
        stmt = stmt.where(Return.status == status)
    if statuses:
        stmt = stmt.where(Return.status.in_(statuses))
    stmt = stmt.order_by(Return.created_at.desc())
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if manufacturer_id:
        # "Returns — read" for MANUFACTURER is "forwarded, own batches"
        # (ARCHITECTURE.md §6.5) — filtered in Python against the joined
        # batch's manufacturer_id rather than a SQL join, matching the
        # small scale of this dataset and keeping this repository free of
        # cross-table business decisions beyond a plain filter.
        batch_ids = {r.batch_id for r in rows}
        if not batch_ids:
            return []
        result = await session.execute(select(Batch.id).where(Batch.id.in_(batch_ids), Batch.manufacturer_id == manufacturer_id))
        owned_batch_ids = {row[0] for row in result.all()}
        rows = [r for r in rows if r.batch_id in owned_batch_ids]

    return rows


async def latest_for_batch(session: AsyncSession, batch_id: str) -> Return | None:
    """ARCHITECTURE.md §7.2: `assert_cert_eligible` checks whether *the*
    return that moved this batch through the pipeline is currently
    disputed. A batch has at most one active return at a time in this
    schema, so "latest by created_at" is unambiguous."""
    result = await session.execute(
        select(Return).where(Return.batch_id == batch_id).order_by(Return.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def delete_all(session: AsyncSession) -> None:
    """Phase-4-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(Return.__table__.delete())
