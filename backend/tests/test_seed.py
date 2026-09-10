"""Seed data faithfulness and determinism — BUILDPHASES.md "Seed data spec".
Exercises the real reset path against the real database, not fixtures."""
import pytest
from sqlalchemy import func, select

from app.core.rbac import Role
from app.models.drug import Drug
from app.models.entity import Agent, Distributor, Facility, Manufacturer, Pharmacy, Regulator, Vehicle
from app.models.user import User
from app.seed.reset import reset_demo_data


async def _count(session, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_expected_entity_counts(seeded, db_session):
    assert await _count(db_session, Pharmacy) == 10
    assert await _count(db_session, Distributor) == 3
    assert await _count(db_session, Agent) == 7
    assert await _count(db_session, Vehicle) == 5
    assert await _count(db_session, Manufacturer) == 4
    assert await _count(db_session, Facility) == 3
    assert await _count(db_session, Regulator) == 1
    assert await _count(db_session, Drug) == 9
    assert await _count(db_session, User) == 5


@pytest.mark.asyncio
async def test_critical_seeded_identities(seeded, db_session):
    dist_1 = await db_session.get(Distributor, "dist_1")
    assert dist_1.name == "Sunrise Pharma Distributors"

    agent_1 = await db_session.get(Agent, "agent_1")
    assert agent_1.name == "Ravi Kumar"
    assert agent_1.distributor_id == "dist_1"

    mfr_1 = await db_session.get(Manufacturer, "mfr_1")
    assert mfr_1.name == "Cipla Ltd."

    reg_1 = await db_session.get(Regulator, "reg_1")
    assert reg_1.name == "CDSCO — Tamil Nadu"
    assert reg_1.officer_name == "R. Menon"

    ph_1 = await db_session.get(Pharmacy, "ph_1")
    assert ph_1.name == "Apollo Pharmacy — T. Nagar"


@pytest.mark.asyncio
async def test_demo_users_exist_with_correct_roles_and_entities(seeded, db_session):
    result = await db_session.execute(select(User))
    users = {u.role: u for u in result.scalars().all()}

    assert set(users.keys()) == {
        Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR
    }
    assert users[Role.RETAILER].entity_id == "ph_1"
    assert users[Role.DISTRIBUTOR].entity_id == "dist_1"
    assert users[Role.PICKUP_AGENT].entity_id == "agent_1"
    assert users[Role.MANUFACTURER].entity_id == "mfr_1"
    assert users[Role.REGULATOR].entity_id == "reg_1"
    for user in users.values():
        assert user.is_demo is True
        assert user.password_hash.startswith("$argon2")
        assert user.signing_public_key
        assert user.signing_private_key


@pytest.mark.asyncio
async def test_repeated_reset_produces_logically_equivalent_data(seeded, db_session):
    """Determinism requirement: the *logical* shape must be identical after
    a second reset — same ids, names, roles, relationships — even though
    the Argon2 salt and Ed25519 keypair differ every run by design (see
    app/seed/reset.py docstring)."""

    async def snapshot():
        pharmacies = await db_session.execute(select(Pharmacy.id, Pharmacy.name, Pharmacy.license_no))
        agents = await db_session.execute(select(Agent.id, Agent.distributor_id, Agent.name))
        users = await db_session.execute(select(User.id, User.email, User.role, User.entity_id, User.is_demo))
        return (
            sorted(pharmacies.all()),
            sorted(agents.all()),
            sorted(users.all()),
        )

    before = await snapshot()
    await reset_demo_data(db_session)
    after = await snapshot()

    assert before == after
