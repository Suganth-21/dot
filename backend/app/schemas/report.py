"""Wire shapes for /api/reports — camelCase, matching
`frontend/src/services/alertService.js`'s `listReports`/`generateReport`
(CLAUDE.md rule 3). See ARCHITECTURE.md §4.9, §8.6.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    title: str | None = None
    region: str | None = None
    category: str | None = None


class ReportOut(BaseModel):
    id: str
    title: str
    region: str
    category: str
    created_at: datetime = Field(serialization_alias="createdAt")
    size: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, r: Any) -> "ReportOut":
        return cls(id=r.id, title=r.title, region=r.region, category=r.category, created_at=r.created_at, size=r.size)
