"""Phase 8 — analytics, entities, notifications, reports.

Adds: reports. Entities and analytics are computed on existing tables (no
new schema); notification reads are Phase 8 additions to the Phase 4
`notifications` table (no schema change there either). See
ARCHITECTURE.md §4.9, §8.9, §8.10, §8.11 and BUILDPHASES.md Phase 8.

Revision ID: 0006_phase8_reports
Revises: 0005_phase5_routes
Create Date: 2026-09-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_phase8_reports"
down_revision = "0005_phase5_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("size", sa.Text(), nullable=True),
        # Real PDF generation is Phase 9 — metadata only until then
        # (ARCHITECTURE.md §4.9, BUILDPHASES.md cut list #2).
        sa.Column("file_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("reports")
