"""Real login, /me, and token-failure behavior. ARCHITECTURE.md §6, §8.1.
Exercises actual HTTP requests against a real database — no mocked auth."""
import time

import pytest
from jose import jwt

DEMO_PASSWORD = "Demo@Test123"
RETAILER_EMAIL = "retailer@dot.in"


@pytest.mark.asyncio
async def test_login_with_valid_credentials_succeeds(client, seeded):
    resp = await client.post("/api/auth/login", json={"email": RETAILER_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["user"]["email"] == RETAILER_EMAIL
    assert body["user"]["role"] == "RETAILER"
    assert body["user"]["entityId"] == "ph_1"


@pytest.mark.asyncio
async def test_login_with_wrong_password_fails(client, seeded):
    resp = await client.post("/api/auth/login", json={"email": RETAILER_EMAIL, "password": "not-the-password"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_with_unknown_email_fails(client, seeded):
    resp = await client.post("/api/auth/login", json={"email": "nobody@dot.in", "password": DEMO_PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_response_never_contains_password_hash(client, seeded):
    resp = await client.post("/api/auth/login", json={"email": RETAILER_EMAIL, "password": DEMO_PASSWORD})
    body_text = resp.text
    assert "password_hash" not in body_text
    assert "passwordHash" not in body_text
    assert "signing_private_key" not in body_text
    assert "signingPrivateKey" not in body_text


@pytest.mark.asyncio
async def test_me_works_with_valid_access_token(client, seeded):
    login_resp = await client.post("/api/auth/login", json={"email": RETAILER_EMAIL, "password": DEMO_PASSWORD})
    access_token = login_resp.json()["accessToken"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["email"] == RETAILER_EMAIL
    assert "passwordHash" not in resp.text
    assert "signingPrivateKey" not in resp.text
    assert "signing_private_key" not in resp.text


@pytest.mark.asyncio
async def test_me_fails_without_token(client, seeded):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_fails_with_garbage_token(client, seeded):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_expired_access_token_returns_401(client, seeded):
    # Craft a token that is structurally valid (same secret, same claims
    # shape) but already expired — proves expiry is actually checked, not
    # just signature validity.
    now = int(time.time())
    expired = jwt.encode(
        {
            "sub": "usr_retailer",
            "role": "RETAILER",
            "entity_id": "ph_1",
            "type": "access",
            "iat": now - 3600,
            "exp": now - 1,
            "jti": "expired-test-token",
        },
        "test-only-jwt-secret-not-for-real-use",
        algorithm="HS256",
    )
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"
