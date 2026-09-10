"""Phase 3 — fraud engine, alerts, Patient Shield.

Adds: alerts, patient_reports. See ARCHITECTURE.md §4.7, §4.9 and
BUILDPHASES.md Phase 3.

Revision ID: 0003_phase3_fraud_alerts
Revises: 0002_phase2_batches_events_sales
Create Date: 2026-09-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_phase3_fraud_alerts"
down_revision = "0002_phase2_batches_events_sales"
branch_labels = None
depends_on = None

_alert_type_enum = postgresql.ENUM(
    "REENTRY", "QUANTITY_MISMATCH", "CERT_MISMATCH", "PATIENT_REPORT", "QUANTITY_CAP",
    name="alert_type_enum",
)
_alert_severity_enum = postgresql.ENUM("critical", "high", "medium", "low", name="alert_severity_enum")
_alert_status_enum = postgresql.ENUM("OPEN", "INVESTIGATING", "ESCALATED", "CLOSED", name="alert_status_enum")


def upgrade() -> None:
    bind = op.get_bind()

    _alert_type_enum.create(bind, checkfirst=True)
    _alert_severity_enum.create(bind, checkfirst=True)
    _alert_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "REENTRY", "QUANTITY_MISMATCH", "CERT_MISMATCH", "PATIENT_REPORT", "QUANTITY_CAP",
                name="alert_type_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM("critical", "high", "medium", "low", name="alert_severity_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "OPEN", "INVESTIGATING", "ESCALATED", "CLOSED", name="alert_status_enum", create_type=False,
            ),
            nullable=False, server_default="OPEN",
        ),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("batches.id"), nullable=True),
        sa.Column("drug_name", sa.Text(), nullable=True),
        sa.Column(
            "drug_category",
            postgresql.ENUM("oncology", "antibiotics", "cardiovascular", "other",
                             name="category_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column("entity_name", sa.Text(), nullable=True),
        sa.Column("district", sa.Text(), nullable=True),
        sa.Column("manufacturer_id", sa.Text(), sa.ForeignKey("manufacturers.id"), nullable=True),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("audit_trail", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_type", "alerts", ["type"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_district", "alerts", ["district"])
    op.create_index("ix_alerts_manufacturer_id", "alerts", ["manufacturer_id"])
    op.create_index("ix_alerts_ts", "alerts", ["ts"])

    op.create_table(
        "patient_reports",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("batches.id"), nullable=True),
        sa.Column("lat", sa.Double(), nullable=True),
        sa.Column("lng", sa.Double(), nullable=True),
        sa.Column("district", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_hash", sa.Text(), nullable=True),
        sa.Column("pharmacy_name", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.Text(), nullable=True),
    )
    op.create_index("ix_patient_reports_batch_id", "patient_reports", ["batch_id"])
    op.create_index("ix_patient_reports_ts", "patient_reports", ["ts"])


def downgrade() -> None:
    op.drop_table("patient_reports")
    op.drop_table("alerts")

    bind = op.get_bind()
    _alert_status_enum.drop(bind, checkfirst=True)
    _alert_severity_enum.drop(bind, checkfirst=True)
    _alert_type_enum.drop(bind, checkfirst=True)
