"""Authentication: login, demo-login, refresh rotation, logout, and current-
user resolution. All business decisions about tokens live here — routers
only validate HTTP input and serialize what this module returns
(CLAUDE.md rule 7, ARCHITECTURE.md §2).

The five demo accounts go through the *same* functions as a real login
(`_issue_token_pair` is the one and only place a token pair is minted) —
ARCHITECTURE.md §6.4: "a seeded shortcut through a real front door, not a
second door."
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import NotFound, Unauthorized
from app.core.rbac import Role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories import refresh_token_repo, user_repo


def _hash_token(raw_token: str) -> str:
    # The refresh token itself is a JWT (ARCHITECTURE.md §6.1); only its
    # hash is ever persisted, so a leaked database row is not a usable
    # credential on its own — same principle as password storage.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _issue_token_pair(
    session: AsyncSession, user: User, *, family_id: str | None = None
) -> tuple[str, str, RefreshToken]:
    settings = get_settings()
    family = family_id or uuid.uuid4().hex
    jti = uuid.uuid4().hex

    access_token = create_access_token(user_id=user.id, role=user.role.value, entity_id=user.entity_id)
    refresh_token_str = create_refresh_token(user_id=user.id, family_id=family, jti=jti)

    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
    row = await refresh_token_repo.create(
        session,
        RefreshToken(
            id=f"rt_{jti}",
            user_id=user.id,
            token_hash=_hash_token(refresh_token_str),
            family_id=family,
            revoked=False,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        ),
    )
    return access_token, refresh_token_str, row


async def login(session: AsyncSession, *, email: str, password: str) -> tuple[User, str, str]:
    user = await user_repo.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        # Deliberately identical error for "no such user" and "wrong
        # password" — distinguishing them tells an attacker which emails
        # are registered.
        raise Unauthorized("Invalid email or password.", code="INVALID_CREDENTIALS")

    access_token, refresh_token_str, _row = await _issue_token_pair(session, user)
    await session.commit()
    return user, access_token, refresh_token_str


async def demo_login(session: AsyncSession, *, role: Role) -> tuple[User, str, str]:
    settings = get_settings()
    if not settings.enable_demo_login:
        raise NotFound("Demo login is disabled.", code="DEMO_LOGIN_DISABLED")

    user = await user_repo.get_demo_user_by_role(session, role)
    if user is None:
        raise NotFound("No demo account exists for this role.", code="DEMO_LOGIN_DISABLED")

    # Defense in depth: prove the seeded hash actually matches the
    # configured demo password rather than trusting `is_demo` alone. This
    # exercises the identical Argon2 verification path a real login uses —
    # the demo endpoint never skips password verification, it just supplies
    # the password itself instead of reading it from the request body.
    if not settings.demo_password or not verify_password(settings.demo_password, user.password_hash):
        raise NotFound("Demo login is disabled.", code="DEMO_LOGIN_DISABLED")

    access_token, refresh_token_str, _row = await _issue_token_pair(session, user)
    await session.commit()
    return user, access_token, refresh_token_str


async def refresh(session: AsyncSession, *, refresh_token_str: str) -> tuple[str, str]:
    payload = decode_token(refresh_token_str, expected_type="refresh")
    token_hash = _hash_token(refresh_token_str)
    stored = await refresh_token_repo.get_by_hash(session, token_hash)

    if stored is None:
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED")

    if stored.revoked:
        # Reuse of a token already rotated away is the signature of theft:
        # someone else used the legitimate rotation, and now the original
        # (stolen) token is being replayed. Kill the whole family so the
        # thief's chain dies too, not just this one token.
        await refresh_token_repo.revoke_family(session, stored.family_id)
        await session.commit()
        raise Unauthorized("Refresh token has been revoked.", code="TOKEN_EXPIRED")

    if stored.expires_at <= datetime.now(UTC):
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED")

    user = await user_repo.get_by_id(session, payload["sub"])
    if user is None:
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED")

    new_access, new_refresh, new_row = await _issue_token_pair(session, user, family_id=stored.family_id)
    # Rotate: the old row is marked revoked and points at its replacement.
    # It is never deleted — a later reuse attempt needs it on record.
    await refresh_token_repo.revoke(session, stored, replaced_by_id=new_row.id)
    await session.commit()
    return new_access, new_refresh


async def logout(session: AsyncSession, *, refresh_token_str: str) -> None:
    token_hash = _hash_token(refresh_token_str)
    stored = await refresh_token_repo.get_by_hash(session, token_hash)
    if stored is not None and not stored.revoked:
        await refresh_token_repo.revoke(session, stored)
        await session.commit()
    # A refresh token that does not exist or is already revoked is treated
    # as already logged out, not as an error — logout is idempotent by
    # design and never leaks whether a given token was ever valid.


async def resolve_current_user(session: AsyncSession, access_token: str) -> User:
    """Decodes the access token and loads the real user row from the
    database — the token's claims are never trusted as identity on their
    own (a deleted or demoted user must lose access immediately)."""
    payload = decode_token(access_token, expected_type="access")
    user = await user_repo.get_by_id(session, payload["sub"])
    if user is None:
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED")
    return user
