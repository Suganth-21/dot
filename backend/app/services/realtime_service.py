"""Channel subscription authorization — ARCHITECTURE.md §9.2: "Subscriptions
are server-authorised. The client sends {action: 'subscribe', channel: …}
and the server checks the same RBAC matrix from §6.5 before joining."

Lives in `services/` rather than `core/realtime.py` because it queries
batch/route/return ownership — `core` sits beside `services` in
ARCHITECTURE.md §2's dependency diagram, not above `repositories`
(`core/realtime.py`'s own docstring explains the split). The actual
publish/connection-registry mechanism stays in `core.realtime.hub`; this
module only ever answers "is this user allowed to join this channel."
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.models.user import User
from app.repositories import batch_repo, return_repo, route_repo


async def is_subscribe_allowed(session: AsyncSession, user: User, channel: str) -> bool:
    """Returns `False` for anything not explicitly recognised — fails
    closed, same philosophy as `rbac.is_role_allowed`."""
    role = user.role

    if channel == "alerts:regulator":
        return role == Role.REGULATOR

    if channel.startswith("alerts:manufacturer:"):
        manufacturer_id = channel.removeprefix("alerts:manufacturer:")
        return role == Role.MANUFACTURER and manufacturer_id == user.entity_id

    if channel == "fleet:all":
        return role in (Role.REGULATOR, Role.MANUFACTURER)

    if channel.startswith("fleet:"):
        distributor_id = channel.removeprefix("fleet:")
        return role == Role.REGULATOR or (role == Role.DISTRIBUTOR and distributor_id == user.entity_id)

    if channel.startswith("returns:"):
        distributor_id = channel.removeprefix("returns:")
        return role == Role.REGULATOR or (role == Role.DISTRIBUTOR and distributor_id == user.entity_id)

    if channel.startswith("batch:"):
        batch_id = channel.removeprefix("batch:")
        batch = await batch_repo.get_by_id(session, batch_id)
        if batch is None:
            return False
        if role == Role.REGULATOR:
            return True
        if role == Role.RETAILER:
            return batch.pharmacy_id == user.entity_id
        if role == Role.DISTRIBUTOR:
            return batch.distributor_id == user.entity_id
        if role == Role.MANUFACTURER:
            return batch.manufacturer_id == user.entity_id
        return False

    if channel.startswith("route:"):
        route_id = channel.removeprefix("route:")
        if role == Role.REGULATOR:
            return True
        route = await route_repo.get_by_id(session, route_id)
        if route is None:
            return False
        if role == Role.DISTRIBUTOR:
            return route.distributor_id == user.entity_id
        if role == Role.PICKUP_AGENT:
            return route.agent_id == user.entity_id
        stops = await route_repo.list_stops(session, route_id)
        if role == Role.RETAILER:
            return any(s.pharmacy_id == user.entity_id for s in stops)
        if role == Role.MANUFACTURER:
            for stop in stops:
                if not stop.return_id:
                    continue
                ret = await return_repo.get_by_id(session, stop.return_id)
                if ret is None:
                    continue
                batch = await batch_repo.get_by_id(session, ret.batch_id)
                if batch is not None and batch.manufacturer_id == user.entity_id:
                    return True
            return False
        return False

    if channel.startswith("notifications:"):
        parts = channel.split(":")
        if len(parts) != 3:
            return False
        _, role_str, entity_id = parts
        return role.value == role_str and entity_id == (user.entity_id or "")

    return False
