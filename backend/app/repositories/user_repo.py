"""Database access for `users`. No business decisions — see ARCHITECTURE.md
§2. Password checks, token issuance, and demo-account gating all live in
`app.services.auth_service`.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.models.user import User


async def get_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_demo_user_by_role(session: AsyncSession, role: Role) -> User | None:
    result = await session.execute(
        select(User).where(User.role == role, User.is_demo.is_(True))
    )
    return result.scalar_one_or_none()


async def create(session: AsyncSession, user: User) -> User:
    session.add(user)
    return user


async def delete_all(session: AsyncSession) -> None:
    """Phase-1-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(User.__table__.delete())
