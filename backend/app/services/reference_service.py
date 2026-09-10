"""Reference/entity reads — pharmacies, distributors, manufacturers,
facilities, regulators, agents, vehicles, drugs. No rules to enforce here;
the only reason this is a service and not a router calling the repository
directly is CLAUDE.md rule 7 ("routers never touch the database").
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.drug import Drug
from app.models.entity import (
    Agent,
    Distributor,
    Facility,
    Manufacturer,
    Pharmacy,
    Regulator,
    Vehicle,
)
from app.repositories import reference_repo


async def list_pharmacies(session: AsyncSession) -> list[Pharmacy]:
    return await reference_repo.list_pharmacies(session)


async def get_pharmacy(session: AsyncSession, pharmacy_id: str) -> Pharmacy:
    pharmacy = await reference_repo.get_pharmacy(session, pharmacy_id)
    if pharmacy is None:
        raise NotFound("Pharmacy not found.", code="PHARMACY_NOT_FOUND")
    return pharmacy


async def list_distributors(session: AsyncSession) -> list[Distributor]:
    return await reference_repo.list_distributors(session)


async def list_manufacturers(session: AsyncSession) -> list[Manufacturer]:
    return await reference_repo.list_manufacturers(session)


async def list_facilities(session: AsyncSession) -> list[Facility]:
    return await reference_repo.list_facilities(session)


async def get_regulator_profile(session: AsyncSession, regulator_id: str) -> Regulator:
    regulator = await reference_repo.get_regulator(session, regulator_id)
    if regulator is None:
        raise NotFound("Regulator not found.", code="REGULATOR_NOT_FOUND")
    return regulator


async def list_agents(session: AsyncSession, distributor_id: str | None) -> list[Agent]:
    return await reference_repo.list_agents(session, distributor_id)


async def list_vehicles(session: AsyncSession, distributor_id: str | None) -> list[Vehicle]:
    return await reference_repo.list_vehicles(session, distributor_id)


async def list_drugs(session: AsyncSession) -> list[Drug]:
    return await reference_repo.list_drugs(session)
