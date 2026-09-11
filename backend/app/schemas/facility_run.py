"""Wire shapes for /api/facility-runs — camelCase, mirroring
`app.schemas.route`'s conventions. See ARCHITECTURE.md §4.6/§8.4 for the
pickup-leg precedent this leg reuses."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RouteStatus


class FacilityRunBatchOut(BaseModel):
    """One manifest line — denormalised off the Batch row so the frontend
    never needs a second fetch to show what's actually on the truck."""

    batch_id: str = Field(serialization_alias="batchId")
    drug_name: str = Field(serialization_alias="drugName")
    quantity: int

    model_config = ConfigDict(populate_by_name=True)


class PosOut(BaseModel):
    lat: float
    lng: float


class FacilityRunOut(BaseModel):
    id: str
    distributor_id: str = Field(serialization_alias="distributorId")
    agent_id: str = Field(serialization_alias="agentId")
    agent_name: str | None = Field(default=None, serialization_alias="agentName")
    vehicle_id: str = Field(serialization_alias="vehicleId")
    vehicle_reg: str | None = Field(default=None, serialization_alias="vehicleReg")
    facility_id: str = Field(serialization_alias="facilityId")
    facility_name: str | None = Field(default=None, serialization_alias="facilityName")
    batches: list[FacilityRunBatchOut] = Field(default_factory=list)
    delivered: bool
    status: RouteStatus
    running: bool
    path: list[dict[str, float]]
    seg_index: int = Field(serialization_alias="segIndex")
    seg_t: float = Field(serialization_alias="segT")
    pos: PosOut | None = None
    eta_min: int | None = Field(default=None, serialization_alias="etaMin")
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, run: Any, batch_outs: list[FacilityRunBatchOut]) -> FacilityRunOut:
        pos = PosOut(lat=run.pos_lat, lng=run.pos_lng) if run.pos_lat is not None else None
        return cls(
            id=run.id, distributor_id=run.distributor_id, agent_id=run.agent_id, agent_name=run.agent_name,
            vehicle_id=run.vehicle_id, vehicle_reg=run.vehicle_reg, facility_id=run.facility_id,
            facility_name=run.facility_name, batches=batch_outs, delivered=run.delivered,
            status=run.status, running=run.running,
            path=run.path, seg_index=run.seg_index, seg_t=run.seg_t, pos=pos, eta_min=run.eta_min,
            created_at=run.created_at,
        )


class CreateFacilityRunRequest(BaseModel):
    distributor_id: str = Field(validation_alias="distributorId")
    batch_ids: list[str] = Field(validation_alias="batchIds")
    facility_id: str = Field(validation_alias="facilityId")
    agent_id: str = Field(validation_alias="agentId")
    vehicle_id: str = Field(validation_alias="vehicleId")

    model_config = ConfigDict(populate_by_name=True)


class DispatchResponse(BaseModel):
    ok: bool = True
