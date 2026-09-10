"""Real-time channel authorization — ARCHITECTURE.md §9.1, §9.2;
BUILDPHASES.md Phase 7. Exercised at the service layer
(`realtime_service.is_subscribe_allowed`) rather than over a live
WebSocket connection: httpx's `ASGITransport` (this suite's HTTP client)
never invokes FastAPI's lifespan, so the Redis-backed hub never actually
starts under pytest (see `app.main`'s `_lifespan` docstring, and
`core.realtime.RealtimeHub.enabled`, which is exactly why `hub.publish(...)`
is safe to call unconditionally from every service without a live Redis
connection in the test environment).

A genuine end-to-end WebSocket connect/subscribe/publish/receive round trip
needs a live ASGI server and a live Redis instance — see
`backend/scripts/ws_load_test.py` and `backend/OPERATIONS.md` for that,
run manually, not from pytest.
"""
from datetime import UTC, datetime

import pytest

from app.core.rbac import Role
from app.models.user import User
from app.services import realtime_service


def _user(role: Role, entity_id: str | None) -> User:
    return User(
        id=f"usr_test_{role.value.lower()}", email=f"test-{role.value.lower()}@dot.in", password_hash="x",
        name="Test User", role=role, entity_id=entity_id, is_demo=False,
        signing_public_key="x", signing_private_key="x", created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_alerts_regulator_channel_only_for_regulator(seeded, db_session):
    assert await realtime_service.is_subscribe_allowed(db_session, _user(Role.REGULATOR, "reg_1"), "alerts:regulator")
    assert not await realtime_service.is_subscribe_allowed(db_session, _user(Role.RETAILER, "ph_1"), "alerts:regulator")


@pytest.mark.asyncio
async def test_alerts_manufacturer_channel_scoped_to_own_id(seeded, db_session):
    mfr1 = _user(Role.MANUFACTURER, "mfr_1")
    assert await realtime_service.is_subscribe_allowed(db_session, mfr1, "alerts:manufacturer:mfr_1")
    assert not await realtime_service.is_subscribe_allowed(db_session, mfr1, "alerts:manufacturer:mfr_2")


@pytest.mark.asyncio
async def test_fleet_all_regulator_and_manufacturer_only(seeded, db_session):
    assert await realtime_service.is_subscribe_allowed(db_session, _user(Role.REGULATOR, "reg_1"), "fleet:all")
    assert await realtime_service.is_subscribe_allowed(db_session, _user(Role.MANUFACTURER, "mfr_1"), "fleet:all")
    assert not await realtime_service.is_subscribe_allowed(db_session, _user(Role.DISTRIBUTOR, "dist_1"), "fleet:all")


@pytest.mark.asyncio
async def test_fleet_distributor_channel_own_only(seeded, db_session):
    dist1 = _user(Role.DISTRIBUTOR, "dist_1")
    assert await realtime_service.is_subscribe_allowed(db_session, dist1, "fleet:dist_1")
    assert not await realtime_service.is_subscribe_allowed(db_session, dist1, "fleet:dist_2")


@pytest.mark.asyncio
async def test_batch_channel_scoped_by_ownership(seeded, db_session):
    # ph_1 owns BATCH-DOX-2026-A17 (seeded).
    ph1 = _user(Role.RETAILER, "ph_1")
    ph_other = _user(Role.RETAILER, "ph_9")
    assert await realtime_service.is_subscribe_allowed(db_session, ph1, "batch:BATCH-DOX-2026-A17")
    assert not await realtime_service.is_subscribe_allowed(db_session, ph_other, "batch:BATCH-DOX-2026-A17")
    assert not await realtime_service.is_subscribe_allowed(db_session, ph1, "batch:BATCH-DOES-NOT-EXIST")


@pytest.mark.asyncio
async def test_notifications_channel_exact_role_and_entity_match(seeded, db_session):
    retailer = _user(Role.RETAILER, "ph_1")
    assert await realtime_service.is_subscribe_allowed(db_session, retailer, "notifications:RETAILER:ph_1")
    assert not await realtime_service.is_subscribe_allowed(db_session, retailer, "notifications:RETAILER:ph_2")
    assert not await realtime_service.is_subscribe_allowed(db_session, retailer, "notifications:DISTRIBUTOR:ph_1")


@pytest.mark.asyncio
async def test_unrecognised_channel_is_rejected(seeded, db_session):
    assert not await realtime_service.is_subscribe_allowed(
        db_session, _user(Role.REGULATOR, "reg_1"), "something:made-up",
    )


@pytest.mark.asyncio
async def test_hub_publish_is_a_safe_noop_without_a_started_connection():
    """`hub` is a module-level singleton constructed at import time; its
    Redis connection is only opened by `app.main`'s lifespan, which pytest
    never triggers (see this module's docstring). Every service calls
    `hub.publish(...)` unconditionally after every commit — this proves
    that's always safe, not just usually."""
    from app.core.realtime import hub

    assert hub.enabled is False
    await hub.publish("alerts:regulator", "alert.created", {"id": "alert_test"})  # must not raise
