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
    days = (expiry_date - now).days
    if days < 0:
        return BatchStatus.EXPIRED
    if days <= 60:
        return BatchStatus.EXPIRING_SOON
    return BatchStatus.ACTIVE
