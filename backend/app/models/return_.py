"""Return — a pharmacy's reverse-logistics request for an expired/damaged/
recalled batch. ARCHITECTURE.md §4.5. Persistence shape only; every rule
(ownership, the dispute gate, state-machine validation) lives in
`app.services.return_service` (CLAUDE.md rule 7).

Three independent quantity columns is the whole point (ARCHITECTURE.md
§4.5): `quantity_claimed`, `picked_quantity` and `quantity_received` are
three separate attestations by three different parties. Never collapse
them into one column and never auto-copy one into another.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DrugCategory, ReturnReason, ReturnStatus

_reason_enum = Enum(ReturnReason, name="reason_enum", values_callable=lambda e: [m.value for m in e])
_return_status_enum = Enum(
    ReturnStatus, name="return_status_enum", values_callable=lambda e: [m.value for m in e]
)


class Return(Base):
    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint("quantity_claimed > 0", name="ck_returns_quantity_claimed_positive"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    pharmacy_id: Mapped[str] = mapped_column(ForeignKey("pharmacies.id"), nullable=False, index=True)
    distributor_id: Mapped[str] = mapped_column(ForeignKey("distributors.id"), nullable=False, index=True)

    drug_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DrugCategory] = mapped_column(
        Enum(DrugCategory, name="category_enum", create_type=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    quantity_claimed: Mapped[int] = mapped_column(nullable=False)
    picked_quantity: Mapped[int | None] = mapped_column()
    quantity_received: Mapped[int | None] = mapped_column()

    reason: Mapped[ReturnReason] = mapped_column(_reason_enum, nullable=False)
    status: Mapped[ReturnStatus] = mapped_column(_return_status_enum, nullable=False, index=True)

    photo_hash: Mapped[str | None] = mapped_column(Text)
    distributor_photo_hash: Mapped[str | None] = mapped_column(Text)
    distributor_notes: Mapped[str | None] = mapped_column(Text)
    dispute_notes: Mapped[str | None] = mapped_column(Text)
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    # No FK yet — `routes` doesn't exist until Phase 5's migration creates
    # it. Plain nullable text until then; Phase 5 adds the constraint once
    # the target table exists.
    route_id: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
