"""Wire shapes for /api/notifications — camelCase, matching what
`frontend/src/services/notificationService.js` already reads (CLAUDE.md
rule 3). See ARCHITECTURE.md §4.8, §8.11.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationKind


class NotificationOut(BaseModel):
    id: str
    title: str
    body: str
    kind: NotificationKind
    link: str | None = None
    read: bool
    ts: datetime

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, n: Any) -> "NotificationOut":
        return cls(id=n.id, title=n.title, body=n.body, kind=n.kind, link=n.link, read=n.read, ts=n.ts)


class MarkReadResponse(BaseModel):
    ok: bool = True
