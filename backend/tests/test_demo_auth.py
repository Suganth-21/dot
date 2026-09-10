"""The five one-click demo logins go through real auth — ARCHITECTURE.md
§6.4, BUILDPHASES.md Phase 1 verification. Never a second auth mechanism."""
from unittest.mock import patch

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select

from app.core.rbac import Role
from app.models.user import User

ALL_ROLES = ["RETAILER", "DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER", "REGULATOR"]


@pytest.mark.asyncio
async def test_demo_login_succeeds_when_enabled_for_every_role(client, seeded):
    for role in ALL_ROLES:
        resp = await client.post("/api/auth/demo-login", json={"role": role})
        assert resp.status_code == 200, f"{role}: {resp.text}"
        body = resp.json()
        assert body["accessToken"]
        assert body["refreshToken"]
        assert body["user"]["role"] == role


@pytest.mark.asyncio
async def test_demo_account_is_backed_by_a_real_user_row_with_argon2_hash(seeded, db_session):
    result = await db_session.execute(select(User).where(User.role == Role.RETAILER))
    user = result.scalar_one()
    assert user.is_demo is True
    assert user.email == "retailer@dot.in"
    # Argon2 hashes always start with $argon2 — proves this isn't a bare
    # SHA hash or plaintext (CLAUDE.md rule 6).
    assert user.password_hash.startswith("$argon2")
    PasswordHasher().verify(user.password_hash, "Demo@Test123")


@pytest.mark.asyncio
async def test_demo_login_issues_real_jwt_via_the_same_path_as_login(client, seeded):
    demo_resp = await client.post("/api/auth/demo-login", json={"role": "RETAILER"})
    demo_token = demo_resp.json()["accessToken"]

    login_resp = await client.post(
        "/api/auth/login", json={"email": "retailer@dot.in", "password": "Demo@Test123"}
    )
    login_token = login_resp.json()["accessToken"]

    # Both tokens must resolve through the identical /me code path to the
    # identical user — proving demo-login didn't mint a special token type.
    for token in (demo_token, login_token):
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["user"]["email"] == "retailer@dot.in"


@pytest.mark.asyncio
async def test_demo_login_returns_404_when_disabled(client, seeded):
    with patch("app.services.auth_service.get_settings") as mock_settings:
        mock_settings.return_value.enable_demo_login = False
        resp = await client.post("/api/auth/demo-login", json={"role": "RETAILER"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DEMO_LOGIN_DISABLED"


@pytest.mark.asyncio
async def test_demo_login_cannot_be_used_to_obtain_a_token_for_a_non_demo_user(client, seeded, db_session):
    # Flip the seeded retailer to is_demo=False — demo-login must then find
    # no eligible row for that role rather than falling back to it.
    result = await db_session.execute(select(User).where(User.role == Role.RETAILER))
    user = result.scalar_one()
    user.is_demo = False
    await db_session.commit()

    resp = await client.post("/api/auth/demo-login", json={"role": "RETAILER"})
    assert resp.status_code == 404
