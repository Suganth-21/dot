"""Ed25519 keypair generation/encryption (Phase 1) plus canonical JSON,
SHA-256 hashing, and Ed25519 sign/verify (Phase 2) — ARCHITECTURE.md §7.5.

No blockchain, no distributed ledger, no external anchoring: tamper-
evidence comes entirely from a signed hash chain in ordinary PostgreSQL
rows, per CLAUDE.md rule 5 and ARCHITECTURE.md §7.5's "why this gives
tamper-evidence without a blockchain".
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.signing_master_key:
        raise RuntimeError("SIGNING_MASTER_KEY is not configured")
    # Fernet needs a 32-byte urlsafe-base64 key; derive one deterministically
    # from the configured master key so any string can be used in .env.
    derived = hashlib.sha256(settings.signing_master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def generate_signing_keypair() -> tuple[str, str]:
    """Returns (public_key_b64, encrypted_private_key) for a new Ed25519
    identity. The private key is encrypted with SIGNING_MASTER_KEY before
    it ever reaches the database — never store it raw."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    public_raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    private_raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    public_b64 = base64.b64encode(public_raw).decode("ascii")
    encrypted_private = _fernet().encrypt(private_raw).decode("ascii")
    return public_b64, encrypted_private


def decrypt_signing_private_key(encrypted_private_key: str) -> bytes:
    """Decrypts a stored private key to raw bytes. Only ever call this from
    the Phase 2 event-signing code path — never to log or return a key."""
    try:
        return _fernet().decrypt(encrypted_private_key.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("signing private key could not be decrypted") from exc


# ---------------------------------------------------------------------------
# Phase 2 — canonical JSON, SHA-256 chaining, Ed25519 sign/verify.
# See ARCHITECTURE.md §7.5 for the exact field set and ordering this is
# used with; this module only implements the mechanism, not the event
# payload shape (that lives in app.services.event_service, the one and only
# writer to the events table).
# ---------------------------------------------------------------------------


def canonical_json(payload: dict[str, Any]) -> bytes:
    """RFC-8785-style JSON canonicalization: keys sorted lexicographically
    at every level, no insignificant whitespace, UTF-8. Two calls with
    equal `payload` values always produce byte-identical output — that is
    the entire property a hash chain's reproducibility depends on. Never
    hash a Python dict's `repr()` or a default `json.dumps()` (its
    minor-but-real formatting choices are not part of this contract, and
    "whatever `dict.items()` happened to hand back" is not deterministic
    across processes for keys inserted in a different order)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ed25519_sign(private_key_raw: bytes, hash_hex: str) -> str:
    """Signs the *hash bytes* (not the JSON payload) — ARCHITECTURE.md
    §7.5: `signature = ed25519_sign(actor_private_key, bytes.fromhex(hash))`.
    Returns the signature, base64-encoded, ready to persist as text."""
    key = Ed25519PrivateKey.from_private_bytes(private_key_raw)
    signature = key.sign(bytes.fromhex(hash_hex))
    return base64.b64encode(signature).decode("ascii")


def ed25519_verify(public_key_b64: str, hash_hex: str, signature_b64: str) -> bool:
    """Read-only: reports whether `signature_b64` is a valid Ed25519
    signature over `hash_hex` by the holder of `public_key_b64`. Never
    raises on a bad signature or malformed input — a verification routine
    that can throw invites a caller to accidentally treat "couldn't check"
    as "passed"."""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        public_key.verify(base64.b64decode(signature_b64), bytes.fromhex(hash_hex))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
