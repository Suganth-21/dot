"""Real photo upload — BUILDPHASES.md Phase 9. Real HTTP requests against a
real database; the uploaded bytes are written to a real (test-machine)
`backend/uploads/` directory and cleaned up after each test.
"""
import hashlib

import pytest

from app.services.upload_service import UPLOAD_DIR


async def _headers(client, role: str) -> dict:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_upload_requires_authentication(client, seeded):
    resp = await client.post("/api/uploads/photo", files={"file": ("strip.jpg", b"fake-photo-bytes", "image/jpeg")})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_computes_real_sha256(client, seeded):
    headers = await _headers(client, "RETAILER")
    content = b"a genuine strip photo, or close enough for a hash"
    expected_hash = hashlib.sha256(content).hexdigest()

    resp = await client.post(
        "/api/uploads/photo", files={"file": ("strip.jpg", content, "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["photoHash"] == expected_hash
    assert body["url"].startswith("/api/uploads/files/")

    stored = list(UPLOAD_DIR.glob(f"{expected_hash}_*"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == content
    stored[0].unlink()  # test cleanup — this directory isn't reset by `seeded`


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(client, seeded):
    headers = await _headers(client, "RETAILER")
    resp = await client.post(
        "/api/uploads/photo", files={"file": ("empty.jpg", b"", "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EMPTY_UPLOAD"


@pytest.mark.asyncio
async def test_upload_same_content_twice_produces_same_hash(client, seeded):
    headers = await _headers(client, "RETAILER")
    content = b"identical bytes both times"
    expected_hash = hashlib.sha256(content).hexdigest()

    first = await client.post("/api/uploads/photo", files={"file": ("a.jpg", content, "image/jpeg")}, headers=headers)
    second = await client.post("/api/uploads/photo", files={"file": ("b.jpg", content, "image/jpeg")}, headers=headers)

    assert first.json()["photoHash"] == expected_hash
    assert second.json()["photoHash"] == expected_hash

    for f in UPLOAD_DIR.glob(f"{expected_hash}_*"):
        f.unlink()
