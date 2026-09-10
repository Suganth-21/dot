"""Password hashing and JWT encode/decode. CLAUDE.md rule 6: Argon2 for
passwords, JWT access + refresh. Never bcrypt-by-default, never SHA for
passwords, never a plaintext password anywhere.

Uses `argon2-cffi` directly rather than the `passlib` wrapper ARCHITECTURE.md
§1.4 names: passlib's argon2 backend probes `argon2.__about__`, which recent
argon2-cffi releases no longer ship, breaking hash verification outright.
`argon2-cffi`'s own `PasswordHasher` gives the identical algorithm (Argon2id,
same tunable cost parameters) with no such dependency landmine. Documented
as a deviation in ARCHITECTURE.md.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt

from app.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _jwt_secret() -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        # Fails loudly rather than signing tokens with an empty/default
        # secret — CLAUDE.md rule 7: no secrets in code, and a missing one
        # is a configuration bug, not something to paper over.
        raise RuntimeError("JWT_SECRET is not configured")
    return settings.jwt_secret


def create_access_token(*, user_id: str, role: str, entity_id: str | None) -> str:
    settings = get_settings()
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "entity_id": entity_id,
        "type": "access",
        "iat": now,
        "exp": now + settings.jwt_access_ttl_min * 60,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


def create_refresh_token(*, user_id: str, family_id: str, jti: str, ttl_days: int | None = None) -> str:
    settings = get_settings()
    now = int(time.time())
    days = ttl_days if ttl_days is not None else settings.jwt_refresh_ttl_days
    claims: dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "family": family_id,
        "iat": now,
        "exp": now + days * 86400,
        "jti": jti,
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decodes and validates a JWT. Raises `Unauthorized` (401) on any
    failure — expired, malformed, wrong signature, or wrong `type` (an
    access token presented where a refresh token belongs, or vice versa)."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except JWTError as exc:
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED") from exc

    if payload.get("type") != expected_type:
        raise Unauthorized("Invalid or expired token.", code="TOKEN_EXPIRED")

    return payload
