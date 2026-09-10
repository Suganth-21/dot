"""Database access for `events`. Insert and select only — no update, no
delete, anywhere in this module or any other (CLAUDE.md rule 2, "append-
only event log"). `app.services.event_service` is the only caller
permitted to invoke `create`; every other module reads.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


async def get_last(session: AsyncSession, batch_id: str) -> Event | None:
    """Caller must already hold the batch row lock (`batch_repo.get_for_update`)
    before calling this — that lock is what makes "read the last event, then
    insert the next one" safe under concurrency (ARCHITECTURE.md §3, §7.5)."""
    result = await session.execute(
        select(Event).where(Event.batch_id == batch_id).order_by(Event.sequence.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def list_for_batch(session: AsyncSession, batch_id: str) -> list[Event]:
    result = await session.execute(
        select(Event).where(Event.batch_id == batch_id).order_by(Event.sequence.asc())
    )
    return list(result.scalars().all())


async def types_for_batch(session: AsyncSession, batch_id: str) -> set:
    """ARCHITECTURE.md §7.2: `assert_cert_eligible` checks which event
    types a batch's chain already contains (e.g. has it ever seen a
    `FORWARDED` event) without needing every event's full row."""
    result = await session.execute(select(Event.type).where(Event.batch_id == batch_id))
    return {row[0] for row in result.all()}


async def create(session: AsyncSession, event: Event) -> Event:
    session.add(event)
    return event


async def delete_all(session: AsyncSession) -> None:
    """Phase-2-owned truncate for demo reset — see app.seed.reset. The one
    exception to "events are never deleted": a full demo reset rebuilds the
    entire dataset from nothing, batches included — there is no chain left
    to protect once its batch itself is gone."""
    await session.execute(Event.__table__.delete())
