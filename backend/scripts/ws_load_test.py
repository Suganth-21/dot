#!/usr/bin/env python
"""Load test for the WebSocket fan-out — BUILDPHASES.md Phase 9. Opens N
concurrent connections to /api/ws, has each subscribe to a channel, then
waits for one published message to reach all of them, reporting the
slowest delivery — ARCHITECTURE.md §9's "alert arrives in under 2 seconds"
requirement under connection load rather than the single-client case the
pytest suite exercises.

Not run as part of the automated build — a real load test hits a real
running server and is a deliberate, separate operator action. See
backend/OPERATIONS.md.

Usage:
    python scripts/ws_load_test.py --url ws://localhost:8000/api/ws \\
        --connections 200 --channel alerts:regulator --token <access token>

Requires a REGULATOR access token (or whatever role is authorized for
`--channel`) and a separate trigger (e.g. a real re-entry registration) to
actually publish onto that channel while this script is listening — this
script only measures fan-out latency, it doesn't fabricate the underlying
domain event.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time

try:
    import websockets
except ImportError:  # pragma: no cover — a dev-only script, not a runtime dependency
    raise SystemExit("pip install websockets  # not a backend runtime dependency, load-test tooling only")


async def _one_connection(url: str, token: str, channel: str, results: list[float], start_barrier: asyncio.Event) -> None:
    async with websockets.connect(f"{url}?token={token}") as ws:
        await ws.send(json.dumps({"action": "subscribe", "channel": channel}))
        ack = json.loads(await ws.recv())
        if ack.get("type") != "subscribed":
            print(f"subscribe failed: {ack}")
            return

        await start_barrier.wait()
        t0 = time.monotonic()
        message = json.loads(await ws.recv())
        elapsed = time.monotonic() - t0
        results.append(elapsed)
        if message.get("channel") != channel:
            print(f"unexpected channel in message: {message.get('channel')}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://localhost:8000/api/ws")
    parser.add_argument("--connections", type=int, default=200)
    parser.add_argument("--channel", default="alerts:regulator")
    parser.add_argument("--token", required=True, help="A valid access token authorized for --channel")
    args = parser.parse_args()

    results: list[float] = []
    start_barrier = asyncio.Event()

    tasks = [
        asyncio.create_task(_one_connection(args.url, args.token, args.channel, results, start_barrier))
        for _ in range(args.connections)
    ]
    await asyncio.sleep(2)  # let every connection finish subscribing
    print(f"{args.connections} connections subscribed to {args.channel} — trigger the publish now.")
    start_barrier.set()

    await asyncio.gather(*tasks, return_exceptions=True)

    if results:
        print(f"received: {len(results)}/{args.connections}")
        print(f"min={min(results):.3f}s max={max(results):.3f}s avg={sum(results) / len(results):.3f}s")
        print("PASS (< 2s)" if max(results) < 2.0 else "FAIL (>= 2s) — see ARCHITECTURE.md §9's requirement")
    else:
        print("no messages received — did you trigger a publish on this channel?")


if __name__ == "__main__":
    asyncio.run(main())
