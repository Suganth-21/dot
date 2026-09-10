"""Database access for `notifications`. ARCHITECTURE.md §4.8. Insert was
Phase 4's job; Phase 8 adds the read/mark-read side.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.models.notification import Notification


async def create(session: AsyncSession, notification: Notification) -> Notification:
    session.add(notification)
    return notification


async def get_by_id(session: AsyncSession, notification_id: str) -> Notification | None:
    return await session.get(Notification, notification_id)


async def list_for_user(
    session: AsyncSession, role: Role, user_id: str | None, *, limit: int = 40
) -> list[Notification]:
    """ARCHITECTURE.md §4.8: "scope server-side to role = :role AND (user_id
    = :me OR user_id IS NULL)... Return at most 40, newest first." """
    stmt = (
        select(Notification)
        .where(Notification.role == role)
        .where(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))
        .order_by(Notification.ts.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_all_read(session: AsyncSession, role: Role, user_id: str | None) -> None:
    notifications = await list_for_user(session, role, user_id, limit=10_000)
    for n in notifications:
        n.read = True


async def delete_all(session: AsyncSession) -> None:
    """Phase-4-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(Notification.__table__.delete())
