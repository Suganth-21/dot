"""Async SQLAlchemy engine + session factory.

One engine for the process. `async_session_factory` is what both the app
(via `app.deps.get_db`) and the health check use to talk to PostgreSQL.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# NullPool: no connection is held open between requests, so no asyncpg
# connection is ever reused across a different event loop. In production
# there is only one loop and this trades a little latency per request for
# never depending on cross-loop connection reuse being safe — a real
# pool (pool_size tuning) is a later-phase performance decision, not a
# Phase 0 one. In the test suite it's load-bearing: pytest-asyncio gives
# each test function its own event loop, and a pooled connection surviving
# from one loop into the next is exactly the kind of bug this project's
# integrity story can't afford anywhere, tests included.
engine = create_async_engine(settings.database_url, poolclass=NullPool, future=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
