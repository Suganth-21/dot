"""Batch status derivation — ARCHITECTURE.md §5.1. Split out from
`batch_service` (rather than defined there) so it has no dependency on
`fraud_service`: both `batch_service` and `alert_service` need it (the
latter to embed a full `BatchOut` — including its derived status — in
`GET /api/alerts/{id}`'s response), and `batch_service` -> `fraud_service`
-> `alert_service` -> `batch_service` would otherwise be a circular import.
"""
from __future__ import annotations

from datetime import datetime

from app.models.enums import BatchStatus

_STICKY_STATUSES = {BatchStatus.IN_RETURN, BatchStatus.DESTROYED}


def derive_status(expiry_date: datetime, stored_status: BatchStatus, now: datetime) -> BatchStatus:
    """`IN_RETURN` and `DESTROYED` are sticky and never recomputed from
    expiry. The other three are derived on every read against the pinned
    demo clock (`DEMO_NOW`) rather than real wall-clock time —
    ARCHITECTURE.md §4.10 pins the whole system to it so "days to expiry"
    stays consistent with what the frontend computes."""
    if stored_status in _STICKY_STATUSES:
        return stored_status
    # Calendar-day comparison, not a raw datetime subtraction: `expiry_date`
    # on a *newly registered* batch is whatever a real client sent on the
    # wire, and a plain `type="date"` HTML input (frontend/src/pages/
    # pharmacy.jsx's InventoryAdd form) produces a date with no time
    # component, which Pydantic parses as a timezone-naive `datetime` —
    # subtracting that directly from `now` (always timezone-aware, from
    # DEMO_NOW's `+05:30` offset) raises `TypeError: can't subtract
    # offset-naive and offset-aware datetimes` and 500s every registration
    # of a batch with a date-only expiry. `.date()` on both sides sidesteps
    # naive/aware entirely and matches what "days to expiry" already means
    # everywhere else in this codebase (whole calendar days, not sub-day
    # precision) — including the frontend's own day-rounding
    # (`Math.round((new Date(batch.expiryDate) - now) / 86400000)`).
    days = (expiry_date.date() - now.date()).days
    if days < 0:
        return BatchStatus.EXPIRED
    if days <= 60:
        return BatchStatus.EXPIRING_SOON
    return BatchStatus.ACTIVE
