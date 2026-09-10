"""Event — one link in a batch's append-only, hash-chained history.
ARCHITECTURE.md §4.4. `app.services.event_service` is the only module
permitted to write rows here — see that module's docstring. This model
defines persistence shape only, plus the three uniqueness constraints that
are the database-level defense against a duplicated or forked chain
(ARCHITECTURE.md §4.4, "Constraints — these are the teeth").
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Double, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EventType

_event_type_enum = Enum(EventType, name="event_type_enum", values_callable=lambda e: [m.value for m in e])

GENESIS_HASH = "0" * 64


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("batch_id", "sequence", name="uq_events_batch_sequence"),
        UniqueConstraint("hash", name="uq_events_hash"),
        UniqueConstraint("batch_id", "prev_hash", name="uq_events_batch_prev_hash"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[EventType] = mapped_column(_event_type_enum, nullable=False)

    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_name: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gps_lat: Mapped[float | None] = mapped_column(Double)
    gps_lng: Mapped[float | None] = mapped_column(Double)
    photo_hash: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer_key_id: Mapped[str] = mapped_column(Text, nullable=False)
