"""FacilityRun — a distributor's delivery of already-scheduled, confirmed
batches to a manufacturer's destruction facility. The second, previously
unmodeled leg of the reverse chain: pharmacy -> distributor (Route/
RouteStop, app.models.route) is the pickup leg; this is distributor ->
facility, the drop-off leg. Persistence shape only; every rule (which
batches are eligible, dispatch, delivery) lives in
`app.services.facility_run_service` (CLAUDE.md rule 7).

Unlike a pickup Route, a facility run always has exactly one destination
(the facility) carrying however many batches were loaded onto it, so there
is no separate "stops" table here — `batch_ids` is the manifest.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RouteStatus

# Reuses the same native `route_status_enum` Postgres type as app.models.route
# (planned/active/completed is exactly the lifecycle this needs too) —
# `create_type=False` at the migration layer keeps this from trying to
# redefine a type that already exists.
_run_status_enum = Enum(RouteStatus, name="route_status_enum", values_callable=lambda e: [m.value for m in e])


class FacilityRun(Base):
    __tablename__ = "facility_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    distributor_id: Mapped[str] = mapped_column(ForeignKey("distributors.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_name: Mapped[str | None] = mapped_column(Text)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    vehicle_reg: Mapped[str | None] = mapped_column(Text)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    facility_name: Mapped[str | None] = mapped_column(Text)

    batch_ids: Mapped[list] = mapped_column(JSONB, nullable=False)

    # True the instant `deliver_run` does its real work (event, holder
    # flip, notifications) — distinct from `status`/`running`, which stay
    # active/true through the drive-home leg queued at that same moment.
    # Without this, "already delivered, now just driving home" and "still
    # en route to the facility, not yet delivered" would both read as
    # running=True/status=active and be impossible to tell apart client-side.
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[RouteStatus] = mapped_column(_run_status_enum, nullable=False, default=RouteStatus.planned)
    running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    path: Mapped[list] = mapped_column(JSONB, nullable=False)
    seg_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seg_t: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    pos_lat: Mapped[float | None] = mapped_column(Double)
    pos_lng: Mapped[float | None] = mapped_column(Double)
    eta_min: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
