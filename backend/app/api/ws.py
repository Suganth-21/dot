"""WS /api/ws?token=<access token>. Token auth on connect; every
subscribe/unsubscribe is server-authorized against
`app.services.realtime_service.is_subscribe_allowed` (ARCHITECTURE.md §9.1,
§9.2). There is exactly one exception to authentication anywhere in this
API — `/api/public/*` — and this is not it: an invalid or missing token
here is closed with 4401, same as the architecture doc specifies.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.errors import DomainError
from app.core.realtime import hub
from app.db import async_session_factory
from app.services import auth_service, realtime_service

logger = logging.getLogger("dot.ws")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    if not token:
        await websocket.close(code=4401)
        return

    async with async_session_factory() as session:
        try:
            user = await auth_service.resolve_current_user(session, token)
        except DomainError:
            await websocket.close(code=4401)
            return

    await websocket.accept()
    subscribed: set[str] = set()

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            channel = message.get("channel")
            if not channel or not isinstance(channel, str):
                await websocket.send_json({"type": "error", "code": "MALFORMED_REQUEST"})
                continue

            if action == "subscribe":
                async with async_session_factory() as session:
                    allowed = await realtime_service.is_subscribe_allowed(session, user, channel)
                if not allowed:
                    await websocket.send_json({"type": "error", "code": "SUBSCRIBE_FORBIDDEN", "channel": channel})
                    continue
                await hub.subscribe_local(channel, websocket)
                subscribed.add(channel)
                await websocket.send_json({"type": "subscribed", "channel": channel})
            elif action == "unsubscribe":
                await hub.unsubscribe_local(channel, websocket)
                subscribed.discard(channel)
                await websocket.send_json({"type": "unsubscribed", "channel": channel})
            else:
                await websocket.send_json({"type": "error", "code": "UNKNOWN_ACTION"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket handler error")
    finally:
        hub.drop_connection(websocket)
