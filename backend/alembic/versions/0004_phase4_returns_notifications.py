"""Phase 4 — return flow and the dispute gate.

Adds: returns, notifications. See ARCHITECTURE.md §4.5, §4.8 and
BUILDPHASES.md Phase 4.

Revision ID: 0004_phase4_returns
Revises: 0003_phase3_fraud_alerts
Create Date: 2026-09-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_phase4_returns"
down_revision = "0003_phase3_fraud_alerts"
branch_labels = None
depends_on = None

_reason_enum = postgresql.ENUM("EXPIRED", "DAMAGED", "RECALL", name="reason_enum")
_return_status_enum = postgresql.ENUM(
    "REQUESTED", "SCHEDULED", "ARRIVED", "PICKED_UP", "CONFIRMED", "DISPUTED", "FORWARDED",
    name="return_status_enum",
)
_kind_enum = postgresql.ENUM("info", "warning", "danger", "success", name="kind_enum")


def upgrade() -> None:
    bind = op.get_bind()

    _reason_enum.create(bind, checkfirst=True)
    _return_status_enum.create(bind, checkfirst=True)
    _kind_enum.create(bind, checkfirst=True)

    op.create_table(
        "returns",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("pharmacy_id", sa.Text(), sa.ForeignKey("pharmacies.id"), nullable=False),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("drug_name", sa.Text(), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM("oncology", "antibiotics", "cardiovascular", "other",
                             name="category_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("quantity_claimed", sa.Integer(), nullable=False),
        sa.Column("picked_quantity", sa.Integer(), nullable=True),
        sa.Column("quantity_received", sa.Integer(), nullable=True),
        sa.Column(
            "reason",
            postgresql.ENUM("EXPIRED", "DAMAGED", "RECALL", name="reason_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "REQUESTED", "SCHEDULED", "ARRIVED", "PICKED_UP", "CONFIRMED", "DISPUTED", "FORWARDED",
                name="return_status_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("photo_hash", sa.Text(), nullable=True),
        sa.Column("distributor_photo_hash", sa.Text(), nullable=True),
        sa.Column("distributor_notes", sa.Text(), nullable=True),
        sa.Column("dispute_notes", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        # No FK — `routes` doesn't exist until Phase 5. Plain nullable text;
        # Phase 5's migration adds the constraint once the target exists.
        sa.Column("route_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_claimed > 0", name="ck_returns_quantity_claimed_positive"),
    )
    op.create_index("ix_returns_batch_id", "returns", ["batch_id"])
    op.create_index("ix_returns_pharmacy_id", "returns", ["pharmacy_id"])
    op.create_index("ix_returns_distributor_id", "returns", ["distributor_id"])
    op.create_index("ix_returns_status", "returns", ["status"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(
                "RETAILER", "DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER", "REGULATOR",
                name="role_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("info", "warning", "danger", "success", name="kind_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_role", "notifications", ["role"])
    op.create_index("ix_notifications_ts", "notifications", ["ts"])
    op.create_index("ix_notifications_role_user_ts", "notifications", ["role", "user_id", "ts"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("returns")

    bind = op.get_bind()
    _kind_enum.drop(bind, checkfirst=True)
    _return_status_enum.drop(bind, checkfirst=True)
    _reason_enum.drop(bind, checkfirst=True)
