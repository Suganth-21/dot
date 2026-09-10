"""Alert — a fraud/compliance signal raised for the regulator. ARCHITECTURE.md
§4.7. Persistence shape only; every rule that decides *when* to raise one
lives in `app.services.fraud_service`, and ordering/status-transition logic
lives in `app.services.alert_service` (CLAUDE.md rule 7).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AlertStatus, AlertType, AlertSeverity, DrugCategory

_alert_type_enum = Enum(AlertType, name="alert_type_enum", values_callable=lambda e: [m.value for m in e])
_alert_severity_enum = Enum(
    AlertSeverity, name="alert_severity_enum", values_callable=lambda e: [m.value for m in e]
)
_alert_status_enum = Enum(
    AlertStatus, name="alert_status_enum", values_callable=lambda e: [m.value for m in e]
)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[AlertType] = mapped_column(_alert_type_enum, nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(_alert_severity_enum, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        _alert_status_enum, nullable=False, default=AlertStatus.OPEN, index=True
    )

    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"))
    drug_name: Mapped[str | None] = mapped_column(Text)
    # DrugCategory reused rather than a duplicate enum — the value set is
    # identical (ARCHITECTURE.md §4.7's alert.drugCategory is the batch's
    # own category, denormalised for the priority sort in §4.7).
    drug_category: Mapped[DrugCategory | None] = mapped_column(
        Enum(DrugCategory, name="category_enum", create_type=False, values_callable=lambda e: [m.value for m in e])
    )

    entity_id: Mapped[str | None] = mapped_column(Text)
    entity_name: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text, index=True)
    manufacturer_id: Mapped[str | None] = mapped_column(ForeignKey("manufacturers.id"), index=True)

    rule: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    audit_trail: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
