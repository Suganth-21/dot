"""Unit tests for the hash-chain mechanism itself — ARCHITECTURE.md §7.5.
No database needed: canonical JSON, SHA-256, and Ed25519 are pure functions."""
from app.core.crypto import (
    canonical_json,
    ed25519_sign,
    ed25519_verify,
    generate_signing_keypair,
    sha256_hex,
)


def test_canonical_json_is_deterministic_regardless_of_key_insertion_order():
    a = {"type": "REGISTERED", "sequence": 0, "actor": {"role": "RETAILER", "id": "ph_1", "name": "Apollo"}}
    b = {"actor": {"name": "Apollo", "id": "ph_1", "role": "RETAILER"}, "sequence": 0, "type": "REGISTERED"}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_has_no_insignificant_whitespace():
    payload = {"a": 1, "b": [1, 2, 3]}
    assert canonical_json(payload) == b'{"a":1,"b":[1,2,3]}'


def test_canonical_json_differs_for_different_content():
    assert canonical_json({"a": 1}) != canonical_json({"a": 2})


def test_sha256_hex_is_64_hex_chars_and_deterministic():
    h1 = sha256_hex(b"hello")
    h2 = sha256_hex(b"hello")
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_ed25519_sign_and_verify_round_trip():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    import base64

    key = Ed25519PrivateKey.generate()
    private_raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_b64 = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")

    event_hash = sha256_hex(b"some event payload")
    signature = ed25519_sign(private_raw, event_hash)

    assert ed25519_verify(public_b64, event_hash, signature) is True


def test_ed25519_verify_fails_on_wrong_hash():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    import base64

    key = Ed25519PrivateKey.generate()
    private_raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_b64 = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")

    real_hash = sha256_hex(b"real payload")
    tampered_hash = sha256_hex(b"tampered payload")
    signature = ed25519_sign(private_raw, real_hash)

    assert ed25519_verify(public_b64, tampered_hash, signature) is False


def test_ed25519_verify_fails_on_wrong_public_key():
    real_public, _ = generate_signing_keypair()
    other_public, other_encrypted_private = generate_signing_keypair()

    from app.core.crypto import decrypt_signing_private_key

    event_hash = sha256_hex(b"payload")
    signature = ed25519_sign(decrypt_signing_private_key(other_encrypted_private), event_hash)

    assert ed25519_verify(real_public, event_hash, signature) is False


def test_ed25519_verify_never_raises_on_garbage_input():
    assert ed25519_verify("not-base64!!!", "not-hex", "also-not-base64") is False


def test_generate_signing_keypair_round_trips_through_encryption():
    from app.core.crypto import decrypt_signing_private_key

    public_b64, encrypted_private = generate_signing_keypair()
    private_raw = decrypt_signing_private_key(encrypted_private)
    assert len(private_raw) == 32  # Ed25519 raw private key length

    event_hash = sha256_hex(b"payload")
    signature = ed25519_sign(private_raw, event_hash)
    assert ed25519_verify(public_b64, event_hash, signature) is True
