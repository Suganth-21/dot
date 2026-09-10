"""The hash chain: canonical payload construction, SHA-256 hashing,
Ed25519 signing, and append. **This module is the only place in the
codebase permitted to write to the `events` table** (CLAUDE.md rule 2,
ARCHITECTURE.md §2). Every other service that needs an event on the record
calls `append()` — never `event_repo.create()` directly.

Concurrency and atomicity (ARCHITECTURE.md §3, §8): `append()` does not
take its own lock and does not commit. The caller must already hold the
batch row lock (`batch_repo.get_for_update`) before calling this, and must
commit the caller's own transaction afterward — that is what makes "read
the last event, compute the next one, insert it" safe under concurrent
requests, and what makes the event insert atomic with whatever business
state change (quantity decrement, status change, ...) caused it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import (
    canonical_json,
    decrypt_signing_private_key,
    ed25519_sign,
    ed25519_verify,
    sha256_hex,
)
from app.core.errors import InternalError
from app.models.batch import Batch
from app.models.enums import EventType
from app.models.event import GENESIS_HASH, Event
from app.repositories import event_repo, reference_repo

# Event actors are entities (a pharmacy, a distributor, ...), not login
# users — a role's demo login is a convenience for a human to act *as* that
# entity, but the signature on the record is the entity's, per
# ARCHITECTURE.md §7.5's "each entity gets an Ed25519 keypair". See the
# Phase 2 implementation notes in ARCHITECTURE.md for why this differs from
# where Phase 1 initially placed signing keys (on `users`).
_SIGNING_ENTITY_LOOKUP = {
    "RETAILER": reference_repo.get_pharmacy,
    "DISTRIBUTOR": reference_repo.get_distributor,
    "PICKUP_AGENT": reference_repo.get_agent,
    "MANUFACTURER": reference_repo.get_manufacturer,
}


def _format_ts(ts: datetime) -> str:
    """Millisecond-precision, UTC, `Z`-suffixed — ARCHITECTURE.md §7.5's
    canonical example (`"2026-09-15T09:30:00.000Z"`). `append()` truncates
    `ts` to millisecond precision before this is ever called so that
    reloading the same instant from PostgreSQL (which stores microsecond
    precision) and reformatting it reproduces this exact string — the hash
    must survive a round trip through the database unchanged."""
    ts_utc = ts.astimezone(timezone.utc)
    ms = ts_utc.microsecond // 1000
    return ts_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


async def _resolve_signing_identity(session: AsyncSession, actor_role: str, actor_id: str) -> tuple[str, str]:
    getter = _SIGNING_ENTITY_LOOKUP.get(actor_role)
    if getter is None:
        raise InternalError(f"No signing identity resolver for role {actor_role}.", code="NO_SIGNING_IDENTITY")
    entity = await getter(session, actor_id)
    if entity is None or not entity.signing_private_key or not entity.signing_public_key:
        raise InternalError(
            f"No signing keypair for {actor_role} {actor_id}.", code="NO_SIGNING_IDENTITY"
        )
    return entity.signing_public_key, entity.signing_private_key


async def _resolve_public_key(session: AsyncSession, actor_role: str, signer_key_id: str) -> str | None:
    getter = _SIGNING_ENTITY_LOOKUP.get(actor_role)
    if getter is None:
        return None
    entity = await getter(session, signer_key_id)
    if entity is None:
        return None
    return entity.signing_public_key


def _canonical_payload(
    *,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    batch_id: str,
    gps_lat: float | None,
    gps_lng: float | None,
    meta: dict,
    photo_hash: str | None,
    prev_hash: str,
    sequence: int,
    ts: datetime,
    event_type: str,
) -> dict:
    """The exact stable field set from ARCHITECTURE.md §7.5 — nothing that
    is assigned after insert (no `id`, no database defaults) and nothing
    that could vary between two calls describing the same event."""
    return {
        "actor": {"id": actor_id, "name": actor_name, "role": actor_role},
        "batchId": batch_id,
        "gps": {"lat": gps_lat, "lng": gps_lng} if gps_lat is not None and gps_lng is not None else None,
        "meta": meta,
        "photoHash": photo_hash,
        "prevHash": prev_hash,
        "sequence": sequence,
        "ts": _format_ts(ts),
        "type": event_type,
    }


async def append(
    session: AsyncSession,
    *,
    batch: Batch,
    event_type: EventType,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    meta: dict | None = None,
    gps: tuple[float, float] | None = None,
    photo_hash: str | None = None,
    ts: datetime | None = None,
) -> Event:
    """Appends the next event in `batch`'s chain. Caller must already hold
    `batch`'s row lock in this same transaction and must commit afterward —
    see this module's docstring."""
    meta = meta if meta is not None else {}

    last = await event_repo.get_last(session, batch.id)
    sequence = 0 if last is None else last.sequence + 1
    prev_hash = GENESIS_HASH if last is None else last.hash

    now = ts or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    now = now.replace(microsecond=(now.microsecond // 1000) * 1000)

    gps_lat, gps_lng = gps if gps is not None else (None, None)
    if photo_hash is None:
        # Deterministic placeholder — ARCHITECTURE.md cut list: "no real
        # photo upload yet; deterministic photoHash from batch + type +
        # timestamp, as the mock does". Keyed off `sequence` rather than a
        # wall-clock timestamp so a reseeded batch's events hash identically
        # every reset (BUILDPHASES.md determinism requirement).
        photo_hash = sha256_hex(f"{batch.id}:{event_type.value}:{sequence}".encode("utf-8"))

    payload = _canonical_payload(
        actor_id=actor_id, actor_name=actor_name, actor_role=actor_role, batch_id=batch.id,
        gps_lat=gps_lat, gps_lng=gps_lng, meta=meta, photo_hash=photo_hash, prev_hash=prev_hash,
        sequence=sequence, ts=now, event_type=event_type.value,
    )
    event_hash = sha256_hex(canonical_json(payload))

    _public_key, encrypted_private_key = await _resolve_signing_identity(session, actor_role, actor_id)
    private_key_raw = decrypt_signing_private_key(encrypted_private_key)
    signature = ed25519_sign(private_key_raw, event_hash)

    row = Event(
        id=f"evt_{uuid.uuid4().hex[:16]}",
        batch_id=batch.id,
        sequence=sequence,
        type=event_type,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        ts=now,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        photo_hash=photo_hash,
        meta=meta,
        prev_hash=prev_hash,
        hash=event_hash,
        signature=signature,
        signer_key_id=actor_id,
    )
    await event_repo.create(session, row)
    return row


async def verify_chain(session: AsyncSession, batch_id: str) -> dict:
    """Read-only. Walks every event for `batch_id` in sequence order and
    checks, independently, for each event (ARCHITECTURE.md §7.5 / this
    phase's brief §19):

    1. sequence is contiguous from 0 (a gap — including a removed event —
       is detected here)
    2. `prev_hash` equals the previous event's stored `hash` (genesis event
       must point at `GENESIS_HASH`)
    3. recomputing the hash from the event's own stored fields reproduces
       its stored `hash` (catches tampering with any hashed field,
       including `meta`)
    4. the stored `signature` verifies against the stored `hash` under the
       signer's current public key (catches a tampered `hash` or
       `signature` even when spoofed self-consistently)

    Never repairs or rewrites anything — a verification routine with write
    access to what it's verifying is not a verification routine.
    """
    events = await event_repo.list_for_batch(session, batch_id)

    errors: list[dict] = []
    expected_prev = GENESIS_HASH

    for index, event in enumerate(events):
        if event.sequence != index:
            errors.append({"sequence": event.sequence, "reason": "SEQUENCE_GAP"})

        if event.prev_hash != expected_prev:
            errors.append({"sequence": event.sequence, "reason": "PREV_HASH_MISMATCH"})

        recomputed_payload = _canonical_payload(
            actor_id=event.actor_id, actor_name=event.actor_name, actor_role=event.actor_role,
            batch_id=event.batch_id, gps_lat=event.gps_lat, gps_lng=event.gps_lng, meta=event.meta,
            photo_hash=event.photo_hash, prev_hash=event.prev_hash, sequence=event.sequence,
            ts=event.ts, event_type=event.type.value if hasattr(event.type, "value") else event.type,
        )
        recomputed_hash = sha256_hex(canonical_json(recomputed_payload))
        if recomputed_hash != event.hash:
            errors.append({"sequence": event.sequence, "reason": "HASH_MISMATCH"})

        public_key = await _resolve_public_key(session, event.actor_role, event.signer_key_id)
        if public_key is None or not ed25519_verify(public_key, event.hash, event.signature):
            errors.append({"sequence": event.sequence, "reason": "SIGNATURE_INVALID"})

        # Advance on the event's *own* hash regardless of whether it passed
        # — a single broken link should not cascade into flagging every
        # event after it as also broken.
        expected_prev = event.hash

    broken_at = errors[0]["sequence"] if errors else None
    return {"valid": len(errors) == 0, "brokenAtSequence": broken_at, "checked": len(events), "errors": errors}
