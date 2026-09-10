"""Wire shapes for /api/alerts — camelCase, matching what
`frontend/src/services/alertService.js` already reads and sends (CLAUDE.md
rule 3). See ARCHITECTURE.md §4.7, §8.6.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertSeverity, AlertStatus, AlertType, DrugCategory
from app.schemas.batch import BatchOut


class AuditTrailEntryOut(BaseModel):
    action: str
    officer: str
    ts: datetime
    notes: str | None = None

    model_config = ConfigDict(extra="ignore")


class AlertOut(BaseModel):
    id: str
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    batch_id: str | None = Field(default=None, serialization_alias="batchId")
    drug_name: str | None = Field(default=None, serialization_alias="drugName")
    drug_category: DrugCategory | None = Field(default=None, serialization_alias="drugCategory")
    entity_id: str | None = Field(default=None, serialization_alias="entityId")
    entity_name: str | None = Field(default=None, serialization_alias="entityName")
    district: str | None = None
    manufacturer_id: str | None = Field(default=None, serialization_alias="manufacturerId")
    rule: str
    message: str
    audit_trail: list[AuditTrailEntryOut] = Field(default_factory=list, serialization_alias="auditTrail")
    ts: datetime
    batch: BatchOut | None = None

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, alert: Any, *, batch: BatchOut | None = None) -> "AlertOut":
        return cls(
            id=alert.id,
            type=alert.type,
            severity=alert.severity,
            status=alert.status,
            batch_id=alert.batch_id,
            drug_name=alert.drug_name,
            drug_category=alert.drug_category,
            entity_id=alert.entity_id,
            entity_name=alert.entity_name,
            district=alert.district,
            manufacturer_id=alert.manufacturer_id,
            rule=alert.rule,
            message=alert.message,
            audit_trail=[AuditTrailEntryOut(**entry) for entry in (alert.audit_trail or [])],
            ts=alert.ts,
            batch=batch,
        )


class AlertStatusUpdateRequest(BaseModel):
    status: AlertStatus
    officer: str | None = None


class AlertStatusUpdateResponse(BaseModel):
    ok: bool = True
