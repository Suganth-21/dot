"""Server-side role enforcement — ARCHITECTURE.md §6.5. A route with a role
guard rejects the wrong role with 403 before the handler runs; it never
returns a fabricated success (CLAUDE.md rule 2)."""
import pytest

DEMO_PASSWORD = "Demo@Test123"


async def _access_token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_regulator_can_read_their_own_profile(client, seeded):
    token = await _access_token(client, "REGULATOR")
    resp = await client.get("/api/regulator/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "reg_1"
    assert body["officerName"] == "R. Menon"


@pytest.mark.asyncio
async def test_retailer_token_on_regulator_only_endpoint_returns_403(client, seeded):
    token = await _access_token(client, "RETAILER")
    resp = await client.get("/api/regulator/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER"])
async def test_every_non_regulator_role_is_rejected_from_the_regulator_endpoint(client, seeded, role):
    token = await _access_token(client, role)
    resp = await client.get("/api/regulator/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regulator_endpoint_requires_authentication_at_all(client, seeded):
    resp = await client.get("/api/regulator/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reference_endpoints_are_open_to_every_authenticated_role(client, seeded):
    for role in ["RETAILER", "DISTRIBUTOR", "PICKUP_AGENT", "MANUFACTURER", "REGULATOR"]:
        token = await _access_token(client, role)
        resp = await client.get("/api/reference/distributors", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, f"{role}: {resp.text}"


@pytest.mark.asyncio
async def test_reference_endpoints_reject_unauthenticated_requests(client, seeded):
    resp = await client.get("/api/reference/distributors")
    assert resp.status_code == 401
