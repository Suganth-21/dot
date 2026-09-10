"""10 concurrent event appends must produce one valid chain with unique,
contiguous sequence numbers — ARCHITECTURE.md §7.5 "How to test",
BUILDPHASES.md Phase 2 §22. Real concurrent tasks against the real
database: each request opens its own session/connection (NullPool — see
app/db.py), so this genuinely exercises PostgreSQL's row lock
(`SELECT ... FOR UPDATE` in `batch_repo.get_for_update`), not asyncio
cooperative scheduling alone.
"""
import asyncio

import pytest
from sqlalchemy import select

from app.models.event import Event

BATCH_ID = "BATCH-DOX-2026-A17"  # seeded with quantity=50, exactly 1 event


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_ten_concurrent_sales_produce_no_duplicate_or_gapped_sequence(client, seeded, db_session):
    token = await _token(client, "RETAILER")
    headers = {"Authorization": f"Bearer {token}"}

    async def sell_one():
        return await client.post(f"/api/batches/{BATCH_ID}/sale", json={"units": 1}, headers=headers)

    responses = await asyncio.gather(*[sell_one() for _ in range(10)])

    for resp in responses:
        assert resp.status_code == 200, resp.text

    db_session.expire_all()
    result = await db_session.execute(
        select(Event.sequence).where(Event.batch_id == BATCH_ID).order_by(Event.sequence)
    )
    sequences = [row[0] for row in result.all()]

    # 1 REGISTERED + 10 SALE = 11 events, sequence 0..10 with no gap and no
    # duplicate — exactly what a row lock around "read last, insert next"
    # guarantees and a bare `max(sequence) + 1` without one would not.
    assert sequences == list(range(11))
    assert len(sequences) == len(set(sequences))

    final = await client.get(f"/api/batches/{BATCH_ID}", headers=headers)
    assert final.json()["quantity"] == 40

    regulator_token = await _token(client, "REGULATOR")
    verify_resp = await client.get(
        f"/api/batches/{BATCH_ID}/verify-chain", headers={"Authorization": f"Bearer {regulator_token}"}
    )
    assert verify_resp.json()["valid"] is True
