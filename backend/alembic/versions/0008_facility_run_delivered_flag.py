"""facility_runs.delivered — an explicit flag distinguishing "already
delivered, now driving home" from "still en route to the facility" now
that both states share running=True/status=active during the drive-home
leg (facility_run_service.deliver_run no longer completes the run
instantly). See gps_simulator.py's module docstring for the drive-home
design this supports.

Revision ID: 0008_facility_run_delivered
Revises: 0007_phase9_facility_runs
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_facility_run_delivered"
down_revision = "0007_phase9_facility_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "facility_runs",
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("facility_runs", "delivered")
