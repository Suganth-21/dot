"""Route and RouteStop — a distributor's pickup run. ARCHITECTURE.md §4.6.
Persistence shape only; route creation (nearest-neighbour ordering),
dispatch, and stop transitions live in `app.services.pickup_service`
(CLAUDE.md rule 7).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RouteStatus, StopStatus

_route_status_enum = Enum(RouteStatus, name="route_status_enum", values_callable=lambda e: [m.value for m in e])
_stop_status_enum = Enum(StopStatus, name="stop_status_enum", values_callable=lambda e: [m.value for m in e])


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    distributor_id: Mapped[str] = mapped_column(ForeignKey("distributors.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_name: Mapped[str | None] = mapped_column(Text)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    vehicle_reg: Mapped[str | None] = mapped_column(Text)

    status: Mapped[RouteStatus] = mapped_column(_route_status_enum, nullable=False, default=RouteStatus.planned)
    running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    path: Mapped[list] = mapped_column(JSONB, nullable=False)
    seg_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seg_t: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    pos_lat: Mapped[float | None] = mapped_column(Double)
    pos_lng: Mapped[float | None] = mapped_column(Double)
    eta_min: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (UniqueConstraint("route_id", "stop_order", name="uq_route_stops_route_order"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), nullable=False, index=True)
    return_id: Mapped[str | None] = mapped_column(ForeignKey("returns.id"))
    pharmacy_id: Mapped[str] = mapped_column(ForeignKey("pharmacies.id"), nullable=False)
    pharmacy_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lng: Mapped[float] = mapped_column(Double, nullable=False)
    # `order` is a reserved word in some SQL dialects and shadows a common
    # builtin name in Python — mapped to the same wire meaning ARCHITECTURE.md
    # §4.6 calls `order` (1-based position), just spelled `stop_order` here.
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StopStatus] = mapped_column(_stop_status_enum, nullable=False, default=StopStatus.PENDING)
    expected_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    counted: Mapped[int | None] = mapped_column(Integer)
