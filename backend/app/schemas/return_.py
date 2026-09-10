"""Wire shapes for /api/returns — camelCase, matching what
`frontend/src/services/returnService.js` already reads and sends (CLAUDE.md
rule 3). See ARCHITECTURE.md §4.5, §5.2, §7.1, §8.3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DrugCategory, ReturnReason, ReturnStatus
from app.schemas.batch import BatchOut
from app.schemas.reference import DistributorOut, PharmacyOut


class CreateReturnRequest(BaseModel):
    """ARCHITECTURE.md §8.3: `POST /api/returns`, body `{batchId, quantity,
    distributorId, reason, photoHash}` — matching `returnService.js`'s
    `createReturn(batchId, data, actor)` field for field."""

    batch_id: str = Field(validation_alias="batchId")
    quantity: int = Field(gt=0)
    distributor_id: str = Field(validation_alias="distributorId")
    reason: ReturnReason
    photo_hash: str | None = Field(default=None, validation_alias="photoHash")

    model_config = ConfigDict(populate_by_name=True)


class ReturnOut(BaseModel):
    id: str
    batch_id: str = Field(serialization_alias="batchId")
    pharmacy_id: str = Field(serialization_alias="pharmacyId")
    distributor_id: str = Field(serialization_alias="distributorId")
    drug_name: str = Field(serialization_alias="drugName")
    category: DrugCategory
    quantity_claimed: int = Field(serialization_alias="quantityClaimed")
    picked_quantity: int | None = Field(default=None, serialization_alias="pickedQuantity")
    quantity_received: int | None = Field(default=None, serialization_alias="quantityReceived")
    reason: ReturnReason
    status: ReturnStatus
    photo_hash: str | None = Field(default=None, serialization_alias="photoHash")
    distributor_photo_hash: str | None = Field(default=None, serialization_alias="distributorPhotoHash")
    distributor_notes: str | None = Field(default=None, serialization_alias="distributorNotes")
    dispute_notes: str | None = Field(default=None, serialization_alias="disputeNotes")
    resolution_notes: str | None = Field(default=None, serialization_alias="resolutionNotes")
    route_id: str | None = Field(default=None, serialization_alias="routeId")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, ret: Any) -> ReturnOut:
        return cls(
            id=ret.id, batch_id=ret.batch_id, pharmacy_id=ret.pharmacy_id, distributor_id=ret.distributor_id,
            drug_name=ret.drug_name, category=ret.category, quantity_claimed=ret.quantity_claimed,
            picked_quantity=ret.picked_quantity, quantity_received=ret.quantity_received, reason=ret.reason,
            status=ret.status, photo_hash=ret.photo_hash, distributor_photo_hash=ret.distributor_photo_hash,
            distributor_notes=ret.distributor_notes, dispute_notes=ret.dispute_notes,
            resolution_notes=ret.resolution_notes, route_id=ret.route_id,
            created_at=ret.created_at, updated_at=ret.updated_at,
        )


class ReturnDetailOut(ReturnOut):
    """`getReturn(id)` — the mock spreads the return plus `batch`,
    `pharmacy`, `distributor` joined directly onto the response
    (`{...r, batch, pharmacy, distributor}`)."""

    batch: BatchOut | None = None
    pharmacy: PharmacyOut | None = None
    distributor: DistributorOut | None = None


class DistributorReceiveRequest(BaseModel):
    quantity_received: int = Field(ge=0, validation_alias="quantityReceived")
    photo_hash: str | None = Field(default=None, validation_alias="photoHash")
    notes: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class DistributorReceiveResponse(BaseModel):
    """ARCHITECTURE.md §8.3 / BUILDPHASES.md error conventions: this is a
    *successful* (200) response even when `dispute` is true — the dispute
    gate refusal is a separate, later 409 on `forward`/`resolve`, not on
    `receive` itself. Matches the mock's `{dispute, alert?}` shape exactly."""

    dispute: bool
    alert: Any | None = None


class ResolveDisputeRequest(BaseModel):
    resolution_notes: str = Field(validation_alias="resolutionNotes")

    model_config = ConfigDict(populate_by_name=True)


class ResolveDisputeResponse(BaseModel):
    ok: bool = True


class ForwardReturnsRequest(BaseModel):
    return_ids: list[str] = Field(validation_alias="returnIds")

    model_config = ConfigDict(populate_by_name=True)


class ForwardReturnsResponse(BaseModel):
    ok: bool = True
    forwarded: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)


class SetReturnStatusRequest(BaseModel):
    status: str
