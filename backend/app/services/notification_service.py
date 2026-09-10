"""Notification persistence and reads — ARCHITECTURE.md §4.8, §8.11.
`notify()` (Phase 4) matches
`frontend/src/services/notificationService.js`'s `notify(role, title, body,
kind, link)` signature exactly (broadcast by role, `user_id` left `NULL`
for every Phase 4/5/6 call site — nothing targets a single user yet).

`get_notifications` (Phase 8) keeps `getNotifications(role)`'s signature
per ARCHITECTURE.md §4.8's decided resolution, but the `role` argument is
*not* trusted for scoping — only `current_user.role` is. Otherwise a
caller could read another role's broadcast feed by passing a different
`role=` query value; the parameter only exists to match the frontend's
call shape.

No WebSocket publish here — `notify()` is called mid-transaction by every
caller (before their own commit), and publishing here would violate the
"publish after commit" rule (ARCHITECTURE.md §3) for every one of them.
Retrofitting post-commit publish at every `notify()` call site across
return_service/pickup_service/manufacturer_service was out of scope for
this pass — recorded as a known gap, not silently dropped (see
BUILDPHASES.md's Phase 7 implementation notes).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.core.rbac import Role
from app.models.enums import NotificationKind
from app.models.notification import Notification
from app.models.user import User
from app.repositories import notification_repo
from app.schemas.notification import MarkReadResponse, NotificationOut


async def notify(
    session: AsyncSession,
    role: Role,
    title: str,
    body: str,
    kind: NotificationKind = NotificationKind.info,
    link: str | None = None,
    *,
    user_id: str | None = None,
) -> Notification:
    """Does not commit — the caller owns the transaction, same discipline
    as `event_service.append` and `alert_service.raise_alert`."""
    notification = Notification(
        id=f"ntf_{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        role=role,
        title=title,
        body=body,
        kind=kind,
        link=link,
        read=False,
        ts=datetime.now(timezone.utc),
    )
    await notification_repo.create(session, notification)
    return notification


async def get_notifications(session: AsyncSession, current_user: User, _role_param: str | None) -> list[NotificationOut]:
    rows = await notification_repo.list_for_user(session, current_user.role, current_user.id)
    return [NotificationOut.from_model(n) for n in rows]


async def mark_all_read(session: AsyncSession, current_user: User, _role_param: str | None) -> MarkReadResponse:
    await notification_repo.mark_all_read(session, current_user.role, current_user.id)
    await session.commit()
    return MarkReadResponse(ok=True)


async def mark_read(session: AsyncSession, current_user: User, notification_id: str) -> MarkReadResponse:
    notification = await notification_repo.get_by_id(session, notification_id)
    if notification is None:
        raise NotFound("Notification not found.", code="NOTIFICATION_NOT_FOUND")
    if notification.role != current_user.role or (
        notification.user_id is not None and notification.user_id != current_user.id
    ):
        raise Forbidden("This notification does not belong to you.", code="NOT_YOUR_NOTIFICATION")
    notification.read = True
    await session.commit()
    return MarkReadResponse(ok=True)
