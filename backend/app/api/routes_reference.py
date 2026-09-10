"""GET /api/reference/* — the first real data the frontend can read
(BUILDPHASES.md Phase 1). All routes require authentication only; none are
role-restricted per ARCHITECTURE.md §8.8 ("A", no role in brackets).
HTTP layer only — see `app.services.reference_service` for the reads.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.reference import (
    AgentOut,
    DistributorOut,
    DrugOut,
    FacilityOut,
    ManufacturerOut,
    PharmacyOut,
    VehicleOut,
)
from app.services import reference_service

router = APIRouter()

_authenticated = require_permission("reference:read")


@router.get("/reference/distributors", response_model=list[DistributorOut])
async def get_distributors(
    session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> list[DistributorOut]:
    rows = await reference_service.list_distributors(session)
    return [DistributorOut.model_validate(r) for r in rows]


@router.get("/reference/manufacturers", response_model=list[ManufacturerOut])
async def get_manufacturers(
    session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> list[ManufacturerOut]:
    rows = await reference_service.list_manufacturers(session)
    return [ManufacturerOut.model_validate(r) for r in rows]


@router.get("/reference/facilities", response_model=list[FacilityOut])
async def get_facilities(
    session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> list[FacilityOut]:
    rows = await reference_service.list_facilities(session)
    return [FacilityOut.model_validate(r) for r in rows]


@router.get("/reference/pharmacies", response_model=list[PharmacyOut])
async def get_pharmacies(
    session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> list[PharmacyOut]:
    rows = await reference_service.list_pharmacies(session)
    return [PharmacyOut.model_validate(r) for r in rows]


@router.get("/reference/pharmacies/{pharmacy_id}", response_model=PharmacyOut)
async def get_pharmacy(
    pharmacy_id: str, session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> PharmacyOut:
    row = await reference_service.get_pharmacy(session, pharmacy_id)
    return PharmacyOut.model_validate(row)


@router.get("/reference/agents", response_model=list[AgentOut])
async def get_agents(
    distributorId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(_authenticated),
) -> list[AgentOut]:
    rows = await reference_service.list_agents(session, distributorId)
    return [AgentOut.model_validate(r) for r in rows]


@router.get("/reference/vehicles", response_model=list[VehicleOut])
async def get_vehicles(
    distributorId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(_authenticated),
) -> list[VehicleOut]:
    rows = await reference_service.list_vehicles(session, distributorId)
    return [VehicleOut.model_validate(r) for r in rows]


@router.get("/reference/drugs", response_model=list[DrugOut])
async def get_drugs(
    session: AsyncSession = Depends(get_db), _user: User = Depends(_authenticated)
) -> list[DrugOut]:
    """Not in ARCHITECTURE.md §8.8's table, but `drugs` is Phase-1-owned
    reference data and later phases (batch registration) will need to read
    it — additive, read-only, no contract to violate."""
    rows = await reference_service.list_drugs(session)
    return [DrugOut.model_validate(r) for r in rows]
