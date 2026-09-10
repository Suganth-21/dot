"""GET /api/alerts, GET /api/alerts/{id}, PATCH /api/alerts/{id}/status.
HTTP layer only — see `app.services.alert_service` for every rule and role
scoping (CLAUDE.md rule 7). ARCHITECTURE.md §8.6.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.schemas.alert import (
    AlertOut,
    AlertStatusUpdateRequest,
    AlertStatusUpdateResponse,
)
from app.schemas.report import GenerateReportRequest, ReportOut
from app.services import alert_service

router = APIRouter()


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    district: str | None = Query(default=None),
    drugCategory: str | None = Query(default=None),
    manufacturerId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("alerts:read")),
) -> list[AlertOut]:
    return await alert_service.list_alerts(
        session, current_user, type_=type, status=status, district=district,
        drug_category=drugCategory, manufacturer_id=manufacturerId,
    )


@router.get("/alerts/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("alerts:read")),
) -> AlertOut:
    return await alert_service.get_alert(session, current_user, alert_id)


@router.patch("/alerts/{alert_id}/status", response_model=AlertStatusUpdateResponse)
async def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.REGULATOR)),
) -> AlertStatusUpdateResponse:
    # alert_service.update_status no longer commits internally (Phase 4) —
    # it's shared with return_service.resolve_dispute, which needs the
    # alert-close folded into its own single transaction. This route is the
    # one place that update_status is the *entire* operation, so it owns
    # the commit.
    result = await alert_service.update_status(session, alert_id, payload.status, payload.officer)
    await session.commit()
    return result


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("reports:generate")),
) -> list[ReportOut]:
    return await alert_service.list_reports(session)


@router.post("/reports", response_model=ReportOut)
async def generate_report(
    payload: GenerateReportRequest,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("reports:generate")),
) -> ReportOut:
    return await alert_service.generate_report(session, payload)
