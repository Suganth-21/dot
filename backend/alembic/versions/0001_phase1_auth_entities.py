"""Phase 1 — auth, entities, reference data.

Adds: users, refresh_tokens, pharmacies, distributors, manufacturers,
facilities, regulators, agents, vehicles, drugs. See ARCHITECTURE.md §4.1,
§4.2 and BUILDPHASES.md Phase 1.

Revision ID: 0001_phase1_auth_entities
Revises:
Create Date: 2026-09-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_phase1_auth_entities"
down_revision = None
branch_labels = None
depends_on = None

_role_enum = postgresql.ENUM(
    "RETAILER", "DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER", "REGULATOR",
    name="role_enum",
)
_agent_status_enum = postgresql.ENUM("idle", "active", "offline", name="agent_status_enum")
_category_enum = postgresql.ENUM(
    "oncology", "antibiotics", "cardiovascular", "other", name="category_enum"
)


def upgrade() -> None:
    bind = op.get_bind()

    # CITEXT gives case-insensitive unique emails at the database level
    # rather than relying on every call site to .lower() first.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    _role_enum.create(bind, checkfirst=True)
    _agent_status_enum.create(bind, checkfirst=True)
    _category_enum.create(bind, checkfirst=True)

    op.create_table(
        "distributors",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("license_no", sa.Text(), nullable=False, unique=True),
    )

    op.create_table(
        "manufacturers",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("license_no", sa.Text(), nullable=False, unique=True),
    )

    op.create_table(
        "facilities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("license_no", sa.Text(), nullable=False, unique=True),
    )

    op.create_table(
        "regulators",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("officer_name", sa.Text(), nullable=False),
        sa.Column("officer_designation", sa.Text(), nullable=False),
        sa.Column("officer_id", sa.Text(), nullable=False),
    )

    op.create_table(
        "pharmacies",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lng", sa.Double(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("license_no", sa.Text(), nullable=False, unique=True),
        sa.Column("phone", sa.Text(), nullable=True),
    )

    op.create_table(
        "drugs",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM("oncology", "antibiotics", "cardiovascular", "other",
                             name="category_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("idle", "active", "offline", name="agent_status_enum", create_type=False),
            nullable=False,
            server_default="idle",
        ),
    )
    op.create_index("ix_agents_distributor_id", "agents", ["distributor_id"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("reg_no", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "status",
            postgresql.ENUM("idle", "active", "offline", name="agent_status_enum", create_type=False),
            nullable=False,
            server_default="idle",
        ),
        sa.Column("lat", sa.Double(), nullable=True),
        sa.Column("lng", sa.Double(), nullable=True),
    )
    op.create_index("ix_vehicles_distributor_id", "vehicles", ["distributor_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("RETAILER", "DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER", "REGULATOR",
                             name="role_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signing_public_key", sa.Text(), nullable=False),
        sa.Column("signing_private_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_entity_id", "users", ["entity_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("family_id", sa.Text(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("replaced_by_id", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("vehicles")
    op.drop_table("agents")
    op.drop_table("drugs")
    op.drop_table("pharmacies")
    op.drop_table("regulators")
    op.drop_table("facilities")
    op.drop_table("manufacturers")
    op.drop_table("distributors")

    bind = op.get_bind()
    _category_enum.drop(bind, checkfirst=True)
    _agent_status_enum.drop(bind, checkfirst=True)
    _role_enum.drop(bind, checkfirst=True)
