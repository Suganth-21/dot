"""Batch — the pharmaceutical unit being tracked. ARCHITECTURE.md §4.3.
Persistence shape only; every rule (status derivation, ownership, fraud
checks) lives in `app.services.batch_service` (CLAUDE.md rule 7).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import BatchStatus, DrugCategory, HolderType

_category_enum = Enum(DrugCategory, name="category_enum", values_callable=lambda e: [m.value for m in e])
_batch_status_enum = Enum(BatchStatus, name="batch_status_enum", values_callable=lambda e: [m.value for m in e])
_holder_enum = Enum(HolderType, name="holder_enum", values_callable=lambda e: [m.value for m in e])


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint("initial_quantity > 0", name="ck_batches_initial_quantity_positive"),
        CheckConstraint("quantity >= 0", name="ck_batches_quantity_non_negative"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    drug_key: Mapped[str] = mapped_column(ForeignKey("drugs.key"), nullable=False)
    drug_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DrugCategory] = mapped_column(_category_enum, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    manufacturer_id: Mapped[str] = mapped_column(ForeignKey("manufacturers.id"), nullable=False, index=True)
    manufacturer_name: Mapped[str] = mapped_column(Text, nullable=False)
    pharmacy_id: Mapped[str | None] = mapped_column(ForeignKey("pharmacies.id"), index=True)
    distributor_id: Mapped[str | None] = mapped_column(ForeignKey("distributors.id"), index=True)

    mfg_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    initial_quantity: Mapped[int] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)

    status: Mapped[BatchStatus] = mapped_column(_batch_status_enum, nullable=False, index=True)

    holder_type: Mapped[HolderType | None] = mapped_column(_holder_enum)
    holder_id: Mapped[str | None] = mapped_column(Text)
    holder_name: Mapped[str | None] = mapped_column(Text)

    scheduled_facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"))
    scheduled_facility_date: Mapped[date | None] = mapped_column()

    destroyed: Mapped[bool] = mapped_column(nullable=False, default=False)
    destroyed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cert_id: Mapped[str | None] = mapped_column(Text, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
