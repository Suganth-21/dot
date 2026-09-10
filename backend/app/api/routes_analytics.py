"""GET /api/analytics/* — nine endpoints. HTTP layer only — see
`app.services.analytics_service` (CLAUDE.md rule 7). ARCHITECTURE.md §8.10.
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden
from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.services import analytics_service

router = APIRouter()


def _check_own_scope(current_user: User, entity_id: str) -> None:
    """ARCHITECTURE.md §6.5 "Analytics" row: "own scope" for
    RETAILER/DISTRIBUTOR/MANUFACTURER, "national" (unrestricted) for
    REGULATOR."""
    if current_user.role == Role.REGULATOR:
        return
    if current_user.entity_id != entity_id:
        raise Forbidden("You can only view your own analytics.", code="NOT_YOUR_ENTITY")


@router.get("/analytics/pharmacy/{pharmacy_id}/stats", response_model=dict[str, Any])
async def pharmacy_stats(
    pharmacy_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, pharmacy_id)
    return await analytics_service.pharmacy_stats(session, pharmacy_id)


@router.get("/analytics/pharmacy/{pharmacy_id}/sparkline", response_model=list[dict[str, Any]])
async def pharmacy_sparkline(
    pharmacy_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> list[dict[str, Any]]:
    _check_own_scope(current_user, pharmacy_id)
    return await analytics_service.pharmacy_sparkline(session, pharmacy_id)


@router.get("/analytics/pharmacy/{pharmacy_id}", response_model=dict[str, Any])
async def pharmacy_analytics(
    pharmacy_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, pharmacy_id)
    return await analytics_service.pharmacy_analytics(session, pharmacy_id)


@router.get("/analytics/distributor/{distributor_id}/stats", response_model=dict[str, Any])
async def distributor_stats(
    distributor_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, distributor_id)
    return await analytics_service.distributor_stats(session, distributor_id)


@router.get("/analytics/distributor/{distributor_id}", response_model=dict[str, Any])
async def distributor_analytics(
    distributor_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, distributor_id)
    return await analytics_service.distributor_analytics(session, distributor_id)


@router.get("/analytics/manufacturer/{manufacturer_id}/stats", response_model=dict[str, Any])
async def manufacturer_stats(
    manufacturer_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, manufacturer_id)
    return await analytics_service.manufacturer_stats(session, manufacturer_id)


@router.get("/analytics/manufacturer/{manufacturer_id}", response_model=dict[str, Any])
async def manufacturer_analytics(
    manufacturer_id: str, session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> dict[str, Any]:
    _check_own_scope(current_user, manufacturer_id)
    return await analytics_service.manufacturer_analytics(session, manufacturer_id)


@router.get("/analytics/regulator/stats", response_model=dict[str, Any])
async def regulator_stats(
    session: AsyncSession = Depends(get_db), _current_user: User = Depends(require_role(Role.REGULATOR)),
) -> dict[str, Any]:
    return await analytics_service.regulator_stats(session)


@router.get("/analytics/regulator", response_model=dict[str, Any])
async def regulator_analytics(
    session: AsyncSession = Depends(get_db), _current_user: User = Depends(require_role(Role.REGULATOR)),
) -> dict[str, Any]:
    return await analytics_service.regulator_analytics(session)
