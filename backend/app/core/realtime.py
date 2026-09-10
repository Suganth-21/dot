"""Real-time layer: Redis pub/sub publisher plus a per-worker WebSocket
connection registry. ARCHITECTURE.md §9. Any uvicorn worker can publish;
any worker holding a matching local WebSocket subscriber relays the
message — that's what makes this safe across multiple workers, unlike an
in-process-only pub/sub would be.

**Publish after commit, always** (ARCHITECTURE.md §3's "Two ordering rules
that matter"). Every call site in `app.services.*` that publishes does so
strictly after its own `await session.commit()` — publishing inside an
open transaction that then rolls back would tell subscribers about state
that was never actually written.

Deliberately has no dependency on `app.repositories` — ARCHITECTURE.md §2's
dependency diagram places `core` (crypto, errors, rbac, realtime) beside
`services`, not below `repositories`. Channel *authorization* (which needs
to query batch/route/return ownership) lives in
`app.services.realtime_service` instead; this module is pure pub/sub
mechanism.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import WebSocket

from app.config import get_settings

logger = logging.getLogger("dot.realtime")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


class RealtimeHub:
    """One instance, created at app startup, torn down at shutdown (see
    `app.main`'s lifespan). `redis_url=None` (e.g. in the test suite, which
    never starts the lifespan at all — see `app.main`'s `_lifespan`
    docstring) leaves the hub inert: `publish()` becomes a no-op instead of
    raising, so no service call site needs an `if redis_configured` guard.
    """

    def __init__(self, redis_url: str | None):
        self._redis_url = redis_url
        self._redis: redis_asyncio.Redis | None = None
        self._pubsub: Any = None
        self._local_subscribers: dict[str, set[WebSocket]] = {}
        self._listen_task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    async def start(self) -> None:
        if not self._redis_url:
            logger.warning("REDIS_URL not configured — realtime layer disabled")
            return
        self._redis = redis_asyncio.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        self._listen_task = asyncio.create_task(self._listen())
        logger.info("realtime hub started")

    async def stop(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pubsub is not None:
            await self._pubsub.close()
        if self._redis is not None:
            await self._redis.close()
        self._redis = None

    async def publish(self, channel: str, msg_type: str, data: Any) -> None:
        if not self.enabled:
            return
        envelope = {"type": msg_type, "channel": channel, "ts": _now_iso(), "data": data}
        await self._redis.publish(channel, json.dumps(envelope, default=str))

    async def subscribe_local(self, channel: str, ws: WebSocket) -> None:
        if not self.enabled:
            return
        is_new = channel not in self._local_subscribers
        self._local_subscribers.setdefault(channel, set()).add(ws)
        if is_new:
            await self._pubsub.subscribe(channel)

    async def unsubscribe_local(self, channel: str, ws: WebSocket) -> None:
        if not self.enabled:
            return
        subs = self._local_subscribers.get(channel)
        if not subs:
            return
        subs.discard(ws)
        if not subs:
            del self._local_subscribers[channel]
            await self._pubsub.unsubscribe(channel)

    def drop_connection(self, ws: WebSocket) -> None:
        """Called once on disconnect rather than per-channel — cheaper than
        an unsubscribe round trip per subscription when a socket just
        dropped."""
        for channel in list(self._local_subscribers.keys()):
            self._local_subscribers[channel].discard(ws)
            if not self._local_subscribers[channel]:
                del self._local_subscribers[channel]

    async def _listen(self) -> None:
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                channel = message["channel"]
                payload = message["data"]
                for ws in list(self._local_subscribers.get(channel, [])):
                    try:
                        await ws.send_text(payload)
                    except Exception:  # noqa: BLE001 — a dead socket is cleaned up on its own disconnect handler
                        logger.debug("dropping a send to a socket that looks dead", exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — the listen loop must never silently die
            logger.exception("realtime listen loop crashed")


hub = RealtimeHub(get_settings().redis_url)
