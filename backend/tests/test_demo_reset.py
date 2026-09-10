"""POST /api/demo/reset — ARCHITECTURE.md §8.12, environment-gated."""
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.entity import Pharmacy


async def _token(client) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": "RETAILER"})
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_demo_reset_reseeds_when_enabled(client, seeded, db_session):
    token = await _token(client)
    resp = await client.post("/api/demo/reset", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    result = await db_session.execute(select(Pharmacy))
    assert len(result.scalars().all()) == 10


@pytest.mark.asyncio
async def test_demo_reset_requires_authentication(client, seeded):
    resp = await client.post("/api/demo/reset")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_demo_reset_disabled_returns_403(client, seeded):
    token = await _token(client)
    with patch("app.api.routes_demo.get_settings") as mock_settings:
        mock_settings.return_value.enable_demo_reset = False
        resp = await client.post("/api/demo/reset", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "DEMO_RESET_DISABLED"
