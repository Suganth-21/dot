"""Database access for `routes` and `route_stops`. No business decisions —
nearest-neighbour ordering, dispatch, and stop transitions live in
`app.services.pickup_service` (ARCHITECTURE.md §2).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.route import Route, RouteStop


async def get_by_id(session: AsyncSession, route_id: str) -> Route | None:
    return await session.get(Route, route_id)


async def get_for_update(session: AsyncSession, route_id: str) -> Route | None:
    result = await session.execute(select(Route).where(Route.id == route_id).with_for_update())
    return result.scalar_one_or_none()


async def create(session: AsyncSession, route: Route) -> Route:
    session.add(route)
    return route


async def list_routes(
    session: AsyncSession, *, distributor_id: str | None = None, agent_id: str | None = None
) -> list[Route]:
    stmt = select(Route)
    if distributor_id:
        stmt = stmt.where(Route.distributor_id == distributor_id)
    if agent_id:
        stmt = stmt.where(Route.agent_id == agent_id)
    stmt = stmt.order_by(Route.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_active(session: AsyncSession) -> list[Route]:
    """Every currently-running route — the GPS simulator's tick target."""
    result = await session.execute(select(Route).where(Route.running.is_(True)))
    return list(result.scalars().all())


async def list_stops(session: AsyncSession, route_id: str) -> list[RouteStop]:
    result = await session.execute(
        select(RouteStop).where(RouteStop.route_id == route_id).order_by(RouteStop.stop_order)
    )
    return list(result.scalars().all())


async def get_stop_by_order(session: AsyncSession, route_id: str, order: int) -> RouteStop | None:
    result = await session.execute(
        select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.stop_order == order)
    )
    return result.scalar_one_or_none()


async def create_stop(session: AsyncSession, stop: RouteStop) -> RouteStop:
    session.add(stop)
    return stop


async def delete_all(session: AsyncSession) -> None:
    """Phase-5-owned truncate for demo reset — see app.seed.reset. Stops
    before routes (FK)."""
    await session.execute(RouteStop.__table__.delete())
    await session.execute(Route.__table__.delete())
