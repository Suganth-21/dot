"""Database access for reference/entity data — pharmacies, distributors,
manufacturers, facilities, regulators, agents, vehicles, drugs. Plain reads;
no business decisions (ARCHITECTURE.md §2, §8.8).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug import Drug
from app.models.entity import Agent, Distributor, Facility, Manufacturer, Pharmacy, Regulator, Vehicle


async def list_pharmacies(session: AsyncSession) -> list[Pharmacy]:
    result = await session.execute(select(Pharmacy).order_by(Pharmacy.id))
    return list(result.scalars().all())


async def search_pharmacies(session: AsyncSession, term: str, limit: int = 12) -> list[Pharmacy]:
    like = f"%{term.lower()}%"
    result = await session.execute(
        select(Pharmacy).where(func.lower(Pharmacy.name).like(like)).order_by(Pharmacy.id).limit(limit)
    )
    return list(result.scalars().all())


async def get_pharmacy(session: AsyncSession, pharmacy_id: str) -> Pharmacy | None:
    return await session.get(Pharmacy, pharmacy_id)


async def list_distributors(session: AsyncSession) -> list[Distributor]:
    result = await session.execute(select(Distributor).order_by(Distributor.id))
    return list(result.scalars().all())


async def list_manufacturers(session: AsyncSession) -> list[Manufacturer]:
    result = await session.execute(select(Manufacturer).order_by(Manufacturer.id))
    return list(result.scalars().all())


async def list_facilities(session: AsyncSession) -> list[Facility]:
    result = await session.execute(select(Facility).order_by(Facility.id))
    return list(result.scalars().all())


async def get_distributor(session: AsyncSession, distributor_id: str) -> Distributor | None:
    return await session.get(Distributor, distributor_id)


async def get_manufacturer(session: AsyncSession, manufacturer_id: str) -> Manufacturer | None:
    return await session.get(Manufacturer, manufacturer_id)


async def get_facility(session: AsyncSession, facility_id: str) -> Facility | None:
    return await session.get(Facility, facility_id)


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return await session.get(Agent, agent_id)


async def get_regulator(session: AsyncSession, regulator_id: str) -> Regulator | None:
    return await session.get(Regulator, regulator_id)


async def list_agents(session: AsyncSession, distributor_id: str | None) -> list[Agent]:
    stmt = select(Agent).order_by(Agent.id)
    if distributor_id:
        stmt = stmt.where(Agent.distributor_id == distributor_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_vehicle(session: AsyncSession, vehicle_id: str) -> Vehicle | None:
    return await session.get(Vehicle, vehicle_id)


async def list_vehicles(session: AsyncSession, distributor_id: str | None) -> list[Vehicle]:
    stmt = select(Vehicle).order_by(Vehicle.id)
    if distributor_id:
        stmt = stmt.where(Vehicle.distributor_id == distributor_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_drugs(session: AsyncSession) -> list[Drug]:
    result = await session.execute(select(Drug).order_by(Drug.key))
    return list(result.scalars().all())


async def delete_all(session: AsyncSession) -> None:
    """Phase-1-owned truncate for demo reset — see app.seed.reset. Order
    respects FK dependencies (agents/vehicles reference distributors)."""
    await session.execute(Agent.__table__.delete())
    await session.execute(Vehicle.__table__.delete())
    await session.execute(Pharmacy.__table__.delete())
    await session.execute(Distributor.__table__.delete())
    await session.execute(Manufacturer.__table__.delete())
    await session.execute(Facility.__table__.delete())
    await session.execute(Regulator.__table__.delete())
    await session.execute(Drug.__table__.delete())
