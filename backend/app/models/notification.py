"""Notification — a record/event powering the per-role bell. ARCHITECTURE.md
§4.8. Phase 4 only ever writes these (on return lifecycle state changes,
via `app.services.notification_service.notify`); the read endpoints
(`GET /api/notifications`, mark-read) are Phase 8's job — see
BUILDPHASES.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.rbac import Role
from app.models.base import Base
from app.models.enums import NotificationKind

_role_enum = Enum(Role, name="role_enum", create_type=False, values_callable=lambda e: [m.value for m in e])
_kind_enum = Enum(NotificationKind, name="kind_enum", values_callable=lambda e: [m.value for m in e])


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # NULL = broadcast to the whole role (ARCHITECTURE.md §4.8). No demo
    # scenario in Phase 4 targets a single user yet — every call site
    # broadcasts by role, matching frontend/src/services/notificationService.js's
    # `notify(role, ...)` signature exactly.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[Role] = mapped_column(_role_enum, nullable=False, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(_kind_enum, nullable=False)
    link: Mapped[str | None] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
