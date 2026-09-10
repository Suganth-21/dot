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
