"""GET/POST /api/routes, GET /api/fleet, and stop actions. HTTP layer only —
see `app.services.pickup_service` for every rule and role scoping
(CLAUDE.md rule 7). ARCHITECTURE.md §8.4.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.schemas.route import AgentPickupRequest, CreateRouteRequest, DispatchResponse, FleetOut, RouteOut
from app.services import pickup_service

router = APIRouter()


@router.get("/routes", response_model=list[RouteOut])
async def list_routes(
    distributorId: str | None = Query(default=None),
    agentId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("routes:read")),
) -> list[RouteOut]:
    return await pickup_service.list_routes(session, current_user, distributor_id=distributorId, agent_id=agentId)


@router.get("/routes/{route_id}", response_model=RouteOut)
async def get_route(
    route_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("routes:read")),
) -> RouteOut:
    return await pickup_service.get_route(session, current_user, route_id)


@router.get("/fleet", response_model=FleetOut)
async def list_fleet(
    distributorId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("routes:read")),
) -> FleetOut:
    return await pickup_service.list_fleet(session, distributorId)


@router.post("/routes", response_model=RouteOut)
async def create_route(
    payload: CreateRouteRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("routes:create_or_dispatch")),
) -> RouteOut:
    return await pickup_service.create_route(session, current_user, payload)


@router.post("/routes/{route_id}/dispatch", response_model=DispatchResponse)
async def dispatch_route(
    route_id: str,
    session: AsyncSession = Depends(get_db),
    # ARCHITECTURE.md §8.4: "Agent 'Start Route' calls the same function" —
    # dispatch is the one routes action both DISTRIBUTOR and PICKUP_AGENT
    # may call, which `rbac.PERMISSION_MATRIX`'s single
    # "routes:create_or_dispatch" key (DISTRIBUTOR-only, correct for
    # *create*) can't express alongside routes:create — bypassed here
    # directly, same precedent as the Phase 4 Kanban endpoint.
    current_user: User = Depends(require_role(Role.DISTRIBUTOR, Role.PICKUP_AGENT)),
) -> DispatchResponse:
    return await pickup_service.dispatch_route(session, current_user, route_id)


@router.post("/routes/{route_id}/stops/{index}/arrive", response_model=RouteOut)
async def agent_arrive(
    route_id: str,
    index: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("routes:arrive_or_pickup")),
) -> RouteOut:
    return await pickup_service.agent_arrive(session, current_user, route_id, index)


@router.post("/routes/{route_id}/stops/{index}/pickup", response_model=RouteOut)
async def agent_pickup(
    route_id: str,
    index: int,
    payload: AgentPickupRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("routes:arrive_or_pickup")),
) -> RouteOut:
    return await pickup_service.agent_pickup(session, current_user, route_id, index, payload.counted)
