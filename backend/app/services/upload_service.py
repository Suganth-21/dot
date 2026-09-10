"""Real photo upload — BUILDPHASES.md Phase 9: "Real photo upload with
server-computed `photo_hash`." Stores to local disk under `backend/uploads/`
(a legitimate, simple stand-in for object storage — genuinely working, not
a stub) and computes a real SHA-256 over the uploaded bytes, the same
primitive `app.core.crypto.sha256_hex` uses for the event hash chain.

This is additive: no existing endpoint requires it. Batch/return/event
`photoHash` fields still accept a caller-supplied hash (or fall back to
the deterministic placeholder — ARCHITECTURE.md's cut list) exactly as
before; this gives a caller who *does* have a real photo a real path to a
real, server-verified hash instead.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.crypto import sha256_hex

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB — generous for a strip/label photo, not for abuse


class UploadTooLarge(Exception):
    pass


def _safe_suffix(filename: str | None) -> str:
    if not filename:
        return ""
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in (".jpg", ".jpeg", ".png", ".webp", ".heic") else ""


def save_photo(content: bytes, filename: str | None) -> tuple[str, str]:
    """Returns `(photo_hash, relative_path)`. Raises `UploadTooLarge` past
    `MAX_UPLOAD_BYTES` — checked here (after the caller has already read the
    bytes) as well as the caller ideally checking `Content-Length` first;
    belt and suspenders against a client that lies about size."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge(f"Upload exceeds {MAX_UPLOAD_BYTES} bytes.")

    photo_hash = sha256_hex(content)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _safe_suffix(filename)
    stored_name = f"{photo_hash}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(content)

    return photo_hash, f"/api/uploads/files/{stored_name}"
