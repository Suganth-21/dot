"""Test harness setup.

Testing strategy (Phase 0, per BUILDPHASES.md): these tests run against a
REAL PostgreSQL database, not sqlite and not an in-memory fake — the health
check's whole job is to prove real connectivity, and a fake DB would prove
nothing. This requires a running local PostgreSQL server reachable at
TEST_DATABASE_URL (or the default below), with the target database already
created:

    createdb -U <role> dot_test

The dev database (DATABASE_URL in backend/.env) is never touched by tests —
this module forces DATABASE_URL to the test database for the whole test
session, overriding whatever backend/.env or the shell environment set, so a
misconfigured local .env can never point the suite at real data.
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://dot:dot@localhost:5432/dot_test"
)
os.environ["CORS_ORIGINS"] = os.environ.get("CORS_ORIGINS", "http://localhost:3000")

# Phase 1: auth/demo secrets are forced here too, the same way DATABASE_URL
# is forced above — the test suite must not depend on whatever a developer
# happens to have in backend/.env to be deterministic.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-real-use"
os.environ["SIGNING_MASTER_KEY"] = "test-only-signing-master-key-not-for-real-use"
os.environ["ENABLE_DEMO_LOGIN"] = "true"
os.environ["DEMO_PASSWORD"] = "Demo@Test123"
os.environ["ENABLE_DEMO_RESET"] = "true"
os.environ["JWT_ACCESS_TTL_MIN"] = "30"
# Phase 2: every seeded date and status derivation is pinned to this
# constant — ARCHITECTURE.md §4.10. Forced here for the same reason as the
# secrets above: determinism independent of a developer's local .env.
os.environ["DEMO_NOW"] = "2026-09-15T09:30:00+05:30"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()  # force a fresh Settings() read of the env vars set above

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture()
def app():
    """A fresh FastAPI instance per test — cheap, and keeps tests that add
    temporary routes (see test_errors.py) from leaking into other tests."""
    return create_app()


@pytest_asyncio.fixture()
async def client(app):
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware re-raises
    # after sending its response (real ASGI servers just log that re-raise
    # and the client never sees it). Matching that here means these tests
    # observe what an actual client receives, not an internal implementation
    # detail of the test transport.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def db_session():
    """A raw session for arranging/asserting database state directly —
    used by Phase 1 tests to seed before a request and to check rows after
    one, independent of whatever session a route handler opens."""
    from app.db import async_session_factory

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture()
async def seeded(db_session):
    """Runs the real Phase 1 reset/seed path before a test. Function-scoped
    (not session-scoped) so each test starts from the same deterministic
    state regardless of what an earlier test wrote or revoked."""
    from app.seed.reset import reset_demo_data

    await reset_demo_data(db_session)
    return db_session


@pytest.fixture(autouse=True, scope="session")
def _dispose_engine_after_session():
    """Without this, asyncpg connections opened during the session are torn
    down by garbage collection after their event loop has already closed,
    which surfaces as a harmless but noisy 'coroutine was never awaited'
    warning. Disposing the pool explicitly, in its own short-lived loop
    after every per-test loop has already closed, avoids that."""
    import asyncio

    yield

    from app.db import engine

    asyncio.run(engine.dispose())
