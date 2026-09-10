"""GET /api/notifications, PATCH /api/notifications/read-all,
PATCH /api/notifications/{id}/read. HTTP layer only — see
`app.services.notification_service` (CLAUDE.md rule 7). ARCHITECTURE.md §8.11.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import MarkReadResponse, NotificationOut
from app.services import notification_service

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationOut])
async def get_notifications(
    role: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationOut]:
    return await notification_service.get_notifications(session, current_user, role)


@router.patch("/notifications/read-all", response_model=MarkReadResponse)
async def mark_all_read(
    role: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MarkReadResponse:
    return await notification_service.mark_all_read(session, current_user, role)


@router.patch("/notifications/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MarkReadResponse:
    return await notification_service.mark_read(session, current_user, notification_id)
