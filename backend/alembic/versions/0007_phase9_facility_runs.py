"""Phase 9 — facility runs (distributor -> destruction facility, the
second, previously unmodeled leg of the reverse chain; pharmacy ->
distributor already existed as Phase 5's routes/route_stops).

Adds: facility_runs. Adds EventType.FACILITY_ARRIVED to event_type_enum.

Revision ID: 0007_phase9_facility_runs
Revises: 0006_phase8_reports
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_phase9_facility_runs"
down_revision = "0006_phase8_reports"
branch_labels = None
depends_on = None

_route_status_enum = postgresql.ENUM("planned", "active", "completed", name="route_status_enum", create_type=False)


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction (the new value just
    # can't be *used* in that same transaction — irrelevant here, it's only
    # ever used by later, separate requests).
    op.execute("ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'FACILITY_ARRIVED'")

    op.create_table(
        "facility_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("agent_id", sa.Text(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=True),
        sa.Column("vehicle_id", sa.Text(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("vehicle_reg", sa.Text(), nullable=True),
        sa.Column("facility_id", sa.Text(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("facility_name", sa.Text(), nullable=True),
        sa.Column("batch_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", _route_status_enum, nullable=False, server_default="planned"),
        sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("path", postgresql.JSONB(), nullable=False),
        sa.Column("seg_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seg_t", sa.Double(), nullable=False, server_default="0"),
        sa.Column("pos_lat", sa.Double(), nullable=True),
        sa.Column("pos_lng", sa.Double(), nullable=True),
        sa.Column("eta_min", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_facility_runs_distributor_id", "facility_runs", ["distributor_id"])
    op.create_index("ix_facility_runs_agent_id", "facility_runs", ["agent_id"])
    op.create_index("ix_facility_runs_facility_id", "facility_runs", ["facility_id"])


def downgrade() -> None:
    op.drop_table("facility_runs")
    # Postgres has no ALTER TYPE ... DROP VALUE — the enum value addition
    # above is intentionally one-way, same precedent as any other additive
    # enum migration.
