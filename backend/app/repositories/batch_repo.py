"""Database access for `batches`. No business decisions — status
derivation, ownership, and every domain rule live in
`app.services.batch_service` (ARCHITECTURE.md §2).
"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.enums import BatchStatus


async def get_by_id(session: AsyncSession, batch_id: str) -> Batch | None:
    return await session.get(Batch, batch_id)


async def get_by_id_or_code(session: AsyncSession, identifier: str) -> Batch | None:
    """`GET /api/batches/{id}` accepts an id or a bare code
    (ARCHITECTURE.md §8.2) — tries id first, then code, matching the
    lookup order `verify_service` will use in Phase 3 for `/api/public/verify`."""
    batch = await session.get(Batch, identifier)
    if batch is not None:
        return batch
    result = await session.execute(select(Batch).where(Batch.code == identifier))
    return result.scalar_one_or_none()


async def get_for_update(session: AsyncSession, batch_id: str) -> Batch | None:
    """`SELECT ... FOR UPDATE` — the row lock every read-modify-write on a
    batch must take before inspecting its latest event or mutating its
    quantity (ARCHITECTURE.md §3, §8). Locking by primary key only (not by
    code) is deliberate: every caller of this function already has the
    real id, either from a prior lookup or from the URL path."""
    result = await session.execute(select(Batch).where(Batch.id == batch_id).with_for_update())
    return result.scalar_one_or_none()


async def create(session: AsyncSession, batch: Batch) -> Batch:
    session.add(batch)
    return batch


async def list_batches(
    session: AsyncSession,
    *,
    pharmacy_id: str | None = None,
    manufacturer_id: str | None = None,
    distributor_id: str | None = None,
    status: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Batch]:
    stmt = select(Batch)
    if pharmacy_id:
        stmt = stmt.where(Batch.pharmacy_id == pharmacy_id)
    if manufacturer_id:
        stmt = stmt.where(Batch.manufacturer_id == manufacturer_id)
    if distributor_id:
        stmt = stmt.where(Batch.distributor_id == distributor_id)
    if status:
        stmt = stmt.where(Batch.status == status)
    if query:
        term = f"%{query.lower()}%"
        stmt = stmt.where(or_(func.lower(Batch.drug_name).like(term), func.lower(Batch.id).like(term)))
    stmt = stmt.order_by(Batch.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search(session: AsyncSession, term: str, limit: int = 12) -> list[Batch]:
    like = f"%{term.lower()}%"
    stmt = (
        select(Batch)
        .where(or_(func.lower(Batch.drug_name).like(like), func.lower(Batch.id).like(like)))
        .order_by(Batch.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def sum_registered_units(session: AsyncSession, batch_id: str) -> int:
    """ARCHITECTURE.md §7.4: "must count units registered across all
    pharmacies for that batch id ... excluding units destroyed through a
    completed return." `batches.id` is a primary key, so today this is
    always 0 or 1 rows — written as a genuine aggregate (not a single
    `get()`) so it stays correct if a future phase ever allows more than
    one registration to share a batch id (see fraud_service.check_quantity_cap's
    docstring for why that matters now)."""
    stmt = select(func.coalesce(func.sum(Batch.initial_quantity), 0)).where(
        Batch.id == batch_id, Batch.status != BatchStatus.DESTROYED
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def delete_all(session: AsyncSession) -> None:
    """Phase-2-owned truncate for demo reset — see app.seed.reset. Must run
    after events/sales (both FK to batches) are truncated."""
    await session.execute(Batch.__table__.delete())
