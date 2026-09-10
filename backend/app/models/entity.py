"""Entity tables: pharmacy, distributor, manufacturer, facility, regulator,
agent, vehicle. Pure persistence shape — see ARCHITECTURE.md §4.2. No
business logic lives here (CLAUDE.md rule 7).
"""
from __future__ import annotations

from sqlalchemy import Double, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AgentStatus

_agent_status_enum = Enum(
    AgentStatus, name="agent_status_enum", values_callable=lambda e: [m.value for m in e]
)


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lng: Mapped[float] = mapped_column(Double, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    license_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(Text)
    # Phase 2 addition — see ARCHITECTURE.md §7.5 "Each entity gets an
    # Ed25519 keypair at seed time" and the Phase 2 implementation notes:
    # event actors are entities (a pharmacy, a distributor, ...), not login
    # users, so the signing key that authors an event lives here rather
    # than on `users`. Nullable at the database level (no backfill
    # migration for pre-Phase-2 rows) — every seed path populates it.
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    signing_private_key: Mapped[str | None] = mapped_column(Text)


class Distributor(Base):
    __tablename__ = "distributors"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lng: Mapped[float] = mapped_column(Double, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    license_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    signing_private_key: Mapped[str | None] = mapped_column(Text)

    agents: Mapped[list[Agent]] = relationship(back_populates="distributor")
    vehicles: Mapped[list[Vehicle]] = relationship(back_populates="distributor")


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lng: Mapped[float] = mapped_column(Double, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    license_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    signing_private_key: Mapped[str | None] = mapped_column(Text)


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lng: Mapped[float] = mapped_column(Double, nullable=False)
    license_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class Regulator(Base):
    """New in Phase 1 — ARCHITECTURE.md §4.2. Backs `reg_1` and moves the
    officer profile that `pages/regulator.jsx` currently hardcodes into
    seeded data (Open question #5, decided)."""

    __tablename__ = "regulators"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    officer_name: Mapped[str] = mapped_column(Text, nullable=False)
    officer_designation: Mapped[str] = mapped_column(Text, nullable=False)
    officer_id: Mapped[str] = mapped_column(Text, nullable=False)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    distributor_id: Mapped[str] = mapped_column(ForeignKey("distributors.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentStatus] = mapped_column(
        _agent_status_enum, nullable=False, default=AgentStatus.idle
    )
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    signing_private_key: Mapped[str | None] = mapped_column(Text)

    distributor: Mapped[Distributor] = relationship(back_populates="agents")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    distributor_id: Mapped[str] = mapped_column(ForeignKey("distributors.id"), nullable=False)
    reg_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[AgentStatus] = mapped_column(
        _agent_status_enum, nullable=False, default=AgentStatus.idle
    )
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)

    distributor: Mapped[Distributor] = relationship(back_populates="vehicles")
