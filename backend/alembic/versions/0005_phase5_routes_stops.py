"""Phase 5 — pickups, routes, and the agent app.

Adds: routes, route_stops. Also adds the foreign key on returns.route_id
that Phase 4 could not add (routes didn't exist yet — see
ARCHITECTURE.md §4.5 / BUILDPHASES.md Phase 4 notes). See ARCHITECTURE.md
§4.6, §5.3 and BUILDPHASES.md Phase 5.

Revision ID: 0005_phase5_routes
Revises: 0004_phase4_returns
Create Date: 2026-09-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_phase5_routes"
down_revision = "0004_phase4_returns"
branch_labels = None
depends_on = None

_route_status_enum = postgresql.ENUM("planned", "active", "completed", name="route_status_enum")
_stop_status_enum = postgresql.ENUM("PENDING", "CURRENT", "ARRIVED", "DONE", name="stop_status_enum")


def upgrade() -> None:
    bind = op.get_bind()

    _route_status_enum.create(bind, checkfirst=True)
    _stop_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "routes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("agent_id", sa.Text(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=True),
        sa.Column("vehicle_id", sa.Text(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("vehicle_reg", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("planned", "active", "completed", name="route_status_enum", create_type=False),
            nullable=False, server_default="planned",
        ),
        sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("path", postgresql.JSONB(), nullable=False),
        sa.Column("seg_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seg_t", sa.Double(), nullable=False, server_default="0"),
        sa.Column("pos_lat", sa.Double(), nullable=True),
        sa.Column("pos_lng", sa.Double(), nullable=True),
        sa.Column("eta_min", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_routes_distributor_id", "routes", ["distributor_id"])
    op.create_index("ix_routes_agent_id", "routes", ["agent_id"])

    op.create_table(
        "route_stops",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("route_id", sa.Text(), sa.ForeignKey("routes.id"), nullable=False),
        sa.Column("return_id", sa.Text(), sa.ForeignKey("returns.id"), nullable=True),
        sa.Column("pharmacy_id", sa.Text(), sa.ForeignKey("pharmacies.id"), nullable=False),
        sa.Column("pharmacy_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("stop_order", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("PENDING", "CURRENT", "ARRIVED", "DONE", name="stop_status_enum", create_type=False),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("expected_batches", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("counted", sa.Integer(), nullable=True),
        sa.UniqueConstraint("route_id", "stop_order", name="uq_route_stops_route_order"),
    )
    op.create_index("ix_route_stops_route_id", "route_stops", ["route_id"])

    # Phase 4's `returns.route_id` had no FK because `routes` didn't exist
    # yet — add it now that the target table does.
    op.create_foreign_key(
        "fk_returns_route_id", "returns", "routes", ["route_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_returns_route_id", "returns", type_="foreignkey")
    op.drop_table("route_stops")
    op.drop_table("routes")

    bind = op.get_bind()
    _stop_status_enum.drop(bind, checkfirst=True)
    _route_status_enum.drop(bind, checkfirst=True)
