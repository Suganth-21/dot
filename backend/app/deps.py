"""Shared FastAPI dependencies: database session, current-user resolution,
and role guards. See ARCHITECTURE.md §2.

Role guards live here (not in `app.core.rbac`) because they are FastAPI
wiring around the framework-agnostic matrix `rbac` defines — see the module
docstring on `app.core.rbac` for why the split is drawn there.
"""
from collections.abc import AsyncGenerator, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, Unauthorized
from app.core.rbac import Role, is_role_allowed
from app.db import async_session_factory
from app.models.user import User
from app.services import auth_service

# auto_error=False: a missing Authorization header should be OUR 401 in the
# standard error envelope, not FastAPI's default (which — confusingly for a
# missing bearer token — is a bare 403).
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Resolves the bearer token to the real user row in the database — see
    ARCHITECTURE.md §6.3. Returns the ORM object (not a stripped-down
    carrier) so `GET /api/auth/me` and every ownership check downstream has
    `entity_id`, `role`, `name`, and `email` without a second query. Routers
    serialize this through `UserPublic`, which never includes
    `password_hash` or `signing_private_key`."""
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Authentication required.", code="INVALID_CREDENTIALS")

    return await auth_service.resolve_current_user(session, credentials.credentials)


def require_role(*roles: Role) -> Callable[[User], User]:
    """A route with no `require_role` at all is not "open to everyone" —
    every authenticated route still declares its allowed roles explicitly.
    A role outside `roles` gets 403, never a fabricated success
    (CLAUDE.md rule 2)."""

    async def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise Forbidden(
                f"Role {current_user.role.value} is not permitted for this action.",
                code="FORBIDDEN_ROLE",
            )
        return current_user

    return _guard


def require_permission(resource_action: str) -> Callable[[User], User]:
    """Same shape as `require_role`, but checks against the named entry in
    `app.core.rbac.PERMISSION_MATRIX` instead of an inline role list — use
    this where the matrix, not the route, should own the answer."""

    async def _guard(current_user: User = Depends(get_current_user)) -> User:
        if not is_role_allowed(resource_action, current_user.role):
            raise Forbidden(
                f"Role {current_user.role.value} is not permitted for this action.",
                code="FORBIDDEN_ROLE",
            )
        return current_user

    return _guard
