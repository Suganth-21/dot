"""Shared enums, mapped to native PostgreSQL enum types.

Single definition point so the Python-side value set and the database
CHECK/enum constraint can never drift apart. See ARCHITECTURE.md §4.
"""
from __future__ import annotations

import enum


class AgentStatus(str, enum.Enum):
    idle = "idle"
    active = "active"
    offline = "offline"


class DrugCategory(str, enum.Enum):
    oncology = "oncology"
    antibiotics = "antibiotics"
    cardiovascular = "cardiovascular"
    other = "other"


class BatchStatus(str, enum.Enum):
    """ARCHITECTURE.md §5.1. `IN_RETURN` and `DESTROYED` are sticky — never
    recomputed from expiry. The other three are time-derived."""

    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"
    IN_RETURN = "IN_RETURN"
    DESTROYED = "DESTROYED"


class HolderType(str, enum.Enum):
    PHARMACY = "PHARMACY"
    DISTRIBUTOR = "DISTRIBUTOR"
    FACILITY = "FACILITY"


class EventType(str, enum.Enum):
    """ARCHITECTURE.md §4.4.1. Phase 2 only ever *writes* REGISTERED and
    SALE; the rest of the set is declared now so the enum/model matches the
    full documented domain and seeded historical events (Phase 4-6 event
    types, authored by the seed script as historical fact, not by a live
    endpoint — see app/seed/seed_data.py) can be stored validly."""

    REGISTERED = "REGISTERED"
    SALE = "SALE"
    RETURN_INITIATED = "RETURN_INITIATED"
    PICKUP_ASSIGNED = "PICKUP_ASSIGNED"
    AGENT_ARRIVED = "AGENT_ARRIVED"
    PICKED_UP = "PICKED_UP"
    DISTRIBUTOR_CONFIRMED = "DISTRIBUTOR_CONFIRMED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
    FORWARDED = "FORWARDED"
    FACILITY_SCHEDULED = "FACILITY_SCHEDULED"
    DESTROYED = "DESTROYED"
    REENTRY_BLOCKED = "REENTRY_BLOCKED"


class AlertType(str, enum.Enum):
    """ARCHITECTURE.md §4.7."""

    REENTRY = "REENTRY"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    CERT_MISMATCH = "CERT_MISMATCH"
    PATIENT_REPORT = "PATIENT_REPORT"
    QUANTITY_CAP = "QUANTITY_CAP"


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class ReturnStatus(str, enum.Enum):
    """ARCHITECTURE.md §5.2. Seven canonical statuses — `ASSIGNED` and
    `EN_ROUTE` are accepted on input as aliases of `SCHEDULED` and never
    stored or emitted (see `app.services.return_service`)."""

    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    ARRIVED = "ARRIVED"
    PICKED_UP = "PICKED_UP"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    FORWARDED = "FORWARDED"


class ReturnReason(str, enum.Enum):
    """ARCHITECTURE.md §4.5."""

    EXPIRED = "EXPIRED"
    DAMAGED = "DAMAGED"
    RECALL = "RECALL"


class NotificationKind(str, enum.Enum):
    """ARCHITECTURE.md §4.8."""

    info = "info"
    warning = "warning"
    danger = "danger"
    success = "success"


class RouteStatus(str, enum.Enum):
    """ARCHITECTURE.md §5.3 / §4.6 — lowercase, the frontend compares these literals."""

    planned = "planned"
    active = "active"
    completed = "completed"


class StopStatus(str, enum.Enum):
    """ARCHITECTURE.md §4.6."""

    PENDING = "PENDING"
    CURRENT = "CURRENT"
    ARRIVED = "ARRIVED"
    DONE = "DONE"
