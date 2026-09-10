"""Refresh rotation, reuse detection, and logout. ARCHITECTURE.md §6.1."""
import pytest

RETAILER_EMAIL = "retailer@dot.in"
DEMO_PASSWORD = "Demo@Test123"


async def _login(client):
    resp = await client.post("/api/auth/login", json={"email": RETAILER_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_valid_refresh_returns_a_new_token_pair(client, seeded):
    tokens = await _login(client)
    resp = await client.post("/api/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"]
    assert body["refreshToken"]


@pytest.mark.asyncio
async def test_refresh_rotates_the_token_value(client, seeded):
    tokens = await _login(client)
    resp = await client.post("/api/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    new_tokens = resp.json()
    assert new_tokens["refreshToken"] != tokens["refreshToken"]
    assert new_tokens["accessToken"] != tokens["accessToken"]


@pytest.mark.asyncio
async def test_rotated_refresh_token_still_works(client, seeded):
    tokens = await _login(client)
    first = await client.post("/api/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    new_refresh = first.json()["refreshToken"]

    second = await client.post("/api/auth/refresh", json={"refreshToken": new_refresh})
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_revoked_old_refresh_token_cannot_be_reused(client, seeded):
    tokens = await _login(client)
    old_refresh = tokens["refreshToken"]

    # Rotate once — old_refresh is now revoked.
    await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})

    # Replaying the original (now-revoked) token must fail, not silently
    # succeed a second time.
    reuse_resp = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_the_whole_family(client, seeded):
    tokens = await _login(client)
    old_refresh = tokens["refreshToken"]

    first_rotation = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    rotated_refresh = first_rotation.json()["refreshToken"]

    # Reuse of the original token — theft signature — must poison the
    # family: even the legitimately rotated descendant stops working.
    await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})

    resp = await client.post("/api/auth/refresh", json={"refreshToken": rotated_refresh})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_refresh_token_fails(client, seeded):
    resp = await client.post("/api/auth/refresh", json={"refreshToken": "not-a-real-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_the_refresh_token(client, seeded):
    tokens = await _login(client)
    logout_resp = await client.post("/api/auth/logout", json={"refreshToken": tokens["refreshToken"]})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["ok"] is True

    reuse_resp = await client.post("/api/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_is_idempotent_on_an_already_revoked_token(client, seeded):
    tokens = await _login(client)
    first = await client.post("/api/auth/logout", json={"refreshToken": tokens["refreshToken"]})
    second = await client.post("/api/auth/logout", json={"refreshToken": tokens["refreshToken"]})
    assert first.status_code == 200
    assert second.status_code == 200
