"""Wire shapes for /api/entities — camelCase, matching what
`frontend/src/services/entityService.js` already reads (CLAUDE.md rule 3).
See ARCHITECTURE.md §8.9.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alert import AlertOut


class EntityOut(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str | None = None
    license_no: str | None = Field(default=None, serialization_alias="licenseNo")
    type: str  # PHARMACY | DISTRIBUTOR | MANUFACTURER
    score: int
    risk: str  # LOW | MEDIUM | HIGH
    alerts_on: int = Field(serialization_alias="alertsOn")
    return_rate: int = Field(serialization_alias="returnRate")
    dispute_rate: int = Field(serialization_alias="disputeRate")

    model_config = ConfigDict(populate_by_name=True)


class EntityDetailOut(EntityOut):
    alerts: list[AlertOut] = Field(default_factory=list)
    batch_count: int = Field(serialization_alias="batchCount")
