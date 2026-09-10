"""Wire shapes for /api/manufacturer/* and /api/batches/{id}/cert-eligibility
— camelCase, matching what `frontend/src/services/manufacturerService.js`
already reads and sends (CLAUDE.md rule 3). See ARCHITECTURE.md §7.2, §8.5.
"""
from __future__ import annotations

from datetime import date as date_

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.batch import BatchOut


class ScheduleFacilityRequest(BaseModel):
    batch_ids: list[str] = Field(validation_alias="batchIds")
    facility_id: str = Field(validation_alias="facilityId")
    date: date_

    model_config = ConfigDict(populate_by_name=True)


class ScheduleFacilityResponse(BaseModel):
    ok: bool = True


class CertEligibilityOut(BaseModel):
    eligible: bool
    reason: str | None = None


class UploadCertificateRequest(BaseModel):
    batch_id: str = Field(validation_alias="batchId")
    cert_id: str | None = Field(default=None, validation_alias="certId")
    file_name: str | None = Field(default=None, validation_alias="fileName")

    model_config = ConfigDict(populate_by_name=True)


class UploadCertificateResponse(BaseModel):
    ok: bool = True
    batch: BatchOut
    covered_batches: list[str] = Field(serialization_alias="coveredBatches")

    model_config = ConfigDict(populate_by_name=True)
