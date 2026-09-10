"""User model — identity, credentials, and signing key material.

`entity_id` intentionally carries no database FK: which table it points into
depends on `role` (pharmacy for RETAILER, distributor for DISTRIBUTOR, ...),
and Postgres has no native polymorphic FK. Referential integrity for it is
an application-level guarantee (checked at seed time and wherever a user is
created), documented here rather than silently assumed. See ARCHITECTURE.md
§4.1.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.rbac import Role
from app.models.base import Base

_role_enum = Enum(Role, name="role_enum", values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Role] = mapped_column(_role_enum, nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(Text, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signing_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Encrypted at rest with SIGNING_MASTER_KEY (app.core.crypto). Only ever
    # decrypted inside event_service in Phase 2 — never logged, never
    # returned through an API response (CLAUDE.md rule 7, ARCHITECTURE §7.5).
    signing_private_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
