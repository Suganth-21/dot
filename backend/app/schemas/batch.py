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
    def from_model(cls, event: Any) -> EventOut:
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

    @classmethod
    def from_model(
        cls, batch: Any, *, status: BatchStatus, events: list[Any], facility_name: str | None = None
    ) -> BatchOut:
        """Assembles the wire shape from an ORM `Batch` row plus its
        already-derived status (see `app.services.batch_status`) and
        already-loaded events. A leaf classmethod rather than a
        `batch_service`-only helper so `alert_service` can embed a full
        `BatchOut` (events included — the regulator alert detail page's
        `HashChain` needs them) in `GET /api/alerts/{id}` without importing
        `batch_service` and risking a circular import through
        `fraud_service` (ARCHITECTURE.md §2's one-way dependency direction).
        """
        holder = None
        if batch.holder_type and batch.holder_id:
            holder = HolderOut(type=batch.holder_type, id=batch.holder_id, name=batch.holder_name or "")

        scheduled_facility = None
        if batch.scheduled_facility_id:
            scheduled_facility = ScheduledFacilityOut(
                id=batch.scheduled_facility_id, name=facility_name or "", date=batch.scheduled_facility_date
            )

        return cls(
            id=batch.id,
            code=batch.code,
            drug_name=batch.drug_name,
            drug_key=batch.drug_key,
            category=batch.category,
            unit_price=float(batch.unit_price),
            manufacturer_id=batch.manufacturer_id,
            manufacturer_name=batch.manufacturer_name,
            pharmacy_id=batch.pharmacy_id,
            distributor_id=batch.distributor_id,
            mfg_date=batch.mfg_date,
            expiry_date=batch.expiry_date,
            initial_quantity=batch.initial_quantity,
            quantity=batch.quantity,
            status=status,
            holder=holder,
            scheduled_facility=scheduled_facility,
            destroyed=batch.destroyed,
            destroyed_date=batch.destroyed_date,
            cert_id=batch.cert_id,
            events=[EventOut.from_model(e) for e in events],
        )


class RegisterBatchResponse(BaseModel):
    reentry: bool = False
    batch: BatchOut
    # ARCHITECTURE.md §7.4 / §8.2: quantity-cap breaches are flagged, not
    # refused — registration still succeeds (`Any` here, not `AlertOut`,
    # to avoid this schema module importing app.schemas.alert, which itself
    # imports BatchOut from here).
    quantity_cap_breach: bool = Field(default=False, serialization_alias="quantityCapBreach")
    alert: Any | None = None

    model_config = ConfigDict(populate_by_name=True)


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
