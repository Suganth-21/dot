"""Wire shapes for /api/routes, /api/fleet — camelCase, matching what
`frontend/src/services/pickupService.js` already reads and sends (CLAUDE.md
rule 3). See ARCHITECTURE.md §4.6, §8.4.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RouteStatus, StopStatus
from app.schemas.reference import AgentOut, VehicleOut


class RouteStopOut(BaseModel):
    pharmacy_id: str = Field(serialization_alias="pharmacyId")
    pharmacy_name: str | None = Field(default=None, serialization_alias="pharmacyName")
    address: str | None = None
    lat: float
    lng: float
    order: int
    status: StopStatus
    expected_batches: int = Field(serialization_alias="expectedBatches")
    return_id: str | None = Field(default=None, serialization_alias="returnId")
    counted: int | None = None

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, stop: Any) -> RouteStopOut:
        return cls(
            pharmacy_id=stop.pharmacy_id, pharmacy_name=stop.pharmacy_name, address=stop.address,
            lat=stop.lat, lng=stop.lng, order=stop.stop_order, status=stop.status,
            expected_batches=stop.expected_batches, return_id=stop.return_id, counted=stop.counted,
        )


class PosOut(BaseModel):
    lat: float
    lng: float


class RouteOut(BaseModel):
    id: str
    distributor_id: str = Field(serialization_alias="distributorId")
    agent_id: str = Field(serialization_alias="agentId")
    agent_name: str | None = Field(default=None, serialization_alias="agentName")
    vehicle_id: str = Field(serialization_alias="vehicleId")
    vehicle_reg: str | None = Field(default=None, serialization_alias="vehicleReg")
    status: RouteStatus
    running: bool
    path: list[dict[str, float]]
    seg_index: int = Field(serialization_alias="segIndex")
    seg_t: float = Field(serialization_alias="segT")
    pos: PosOut | None = None
    eta_min: int | None = Field(default=None, serialization_alias="etaMin")
    created_at: datetime = Field(serialization_alias="createdAt")
    stops: list[RouteStopOut] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, route: Any, stops: list[Any]) -> RouteOut:
        pos = PosOut(lat=route.pos_lat, lng=route.pos_lng) if route.pos_lat is not None else None
        return cls(
            id=route.id, distributor_id=route.distributor_id, agent_id=route.agent_id,
            agent_name=route.agent_name, vehicle_id=route.vehicle_id, vehicle_reg=route.vehicle_reg,
            status=route.status, running=route.running, path=route.path, seg_index=route.seg_index,
            seg_t=route.seg_t, pos=pos, eta_min=route.eta_min, created_at=route.created_at,
            stops=[RouteStopOut.from_model(s) for s in stops],
        )


class CreateRouteRequest(BaseModel):
    distributor_id: str = Field(validation_alias="distributorId")
    return_ids: list[str] = Field(validation_alias="returnIds")
    agent_id: str = Field(validation_alias="agentId")
    vehicle_id: str = Field(validation_alias="vehicleId")
    manual_order: bool = Field(default=False, validation_alias="manualOrder")

    model_config = ConfigDict(populate_by_name=True)


class DispatchResponse(BaseModel):
    ok: bool = True


class FleetOut(BaseModel):
    vehicles: list[VehicleOut]
    agents: list[AgentOut]


class AgentPickupRequest(BaseModel):
    counted: int = Field(ge=0)
