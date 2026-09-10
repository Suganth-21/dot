"""Sale — a point-of-sale decrement against a batch. ARCHITECTURE.md §4.9.
Always written in the same transaction as the batch quantity update and the
SALE event it corresponds to (`app.services.batch_service.record_sale`).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    pharmacy_id: Mapped[str] = mapped_column(ForeignKey("pharmacies.id"), nullable=False, index=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
