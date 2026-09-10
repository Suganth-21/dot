"""Database access for `refresh_tokens` — the persistence that makes
rotation and revocation possible (ARCHITECTURE.md §6.1). No business
decisions: whether a presented token is valid, rotated, or a reuse of a
revoked one is decided in `app.services.auth_service`.
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


async def get_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, token: RefreshToken) -> RefreshToken:
    session.add(token)
    return token


async def revoke(session: AsyncSession, token: RefreshToken, *, replaced_by_id: str | None = None) -> None:
    token.revoked = True
    if replaced_by_id is not None:
        token.replaced_by_id = replaced_by_id


async def revoke_family(session: AsyncSession, family_id: str) -> None:
    """Reuse of an already-rotated token is evidence of theft — revoke every
    token descended from the same login so the thief's chain dies too."""
    await session.execute(
        update(RefreshToken).where(RefreshToken.family_id == family_id).values(revoked=True)
    )


async def delete_all(session: AsyncSession) -> None:
    """Phase-1-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(RefreshToken.__table__.delete())
