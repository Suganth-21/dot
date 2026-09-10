"""Phase 2 — batches, the hash-chained event log, sales.

Adds: batches, events, sales. Extends pharmacies/distributors/manufacturers/
agents with a signing keypair (see ARCHITECTURE.md §7.5 and the Phase 2
implementation notes — event actors are entities, not login users).

Revision ID: 0002_phase2_batches_events_sales
Revises: 0001_phase1_auth_entities
Create Date: 2026-09-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_phase2_batches_events_sales"
down_revision = "0001_phase1_auth_entities"
branch_labels = None
depends_on = None

_batch_status_enum = postgresql.ENUM(
    "ACTIVE", "EXPIRING_SOON", "EXPIRED", "IN_RETURN", "DESTROYED", name="batch_status_enum"
)
_holder_enum = postgresql.ENUM("PHARMACY", "DISTRIBUTOR", "FACILITY", name="holder_enum")
_event_type_enum = postgresql.ENUM(
    "REGISTERED", "SALE", "RETURN_INITIATED", "PICKUP_ASSIGNED", "AGENT_ARRIVED", "PICKED_UP",
    "DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED", "FORWARDED", "FACILITY_SCHEDULED", "DESTROYED",
    "REENTRY_BLOCKED", name="event_type_enum",
)


def upgrade() -> None:
    bind = op.get_bind()

    _batch_status_enum.create(bind, checkfirst=True)
    _holder_enum.create(bind, checkfirst=True)
    _event_type_enum.create(bind, checkfirst=True)

    # Entities become event actors in Phase 2 — see this file's docstring.
    # Nullable: no backfill migration for pre-existing rows, every seed
    # path (re)populates these going forward.
    for table in ("pharmacies", "distributors", "manufacturers", "agents"):
        op.add_column(table, sa.Column("signing_public_key", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("signing_private_key", sa.Text(), nullable=True))

    op.create_table(
        "batches",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("drug_key", sa.Text(), sa.ForeignKey("drugs.key"), nullable=False),
        sa.Column("drug_name", sa.Text(), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM("oncology", "antibiotics", "cardiovascular", "other",
                             name="category_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("manufacturer_id", sa.Text(), sa.ForeignKey("manufacturers.id"), nullable=False),
        sa.Column("manufacturer_name", sa.Text(), nullable=False),
        sa.Column("pharmacy_id", sa.Text(), sa.ForeignKey("pharmacies.id"), nullable=True),
        sa.Column("distributor_id", sa.Text(), sa.ForeignKey("distributors.id"), nullable=True),
        sa.Column("mfg_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_quantity", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("ACTIVE", "EXPIRING_SOON", "EXPIRED", "IN_RETURN", "DESTROYED",
                             name="batch_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "holder_type",
            postgresql.ENUM("PHARMACY", "DISTRIBUTOR", "FACILITY", name="holder_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("holder_id", sa.Text(), nullable=True),
        sa.Column("holder_name", sa.Text(), nullable=True),
        sa.Column("scheduled_facility_id", sa.Text(), sa.ForeignKey("facilities.id"), nullable=True),
        sa.Column("scheduled_facility_date", sa.Date(), nullable=True),
        sa.Column("destroyed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("destroyed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cert_id", sa.Text(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("initial_quantity > 0", name="ck_batches_initial_quantity_positive"),
        sa.CheckConstraint("quantity >= 0", name="ck_batches_quantity_non_negative"),
    )
    op.create_index("ix_batches_code", "batches", ["code"])
    op.create_index("ix_batches_pharmacy_id", "batches", ["pharmacy_id"])
    op.create_index("ix_batches_manufacturer_id", "batches", ["manufacturer_id"])
    op.create_index("ix_batches_distributor_id", "batches", ["distributor_id"])
    op.create_index("ix_batches_status", "batches", ["status"])
    op.create_index("ix_batches_expiry_date", "batches", ["expiry_date"])
    # Case-insensitive search over drug name (⌘K search, §8.2) without a
    # separate search engine — a functional index is enough at this scale.
    op.execute("CREATE INDEX ix_batches_drug_name_lower ON batches (lower(drug_name))")

    op.create_table(
        "events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "REGISTERED", "SALE", "RETURN_INITIATED", "PICKUP_ASSIGNED", "AGENT_ARRIVED", "PICKED_UP",
                "DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED", "FORWARDED", "FACILITY_SCHEDULED", "DESTROYED",
                "REENTRY_BLOCKED", name="event_type_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_name", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gps_lat", sa.Double(), nullable=True),
        sa.Column("gps_lng", sa.Double(), nullable=True),
        sa.Column("photo_hash", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signer_key_id", sa.Text(), nullable=False),
        # The teeth (ARCHITECTURE.md §4.4): no duplicate sequence position,
        # no duplicate hash, and no forking a second event off one prior
        # event — the database refuses all three at the constraint level,
        # not only in application code.
        sa.UniqueConstraint("batch_id", "sequence", name="uq_events_batch_sequence"),
        sa.UniqueConstraint("hash", name="uq_events_hash"),
        sa.UniqueConstraint("batch_id", "prev_hash", name="uq_events_batch_prev_hash"),
    )
    op.create_index("ix_events_batch_id_sequence", "events", ["batch_id", "sequence"])

    op.create_table(
        "sales",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("pharmacy_id", sa.Text(), sa.ForeignKey("pharmacies.id"), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sales_batch_id", "sales", ["batch_id"])
    op.create_index("ix_sales_pharmacy_id", "sales", ["pharmacy_id"])


def downgrade() -> None:
    op.drop_table("sales")
    op.drop_table("events")
    op.drop_table("batches")

    for table in ("pharmacies", "distributors", "manufacturers", "agents"):
        op.drop_column(table, "signing_private_key")
        op.drop_column(table, "signing_public_key")

    bind = op.get_bind()
    _event_type_enum.drop(bind, checkfirst=True)
    _holder_enum.drop(bind, checkfirst=True)
    _batch_status_enum.drop(bind, checkfirst=True)
