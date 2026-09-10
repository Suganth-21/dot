"""Wire shapes for /api/public/* — camelCase, matching what
`frontend/src/services/verifyService.js` already reads and sends (CLAUDE.md
rule 3, rule 4: these routes stay public forever). See ARCHITECTURE.md §3,
§8.7.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BatchStatus


class VerifyBatchSummaryOut(BaseModel):
    """Deliberately minimal — ARCHITECTURE.md §3: "Public responses
    deliberately exclude quantities, pharmacy identity, holder chain, event
    meta, and GPS. A patient needs a verdict, not a supply chain dossier."
    """

    id: str
    drug_name: str = Field(serialization_alias="drugName")
    manufacturer_name: str = Field(serialization_alias="manufacturerName")
    expiry_date: datetime = Field(serialization_alias="expiryDate")
    status: BatchStatus | None = None
    destroyed_date: datetime | None = Field(default=None, serialization_alias="destroyedDate")
    cert_id: str | None = Field(default=None, serialization_alias="certId")

    model_config = ConfigDict(populate_by_name=True)


class VerifyHistoryEntryOut(BaseModel):
    type: str
    ts: datetime


class VerifyBatchOut(BaseModel):
    verdict: str
    batch_id: str | None = Field(default=None, serialization_alias="batchId")
    batch: VerifyBatchSummaryOut | None = None
    history: list[VerifyHistoryEntryOut] | None = None

    model_config = ConfigDict(populate_by_name=True)


class LocationIn(BaseModel):
    lat: float | None = None
    lng: float | None = None
    district: str | None = None


class ReportSuspiciousRequest(BaseModel):
    batch_id: str | None = Field(default=None, validation_alias="batchId")
    location: LocationIn | None = None
    notes: str | None = None
    photo_hash: str | None = Field(default=None, validation_alias="photoHash")
    pharmacy_name: str | None = Field(default=None, validation_alias="pharmacyName")

    model_config = ConfigDict(populate_by_name=True)


class ReportSuspiciousResponse(BaseModel):
    id: str
    batch_id: str | None = Field(default=None, serialization_alias="batchId")
    location: LocationIn | None = None
    notes: str | None = None
    photo_hash: str | None = Field(default=None, serialization_alias="photoHash")
    pharmacy_name: str | None = Field(default=None, serialization_alias="pharmacyName")
    ts: datetime

    model_config = ConfigDict(populate_by_name=True)
