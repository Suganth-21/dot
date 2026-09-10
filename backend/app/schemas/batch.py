"""Wire shapes for /api/batches, /api/search — camelCase, matching what
`frontend/src/services/batchService.js` already reads and sends
(CLAUDE.md rule 3). See ARCHITECTURE.md §4.3, §4.4, §8.2.
"""
from __future__ import annotations

from datetime import date as date_
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BatchStatus, DrugCategory, HolderType


class RegisterBatchRequest(BaseModel):
    batch_id: str = Field(validation_alias="batchId")
    drug_name: str = Field(validation_alias="drugName")
    drug_key: str = Field(validation_alias="drugKey")
    category: DrugCategory
    unit_price: float = Field(validation_alias="unitPrice")
    manufacturer_id: str = Field(validation_alias="manufacturerId")
    manufacturer_name: str = Field(validation_alias="manufacturerName")
    mfg_date: datetime = Field(validation_alias="mfgDate")
    expiry_date: datetime = Field(validation_alias="expiryDate")
    quantity: int = Field(gt=0)

    model_config = ConfigDict(populate_by_name=True)


class SaleRequest(BaseModel):
    units: int = Field(gt=0)


class ActorOut(BaseModel):
    id: str
    name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class GpsOut(BaseModel):
    lat: float
    lng: float

    model_config = ConfigDict(from_attributes=True)


class EventOut(BaseModel):
    id: str
    batch_id: str = Field(serialization_alias="batchId")
    type: str
    actor: ActorOut
    ts: datetime
    gps: GpsOut | None = None
    photo_hash: str | None = Field(default=None, serialization_alias="photoHash")
    meta: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = Field(serialization_alias="prevHash")
    hash: str

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, event: Any) -> "EventOut":
        event_type = event.type.value if hasattr(event.type, "value") else event.type
        gps = GpsOut(lat=event.gps_lat, lng=event.gps_lng) if event.gps_lat is not None else None
        return cls(
            id=event.id,
            batch_id=event.batch_id,
            type=event_type,
            actor=ActorOut(id=event.actor_id, name=event.actor_name, role=event.actor_role),
            ts=event.ts,
            gps=gps,
            photo_hash=event.photo_hash,
            meta=event.meta or {},
            prev_hash=event.prev_hash,
            hash=event.hash,
        )


class HolderOut(BaseModel):
    type: HolderType
    id: str
    name: str


class ScheduledFacilityOut(BaseModel):
    id: str
    name: str
    date: date_ | None = None


class BatchOut(BaseModel):
    id: str
    code: str
    drug_name: str = Field(serialization_alias="drugName")
    drug_key: str = Field(serialization_alias="drugKey")
    category: DrugCategory
    unit_price: float = Field(serialization_alias="unitPrice")
    manufacturer_id: str = Field(serialization_alias="manufacturerId")
    manufacturer_name: str = Field(serialization_alias="manufacturerName")
    pharmacy_id: str | None = Field(default=None, serialization_alias="pharmacyId")
    distributor_id: str | None = Field(default=None, serialization_alias="distributorId")
    mfg_date: datetime = Field(serialization_alias="mfgDate")
    expiry_date: datetime = Field(serialization_alias="expiryDate")
    initial_quantity: int = Field(serialization_alias="initialQuantity")
    quantity: int
    status: BatchStatus
    holder: HolderOut | None = None
    scheduled_facility: ScheduledFacilityOut | None = Field(default=None, serialization_alias="scheduledFacility")
    destroyed: bool
    destroyed_date: datetime | None = Field(default=None, serialization_alias="destroyedDate")
    cert_id: str | None = Field(default=None, serialization_alias="certId")
    events: list[EventOut] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class RegisterBatchResponse(BaseModel):
    reentry: bool = False
    batch: BatchOut


class SearchResultOut(BaseModel):
    type: str
    id: str
    title: str
    subtitle: str
    status: str | None = None


class ChainVerificationError(BaseModel):
    sequence: int
    reason: str


class ChainVerificationOut(BaseModel):
    valid: bool
    broken_at_sequence: int | None = Field(default=None, serialization_alias="brokenAtSequence")
    checked: int
    errors: list[ChainVerificationError] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
