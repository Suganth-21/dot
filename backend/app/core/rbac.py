"""Single source of truth for role -> permission. ARCHITECTURE.md §6.5.

This module is deliberately framework-agnostic: it defines *what* each role
may attempt. The FastAPI dependency that turns this into a 403 lives in
`app.deps` (`require_role`), per the folder layout in ARCHITECTURE.md §2
("deps.py: db session, current_user, role guards"). Keeping the matrix here
and the wiring there means the matrix can be unit-tested with no HTTP layer
involved, and there is exactly one place a future phase edits to add a role
to a resource.

Only two layers together make an authorization decision correct — see
ARCHITECTURE.md §6.5:
  1. The role guard here rejects the wrong role before a handler runs.
  2. An ownership check inside the service (`resource.entity_id ==
     user.entity_id`) — not implemented here, and not skippable by any role,
     including REGULATOR, who is read-only over operational data.
Phase 1 has no ownership-bearing resources yet (batches/returns/etc. land in
later phases); this module carries the full matrix now so later phases wire
guards without ever having to touch this file's authority.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class Role(str, enum.Enum):
    RETAILER = "RETAILER"
    DISTRIBUTOR = "DISTRIBUTOR"
    PICKUP_AGENT = "PICKUP_AGENT"
    MANUFACTURER = "MANUFACTURER"
    REGULATOR = "REGULATOR"


@dataclass(frozen=True)
class CurrentUser:
    """What a validated access token resolves to. `entity_id` is carried
    through so later phases can apply the ownership check above without
    a second database round trip — see ARCHITECTURE.md §6.5."""

    id: str
    role: Role
    entity_id: str | None

    @classmethod
    def from_user(cls, user: object) -> CurrentUser:
        """Builds the lean carrier from an ORM `User` row without importing
        `app.models` here (core stays beneath models in the dependency
        direction — ARCHITECTURE.md §2)."""
        return cls(id=user.id, role=user.role, entity_id=user.entity_id)  # type: ignore[attr-defined]


# Transcribed from ARCHITECTURE.md §6.5. Each key is "resource:action"; the
# value is the set of roles allowed to *attempt* it (the role-guard layer).
# The "own X" / "all" / ownership-scoping qualifiers from that table are
# service-layer concerns (layer 2 above) and are not encoded here — this
# matrix answers "is this role ever allowed near this action", nothing more.
PERMISSION_MATRIX: dict[str, frozenset[Role]] = {
    "batches:read": frozenset({Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR}),
    "batches:register": frozenset({Role.RETAILER}),
    "batches:record_sale": frozenset({Role.RETAILER}),
    "returns:read": frozenset({Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR}),
    "returns:create": frozenset({Role.RETAILER}),
    "returns:receive_or_dispute": frozenset({Role.DISTRIBUTOR}),
    "returns:resolve_dispute": frozenset({Role.DISTRIBUTOR}),
    "returns:forward": frozenset({Role.DISTRIBUTOR}),
    "routes:read": frozenset({Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR}),
    "routes:create_or_dispatch": frozenset({Role.DISTRIBUTOR}),
    "routes:arrive_or_pickup": frozenset({Role.PICKUP_AGENT}),
    "facility:schedule": frozenset({Role.MANUFACTURER}),
    "certificate:upload": frozenset({Role.MANUFACTURER}),
    "alerts:read": frozenset({Role.RETAILER, Role.DISTRIBUTOR, Role.MANUFACTURER, Role.REGULATOR}),
    "alerts:change_status": frozenset({Role.REGULATOR}),
    "entities:read": frozenset({Role.REGULATOR}),
    "reports:generate": frozenset({Role.REGULATOR}),
    "analytics:read": frozenset({Role.RETAILER, Role.DISTRIBUTOR, Role.MANUFACTURER, Role.REGULATOR}),
    # Phase 1 resources.
    "reference:read": frozenset(
        {Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR}
    ),
    "regulator_profile:read": frozenset({Role.REGULATOR}),
    "demo:reset": frozenset(
        {Role.RETAILER, Role.DISTRIBUTOR, Role.PICKUP_AGENT, Role.MANUFACTURER, Role.REGULATOR}
    ),
}


def is_role_allowed(resource_action: str, role: Role) -> bool:
    """A route with no entry in the matrix fails closed (CLAUDE.md rule 2 /
    ARCHITECTURE.md §6.5: "a route with no declaration fails closed")."""
    allowed = PERMISSION_MATRIX.get(resource_action)
    if allowed is None:
        return False
    return role in allowed
