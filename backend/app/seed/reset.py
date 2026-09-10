"""Truncates and re-seeds every table Phase 1 and Phase 2 own, in one
transaction. Powers `POST /api/demo/reset` and the initial seed used by
tests and local dev. See BUILDPHASES.md "Seed data spec" — determinism
requirement: running this twice produces identical rows apart from
generated ids that are already fixed in `app.seed.seed_data`/
`app.seed.seed_batches`, and apart from the Argon2 salt and Ed25519 keypair
bytes, which are expected to differ every run (a password hash and a
signing key are supposed to be unpredictable) while remaining logically
equivalent — the same email still verifies against the same demo password,
and the same batch still produces a chain that verifies.

This module is orchestration over models and services directly rather than
going through `app.repositories` for every step, because a full-database
reset is a seeding concern, not a per-entity read/write — see
`app.services` vs `app.seed` boundary in ARCHITECTURE.md §2. It does,
however, go through `app.services.event_service` for every event, same as
a live request — see app/seed/seed_batches.py's docstring for why that
matters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.crypto import generate_signing_keypair
from app.core.rbac import Role
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.batch import Batch
from app.models.drug import Drug
from app.models.entity import Agent, Distributor, Facility, Manufacturer, Pharmacy, Regulator, Vehicle
from app.models.enums import AgentStatus, DrugCategory
from app.models.event import Event
from app.models.notification import Notification
from app.models.patient_report import PatientReport
from app.models.refresh_token import RefreshToken
from app.models.report import Report
from app.models.return_ import Return
from app.models.route import Route, RouteStop
from app.models.sale import Sale
from app.models.user import User
from app.seed import seed_batches, seed_data


async def _truncate_all_tables(session: AsyncSession) -> None:
    # Children before parents throughout: refresh_tokens/notifications ->
    # users; route_stops -> {routes, returns}; returns -> routes (Phase 5
    # added returns.route_id's FK once routes existed — see
    # ARCHITECTURE.md's Phase 5 notes); alerts/patient_reports/events/sales
    # -> batches -> {pharmacies, manufacturers, distributors, facilities,
    # drugs}; agents/vehicles/routes -> distributors.
    await session.execute(RefreshToken.__table__.delete())
    await session.execute(Notification.__table__.delete())
    await session.execute(Report.__table__.delete())  # standalone — no FKs
    await session.execute(User.__table__.delete())
    await session.execute(Alert.__table__.delete())
    await session.execute(PatientReport.__table__.delete())
    await session.execute(RouteStop.__table__.delete())
    await session.execute(Return.__table__.delete())
    await session.execute(Route.__table__.delete())
    await session.execute(Event.__table__.delete())
    await session.execute(Sale.__table__.delete())
    await session.execute(Batch.__table__.delete())
    await session.execute(Agent.__table__.delete())
    await session.execute(Vehicle.__table__.delete())
    await session.execute(Pharmacy.__table__.delete())
    await session.execute(Distributor.__table__.delete())
    await session.execute(Manufacturer.__table__.delete())
    await session.execute(Facility.__table__.delete())
    await session.execute(Regulator.__table__.delete())
    await session.execute(Drug.__table__.delete())


def _seed_entities(session: AsyncSession) -> None:
    # Phase 2: pharmacies, distributors, manufacturers, and agents are
    # event actors (ARCHITECTURE.md §7.5, "each entity gets an Ed25519
    # keypair") — see the Phase 2 implementation notes for why the key
    # lives on the entity rather than only on the login `users` row.
    for row in seed_data.DISTRIBUTORS:
        public_key, private_key = generate_signing_keypair()
        session.add(Distributor(**row, signing_public_key=public_key, signing_private_key=private_key))
    for row in seed_data.PHARMACIES:
        public_key, private_key = generate_signing_keypair()
        session.add(Pharmacy(**row, signing_public_key=public_key, signing_private_key=private_key))
    for row in seed_data.MANUFACTURERS:
        public_key, private_key = generate_signing_keypair()
        session.add(Manufacturer(**row, signing_public_key=public_key, signing_private_key=private_key))
    for row in seed_data.FACILITIES:
        session.add(Facility(**row))
    session.add(Regulator(**seed_data.REGULATOR))
    for row in seed_data.AGENTS:
        public_key, private_key = generate_signing_keypair()
        session.add(Agent(**row, status=AgentStatus.idle, signing_public_key=public_key,
                           signing_private_key=private_key))
    for row in seed_data.VEHICLES:
        session.add(Vehicle(**row, status=AgentStatus.idle))
    for row in seed_data.DRUGS:
        session.add(Drug(key=row["key"], name=row["name"],
                          category=DrugCategory(row["category"]), price=Decimal(row["price"])))


def _seed_demo_users(session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.demo_password:
        raise RuntimeError("DEMO_PASSWORD is not configured — cannot seed demo accounts")

    password_hash = hash_password(settings.demo_password)
    now = datetime.now(timezone.utc)

    for row in seed_data.DEMO_USERS:
        public_key, encrypted_private_key = generate_signing_keypair()
        session.add(
            User(
                id=row["id"],
                email=row["email"],
                password_hash=password_hash,
                name=row["name"],
                role=Role(row["role"]),
                entity_id=row["entity_id"],
                is_demo=True,
                signing_public_key=public_key,
                signing_private_key=encrypted_private_key,
                created_at=now,
            )
        )


async def reset_demo_data(session: AsyncSession) -> None:
    """Truncates every Phase 1-4-owned table and re-seeds deterministically
    (Phase 3's `alerts`/`patient_reports` and Phase 4's `returns`/
    `notifications` reset to empty — none of the four are seeded with
    historical rows, only the entities/batches/events are). Runs as a
    single transaction: a failure partway
    through rolls back rather than leaving a half-seeded database
    (CLAUDE.md rule 7)."""
    await _truncate_all_tables(session)
    # The truncate above is a Core-level bulk DELETE, which does not touch
    # the session's ORM identity map. Without expunging, re-adding a row
    # with a primary key the session already has mapped (e.g. because the
    # caller's `get_current_user` dependency just loaded that same user in
    # this same request's session) raises a SQLAlchemy identity-map
    # conflict warning on the `session.add()` below.
    session.expunge_all()

    _seed_entities(session)
    _seed_demo_users(session)
    # Batches/events are authored via event_service, which resolves each
    # actor entity's signing key by querying the database — the entities
    # above must actually be persisted (not merely pending) before any of
    # that can succeed.
    await session.flush()

    now = get_settings().demo_now_dt
    await seed_batches.seed_all_batches(session, now)

    await session.commit()
