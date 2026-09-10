"""Wire shapes for /api/reference/* — camelCase on the wire, matching what
`frontend/src/services/referenceService.js` already reads off these objects
(CLAUDE.md rule 3). See ARCHITECTURE.md §4.2, §8.8.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgentStatus, DrugCategory


class PharmacyOut(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str | None = None
    license_no: str = Field(serialization_alias="licenseNo")
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DistributorOut(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str | None = None
    license_no: str = Field(serialization_alias="licenseNo")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ManufacturerOut(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str | None = None
    license_no: str = Field(serialization_alias="licenseNo")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FacilityOut(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    license_no: str = Field(serialization_alias="licenseNo")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RegulatorOut(BaseModel):
    id: str
    name: str
    jurisdiction: str
    officer_name: str = Field(serialization_alias="officerName")
    officer_designation: str = Field(serialization_alias="officerDesignation")
    officer_id: str = Field(serialization_alias="officerId")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentOut(BaseModel):
    id: str
    distributor_id: str = Field(serialization_alias="distributorId")
    name: str
    phone: str
    status: AgentStatus

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class VehicleOut(BaseModel):
    id: str
    distributor_id: str = Field(serialization_alias="distributorId")
    reg_no: str = Field(serialization_alias="regNo")
    status: AgentStatus
    lat: float | None = None
    lng: float | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DrugOut(BaseModel):
    key: str
    name: str
    category: DrugCategory
    price: float

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
