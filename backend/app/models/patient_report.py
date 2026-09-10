"""PatientReport — a public suspicious-medicine report filed through Patient
Shield (`POST /api/public/report`). ARCHITECTURE.md §4.9. Persistence shape
only; `app.services.verify_service` owns the rule that turns one of these
into a `PATIENT_REPORT` alert.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PatientReport(Base):
    __tablename__ = "patient_reports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Nullable — a patient may report with no scannable code (ARCHITECTURE.md §4.9).
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"))
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    district: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    photo_hash: Mapped[str | None] = mapped_column(Text)
    pharmacy_name: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Hashed, never raw — ARCHITECTURE.md §4.9 / §6.6's open question #9:
    # abuse-pattern analysis without storing an identifying IP address.
    ip_hash: Mapped[str | None] = mapped_column(Text)
