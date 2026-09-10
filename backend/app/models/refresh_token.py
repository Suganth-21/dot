"""Refresh-token persistence — what makes rotation and revocation possible.

Only a SHA-256 hash of the token is ever stored, never the raw value (the
same principle as a password: a leaked database row must not itself be a
usable credential). See ARCHITECTURE.md §6.1.

Rotation model: every refresh call issues a new row and marks the old one
`revoked`. All rows sharing a `family_id` descend from one original login.
If a `revoked` token is presented again — proof the token was stolen and
already used by someone else — the entire family is revoked, which forces
re-authentication rather than letting the thief's rotated chain continue.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    family_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    replaced_by_id: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
