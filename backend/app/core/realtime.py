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

**Single-task ownership of the redis-py PubSub object.** `redis.asyncio`'s
`PubSub` is only safe to read from and mutate (subscribe/unsubscribe) from
one task at a time — calling `.subscribe()` from a WebSocket handler's task
while a *different* task is concurrently iterating `.listen()` (or polling
`.get_message()`) silently breaks delivery: the subscribe confirmation and
the read loop race for the same connection, and once that happens the read
loop never yields another message, subscribed or not. This was verified
empirically against a real Redis instance (not a theoretical concern — the
original implementation called `self._pubsub.subscribe()` directly from
`subscribe_local`, which is exactly the caller's task, not `_listen()`'s;
every message published while the app was running was confirmed arriving
at Redis via `redis-cli PSUBSCRIBE`, and zero of them ever reached a
WebSocket client). The fix: `subscribe_local`/`unsubscribe_local` never
touch `self._pubsub` directly. They enqueue a request onto `_sub_queue`
and await a future that `_listen()` — the *only* task that ever calls
`.subscribe()`, `.unsubscribe()`, or `.get_message()` — resolves once the
request is actually applied. `_listen()` also subscribes to a harmless
keepalive channel before starting its read loop, since `get_message()` on
a PubSub with zero subscriptions never establishes a connection for a
later subscribe to attach to.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import WebSocket

from app.config import get_settings

logger = logging.getLogger("dot.realtime")

_KEEPALIVE_CHANNEL = "__hub_keepalive__"
# How often _listen() re-checks _sub_queue while otherwise blocked in
# get_message() — bounds worst-case subscribe-to-first-message latency.
# ARCHITECTURE.md §9.1's "~2-second re-entry alert" demo requirement has
# ample headroom above this.
_POLL_TIMEOUT_S = 0.25


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(UTC).microsecond // 1000:03d}Z"


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
        # (action, channel, future) — drained exclusively inside _listen().
        self._sub_queue: asyncio.Queue[tuple[str, str, asyncio.Future]] = asyncio.Queue()

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    async def start(self) -> None:
        if not self._redis_url:
            logger.warning("REDIS_URL not configured — realtime layer disabled")
            return
        self._redis = redis_asyncio.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        # Establishes the pubsub connection before _listen() starts polling
        # it — see the module docstring for why this specific ordering
        # matters. Never published to; exists purely to give get_message()
        # something to hold open.
        await self._pubsub.subscribe(_KEEPALIVE_CHANNEL)
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

    async def _request(self, action: str, channel: str) -> None:
        """Enqueues a subscribe/unsubscribe for `_listen()` to actually
        perform, and waits for it to confirm — so a caller awaiting
        `subscribe_local` (ws.py sends its "subscribed" ack right after)
        never races ahead of the real Redis subscription completing."""
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._sub_queue.put((action, channel, future))
        await future

    async def subscribe_local(self, channel: str, ws: WebSocket) -> None:
        if not self.enabled:
            return
        is_new = channel not in self._local_subscribers
        self._local_subscribers.setdefault(channel, set()).add(ws)
        if is_new:
            await self._request("subscribe", channel)

    async def unsubscribe_local(self, channel: str, ws: WebSocket) -> None:
        if not self.enabled:
            return
        subs = self._local_subscribers.get(channel)
        if not subs:
            return
        subs.discard(ws)
        if not subs:
            del self._local_subscribers[channel]
            await self._request("unsubscribe", channel)

    def drop_connection(self, ws: WebSocket) -> None:
        """Called once on disconnect rather than per-channel — cheaper than
        an unsubscribe round trip per subscription when a socket just
        dropped. Best-effort on the Redis side: enqueued without waiting,
        since nothing is blocked on this cleanup completing."""
        for channel in list(self._local_subscribers.keys()):
            subs = self._local_subscribers[channel]
            subs.discard(ws)
            if not subs and self.enabled:
                del self._local_subscribers[channel]
                future: asyncio.Future = asyncio.get_event_loop().create_future()
                self._sub_queue.put_nowait(("unsubscribe", channel, future))

    async def _listen(self) -> None:
        assert self._pubsub is not None
        try:
            while True:
                # Every subscribe/unsubscribe touching self._pubsub happens
                # right here, in this task — never in subscribe_local's
                # caller's task. See the module docstring.
                while not self._sub_queue.empty():
                    action, channel, future = self._sub_queue.get_nowait()
                    try:
                        if action == "subscribe":
                            await self._pubsub.subscribe(channel)
                        else:
                            await self._pubsub.unsubscribe(channel)
                        if not future.done():
                            future.set_result(None)
                    except Exception as exc:  # noqa: BLE001 — must not crash the listen loop
                        if not future.done():
                            future.set_exception(exc)
                        logger.exception("realtime subscribe request failed action=%s channel=%s", action, channel)

                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=_POLL_TIMEOUT_S)
                if message is None:
                    continue
                channel = message["channel"]
                payload = message["data"]
                for ws in list(self._local_subscribers.get(channel, [])):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        logger.debug("dropping a send to a socket that looks dead", exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("realtime listen loop crashed")


hub = RealtimeHub(get_settings().redis_url)
